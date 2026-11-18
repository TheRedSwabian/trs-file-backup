# File Backup Feature Specification

## Overview

The trs-file-backup monitors a source directory and creates timestamped backup copies of modified files to a destination directory.

**Implementation Language:** Python; the minimum version is set by `requires-python` in `pyproject.toml`

The tool shall be implemented as a Python command-line application with comprehensive help functionality.

## Functional Requirements

### FR-1: Source Directory Monitoring

**ID:** FR-1
**Title:** Monitor source directory for modified files
**Description:** The system shall identify all files in a source directory that have been modified since the last backup operation.

**Acceptance Criteria:**

- AC-1.1: The system shall accept a source directory path as input
- AC-1.2: The system shall monitor only files in the top-level directory (no subdirectories)
- AC-1.3: The system shall ignore all subdirectories and their contents
- AC-1.4: The system shall compare file modification timestamps against the last backup timestamp
- AC-1.5: The system shall handle invalid or non-existent source directories with clear error messages

### FR-2: File Backup Creation

**ID:** FR-2
**Title:** Create timestamped backup copies
**Description:** The system shall copy modified files to a destination directory with timestamps in the filename.

**Acceptance Criteria:**

- AC-2.1: The system shall copy each modified file to the destination directory
- AC-2.2: The destination filename shall follow the pattern: `{original_filename}_YYYY_MM_DD__HH_MM_SS.{extension}`
- AC-2.3: Example: `report.txt` → `report_2026_01_13__14_30_22.txt`
- AC-2.4: The timestamp shall use 24-hour format (HH: 00-23)
- AC-2.5: All backup files shall be stored flat in the destination directory (no subdirectories)
- AC-2.6: If the destination directory does not exist, it shall be created automatically
- AC-2.7: `run` shall copy the modified files without waiting between or before the copies;
  the debounce delay applies only to `watch` (AC-5.4, AC-5.5), and `run --debounce` only saves it (AC-3.8)
- AC-2.8: The system shall copy the data to a temporary file `.trs-file-backup-<12 random hexadecimal digits>.tmp` in the destination directory
  and give it the backup name only when the data is complete.
  The temporary name has a fixed length of 33 characters, so a long backup name does not make it too long for the file system.
  If the data copy or the rename fails, the system shall remove the temporary file, also when it is read-only, and leave a file that already has the backup name unchanged.
  If only the metadata copy (times, permission bits) fails, the backup shall be kept without a message, because its data is complete.
  A temporary file left behind by a process that was killed during the copy stays in the destination directory

### FR-3: State Persistence

**ID:** FR-3
**Title:** Track last backup timestamp
**Description:** The system shall persist the timestamp of the last successful backup to determine which files have changed.

**Acceptance Criteria:**

- AC-3.1: The system shall store the last backup timestamp in a state file (`.backup_state.json`)
- AC-3.2: The state file shall be stored in the destination (backup) directory
- AC-3.3: The state file shall contain both source and destination directory paths
- AC-3.4: On first run (no state file exists), all files shall be backed up
- AC-3.5: The state file shall be updated after each successful backup operation.
  It shall store the modification time read before the copy, so a version written during the copy is backed up by the next run or debounce
- AC-3.6: The state file shall store the exclusion patterns and the debounce delay (the saved settings);
  `init` saves the values given to it, and `config` changes them (FR-7)
- AC-3.7: `run` and `watch` shall use the saved exclusion patterns when `--exclude` is not given, and the saved debounce delay when `--debounce` is not given
- AC-3.8: A given `--exclude` shall replace the saved user patterns (not be added to them), and a given `--debounce` shall replace the saved delay.
  The new values shall be saved in the state file, also when `run` finds no modified files.
  Only `run --dry-run` never writes the state file.
  `--debounce 0` is a given value.
- AC-3.9: Without a state file, `run` and `watch` shall use the defaults: no user patterns and a debounce delay of 2 seconds
- AC-3.10: The pattern `.backup_state.json` shall appear exactly once in the exclusion patterns that `init`, `run`, `watch` and `config` use and save;
  a pattern given twice shall be saved once
- AC-3.11: For every command, the directory given with `--destination` shall be the destination: the state file shall be read from and written to it,
  and backups shall go into it, also when the `destination_path` stored in the state file names another directory (a copied or moved backup folder).
  Every write of the state file shall store the given directory as `destination_path`.
- AC-3.12: When a state file exists and the `--source` given to `run` or `watch` is another directory than the saved `source_path`,
  the command shall stop before it backs up, writes the state file or the log, or starts watching: it shall print an error that names the saved source
  and says to use another backup folder or to run `init` again, and exit with code 1.
  Both paths are compared after they are made absolute and normalised; on Windows, a difference in letter case alone is not a different directory.
  Without a state file there is no check, and `init` always starts a new state.

