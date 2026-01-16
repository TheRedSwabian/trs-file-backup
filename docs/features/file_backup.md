# File Backup Feature Specification

## Overview

The trs-file-backup monitors a source directory and creates timestamped backup copies of modified files to a destination directory.

**Implementation Language:** Python 3.10+

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
- AC-2.2: The destination filename shall follow the pattern: `YYYY_MM_DD__HH_MM_SS__{original_filename}`
- AC-2.3: Example: `report.txt` → `2026_01_13__14_30_22__report.txt`
- AC-2.4: The timestamp shall use 24-hour format (HH: 00-23)
- AC-2.5: All backup files shall be stored flat in the destination directory (no subdirectories)
- AC-2.6: If the destination directory does not exist, it shall be created automatically

### FR-3: State Persistence

**ID:** FR-3
**Title:** Track last backup timestamp
**Description:** The system shall persist the timestamp of the last successful backup to determine which files have changed.

**Acceptance Criteria:**

- AC-3.1: The system shall store the last backup timestamp in a state file (`.backup_state.json`)
- AC-3.2: The state file shall be stored in the destination (backup) directory
- AC-3.3: The state file shall contain both source and destination directory paths
- AC-3.4: On first run (no state file exists), all files shall be backed up
- AC-3.5: The state file shall be updated after each successful backup operation

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

### FR-5: Real-Time File System Monitoring

**ID:** FR-5
**Title:** Watch mode for continuous file monitoring
**Description:** The system shall provide a watch mode that continuously monitors the source directory and automatically backs up files when they are modified.

**Acceptance Criteria:**

- AC-5.1: The system shall provide a `watch` command that runs continuously
- AC-5.2: The system shall detect file modification events in real-time using file system monitoring
- AC-5.3: The system shall trigger a backup automatically when a file is modified
- AC-5.4: The system shall wait for a file to be fully written before backing it up (debounce mechanism)
- AC-5.5: The system shall use a debounce delay of 2 seconds (no backup if file modified again within 2 seconds)
- AC-5.6: The system shall handle files that are locked or being written by another process (skip with warning)
- AC-5.7: The system shall log each backup operation with timestamp
- AC-5.8: The system shall continue running until explicitly stopped by the user (Ctrl+C)
- AC-5.9: The watch mode shall respect all exclusion patterns defined for the backup

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
- AC-6.8: The system shall log warnings (e.g., file skipped, locked file) with level `WARNING`
- AC-6.9: The system shall log errors (e.g., no access, permission denied) with level `ERROR`
- AC-6.10: The log file shall be a plain text file with UTF-8 encoding
- AC-6.11: Log entries shall be appended to the existing log file (not overwritten)
- AC-6.12: All script interruptions and exceptions shall be logged with appropriate level
- AC-6.13: Each session shall start with a session header logging source path, destination path, and exclusion patterns
- AC-6.14: Each session shall end with a session summary logging completion status and statistics
- AC-6.15: During a session, settings (paths, excludes) shall not be logged repeatedly
- AC-6.16: All excluded files encountered during a session shall be logged with level `WARNING`

**Log Level Usage:**

- **INFO**: Successful operations (session started, backup started, file backed up, operation completed, session ended)
- **WARNING**: Non-critical issues (file skipped due to exclusion, file locked, file not initially backed up)
- **ERROR**: Critical errors (permission denied, source directory not found, copy failed)

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
- Help text shall be accessible via `--help`, `-h`, or running command without arguments
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

Use 'trs-file-backup COMMAND --help' for more information on a specific command.

Examples:
  trs-file-backup run --source ./myproject --destination ./backup
  trs-file-backup watch --source ./myproject --destination ./backup
```

### Command: `run`

**Purpose:** Execute a backup operation

**Syntax:**

```bash
trs-file-backup run --source <path> --destination <path> [--exclude <pattern>] [--dry-run]
# Help
trs-file-backup run --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: Pattern for files/directories to exclude (optional, can be specified multiple times)
- `--debounce`: Seconds to wait before backup (optional, default: 2)
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
  --exclude PATTERN       File/directory patterns to exclude (can be repeated)
  --debounce INTEGER      Seconds to wait before backup (default: 2)
  --dry-run              Show what would be backed up without copying
  --help, -h             Show this message and exit

Examples:
  # Basic backup
  trs-file-backup run --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Exclude log files
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log"

  # Multiple exclusions with custom debounce
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log" --exclude "temp_*" --debounce 5

  # Preview without copying
  trs-file-backup run --source ./src --destination ./backup --dry-run
