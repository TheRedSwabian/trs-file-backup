"""Main CLI application for trs-file-backup."""

import io
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import NoReturn, TextIO

import typer
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from trs_file_backup import __version__
from trs_file_backup.backup import BackupErrorKind, BackupManager, backup_error_reason, classify_backup_error
from trs_file_backup.logger import BackupLogger
from trs_file_backup.patterns import pattern_problem
from trs_file_backup.retention import NO_LIMIT, RULE_FIELDS, RetentionRules, is_valid_rule_value
from trs_file_backup.state import InvalidRetentionRuleError, StateManager

app = typer.Typer(
    name="trs-file-backup",
    help="trs-file-backup - Monitor and backup modified files with timestamps",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
    epilog="""\b
Examples:
  trs-file-backup run --source ./myproject --destination ./backup
  trs-file-backup watch --source ./myproject --destination ./backup

Use 'trs-file-backup COMMAND --help' for detailed information on each command.
""",
)
# No emoji replacement: a file name or pattern such as ":fire:x.txt" must print as it is
console = Console(emoji=False)

STATE_FILE_NAME = ".backup_state.json"
DEFAULT_DEBOUNCE_SECONDS = 2
DEBOUNCE_DEFAULT_HELP = f"saved value, else {DEFAULT_DEBOUNCE_SECONDS}"


def check_exclude_values(values: list[str]) -> list[str]:
    """Return the --exclude values without surrounding whitespace; reject one that AC-4.9 rejects."""
    patterns = [value.strip() for value in values]
    for pattern in patterns:
        problem = pattern_problem(pattern)
        if problem is not None:
            raise typer.BadParameter(f"'{pattern}' is not usable: {problem}. Give a file name or a wildcard pattern such as *.log.")
    return patterns


def exclusion_patterns(user_patterns: list[str]) -> list[str]:
    """Return the state file pattern followed by the user patterns, each pattern once (spec AC-3.10)."""
    return list(dict.fromkeys([STATE_FILE_NAME, *user_patterns]))


def resolve_settings(state: StateManager | None, exclude: list[str], debounce: int | None) -> tuple[list[str], int]:
    """Return the exclusion patterns and debounce delay that run and watch use (spec AC-3.7 to AC-3.10).

    A given option replaces the saved value; an option not given falls back to the saved value,
    or to the default when there is no state file. An empty exclude list means "not given".
    """
    if exclude:
        user_patterns = exclude
    elif state is not None:
        user_patterns = state.excluded_patterns
    else:
        user_patterns = []

    if debounce is not None:
        debounce_seconds = debounce
    elif state is not None:
        debounce_seconds = state.debounce_seconds
    else:
        debounce_seconds = DEFAULT_DEBOUNCE_SECONDS

    return exclusion_patterns(user_patterns), debounce_seconds


class SourceMismatchError(ValueError):
    """The --source given to run or watch is not the source the backup folder was set up for (spec AC-3.12)."""