### FR-4: Exclusion Patterns

**ID:** FR-4
**Title:** Exclude specific files and directories
**Description:** The system shall allow exclusion of certain files and directories from backup.

**Acceptance Criteria:**

- AC-4.1: The system shall exclude hidden files (starting with `.`)
- AC-4.2: The system shall exclude the state file itself from backup
- AC-4.3: Users shall be able to provide additional exclusion patterns via CLI parameter `--exclude`
- AC-4.4: Multiple exclusion patterns can be specified by repeating the `--exclude` parameter
- AC-4.5: Exclusion patterns shall support wildcards (e.g., `*.log`, `temp_*`)
- AC-4.6: Exclusion patterns shall be matched against the filename only (not paths)
- AC-4.7: All subdirectories are automatically excluded (only top-level files are processed)
- AC-4.8: AC-3.6 to AC-3.10 define how exclusion patterns are saved and which patterns `run` and `watch` use
- AC-4.9: `init`, `run` and `watch` shall use an `--exclude` value without leading and trailing whitespace, as `config` does (AC-7.6).
  A pattern that is empty or consists of whitespace only, contains a path separator (`/` or `\`), or is `.` or `..`
  can never match a bare file name (AC-4.6) and shall be rejected; every other pattern is accepted.
  `init`, `run` and `watch` shall reject it with a usage error that names `--exclude`, the pattern and the reason (exit code 2),
  before anything is written.
  Such a pattern in an existing state file, saved by an older version, shall be dropped silently when the state file is read,
  because it cannot be used as a file-name pattern.

### FR-5: Real-Time File System Monitoring

**ID:** FR-5
**Title:** Watch mode for continuous file monitoring
**Description:** The system shall provide a watch mode that continuously monitors the source directory
and automatically backs up files when they are modified, created or moved into it.

**Acceptance Criteria:**

- AC-5.1: The system shall provide a `watch` command that runs continuously
- AC-5.2: The system shall detect file modification, creation and move events in real-time using file system monitoring
- AC-5.3: The system shall trigger a backup automatically when a file is modified
- AC-5.4: The system shall wait for a file to be fully written before backing it up (debounce mechanism)
- AC-5.5: The system shall use the configured debounce delay, default 2 seconds (no backup if another event for the file arrives within that delay).
  AC-3.6 to AC-3.9 define which delay is used
- AC-5.6: The system shall handle files that are locked or being written by another process (skip with warning); AC-6.18 defines how a lock is recognised
- AC-5.7: The system shall log each backup operation with timestamp
- AC-5.8: The system shall continue running until explicitly stopped by the user (Ctrl+C)
- AC-5.9: The watch mode shall respect all exclusion patterns defined for the backup
- AC-5.10: A file created in the source directory, or moved or renamed into it, shall trigger a backup like a modified file (AC-5.3 to AC-5.9).
  For a move or rename, the new name decides; a file moved from the source directory into a subdirectory is ignored (AC-1.3).
  The console and the log name the kind of event: `File modified: <name>`, `File created: <name>` or `File moved: <name>`
- AC-5.11: If the state file cannot be saved after a successful backup, the console and the log shall show the error `Cannot save state file: <reason>`.
  The backup still counts and is logged as backed up, and the watch mode continues

### FR-6: Activity Logging

**ID:** FR-6
**Title:** Log all script activities to a log file
**Description:** The system shall document all activities, operations, and errors in a log file stored in the destination directory.

**Acceptance Criteria:**

- AC-6.1: The system shall create a log file named `backup.log` in the destination directory
- AC-6.2: The log file shall be created during `init` command
- AC-6.3: If the log file does not exist during `run` or `watch` command, it shall be created automatically
- AC-6.4: Each log entry shall include timestamp in format `YYYY-MM-DD HH:MM:SS`
- AC-6.5: Each log entry shall include a log level: `INFO`, `WARNING`, or `ERROR`
- AC-6.6: Log entry format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- AC-6.7: The system shall log successful backup operations with level `INFO`
- AC-6.8: The system shall log warnings (e.g., file skipped, locked file as AC-6.18 defines it) with level `WARNING`
- AC-6.9: The system shall log errors (e.g., no access, permission denied, copy failed as AC-6.18 defines them) with level `ERROR`
- AC-6.10: The log file shall be a plain text file with UTF-8 encoding
- AC-6.11: Log entries shall be appended to the existing log file (not overwritten)
- AC-6.12: All script interruptions and exceptions shall be logged with appropriate level
- AC-6.13: Each session shall start with a session header logging source path, destination path,
  and the exclusion patterns and debounce delay the session actually uses (after AC-3.7 to AC-3.10 are applied)
- AC-6.14: Each session shall end with a session summary logging completion status and statistics
- AC-6.15: During a session, settings (paths, excludes) shall not be logged repeatedly
- AC-6.16: All excluded files encountered during a `watch` session shall be logged with level `WARNING`; `run` logs no excluded files
- AC-6.17: The log entry for an excluded file (AC-6.16) shall give the reason: `File excluded: <name> (hidden file)` for a hidden file (AC-4.1),
  also for the state file, and `File excluded: <name> (matches: <pattern>)` with the first exclusion pattern that matches the name
- AC-6.18: When `run` or `watch` cannot back up a file because of an operating system error, the console and the log shall name the cause,
  and the system shall continue with the next file:
  - Locked file: Windows error 32 (sharing violation) or 33 (lock violation), `BlockingIOError`, or error number `EBUSY`.
    Level `WARNING`, message `File locked, skipping: <name>`.
    A locked file on Windows raises `PermissionError`, so the Windows error decides, not the error number `EACCES`
  - Missing permission: any other `PermissionError`. Level `ERROR`, message `Permission denied: <name>`
  - Any other error, e.g. disk full, path too long, or a file deleted between scan and copy:
    level `ERROR`, message `Backup failed: <name> (<reason>)`, where `<reason>` is the error text from the operating system, else the message of the error

**Log Level Usage:**

- **INFO**: Successful operations (session started, backup started, file backed up, operation completed, session ended)
- **WARNING**: Non-critical issues (file skipped due to exclusion, file locked as AC-6.18 defines it, file not initially backed up)
- **ERROR**: Critical errors (permission denied and copy failed as AC-6.18 defines them, state file not saved in watch mode (AC-5.11), source directory not found)

### FR-7: Show and Edit the Saved Settings

**ID:** FR-7
**Title:** Show and edit the saved settings on the console
**Description:** The system shall print the settings saved in the state file and let the user change single settings in a menu, without running `init` again.

**Acceptance Criteria:**

- AC-7.1: `config show --destination <path>` shall print the saved settings without asking anything:
  the source directory, the debounce delay, and the user exclusion patterns numbered from 1.
  The pattern `.backup_state.json` is not listed, because it is always excluded (AC-3.10).
  An empty list of user patterns shall be printed as `(none)`.
- AC-7.2: `config --destination <path>` shall open a menu when standard input is a terminal; otherwise it shall behave like `config show`
- AC-7.3: The menu shall show the settings as in AC-7.1 and offer these actions:
  change the debounce delay, add a pattern, remove a pattern by its number, clear all user patterns, save and quit, quit without saving
- AC-7.4: The source directory shall be read-only, and the list of tracked files shall be neither shown nor changed
- AC-7.5: A new debounce delay shall be a whole number of 0 or more seconds; a negative number shall be rejected and asked for again
- AC-7.6: A new pattern shall be stored without leading and trailing whitespace.
  Adding a pattern that is already listed, or `.backup_state.json`, shall leave the list unchanged and say so;
  a pattern that AC-4.9 rejects shall be rejected with its reason, and the list stays unchanged.
- AC-7.7: Removing by a number that is not in the list shall print a message and leave the list unchanged; the menu continues, `config` does not exit
- AC-7.8: Clearing shall remove all user patterns; `.backup_state.json` stays excluded (AC-3.10)
- AC-7.9: After each change, the menu shall show the settings again and mark what differs from the state file: a changed delay, a new pattern, a removed pattern
- AC-7.10: Nothing shall be written before the user chooses "save".
  Save shall write the patterns and the delay through the atomic state file update (see Implementation Notes)
  and keep the source directory and the tracked files as the state file holds them at that moment.
- AC-7.11: Quitting with unsaved changes shall ask for confirmation.
  When the input ends before "save", nothing is saved; the exit code is 1 if changes were lost, else 0.
- AC-7.12: Without a state file in the destination directory, `config` and `config show` shall print an error that says to run `init` first,
  exit with code 1, and create nothing.
  A state file that cannot be read shall also give an error and exit code 1.
- AC-7.13: When `config` saves, it shall write a session to `backup.log` as FR-6 describes:
  the session header with command `config` and the saved settings, one line that names the changes, and the session end.
  `config show`, and quitting without saving, shall not write to `backup.log`.
  When the state file was saved but `backup.log` cannot be written, the settings shall stay saved;
  `config` shall print an error that says the settings were saved and names `backup.log`, and exit with code 1.
- AC-7.14: Saved changes take effect at the next start of `run` or `watch` (AC-3.7).
  `run` and `watch` read the state file at their start and keep the settings in memory; `watch` writes them back after each backup and `run` at its end,
  which overwrites a change that `config` saved meanwhile. Stop a running `watch` and wait for a running `run` to finish before using `config`.
- AC-7.15: The text that `config` prints, apart from paths and patterns, shall use ASCII characters only

## Non-Functional Requirements

### NFR-1: Performance

- The system shall handle directories with up to 10,000 files efficiently (< 30 seconds)
- File copying shall provide progress indication for large files (> 10 MB)

### NFR-2: Error Handling

- All file system errors shall be logged with clear error messages
- Permission errors shall not stop the entire backup process
- A summary report shall be provided after each backup run

### NFR-3: Usability

- The CLI interface shall provide clear help messages
- Progress shall be visible during backup operations
- The system shall report the number of files backed up successfully
- The tool shall provide a `--help` / `-h` option for the main command and all subcommands
- Help messages shall include command descriptions, parameter explanations, and usage examples
- Users shall be able to use the tool without reading external documentation
- The console output of all commands shall use ASCII markers (`OK`, `ERROR`, `WARNING`, `->`), so it stays readable on any console code page
- A character in a path that the console encoding cannot show shall be printed as `?`; it shall not end the command, also when the output goes into a pipe or a file
- File names, paths and error messages shall appear on the console exactly as they are: text such as `[red]` or `:fire:` in a name is printed, not read as formatting or emoji code

### NFR-4: Help System

**ID:** NFR-4
**Title:** Comprehensive command-line help
**Description:** The system shall provide built-in help functionality that allows users to understand and use all features without external documentation.

**Requirements:**

- The main command shall display overview help listing all available commands
- Each subcommand shall have detailed help including:
  - Command purpose and description
  - Required and optional parameters with explanations
  - Usage examples
  - Common use cases
- Help text shall be accessible via `--help` or `-h`; `trs-file-backup` without a command shall show the main help.
  A command without its required options shall print a usage error that names the missing option and points to the help option `-h` (exit code 2).
- Error messages shall suggest relevant help commands when parameters are missing or invalid

## CLI Interface Specification

### Main Command Help

**Syntax:**

```bash
trs-file-backup --help
# or
trs-file-backup -h
# or
trs-file-backup
```

**Output:**

```text
Usage: trs-file-backup [OPTIONS] COMMAND [ARGS]...

  trs-file-backup - Monitor and backup modified files with timestamps

  This tool helps you create timestamped backups of modified files from a
  source directory to a destination directory. It supports one-time backups,
  initialization, and continuous monitoring.

Options:
  --version, -v  Show version and exit
  --help, -h     Show this message and exit

Commands:
  run    Execute a one-time backup of modified files
  init   Initialize backup tracking for a directory
  watch  Continuously monitor and backup files in real-time
  config Show and edit the saved settings (debounce delay and exclusion patterns)

Use 'trs-file-backup COMMAND --help' for more information on a specific command.

Examples:
  trs-file-backup run --source ./myproject --destination ./backup
  trs-file-backup watch --source ./myproject --destination ./backup
```

### Command: `run`

**Purpose:** Execute a backup operation

**Syntax:**

```bash
trs-file-backup run --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>] [--dry-run]
# Help
trs-file-backup run --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times).
  It replaces the saved patterns; without it, the saved patterns are used (AC-3.7, AC-3.8)
