"""Main CLI application for trs-file-backup."""

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from trs_file_backup import __version__
from trs_file_backup.backup import BackupManager
from trs_file_backup.logger import BackupLogger
from trs_file_backup.state import StateManager

app = typer.Typer(
    name="trs-file-backup",
    help="trs-file-backup - Monitor and backup modified files with timestamps",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"trs-file-backup version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """trs-file-backup - Monitor and backup modified files with timestamps.

    This tool helps you create timestamped backups of modified files from a
    source directory to a destination directory. It supports one-time backups,
    initialization, and continuous monitoring.

    Use 'trs-file-backup COMMAND --help' for more information on a specific command.

    Examples:

      trs-file-backup run --source ./myproject --destination ./backup

      trs-file-backup watch --source ./myproject --destination ./backup
    """
    pass


@app.command()
def init(
    source: Path = typer.Option(
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        help="File/directory patterns to exclude (can be repeated)",
    ),
    debounce: int = typer.Option(
        2,
        "--debounce",
        help="Seconds to wait before backup (default: 2)",
        min=0,
    ),
):
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
      Exclusion patterns and debounce setting specified here are saved and used for all future backups.
    """
    logger = None
    try:
        # Add default exclusions
        excluded_patterns = [".backup_state.json"] + exclude

        # Create logger
        logger = BackupLogger(destination)

        # Log session start
        logger.log_session_start(
            command="init",
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            debounce_seconds=debounce,
        )

        # Create initial state
        state = StateManager(
            source_path=source,
            destination_path=destination,
            debounce_seconds=debounce,
            excluded_patterns=excluded_patterns,
            files={},
        )

        # Save state
        state.save()

        # Log success
        logger.log_init_success()
        logger.log_session_end()

        # Show user message
        console.print(f"[green]✓[/green] Initialized backup tracking for {source}")
        console.print(f"State file saved to {state.state_file_path}")
        console.print(f"Log file created: {destination / 'backup.log'}")
        console.print("Next run will back up all files.")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    finally:
        if logger is not None:
            logger.close()


@app.command()
def run(
    source: Path = typer.Option(
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        help="File/directory patterns to exclude (can be repeated)",
    ),
    debounce: int = typer.Option(
        2,
        "--debounce",
        help="Seconds to wait before backup (default: 2)",
        min=0,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be backed up without copying",
    ),
):
    """Execute a one-time backup of modified files.

    This command scans the source directory for files that have been modified
    since the last backup and creates timestamped copies in the destination
    directory. Only files changed after the last backup run are processed.

    Examples:

      # Basic backup
      trs-file-backup run --source C:\\Projects\\MyApp --destination C:\\Backup\\MyApp

      # Exclude log files
      trs-file-backup run --source ./src --destination ./backup --exclude "*.log"

      # Multiple exclusions with custom debounce
      trs-file-backup run --source ./src --destination ./backup --exclude "*.log" --exclude "temp_*" --debounce 5

      # Preview without copying
      trs-file-backup run --source ./src --destination ./backup --dry-run
    """
    logger = None
    try:
        # Add default exclusions
        excluded_patterns = [".backup_state.json"] + exclude

        # Load or create state
        state_file = destination / ".backup_state.json"
        state = StateManager.load(state_file)

        if state is None:
            # Create new state
            state = StateManager(
                source_path=source,
                destination_path=destination,
                debounce_seconds=debounce,
                excluded_patterns=excluded_patterns,
                files={},
            )
        else:
            # Update state with current parameters
            state.excluded_patterns = excluded_patterns
            state.debounce_seconds = debounce

        # Create logger
        logger = BackupLogger(destination)

        # Log session start
        logger.log_session_start(
            command="run",
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            debounce_seconds=debounce,
        )

        # Create backup manager
        backup_manager = BackupManager(
            source_path=source,
            destination_path=destination,
            excluded_patterns=excluded_patterns,
            state=state,
        )

        # Get files to backup
        console.print(f"Scanning source directory: {source}")
        files_to_backup = backup_manager.get_files_to_backup()
        logger.log_found_files(len(files_to_backup))

        if len(files_to_backup) == 0:
            console.print("[yellow]No modified files found.[/yellow]")
            logger.log_session_end(0, 0)
            return

        console.print(f"Found {len(files_to_backup)} modified files")

        if dry_run:
            console.print("\n[yellow]Dry-run mode: No files will be copied[/yellow]\n")
            for file in files_to_backup:
                timestamp = datetime.now()
                backup_name = BackupManager.generate_backup_filename(file.name, timestamp)
                console.print(f"  Would backup: {file.name} → {backup_name}")
            logger.log_session_end(0, len(files_to_backup))
            return

        # Backup files
        console.print("Backing up files...")
        backed_up_count = 0
        failed_count = 0

        for file in files_to_backup:
            try:
                # Wait debounce time
                time.sleep(debounce)

                # Backup file
                timestamp = datetime.now()
                backup_path = backup_manager.backup_file(file, timestamp)

                # Update state
                state.update_file_timestamp(file.name, file.stat().st_mtime)

                # Log success
                logger.log_file_backed_up(file.name, backup_path.name)
                console.print(f"  [green]✓[/green] {file.name} → {backup_path.name}")
                backed_up_count += 1

            except PermissionError as e:
                logger.log_error(f"Permission denied: {file.name}")
                console.print(f"  [red]✗[/red] Permission denied: {file.name}")
                failed_count += 1

            except OSError as e:
                logger.log_file_locked(file.name)
                console.print(f"  [yellow]⚠[/yellow] File locked, skipping: {file.name}")
                failed_count += 1

        # Save updated state
        state.save()

        # Log completion
        logger.log_backup_completed(backed_up_count, len(files_to_backup))
        logger.log_session_end(backed_up_count, len(files_to_backup))

        # Show summary
        console.print(f"\n[green]Successfully backed up {backed_up_count} files to {destination}[/green]")
        if failed_count > 0:
            console.print(f"[yellow]Failed: {failed_count} files[/yellow]")
        console.print(f"Logging to: {destination / 'backup.log'}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    finally:
        if logger is not None:
            logger.close()


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
        self.pending_files = {}
        self.backed_up_count = 0

    def on_modified(self, event):
        """Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip excluded files
        if BackupManager.matches_exclusion_pattern(file_path.name, self.backup_manager.excluded_patterns):
            # Find matching pattern for logging
            for pattern in self.backup_manager.excluded_patterns:
                if file_path.match(pattern) or (file_path.name.startswith(".") and pattern == ".backup_state.json"):
                    self.logger.log_file_excluded(file_path.name, pattern)
                    break
            return

        # Log modification
        self.logger.log_file_modified(file_path.name)
        console.print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] File modified: {file_path.name}")

        # Schedule backup after debounce
        self.pending_files[file_path] = time.time()

        # Wait for debounce
        time.sleep(self.debounce_seconds)

        # Check if file is still pending (not modified again)
        if file_path in self.pending_files:
            try:
                timestamp = datetime.now()
                backup_path = self.backup_manager.backup_file(file_path, timestamp)

                # Update state
                self.state.update_file_timestamp(file_path.name, file_path.stat().st_mtime)
                self.state.save()

                # Log success
                self.logger.log_file_backed_up(file_path.name, backup_path.name)
                console.print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Backing up: {file_path.name} → {backup_path.name} [green]✓[/green]")

                self.backed_up_count += 1

                # Remove from pending
                del self.pending_files[file_path]

            except PermissionError:
                self.logger.log_error(f"Permission denied: {file_path.name}")
                console.print(f"[red]✗[/red] Permission denied: {file_path.name}")

            except OSError:
                self.logger.log_file_locked(file_path.name)
                console.print(f"[yellow]⚠[/yellow] File locked, skipping: {file_path.name}")


@app.command()
def watch(
    source: Path = typer.Option(
        ...,
        "--source",
        help="Source directory to monitor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    destination: Path = typer.Option(
        ...,
        "--destination",
        help="Destination backup directory",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        help="File/directory patterns to exclude (can be repeated)",
    ),
    debounce: int = typer.Option(
        2,
        "--debounce",
        help="Seconds to wait after modification before backup",
        min=0,
    ),
):
    """Continuously monitor and backup files in real-time.

    This command starts a file system monitor that watches the source directory
    for changes. When a file is modified, it automatically creates a timestamped
    backup after a short delay (debounce). The monitor runs until you press
    Ctrl+C.

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
      - Hidden directories (starting with .) are automatically excluded
    """
    try:
        # Add default exclusions
        excluded_patterns = [".backup_state.json"] + exclude

        # Load or create state
        state_file = destination / ".backup_state.json"
        state = StateManager.load(state_file)

        if state is None:
            # Create new state
            state = StateManager(
                source_path=source,
                destination_path=destination,
                debounce_seconds=debounce,
                excluded_patterns=excluded_patterns,
                files={},
            )
        else:
            # Update state with current parameters
            state.excluded_patterns = excluded_patterns
            state.debounce_seconds = debounce

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
            debounce_seconds=debounce,
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
            debounce_seconds=debounce,
        )

        # Start observer
        observer = Observer()
        observer.schedule(event_handler, str(source), recursive=False)
        observer.start()

        console.print(f"[green]Starting file system monitor for {source}[/green]")
        console.print("Watching for changes... (Press Ctrl+C to stop)")
        console.print(f"Logging to: {destination / 'backup.log'}\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            logger.log_watch_stopped()
            logger.log_session_end(event_handler.backed_up_count, event_handler.backed_up_count)

            console.print("\n\nCtrl+C detected. Stopping file system monitor...")
            console.print(f"Total files backed up in this session: {event_handler.backed_up_count}")

        observer.join()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    finally:
        if logger is not None:
            logger.close()


if __name__ == "__main__":
    app()