```

**Command Output:**

```text
Scanning source directory: C:\Projects\MyApp
Found 15 modified files
Backing up files...
  ✓ main.py → 2026_01_13__14_30_22__main.py
  ✓ readme.md → 2026_01_13__14_30_25__readme.md
  ✓ config.yaml → 2026_01_13__14_30_26__config.yaml
  ...
Successfully backed up 15 files to C:\Backup\MyApp
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
[2026-01-13 14:30:20] [INFO] Found 15 modified files
[2026-01-13 14:30:22] [INFO] Backed up: main.py → 2026_01_13__14_30_22__main.py
[2026-01-13 14:30:25] [INFO] Backed up: readme.md → 2026_01_13__14_30_25__readme.md
[2026-01-13 14:30:26] [INFO] Backed up: config.yaml → 2026_01_13__14_30_26__config.yaml
[2026-01-13 14:30:27] [WARNING] File excluded: temp.log (matches: *.log)
[2026-01-13 14:30:28] [WARNING] File locked, skipping: database.db
[2026-01-13 14:30:30] [INFO] Backup operation completed: 13 of 15 files backed up
[2026-01-13 14:30:30] [INFO] ========== Session Ended ==========
```

### Command: `init`

**Purpose:** Initialize backup tracking for a directory

**Syntax:**

```bash
trs-file-backup init --source <path> --destination <path> [--exclude <pattern>]
# Help
trs-file-backup init --help
```

**Parameters:**

- `--source`: Path to the source directory (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: Pattern for files/directories to exclude (optional, can be specified multiple times)
- `--debounce`: Seconds to wait before backup (optional, default: 2)

**Help Output:**

```bash
Usage: trs-file-backup init [OPTIONS]

  Initialize backup tracking for a directory

  This command sets up backup tracking by creating a state file in the source
  directory. The next 'run' or 'watch' command will back up all files (first
  full backup). Subsequent runs will only backup modified files.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File/directory patterns to exclude (can be repeated)
  --debounce INTEGER      Seconds to wait before backup (default: 2)
  --help, -h             Show this message and exit

Examples:
  # Basic initialization
  trs-file-backup init --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Initialize with exclusions and custom debounce
  trs-file-backup init --source ./src --destination ./backup --exclude "*.log" --exclude "*.tmp" --debounce 5

Note:
  Exclusion patterns and debounce setting specified here are saved and used for all future backups.
```

**Command Output:**

```text
Initialized backup tracking for C:\Projects\MyApp
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

**Purpose:** Continuously monitor source directory and backup files automatically when modified

**Syntax:**

```bash
trs-file-backup watch --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>]
# Help
trs-file-backup watch --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: Pattern for files/directories to exclude (optional, can be specified multiple times)
- `--debounce`: Seconds to wait after file modification before backup (optional, default: 2)

**Help Output:**

```bash
Usage: trs-file-backup watch [OPTIONS]

  Continuously monitor and backup files in real-time

  This command starts a file system monitor that watches the source directory
  for changes. When a file is modified, it automatically creates a timestamped
  backup after a short delay (debounce). The monitor runs until you press
  Ctrl+C.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File/directory patterns to exclude (can be repeated)
  --debounce INTEGER      Seconds to wait after modification before backup
                          [default: 2]
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
  - Hidden directories (starting with .) are automatically excluded
```

**Command Output:**

```text
Starting file system monitor for C:\Projects\MyApp
Watching for changes... (Press Ctrl+C to stop)
Logging to: C:\Backup\MyApp\backup.log

[2026-01-13 14:32:15] File modified: main.py
[2026-01-13 14:32:17] Backing up: main.py → 2026_01_13__14_32_17__main.py ✓

[2026-01-13 14:35:22] File modified: readme.md
[2026-01-13 14:35:24] Backing up: readme.md → 2026_01_13__14_35_24__readme.md ✓

[2026-01-13 14:38:10] File modified: temp.log (excluded)

Ctrl+C detected. Stopping file system monitor...
Total files backed up in this session: 2
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
[2026-01-13 14:32:17] [INFO] Backed up: main.py → 2026_01_13__14_32_17__main.py
[2026-01-13 14:35:22] [INFO] File modified: readme.md
[2026-01-13 14:35:24] [INFO] Backed up: readme.md → 2026_01_13__14_35_24__readme.md
[2026-01-13 14:38:10] [WARNING] File excluded: temp.log (matches: *.log)
[2026-01-13 14:40:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 14:40:00] [INFO] Session summary: 2 files backed up
[2026-01-13 14:40:00] [INFO] ========== Session Ended ==========
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
- `source_path`: The source directory being monitored
- `destination_path`: The destination backup directory
- `log_file`: Name of the log file (always `backup.log`)
- `debounce_seconds`: Wait time in seconds before backup (default: 2)
- `excluded_patterns`: Contains user-specified exclusion patterns for filenames
- User-specified patterns (via `--exclude`) are appended to the list
- Patterns support wildcards: `*` (any characters), `?` (single character)
- Subdirectories are always excluded automatically