- `--debounce`: Debounce delay in seconds that `watch` uses (optional); `run` itself copies without waiting (AC-2.7).
  It replaces the saved value; without it, the saved value is used, or 2 if none is saved (AC-3.7 to AC-3.9)
- `--dry-run`: Show what would be backed up without actually copying files (optional)

**Help Output:**

```bash
Usage: trs-file-backup run [OPTIONS]

  Execute a one-time backup of modified files

  This command scans the source directory for files that have been modified
  since the last backup and creates timestamped copies in the destination
  directory. Only files changed after the last backup run are processed.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated).
                          Replaces the saved patterns; if not given, the saved
                          patterns are used
  --debounce INTEGER      Seconds to wait in watch mode; run itself copies
                          without waiting. Replaces the saved value; if not
                          given, the saved value is used
                          [default: (saved value, else 2)]
  --dry-run              Show what would be backed up without copying
  --help, -h             Show this message and exit

Examples:
  # Basic backup
  trs-file-backup run --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Exclude log files
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log"

  # Multiple exclusions; save a debounce delay of 5 seconds for watch
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log" --exclude "temp_*" --debounce 5

  # Preview without copying
  trs-file-backup run --source ./src --destination ./backup --dry-run
```

**Command Output:**

```text
Scanning source directory: C:\Projects\MyApp
Found 4 modified files
Backing up files...
  OK main.py -> main_2026_01_13__14_30_21.py
  OK readme.md -> readme_2026_01_13__14_30_21.md
  OK config.yaml -> config_2026_01_13__14_30_21.yaml
  WARNING File locked, skipping: database.db

Successfully backed up 3 files to C:\Backup\MyApp
Failed: 1 files
Logging to: C:\Backup\MyApp\backup.log
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:30:20] [INFO] ========== Session Started ==========
[2026-01-13 14:30:20] [INFO] Command: run
[2026-01-13 14:30:20] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:30:20] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:30:20] [INFO] Exclusion patterns: .backup_state.json, *.log, temp_*
[2026-01-13 14:30:20] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:30:20] [INFO] Found 4 modified files
[2026-01-13 14:30:21] [INFO] Backed up: main.py → main_2026_01_13__14_30_21.py
[2026-01-13 14:30:21] [INFO] Backed up: readme.md → readme_2026_01_13__14_30_21.md
[2026-01-13 14:30:21] [INFO] Backed up: config.yaml → config_2026_01_13__14_30_21.yaml
[2026-01-13 14:30:21] [WARNING] File locked, skipping: database.db
[2026-01-13 14:30:21] [INFO] Backup operation completed: 3 of 4 files backed up
[2026-01-13 14:30:21] [INFO] Session summary: 3 of 4 files backed up
[2026-01-13 14:30:21] [INFO] ========== Session Ended ==========
```

