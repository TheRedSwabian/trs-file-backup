# ✨ Features

## File Backup System

The trs-file-backup provides automated backup functionality for monitoring and backing up modified files with timestamps.

See [File Backup Specification](file_backup.md) for detailed requirements and specifications.

### Key Features

- **Top-Level File Monitoring**: Monitors only files in the main directory (subdirectories ignored)
- **Flat Backup Structure**: All backup files stored in a single directory without subdirectories
- **Incremental Backup**: Only modified files are backed up after the first run
- **Timestamped Filenames**: Each backup includes timestamp in format `YYYY_MM_DD__HH_MM_SS__filename.ext`
- **Smart Exclusions**: Automatically excludes hidden files and subdirectories
- **Custom Exclusion Patterns**: Support for wildcard patterns via `--exclude` parameter
- **Configurable Debounce**: Adjustable delay before backup with `--debounce` parameter (default: 2 seconds)
- **State Tracking**: Maintains backup history in `.backup_state.json` (stored in backup directory)
- **Activity Logging**: All operations logged to `backup.log` with timestamps and severity levels
- **Dry-Run Mode**: Preview what would be backed up without copying files
- **Real-Time Watch Mode**: Continuously monitor directories and backup files automatically
- **Comprehensive Help System**: Built-in help for all commands without external documentation