### Log File Format (`backup.log`)

Plain text file with UTF-8 encoding, one log entry per line.

**Format:** `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`

**Session Structure:**

Each execution of the script creates a session with:

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
[2026-01-13 14:30:20] [INFO] Found 5 modified files
[2026-01-13 14:30:22] [INFO] Backed up: main.py → 2026_01_13__14_30_22__main.py
[2026-01-13 14:30:25] [WARNING] File excluded: debug.log (matches: *.log)
[2026-01-13 14:30:26] [ERROR] Permission denied: secure.dat
[2026-01-13 14:30:28] [INFO] Backed up: readme.md → 2026_01_13__14_30_28__readme.md
[2026-01-13 14:30:30] [INFO] Backup operation completed: 2 of 5 files backed up
[2026-01-13 14:30:30] [INFO] ========== Session Ended ==========

[2026-01-13 16:00:00] [INFO] ========== Session Started ==========
[2026-01-13 16:00:00] [INFO] Command: watch
[2026-01-13 16:00:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 16:00:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 16:00:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 16:00:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 16:00:00] [INFO] Watch mode started, monitoring for changes...
[2026-01-13 16:15:30] [INFO] File modified: config.yaml
[2026-01-13 16:15:32] [INFO] Backed up: config.yaml → 2026_01_13__16_15_32__config.yaml
[2026-01-13 16:20:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 16:20:00] [INFO] Session summary: 1 file backed up
[2026-01-13 16:20:00] [INFO] ========== Session Ended ==========
```

**Log Entry Types:**

- **Session boundaries**: `========== Session Started/Ended ==========`
- **Configuration**: Command, paths, exclusion patterns logged once at session start
- **Operations**: File backups, exclusions, errors during session
- **Summary**: Statistics and completion status at session end

## Implementation Notes

### General

- Implementation language: Python 3.10 or higher
- Use `typer` library for CLI framework with built-in help generation
- Use Python's `pathlib` for cross-platform path handling
- Use `shutil.copy2()` to preserve file metadata during copy
- Use `datetime.now()` for timestamp generation in format `YYYY_MM_DD__HH_MM_SS`
- TimesPath.iterdir()` to iterate only files in the top-level directory (not recursive)
- Skip all entries where `Path.is_dir()` returns True
- Use `shutil.copy2()` to preserve file metadata during copy
- All backup files are stored flat in the destination directory (no subdirectories)- State file (`.backup_state.json`) is stored in the destination directory
- State file contains both source_path and destination_path for reference- Use `datetime.now()` for timestamp generation in format `YYYY_MM_DD__HH_MM_SS`
- Timestamp format: `strftime("%Y_%m_%d__%H_%M_%S")` with 24-hour format
- Backup filename pattern: `{timestamp}__{original_filename}`
- Implement atomic state file updates (write to temp file, then rename)
- Use `pathlib.Path.match()` for pattern matching with wildcard support
- Exclusion patterns are evaluated against filenames only (not paths)

### Watch Mode (FR-5)

- Monitor only the top-level directory (do not watch subdirectories recursively)
- Implement debouncing to wait for files to finish writing
- Debounce delay is configurable via `--debounce` parameter (default: 2 seconds)
- Store debounce setting in state file for consistency across runs
- Use a timer-based approach: reset timer on each modification event, trigger backup when timer expires
- Handle file locking gracefully using try-except around file operations
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
- Log excluded files with pattern match information
- Settings are logged once per session at start, not repeated during operations
- Use `datetime.now()` for timestamp generation in format `YYYY_MM_DD__HH_MM_SS`

### Dependencies

- Python: 3.10+
- `typer`: CLI framework with automatic help generation
- `rich`: Enhanced terminal output (used by typer for help formatting)
- `watchdog`: File system event monitoring (required for watch command)
- `pathlib`: Built-in, for path operations
- `shutil`: Built-in, for file copying
- `json`: Built-in, for state file management
- `logging`: Built-in, for activity logging