### Command: `init`

**Purpose:** Initialize backup tracking for a directory

**Syntax:**

```bash
trs-file-backup init --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>]
# Help
trs-file-backup init --help
```

**Parameters:**

- `--source`: Path to the source directory (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times)
- `--debounce`: Seconds that `watch` waits before a backup; `run` copies without waiting, see AC-2.7 (optional, default: 2)

**Help Output:**

```bash
Usage: trs-file-backup init [OPTIONS]

  Initialize backup tracking for a directory

  This command sets up backup tracking by creating a state file in the
  destination directory. The next 'run' or 'watch' command will back up all files (first
  full backup). Subsequent runs will only backup modified files.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated)
  --debounce INTEGER      Seconds to wait in watch mode; run copies without
                          waiting  [default: 2]
  --help, -h             Show this message and exit

Examples:
  # Basic initialization
  trs-file-backup init --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Initialize with exclusions and custom debounce
  trs-file-backup init --source ./src --destination ./backup --exclude "*.log" --exclude "*.tmp" --debounce 5

Note:
  Exclusion patterns and debounce setting specified here are saved.
  Later 'run' and 'watch' commands use them, unless they are given --exclude or --debounce, which replaces the saved value.
```

**Command Output:**

```text
OK Initialized backup tracking for C:\Projects\MyApp
State file saved to C:\Backup\MyApp\.backup_state.json
Log file created: C:\Backup\MyApp\backup.log
Next run will back up all files.
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:25:10] [INFO] ========== Session Started ==========
[2026-01-13 14:25:10] [INFO] Command: init
[2026-01-13 14:25:10] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:25:10] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:25:10] [INFO] Exclusion patterns: .backup_state.json, *.log, *.tmp
[2026-01-13 14:25:10] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:25:10] [INFO] State file created: .backup_state.json
[2026-01-13 14:25:10] [INFO] Backup tracking initialized successfully
[2026-01-13 14:25:10] [INFO] ========== Session Ended ==========
```