def check_source(state: StateManager | None, source: Path, destination: Path) -> None:
    """Raise SourceMismatchError when the saved source is another directory than the resolved --source.

    The saved path is resolved the same way; on Windows, Path comparison ignores letter case.
    """
    if state is None:
        return
    saved_source = state.source_path.resolve()
    if saved_source != source:
        raise SourceMismatchError(
            f"the backup folder {destination} belongs to the source {saved_source}, not to {source}. "
            "For another source, use another backup folder or run 'trs-file-backup init' again."
        )


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        print(f"trs-file-backup version {__version__}")
        raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        is_eager=True,
    ),
) -> None:
    """
    trs-file-backup - Monitor and backup modified files with timestamps

    This tool helps you create timestamped backups of modified files from a
    source directory to a destination directory. It supports one-time backups,
    initialization, and continuous monitoring.

    Options:
      -v, --version    Show version and exit

    \b
    Examples:
      trs-file-backup run --source ./myproject --destination ./backup
      trs-file-backup watch --source ./myproject --destination ./backup

    Use 'trs-file-backup COMMAND --help' for more information on a specific command.
    """
    if version:
        version_callback(True)

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command()
def init(
    source: Path = typer.Option(  # noqa: B008
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(  # noqa: B008
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: list[str] = typer.Option(  # noqa: B008
        [],
        "--exclude",
        metavar="PATTERN",
        callback=check_exclude_values,
        help="File-name patterns to exclude (can be repeated)",
    ),
    debounce: int = typer.Option(
        2,
        "--debounce",
        help="Seconds to wait in watch mode; run copies without waiting",
        min=0,
    ),
) -> None:
    """Initialize backup tracking for a directory.

    This command sets up backup tracking by creating a state file in the destination
    directory. The next 'run' or 'watch' command will back up all files (first
    full backup). Subsequent runs will only backup modified files.

    Examples:

      # Basic initialization
      trs-file-backup init --source C:\\Projects\\MyApp --destination C:\\Backup\\MyApp

      # Initialize with exclusions and custom debounce
      trs-file-backup init --source ./src --destination ./backup --exclude "*.log" --exclude "*.tmp" --debounce 5

    Note:
      Exclusion patterns and debounce setting specified here are saved.
      Later 'run' and 'watch' commands use them, unless they are given --exclude or --debounce, which replaces the saved value.
      The retention rules are saved as 0 (off); change them with 'config'.
    """
    logger = None
    try:
        excluded_patterns = exclusion_patterns(exclude)

        # Create initial state; the retention rules start as 0 (spec AC-8.15)
        state = StateManager(
            source_path=source,
            destination_path=destination,
            debounce_seconds=debounce,
            excluded_patterns=excluded_patterns,
            files={},
        )

        # Create logger
        logger = BackupLogger(destination)

        # Log session start
        logger.log_session_start(
            command="init",
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            debounce_seconds=debounce,
            retention=state.retention,
        )

        # Save state
        state.save()

        # Log success
        logger.log_init_success()
        logger.log_session_end()

        # Show user message
        console.print(Text.assemble(("OK", "green"), f" Initialized backup tracking for {source}"))
        console.print(f"State file saved to {state.state_file_path}", markup=False)
        console.print(f"Log file created: {destination / 'backup.log'}", markup=False)
        console.print("Next run will back up all files.")

    except Exception as e:
        console.print(Text.assemble(("Error:", "red"), f" {e}"))
        raise typer.Exit(code=1) from None
    finally:
        if logger is not None:
            logger.close()


@app.command()
def run(
    source: Path = typer.Option(  # noqa: B008
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(  # noqa: B008
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: list[str] = typer.Option(  # noqa: B008
        [],
        "--exclude",
        metavar="PATTERN",
        callback=check_exclude_values,
        help="File-name patterns to exclude (can be repeated). Replaces the saved patterns; if not given, the saved patterns are used",
    ),
    debounce: int | None = typer.Option(
        None,
        "--debounce",
        help="Seconds to wait in watch mode; run itself copies without waiting. Replaces the saved value; if not given, the saved value is used",
        min=0,
        show_default=DEBOUNCE_DEFAULT_HELP,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be backed up without copying",
    ),
) -> None:
    """Execute a one-time backup of modified files.

    This command scans the source directory for files that have been modified
    since the last backup and creates timestamped copies in the destination
    directory. Only files changed after the last backup run are processed.

    Examples:

      # Basic backup
      trs-file-backup run --source C:\\Projects\\MyApp --destination C:\\Backup\\MyApp

      # Exclude log files
      trs-file-backup run --source ./src --destination ./backup --exclude "*.log"

      # Multiple exclusions; save a debounce delay of 5 seconds for watch
      trs-file-backup run --source ./src --destination ./backup --exclude "*.log" --exclude "temp_*" --debounce 5

      # Preview without copying
      trs-file-backup run --source ./src --destination ./backup --dry-run
    """
    logger = None
    try:
        # Load or create state
        state_file = destination / STATE_FILE_NAME
        state = StateManager.load(state_file)
        check_source(state, source, destination)
        excluded_patterns, debounce_seconds = resolve_settings(state, exclude, debounce)

        if state is None:
            # Create new state
            state = StateManager(
                source_path=source,
                destination_path=destination,
                debounce_seconds=debounce_seconds,
                excluded_patterns=excluded_patterns,
                files={},
            )
        else:
            # Store the settings this session uses
            state.excluded_patterns = excluded_patterns
            state.debounce_seconds = debounce_seconds

        # Create logger
        logger = BackupLogger(destination)

        # Log session start
        logger.log_session_start(
            command="run",
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            debounce_seconds=debounce_seconds,
            retention=state.retention,
        )

        # Create backup manager
        backup_manager = BackupManager(
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            state=state,
        )

        # Get files to backup
        console.print(f"Scanning source directory: {source}", markup=False)
        files_to_backup = backup_manager.get_files_to_backup()
        logger.log_found_files(len(files_to_backup))

        if len(files_to_backup) == 0:
            console.print("[yellow]No modified files found.[/yellow]")
            if not dry_run and (exclude or debounce is not None):
                # A given option is saved even when nothing is backed up (spec AC-3.8)
                state.save()
            logger.log_session_end(0, 0)
            return

        console.print(f"Found {len(files_to_backup)} modified files")

        if dry_run:
            console.print("\n[yellow]Dry-run mode: No files will be copied[/yellow]\n")
            for file in files_to_backup:
                timestamp = datetime.now()
                backup_name = BackupManager.generate_backup_filename(file.name, timestamp)
                console.print(f"  Would backup: {file.name} -> {backup_name}", markup=False)
            logger.log_session_end(0, len(files_to_backup))
            return

        # Backup files
        console.print("Backing up files...")
        backed_up_count = 0
        failed_count = 0

        for file in files_to_backup:
            try:
                # Read the mtime before the copy: a write during the copy must stay "modified" for the next run
                mtime = file.stat().st_mtime
                timestamp = datetime.now()
                backup_path = backup_manager.backup_file(file, timestamp)

                # Update state
                state.update_file_timestamp(file.name, mtime)

                # Log success
                logger.log_file_backed_up(file.name, backup_path.name)
                console.print(Text.assemble("  ", ("OK", "green"), f" {file.name} -> {backup_path.name}"))
                backed_up_count += 1

            except OSError as e:
                report_backup_error(logger, file.name, e, indent="  ")
                failed_count += 1

        # Save updated state
        state.save()

        # Log completion
        logger.log_backup_completed(backed_up_count, len(files_to_backup))
        logger.log_session_end(backed_up_count, len(files_to_backup))

        # Show summary
        console.print(Text.assemble("\n", (f"Successfully backed up {backed_up_count} files to {destination}", "green")))
        if failed_count > 0:
            console.print(f"[yellow]Failed: {failed_count} files[/yellow]")
        console.print(f"Logging to: {destination / 'backup.log'}", markup=False)

    except Exception as e:
        console.print(Text.assemble(("Error:", "red"), f" {e}"))
        raise typer.Exit(code=1) from None
    finally:
        if logger is not None:
            logger.close()


def report_backup_error(logger: BackupLogger, name: str, error: OSError, indent: str = "") -> None:
    """Print and log a failed backup of the file name by its cause (spec AC-6.18)."""
    match classify_backup_error(error):
        case BackupErrorKind.LOCKED:
            logger.log_file_locked(name)
            console.print(Text.assemble(indent, ("WARNING", "yellow"), f" File locked, skipping: {name}"))
        case BackupErrorKind.PERMISSION_DENIED:
            logger.log_error(f"Permission denied: {name}")
            console.print(Text.assemble(indent, ("ERROR", "red"), f" Permission denied: {name}"))
        case BackupErrorKind.OTHER:
            message = f"Backup failed: {name} ({backup_error_reason(error)})"
            logger.log_error(message)
            console.print(Text.assemble(indent, ("ERROR", "red"), f" {message}"))


class BackupEventHandler(FileSystemEventHandler):
    """Handler for file system events in watch mode."""

    def __init__(
        self,
        backup_manager: BackupManager,
        state: StateManager,
        logger: BackupLogger,
        debounce_seconds: int,
    ):
        """Initialize event handler.

        Args:
            backup_manager: BackupManager instance
            state: StateManager instance
            logger: BackupLogger instance
            debounce_seconds: Debounce delay in seconds
        """
        super().__init__()
        self.backup_manager = backup_manager
        self.state = state
        self.logger = logger
        self.debounce_seconds = debounce_seconds
        # Written by the observer thread, read and cleared by the main thread: every access holds this lock
        self.pending_files: dict[Path, float] = {}
        self._pending_lock = threading.Lock()
        self.backed_up_count = 0

    def on_modified(self, event: FileSystemEvent) -> None:
        """Queue a modified file for backup (spec AC-5.3)."""
        if not event.is_directory:
            self._queue_file(Path(os.fsdecode(event.src_path)), "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        """Queue a created file for backup (spec AC-5.10)."""
        if not event.is_directory:
            self._queue_file(Path(os.fsdecode(event.src_path)), "created")

    def on_moved(self, event: FileSystemEvent) -> None:
        """Queue the destination of a moved or renamed file for backup (spec AC-5.10).

        The source path is never used: the Windows emitter may report it empty.
        """
        if event.is_directory:
            return
        dest_path = Path(os.fsdecode(event.dest_path))
        if self._is_in_subdirectory(dest_path):
            return
        self._queue_file(dest_path, "moved")

    def _is_in_subdirectory(self, file_path: Path) -> bool:
        """Return True if the path of file_path lies in a subdirectory of the source folder.

        The macOS emitter can report a move from the top level into a subdirectory as a moved event.
        The decision uses the paths only, never the file system, so it also holds when the file is gone already.
        """
        source = os.path.normcase(os.path.abspath(self.backup_manager.source_path))
        parent = os.path.normcase(os.path.abspath(file_path.parent))
        relative = os.path.relpath(parent, source)
        return relative != os.curdir and Path(relative).parts[0] != os.pardir

    def _queue_file(self, file_path: Path, change: str) -> None:
        """Log the event and queue file_path for backup, or log why it is excluded (spec AC-6.16, AC-6.17).

        Args:
            file_path: File in the source folder
            change: Kind of change shown to the user: "modified", "created" or "moved"
        """
        name = file_path.name
        reason = BackupManager.exclusion_reason(name, self.backup_manager.excluded_patterns)
        if reason is not None:
            if reason.pattern is None:
                self.logger.log_hidden_file_excluded(name)
            else:
                self.logger.log_file_excluded(name, reason.pattern)
            return

        self.logger.log_file_changed(name, change)
        console.print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File {change}: {name}", markup=False)

        # Update timestamp for this file (extends debounce window if already pending).
        # Popping first lets a case-only rename replace the old spelling, which Windows paths treat as the same key.
        with self._pending_lock:
            self.pending_files.pop(file_path, None)
            self.pending_files[file_path] = time.time()

    def _remove_pending(self, file_path: Path, event_time: float) -> None:
        """Remove file_path from the pending files unless an event newer than event_time arrived meanwhile."""
        with self._pending_lock:
            if self.pending_files.get(file_path) == event_time:
                del self.pending_files[file_path]

    def process_pending_files(self) -> None:
        """Process pending files that have passed the debounce window."""
        now = time.time()

        # Find files that have passed debounce window; the copy below runs without the lock
        with self._pending_lock:
            files_to_backup = [(file_path, event_time) for file_path, event_time in self.pending_files.items() if now - event_time >= self.debounce_seconds]

        # Backup files that passed debounce
        for file_path, event_time in files_to_backup:
            try:
                # Skip a file deleted after its event
                if not file_path.exists():
                    self._remove_pending(file_path, event_time)
                    continue

                # Read the mtime before the copy: a write during the copy must stay "modified" for the next backup
                mtime = file_path.stat().st_mtime
                timestamp = datetime.now()
                backup_path = self.backup_manager.backup_file(file_path, timestamp)

                # Log success
                self.logger.log_file_backed_up(file_path.name, backup_path.name)
                console.print(Text.assemble(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Backing up: {file_path.name} -> {backup_path.name} ", ("OK", "green")))

                self.backed_up_count += 1

                # Update state; a failed save is not a failed backup of this file (spec AC-5.11)
                self.state.update_file_timestamp(file_path.name, mtime)
                self._save_state()

                # Remove from pending; an event during the copy keeps the file pending for the next debounce
                self._remove_pending(file_path, event_time)

            except OSError as e:
                report_backup_error(self.logger, file_path.name, e)
                self._remove_pending(file_path, event_time)

    def _save_state(self) -> None:
        """Save the state file; print and log a failure instead of raising it (spec AC-5.11)."""
        try:
            self.state.save()
        except OSError as e:
            message = f"Cannot save state file: {backup_error_reason(e)}"
            self.logger.log_error(message)
            console.print(Text.assemble(("ERROR", "red"), f" {message}"))


@app.command()
def watch(
    source: Path = typer.Option(  # noqa: B008
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(  # noqa: B008
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: list[str] = typer.Option(  # noqa: B008
        [],
        "--exclude",
        metavar="PATTERN",
        callback=check_exclude_values,
        help="File-name patterns to exclude (can be repeated). Replaces the saved patterns; if not given, the saved patterns are used",
    ),
    debounce: int | None = typer.Option(
        None,
        "--debounce",
        help="Seconds to wait after a file is modified, created or moved in, before backup. Replaces the saved value; if not given, the saved value is used",
        min=0,
        show_default=DEBOUNCE_DEFAULT_HELP,
    ),
) -> None:
    """Continuously monitor and backup files in real-time.

    This command starts a file system monitor that watches the source directory
    for changes. When a file is modified, created or moved into it, it
    automatically creates a timestamped backup after a short delay (debounce).
    The monitor runs until you press Ctrl+C.

    Examples:

      # Basic watch mode
      trs-file-backup watch --source C:\\Projects\\MyApp --destination C:\\Backup\\MyApp

      # Watch with exclusions
      trs-file-backup watch --source ./src --destination ./backup --exclude "*.log"

      # Custom debounce delay (5 seconds)
      trs-file-backup watch --source ./src --destination ./backup --debounce 5

    Tips:
      - Use Ctrl+C to stop monitoring
      - Debounce prevents backing up files that are still being written
      - Subdirectories are ignored; hidden files (starting with .) are excluded
    """
    logger = None
    try:
        # Load or create state
        state_file = destination / STATE_FILE_NAME
        state = StateManager.load(state_file)
        check_source(state, source, destination)
        excluded_patterns, debounce_seconds = resolve_settings(state, exclude, debounce)

        if state is None:
            # Create new state
            state = StateManager(
                source_path=source,
                destination_path=destination,
                debounce_seconds=debounce_seconds,
                excluded_patterns=excluded_patterns,
                files={},
            )
        else:
            # Store the settings this session uses
            state.excluded_patterns = excluded_patterns
            state.debounce_seconds = debounce_seconds

        # Save state
        state.save()

        # Create logger
        logger = BackupLogger(destination)

        # Log session start
        logger.log_session_start(
            command="watch",
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            debounce_seconds=debounce_seconds,
            retention=state.retention,
        )
        logger.log_watch_started()

        # Create backup manager
        backup_manager = BackupManager(
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            state=state,
        )

        # Create event handler
        event_handler = BackupEventHandler(
            backup_manager=backup_manager,
            state=state,
            logger=logger,
            debounce_seconds=debounce_seconds,
        )

        # Start observer
        observer = Observer()
        observer.schedule(event_handler, str(source), recursive=False)
        observer.start()

        console.print(Text(f"Starting file system monitor for {source}", style="green"))
        console.print("Watching for changes... (Press Ctrl+C to stop)")
        console.print(f"Logging to: {destination / 'backup.log'}\n", markup=False)

        try:
            while True:
                # Check for pending files to backup
                event_handler.process_pending_files()
                time.sleep(0.5)  # Check every 0.5 seconds
        except KeyboardInterrupt:
            observer.stop()
            logger.log_watch_stopped()
            logger.log_session_end(event_handler.backed_up_count, event_handler.backed_up_count)

            console.print("\n\nCtrl+C detected. Stopping file system monitor...")

        observer.join()

    except Exception as e:
        console.print(Text.assemble(("Error:", "red"), f" {e}"))
        raise typer.Exit(code=1) from None
    finally:
        if logger is not None:
            logger.close()


config_app = typer.Typer(rich_markup_mode="rich")
app.add_typer(config_app, name="config")

CONFIG_ACTIONS = "  [1] change debounce   [2] add pattern   [3] remove pattern\n  [4] clear patterns    [5] change retention\n  [s] save and quit     [q] quit without saving"
STOP_WATCH_NOTE = "Stop a running 'watch' and wait for a running 'run' to finish first: both write their own settings back and would overwrite your changes."
DESTINATION_HELP = "Destination backup directory that holds the state file"


@dataclass
class SettingsDraft:
    """The settings that the config menu and config set change: the debounce delay, the user patterns without the state file pattern, and the retention rules."""

    debounce_seconds: int
    patterns: list[str]
    retention: RetentionRules

    @classmethod
    def of(cls, state: StateManager) -> "SettingsDraft":
        return cls(state.debounce_seconds, user_patterns(state.excluded_patterns), state.retention)


def user_patterns(patterns: list[str]) -> list[str]:
    """Return the saved patterns without the state file pattern, each pattern once (spec AC-7.1)."""
    return [pattern for pattern in exclusion_patterns(patterns) if pattern != STATE_FILE_NAME]


def _stdin_is_terminal() -> bool:
    """Tell whether standard input is a terminal, so that the config menu can ask (spec AC-7.2)."""
    return sys.stdin.isatty()


def _say(text: str) -> None:
    """Print text as it is: patterns and paths may hold brackets that Rich would read as markup."""
    console.print(text, markup=False, highlight=False, soft_wrap=True)


def _error(text: str) -> NoReturn:
    _say(f"Error: {text}")
    raise typer.Exit(code=1)


def _required_destination(destination: Path | None) -> Path:
    if destination is None:
        raise typer.BadParameter("required, give the backup directory that holds the state file.", param_hint="'--destination'")
    return destination


def _load_saved_state(destination: Path) -> StateManager:
    """Load the state file, or end with exit code 1 without creating anything (spec AC-7.12, AC-8.16)."""
    state_file = destination / STATE_FILE_NAME
    try:
        state = StateManager.load(state_file)
    except InvalidRetentionRuleError as e:
        # The message names the state file, the key, the value and the allowed values (spec AC-8.16)
        _error(str(e))
    except Exception as e:
        _error(f"cannot read {state_file}: {e!r}")
    if state is None:
        _error(f"no saved settings in {destination}. Run 'trs-file-backup init' first.")
    return state


# Per rule: the unit, and the texts for N greater than 0 and for -1 (spec AC-7.16)
_RULE_TEXTS = {
    "hours": ("hour", "keep all backups of the last {count}", "keep all backups"),
    "days": ("day", "keep the last backup per day for {count}", "keep the last backup per day forever"),
    "weeks": ("week", "keep the last backup per week for {count}", "keep the last backup per week forever"),
    "months": ("month", "keep the last backup per month for {count}", "keep the last backup per month forever"),
}
RETENTION_LABEL = "  Retention: "
CHANGED_MARK = "   (changed)"


def retention_lines(rules: RetentionRules, saved: RetentionRules | None = None) -> list[str]:
    """Return the retention block of the settings: one line per rule that is not 0, or the "off" line (spec AC-7.16).

    With saved, as the menu passes it, a rule that differs from saved gets the mark "(changed)",
    and a rule that is 0 but not in saved is listed as "<rule> rule: off".
    """
    if rules.is_off:
        mark = CHANGED_MARK if saved is not None and saved != rules else ""
        return [f"{RETENTION_LABEL}off (no backup is ever deleted){mark}"]
    texts = []
    for name in RULE_FIELDS:
        value = getattr(rules, name)
        changed = saved is not None and value != getattr(saved, name)
        unit, limited, unlimited = _RULE_TEXTS[name]
        if value == NO_LIMIT:
            text = unlimited
        elif value > 0:
            plural = "" if value == 1 else "s"
            text = limited.format(count=f"{value} {unit}{plural}")
        elif changed:
            text = f"{name} rule: off"
        else:
            continue
        texts.append(f"{text}{CHANGED_MARK if changed else ''}")
    indent = " " * len(RETENTION_LABEL)
    return [f"{RETENTION_LABEL if number == 0 else indent}{text}" for number, text in enumerate(texts)]


def _print_settings(source: Path, draft: SettingsDraft, saved: SettingsDraft) -> None:
    """Print the settings and mark what differs from the saved ones (spec AC-7.1, AC-7.9, AC-7.16)."""
    _say("Saved settings")
    _say(f"  Source:    {source}   (read-only)")
    changed = CHANGED_MARK if draft.debounce_seconds != saved.debounce_seconds else ""
    _say(f"  Debounce:  {draft.debounce_seconds} s{changed}")
    if not draft.patterns:
        _say("  Excluded:  (none)")
    for number, pattern in enumerate(draft.patterns, start=1):
        label = "  Excluded:  " if number == 1 else " " * 13
        new = "" if pattern in saved.patterns else "   (new)"
        _say(f"{label}{number}) {pattern}{new}")
    removed = [pattern for pattern in saved.patterns if pattern not in draft.patterns]
    if removed:
        _say(f"  Removed:   {', '.join(removed)}")
    for line in retention_lines(draft.retention, saved.retention):
        _say(line)


def _ask_debounce(current: int) -> int:
    while True:
        value = IntPrompt.ask("New debounce delay in seconds", default=current, console=console)
        if value >= 0:
            return value
        _say("The debounce delay must be 0 or more seconds.")


class _UnwrappedIntPrompt(IntPrompt):
    """An IntPrompt that the console does not wrap, as _say prints: a long prompt with its default stays on one line (spec AC-7.17)."""

    @classmethod
    def get_input(cls, console: Console, prompt: str | Text, password: bool, stream: TextIO | None = None) -> str:
        console.print(prompt, end="", soft_wrap=True)
        return console.input(password=password, stream=stream)


# Per rule: the prompt for its new value (spec AC-7.17)
_RULE_PROMPTS = {
    "hours": "Keep every backup younger than how many hours (0 = off, -1 = no limit)",
    "days": "Keep the last backup per day for how many days (0 = off, -1 = no limit)",
    "weeks": "Keep the last backup per week for how many weeks (0 = off, -1 = no limit)",
    "months": "Keep the last backup per month for how many months (0 = off, -1 = no limit)",
}


def _change_retention(draft: SettingsDraft) -> None:
    """Ask which rule to change, then its new value; Enter keeps the value of the menu (spec AC-7.17)."""
    _say("  [1] hours   [2] days   [3] weeks   [4] months")
    name = RULE_FIELDS[int(Prompt.ask("Choose", choices=["1", "2", "3", "4"], console=console)) - 1]
    while True:
        value = _UnwrappedIntPrompt.ask(_RULE_PROMPTS[name], default=getattr(draft.retention, name), console=console)
        if is_valid_rule_value(value):
            draft.retention = replace(draft.retention, **{name: value})
            return
        _say("The value must be 0 or more, or -1 (no limit).")


def _add_pattern(draft: SettingsDraft) -> None:
    pattern = Prompt.ask("Pattern to add", default="", show_default=False, console=console).strip()
    if not pattern:
        _say("No pattern given; the list is unchanged.")
    elif (problem := pattern_problem(pattern)) is not None:
        _say(f"{pattern} is not usable: {problem}; the list is unchanged.")
    elif pattern == STATE_FILE_NAME:
        _say(f"{STATE_FILE_NAME} is always excluded; the list is unchanged.")
    elif pattern in draft.patterns:
        _say(f"{pattern} is already excluded; the list is unchanged.")
    else:
        draft.patterns.append(pattern)


def _remove_pattern(draft: SettingsDraft) -> None:
    if not draft.patterns:
        _say("There are no patterns to remove.")
        return
    number = IntPrompt.ask("Number of the pattern to remove", console=console)
    if not 1 <= number <= len(draft.patterns):
        _say(f"There is no pattern with number {number}; the list is unchanged.")
        return
    draft.patterns.pop(number - 1)


def _changes(before: SettingsDraft, after: SettingsDraft) -> list[str]:
    """Describe for the log what differs between two settings (spec AC-7.13)."""
    changes = []
    if after.debounce_seconds != before.debounce_seconds:
        changes.append(f"debounce delay {before.debounce_seconds} -> {after.debounce_seconds} seconds")
    changes += [f"added pattern {pattern}" for pattern in after.patterns if pattern not in before.patterns]
    changes += [f"removed pattern {pattern}" for pattern in before.patterns if pattern not in after.patterns]
    for name in RULE_FIELDS:
        old, new = getattr(before.retention, name), getattr(after.retention, name)
        if new != old:
            changes.append(f"retention.{name} {old} -> {new}")
    return changes


def _save(destination: Path, draft: SettingsDraft) -> Path:
    """Write the draft through the atomic state file update and log it (spec AC-7.10, AC-7.13); return the state file.

    The state file is read again first, so that the tracked files a backup wrote meanwhile are kept.
    """
    state = _load_saved_state(destination)
    on_disk = SettingsDraft.of(state)
    state.excluded_patterns = exclusion_patterns(draft.patterns)
    state.debounce_seconds = draft.debounce_seconds
    state.retention = draft.retention
    try:
        state.save()
    except OSError as e:
        _error(f"cannot save {state.state_file_path}: {e}")

    try:
        logger = BackupLogger(destination)
        try:
            logger.log_session_start(
                command="config",
                source_path=state.source_path,
                destination_path=destination,
                excluded_patterns=state.excluded_patterns,
                debounce_seconds=state.debounce_seconds,
                retention=state.retention,
            )
            logger.log_settings_saved(_changes(on_disk, draft))
            logger.log_session_end()
        finally:
            logger.close()
    except OSError as e:
        _error(f"the settings were saved to {state.state_file_path}, but {destination / 'backup.log'} could not be written: {e}")
    return state.state_file_path


def _run_menu(destination: Path, state: StateManager) -> None:
    """Let the user edit a draft of the settings; write it only on save (spec AC-7.3 to AC-7.11, AC-7.17)."""
    saved = SettingsDraft.of(state)
    draft = SettingsDraft(saved.debounce_seconds, list(saved.patterns), saved.retention)
    _say(STOP_WATCH_NOTE)
    try:
        while True:
            _say("")
            _print_settings(state.source_path, draft, saved)
            if draft != saved:
                _say("Unsaved changes: choose s to save them.")
            _say("")
            _say(CONFIG_ACTIONS)
            match Prompt.ask("Choose", choices=["1", "2", "3", "4", "5", "s", "q"], console=console):
                case "1":
                    draft.debounce_seconds = _ask_debounce(draft.debounce_seconds)
                case "2":
                    _add_pattern(draft)
                case "3":
                    _remove_pattern(draft)
                case "4":
                    draft.patterns.clear()
                case "5":
                    _change_retention(draft)
                case "s":
                    state_file = _save(destination, draft)
                    _say(f"Saved to {state_file}. The changes take effect at the next start of 'run', 'watch' or 'cleanup'.")
                    return
                case _:
                    if draft == saved or Confirm.ask("Discard the unsaved changes?", default=False, console=console):
                        _say("Quit, nothing saved.")
                        return
    except EOFError:
        _say("")
        _say("Input ended, nothing saved.")
        if draft != saved:
            raise typer.Exit(code=1) from None


DEBOUNCE_KEY = "debounce"
RETENTION_KEY_PREFIX = "retention."
# The keys of config show KEY and config set KEY VALUE (spec AC-7.18)
SETTING_KEYS = (DEBOUNCE_KEY, *(f"{RETENTION_KEY_PREFIX}{name}" for name in RULE_FIELDS))
# ASCII digits with an optional leading minus sign (spec AC-7.19); int() alone would also take "+5", " 5", "1_000" and other Unicode digits
_WHOLE_NUMBER = re.compile(r"-?[0-9]+")


def _checked_key(key: str) -> str:
    """Return key when it names a setting, else end with exit code 1 and name the valid keys (spec AC-7.18, AC-7.19)."""
    if key not in SETTING_KEYS:
        # ascii() keeps the output ASCII for any key the user typed (spec AC-7.15)
        _error(f"unknown key {key!a}. Valid keys: {', '.join(SETTING_KEYS)}.")
    return key


def _checked_value(key: str, text: str) -> int:
    """Return text as the new value of key, else end with exit code 1 and name the valid values (spec AC-7.19).

    The text must be ASCII digits with an optional leading minus sign; the range is the one the menu checks (spec AC-7.5, AC-8.2).
    """
    is_debounce = key == DEBOUNCE_KEY
    value = None
    if _WHOLE_NUMBER.fullmatch(text):
        try:
            value = int(text)
        except ValueError:  # more digits than int() converts
            value = None
    if value is None or not (value >= 0 if is_debounce else is_valid_rule_value(value)):
        allowed = "a whole number of 0 or more (seconds)" if is_debounce else "0 or more, or -1 (no limit)"
        _error(f"invalid value {text!a} for {key}. Valid values: {allowed}.")
    return value


def _setting(settings: SettingsDraft, key: str) -> int:
    if key == DEBOUNCE_KEY:
        return settings.debounce_seconds
    return int(getattr(settings.retention, key.removeprefix(RETENTION_KEY_PREFIX)))


def _with_setting(settings: SettingsDraft, key: str, value: int) -> SettingsDraft:
    if key == DEBOUNCE_KEY:
        return replace(settings, debounce_seconds=value)
    return replace(settings, retention=replace(settings.retention, **{key.removeprefix(RETENTION_KEY_PREFIX): value}))


def _subcommand_destination(ctx: typer.Context, destination: Path | None) -> Path:
    """Take --destination from the subcommand, else from config, where it may stand before show and set."""
    if destination is None and ctx.parent is not None:
        destination = ctx.parent.params.get("destination")
    return _required_destination(destination)


@config_app.callback(invoke_without_command=True)
def config(
    ctx: typer.Context,
    destination: Path | None = typer.Option(  # noqa: B008
        None,
        "--destination",
        help=DESTINATION_HELP,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Show and edit the saved settings (debounce delay, exclusion patterns and retention rules).

    Without a subcommand, this opens a menu to change the debounce delay, to add,
    remove or clear exclusion patterns and to change the retention rules.
    Nothing is written before you choose save.
    When input does not come from a terminal, it prints the settings like 'config show'.
    The source directory cannot be changed here.

    Keys for 'show KEY' and 'set KEY VALUE':
      debounce          Seconds that watch waits before a backup (0 or more)
      retention.hours   Keep every backup younger than N hours
      retention.days    Keep the last backup per day for N days
      retention.weeks   Keep the last backup per week for N weeks
      retention.months  Keep the last backup per month for N months
      A retention rule is 0 (off), a positive number, or -1 (no limit).

    Examples:

      # Open the menu
      trs-file-backup config --destination C:\\Backup\\MyApp

      # Print the saved settings only
      trs-file-backup config show --destination ./backup

      # Print one value, then change it
      trs-file-backup config show retention.days --destination ./backup
      trs-file-backup config set retention.days 12 --destination ./backup

      # Keep one backup per month forever
      trs-file-backup config set retention.months -1 --destination ./backup

    Note:
      Stop a running 'watch' and wait for a running 'run' to finish first: both write their own
      settings back to the state file and would overwrite your changes.
      Saved changes take effect at the next start of 'run', 'watch' or 'cleanup'.
    """
    if ctx.invoked_subcommand is not None:
        return
    target = _required_destination(destination)
    state = _load_saved_state(target)
    if not _stdin_is_terminal():
        saved = SettingsDraft.of(state)
        _print_settings(state.source_path, saved, saved)
        return
    _run_menu(target, state)


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    key: str | None = typer.Argument(None, metavar="KEY", help="Print only the value of this setting (see the keys in 'config --help')", show_default=False),
    destination: Path | None = typer.Option(  # noqa: B008
        None,
        "--destination",
        help=DESTINATION_HELP,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Print the saved settings, or only the value of one setting.

    Nothing is asked and nothing is written.

    Examples:

      # Print the saved settings
      trs-file-backup config show --destination C:\\Backup\\MyApp

      # Print only the value, for example 12
      trs-file-backup config show retention.days --destination ./backup
    """
    target = _subcommand_destination(ctx, destination)
    if key is not None:
        _checked_key(key)
    state = _load_saved_state(target)
    saved = SettingsDraft.of(state)
    if key is not None:
        _say(str(_setting(saved, key)))
        return
    _print_settings(state.source_path, saved, saved)


# ignore_unknown_options lets a negative VALUE such as -1 through without "--" (spec AC-7.19)
@config_app.command("set", context_settings={"ignore_unknown_options": True})
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., metavar="KEY", help="The setting to change (see the keys in 'config --help')", show_default=False),
    value: str = typer.Argument(..., metavar="VALUE", help="The new value, a whole number that the key allows", show_default=False),
    destination: Path | None = typer.Option(  # noqa: B008
        None,
        "--destination",
        help=DESTINATION_HELP,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Change one setting and save it at once.

    The value is checked as the menu checks it: debounce is 0 or more,
    a retention rule is 0 (off), a positive number, or -1 (no limit).
    The change is logged in backup.log.

    Examples:

      # Keep the last backup per day for 12 days
      trs-file-backup config set retention.days 12 --destination ./backup

      # Keep one backup per month forever
      trs-file-backup config set retention.months -1 --destination ./backup

    Note:
      Stop a running 'watch' and wait for a running 'run' to finish first: both write their own
      settings back to the state file and would overwrite your changes.
      Saved changes take effect at the next start of 'run', 'watch' or 'cleanup'.
    """
    target = _subcommand_destination(ctx, destination)
    new_value = _checked_value(_checked_key(key), value)
    saved = SettingsDraft.of(_load_saved_state(target))
    if _setting(saved, key) == new_value:
        _say(f"{key} is already {new_value}; nothing was written.")
        return
    state_file = _save(target, _with_setting(saved, key, new_value))
    _say(STOP_WATCH_NOTE)
    _say(f"Saved {key} = {new_value} to {state_file}. The change takes effect at the next start of 'run', 'watch' or 'cleanup'.")


def replace_unencodable(stream: TextIO | None) -> None:
    """Make a text stream write "?" for a character its encoding cannot show, instead of raising UnicodeEncodeError.

    Only an io.TextIOWrapper can be reconfigured; any other stream, such as None under pythonw or a test runner's buffer, is left as it is.
    """
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(errors="replace")


def cli() -> None:
    """Start the CLI with stdout and stderr protected against characters the console encoding cannot show.

    File and folder names may hold such characters, for example Japanese names on a cp1252 pipe.
    The protection runs here and not in the Typer callback, because --help and --version run before the callback body.
    """
    replace_unencodable(sys.stdout)
    replace_unencodable(sys.stderr)
    app()


if __name__ == "__main__":
    cli()