### Command: `watch`

**Purpose:** Continuously monitor source directory and backup files automatically when modified, created or moved into it (AC-5.10)

**Syntax:**

```bash
trs-file-backup watch --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>]
# Help
trs-file-backup watch --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times).
  It replaces the saved patterns; without it, the saved patterns are used (AC-3.7, AC-3.8)
- `--debounce`: Seconds to wait after a file is modified, created or moved in, before backup (optional).
  It replaces the saved value; without it, the saved value is used, or 2 if none is saved (AC-3.7 to AC-3.9)

**Help Output:**

```bash
Usage: trs-file-backup watch [OPTIONS]

  Continuously monitor and backup files in real-time

  This command starts a file system monitor that watches the source directory
  for changes. When a file is modified, created or moved into it, it
  automatically creates a timestamped backup after a short delay (debounce).
  The monitor runs until you press Ctrl+C.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated).
                          Replaces the saved patterns; if not given, the saved
                          patterns are used
  --debounce INTEGER      Seconds to wait after a file is modified, created
                          or moved in, before backup. Replaces the saved
                          value; if not given, the saved value is used
                          [default: (saved value, else 2)]
  --help, -h             Show this message and exit

Examples:
  # Basic watch mode
  trs-file-backup watch --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Watch with exclusions
  trs-file-backup watch --source ./src --destination ./backup --exclude "*.log"

  # Custom debounce delay (5 seconds)
  trs-file-backup watch --source ./src --destination ./backup --debounce 5

Tips:
  - Use Ctrl+C to stop monitoring
  - Debounce prevents backing up files that are still being written
  - Subdirectories are ignored; hidden files (starting with .) are excluded
```

**Command Output:**

```text
Starting file system monitor for C:\Projects\MyApp
Watching for changes... (Press Ctrl+C to stop)
Logging to: C:\Backup\MyApp\backup.log

[2026-01-13 14:32:15] File modified: main.py
[2026-01-13 14:32:17] Backing up: main.py -> main_2026_01_13__14_32_17.py OK

[2026-01-13 14:35:22] File modified: readme.md
[2026-01-13 14:35:24] Backing up: readme.md -> readme_2026_01_13__14_35_24.md OK

[2026-01-13 14:39:05] File created: notes.txt
[2026-01-13 14:39:07] Backing up: notes.txt -> notes_2026_01_13__14_39_07.txt OK

Ctrl+C detected. Stopping file system monitor...
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:32:00] [INFO] ========== Session Started ==========
[2026-01-13 14:32:00] [INFO] Command: watch
[2026-01-13 14:32:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:32:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:32:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 14:32:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:32:00] [INFO] Watch mode started, monitoring for changes...
[2026-01-13 14:32:15] [INFO] File modified: main.py
[2026-01-13 14:32:17] [INFO] Backed up: main.py → main_2026_01_13__14_32_17.py
[2026-01-13 14:35:22] [INFO] File modified: readme.md
[2026-01-13 14:35:24] [INFO] Backed up: readme.md → readme_2026_01_13__14_35_24.md
[2026-01-13 14:38:10] [WARNING] File excluded: temp.log (matches: *.log)
[2026-01-13 14:39:05] [INFO] File created: notes.txt
[2026-01-13 14:39:07] [INFO] Backed up: notes.txt → notes_2026_01_13__14_39_07.txt
[2026-01-13 14:40:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 14:40:00] [INFO] Session summary: 3 of 3 files backed up
[2026-01-13 14:40:00] [INFO] ========== Session Ended ==========
```

### Command: `config`

**Purpose:** Show and edit the settings saved in the state file (FR-7)

**Syntax:**

```bash
trs-file-backup config --destination <path>
trs-file-backup config show --destination <path>
# Help
trs-file-backup config --help
trs-file-backup config show --help
```

**Parameters:**

- `--destination`: Path to the destination backup directory that holds the state file (required).
  It may stand before or after `show`.

**Help Output:**

```bash
Usage: trs-file-backup config [OPTIONS] COMMAND [ARGS]...

  Show and edit the saved settings (debounce delay and exclusion patterns).

  Without a subcommand, this opens a menu to change the debounce delay and to add,
  remove or clear exclusion patterns. Nothing is written before you choose save.
  When input does not come from a terminal, it prints the settings like 'config show'.
  The source directory cannot be changed here.

Options:
  --destination PATH  Destination backup directory that holds the state file
  --help, -h          Show this message and exit

Commands:
  show  Print the saved settings without asking anything.

Examples:
  # Open the menu
  trs-file-backup config --destination C:\Backup\MyApp

  # Print the saved settings only
  trs-file-backup config show --destination ./backup

Note:
  Stop a running 'watch' and wait for a running 'run' to finish first: both write their own
  settings back to the state file and would overwrite your changes.
  Saved changes take effect at the next start of 'run' or 'watch'.
```

**Command Output (`config show`):**

```text
Saved settings
  Source:    C:\Projects\MyApp   (read-only)
  Debounce:  5 s
  Excluded:  1) *.log
             2) temp_*
```

**Menu (`config`), after the delay was set to 0 and pattern 2 was removed:**

```text
Saved settings
  Source:    C:\Projects\MyApp   (read-only)
  Debounce:  0 s   (changed)
  Excluded:  1) *.log
  Removed:   temp_*
Unsaved changes: choose s to save them.

  [1] change debounce   [2] add pattern   [3] remove pattern
  [4] clear patterns    [s] save and quit [q] quit without saving
Choose [1/2/3/4/s/q]: s
Saved to C:\Backup\MyApp\.backup_state.json. The changes take effect at the next start of 'run' or 'watch'.
```

Before the first list, the menu prints the note to stop a running `watch` and wait for a running `run` to finish first.
A pattern added in the menu is marked `(new)`.

**Log File Example (backup.log), after this save:**

```text
[2026-01-13 15:10:04] [INFO] ========== Session Started ==========
[2026-01-13 15:10:04] [INFO] Command: config
[2026-01-13 15:10:04] [INFO] Source: C:\Projects\MyApp
[2026-01-13 15:10:04] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 15:10:04] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 15:10:04] [INFO] Debounce delay: 0 seconds
[2026-01-13 15:10:04] [INFO] Settings changed: debounce delay 5 -> 0 seconds; removed pattern temp_*
[2026-01-13 15:10:04] [INFO] ========== Session Ended ==========
```

## Data Structures

### State File Format (`.backup_state.json`)

```json
{
  "source_path": "C:\\Projects\\MyApp",
  "destination_path": "C:\\Backup\\MyApp",
  "log_file": "backup.log",
  "debounce_seconds": 2,
  "excluded_patterns": [
    ".backup_state.json",
    "*.log",
    "temp_*"
  ],
  "files": {
    "main.py": 1736772622.5,
    "readme.md": 1736772625.8,
    "config.yaml": 1736772626.3
  }
}
```

**Notes:**

- The state file is stored in the destination (backup) directory
- On Windows, an antivirus or the indexer may hold the new file for a moment, so the final rename is tried up to 5 times, 0.1 seconds apart, before the save fails
- `source_path`: The source directory being monitored; AC-3.12 defines what happens when `run` or `watch` gets another one
- `destination_path`: The destination backup directory; AC-3.11 defines which directory counts when the folder was copied or moved
- `log_file`: Name of the log file (always `backup.log`)
- `debounce_seconds`: Debounce delay in seconds that `watch` waits before a backup (default: 2); `run` does not wait (AC-2.7)
- `excluded_patterns`: `.backup_state.json`, followed by the user-specified exclusion patterns for filenames
- The user-specified patterns are the ones last given with `--exclude` or saved by `config`; AC-3.6 to AC-3.10 and FR-7 define when they are saved and used
- Patterns support wildcards: `*` (any characters), `?` (single character)
- Subdirectories are always excluded automatically

### Log File Format (`backup.log`)

Plain text file with UTF-8 encoding, one log entry per line.

**Format:** `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`

**Session Structure:**

Each execution of `init`, `run` or `watch`, and each save in the `config` menu, creates a session;
`config show` and quitting `config` without saving write nothing (AC-7.13).
A session has:

1. Session header with configuration
2. Operation log entries
3. Session footer with summary

**Example multi-session log:**

```text
[2026-01-13 10:00:00] [INFO] ========== Session Started ==========
[2026-01-13 10:00:00] [INFO] Command: init
[2026-01-13 10:00:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 10:00:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 10:00:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 10:00:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 10:00:00] [INFO] Backup tracking initialized successfully
[2026-01-13 10:00:00] [INFO] ========== Session Ended ==========

[2026-01-13 14:30:20] [INFO] ========== Session Started ==========
[2026-01-13 14:30:20] [INFO] Command: run
[2026-01-13 14:30:20] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:30:20] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:30:20] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 14:30:20] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:30:20] [INFO] Found 3 modified files
[2026-01-13 14:30:22] [INFO] Backed up: main.py → main_2026_01_13__14_30_22.py
[2026-01-13 14:30:26] [ERROR] Permission denied: secure.dat
[2026-01-13 14:30:28] [INFO] Backed up: readme.md → readme_2026_01_13__14_30_28.md
[2026-01-13 14:30:30] [INFO] Backup operation completed: 2 of 3 files backed up
[2026-01-13 14:30:30] [INFO] Session summary: 2 of 3 files backed up
[2026-01-13 14:30:30] [INFO] ========== Session Ended ==========

[2026-01-13 16:00:00] [INFO] ========== Session Started ==========
[2026-01-13 16:00:00] [INFO] Command: watch
[2026-01-13 16:00:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 16:00:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 16:00:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 16:00:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 16:00:00] [INFO] Watch mode started, monitoring for changes...
[2026-01-13 16:15:30] [INFO] File modified: config.yaml
[2026-01-13 16:15:32] [INFO] Backed up: config.yaml → config_2026_01_13__16_15_32.yaml
[2026-01-13 16:20:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 16:20:00] [INFO] Session summary: 1 of 1 files backed up
[2026-01-13 16:20:00] [INFO] ========== Session Ended ==========
```

**Log Entry Types:**

- **Session boundaries**: `========== Session Started/Ended ==========`
- **Configuration**: Command, paths, exclusion patterns logged once at session start
- **Operations**: File backups, exclusions, errors during session
- **Summary**: Statistics and completion status at session end

## Known Limitations

Behaviour that is known, not wanted, and accepted for now.
Each entry names the decision, so that it is not reported again as a new defect.

### KL-1: Two backups of one file within the same second share a name

The backup name has a resolution of one second (AC-2.2).
When the same file is backed up twice within one second, both backups get the same name,
and the newer complete backup replaces the older one (`os.replace`, AC-2.8).
Only the newer version is kept; a failed copy still leaves the older backup unchanged (AC-2.8).
This was already the behaviour before AC-2.8; the test `test_a_successful_backup_replaces_a_file_of_the_same_name` in `tests/test_backup.py` pins it.

**Decision (2026-11-18):** known and accepted for now.
With the default debounce delay of 2 seconds (AC-5.5), `watch` rarely backs up one file twice within one second.
One `run` backs up each file at most once; only two runs started within the same second can collide.
A change, for example a counter suffix for a name that is already taken, needs its own issue and changes AC-2.2 and that test on purpose.

## Implementation Notes

### General

- Implementation language: Python; the minimum version is set by `requires-python` in `pyproject.toml`
- Use `typer` library for CLI framework with built-in help generation
- Use Python's `pathlib` for cross-platform path handling
- Copy a file as AC-2.8 says: `shutil.copyfile()` to the temporary file, `shutil.copystat()` for the metadata, `os.replace()` to the backup name
- Use `datetime.now()` for timestamp generation
- Use `Path.iterdir()` to iterate only files in the top-level directory (not recursive)
- Skip all entries where `Path.is_dir()` returns True
- All backup files are stored flat in the destination directory (no subdirectories)
- State file (`.backup_state.json`): AC-3.2 and AC-3.11 define its directory, AC-3.3 its two paths, and AC-3.11 and AC-3.12 how each path is used when it is read
- Timestamp format: `strftime("%Y_%m_%d__%H_%M_%S")` with 24-hour format
- Backup filename pattern: see AC-2.2
- Implement atomic state file updates (write to temp file, then rename)
- Use `pathlib.Path.match()` for pattern matching with wildcard support
- Exclusion patterns: AC-4.6 (file name only) and AC-4.9 (which patterns are accepted)

### Watch Mode (FR-5)

- Top-level directory only: AC-1.3 and AC-4.7; the observer is scheduled with `recursive=False`
- Implement debouncing to wait for files to finish writing
- Debounce delay and its default: AC-5.5
- The debounce delay is saved in the state file; AC-3.6 to AC-3.9 define which delay `run` and `watch` use
- Use a timer-based approach: reset the timer on each event that AC-5.5 and AC-5.10 name, trigger backup when timer expires
- Catch the errors of the copy with try-except and report them by cause, as AC-6.18 defines it
- Log skipped files (locked/excluded) separately from successful backups
- Ensure clean shutdown on SIGINT (Ctrl+C)

### Help System

- Use `typer` with `rich` for formatted help output
- All commands must have detailed `help` parameter texts
- Provide usage examples in command docstrings
- Help text should be clear, concise, and actionable
- Include tips and notes for common use cases

### Logging (FR-6)

- Log file (`backup.log`) is stored in the destination directory
- Use Python's `logging` module for structured logging
- Log format: `[%(asctime)s] [%(levelname)s] %(message)s`
- Time format for logs: `%Y-%m-%d %H:%M:%S`
- Log to file only (not to console), console shows user-friendly messages
- Create log file during init or first run if it doesn't exist
- Always append to existing log file using mode 'a', never overwrite
- Use `logging.FileHandler` with UTF-8 encoding and append mode
- Each script execution creates a session with:
  - Session start marker and configuration (command, paths, excludes)
  - Operation logs (backups, exclusions, errors)
  - Session end marker and summary
- Log excluded files with the reason defined in AC-6.17
- Settings are logged once per session at start, not repeated during operations

### Dependencies

- Python: the minimum version is set by `requires-python` in `pyproject.toml`
- `typer`: CLI framework with automatic help generation
- `rich`: Enhanced terminal output (used by typer for help formatting) and the prompts of the `config` menu
- `watchdog`: File system event monitoring (required for watch command)
- `pathlib`: Built-in, for path operations
- `shutil`: Built-in, for file copying
- `json`: Built-in, for state file management
- `logging`: Built-in, for activity logging
