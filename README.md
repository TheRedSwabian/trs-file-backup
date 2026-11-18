# trs-file-backup

**trs-file-backup** automatically watches your working directories and creates timestamped backups of every changed file — purely local, no cloud, no sync service, no complex setup. Ideal for developers and creators who want a simple safety net while working on files that are not (yet) in version control.

![maintained](https://img.shields.io/badge/maintained-yes-success?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-009b9b?style=flat-square)
![PyPI](https://img.shields.io/pypi/v/trs-file-backup?style=flat-square)
![Python](https://img.shields.io/pypi/pyversions/trs-file-backup?style=flat-square)
![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)
[![Build Status](https://github.com/TheRedSwabian/trs-file-backup/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/TheRedSwabian/trs-file-backup/actions)
[![codecov](https://codecov.io/gh/TheRedSwabian/trs-file-backup/branch/develop/graph/badge.svg)](https://codecov.io/gh/TheRedSwabian/trs-file-backup)

## Requirements

- **Python** 3.13.17 or higher
- **OS**: Windows, Linux, macOS

## Features

- 📁 **Top-Level Monitoring** *(subdirectory support planned)*: Monitors files directly in the source directory
- 📦 **Flat Backup Structure**: All backups stored in one directory for easy access
- 🔄 **Incremental Backups**: Only backup files that have changed
- 🕐 **Timestamped Files**: Each backup uses format `filename_YYYY_MM_DD__HH_MM_SS.ext`
- 👁️ **Watch Mode**: Continuously monitor directories and backup automatically
- ⏱️ **Configurable Debounce**: Adjustable delay before a backup in watch mode (default: 2 seconds); `run` copies at once
- 🎯 **Smart Exclusions**: Automatically skip hidden files
- 🚫 **Custom Patterns**: Exclude specific files with wildcard patterns
- 📊 **State Tracking**: Maintain backup history in `.backup_state.json` (stored in backup directory)
- 🛠️ **Settings Menu**: Show and edit the saved exclusion patterns and debounce delay with `config`
- 📝 **Activity Logging**: All operations logged to `backup.log` with timestamps
- 🔍 **Dry-Run Mode**: Preview changes before backing up

## Quick Start

### Installation

Install this via pip (or your favorite package manager):

```bash
pip install trs-file-backup
```

### Basic Usage

```bash
# Initialize backup tracking
trs-file-backup init --source ./myproject --destination ./backup

# One-time backup of modified files
trs-file-backup run --source ./myproject --destination ./backup

# Continuous monitoring (watch mode)
trs-file-backup watch --source ./myproject --destination ./backup

# Exclude specific patterns
trs-file-backup run --source ./myproject --destination ./backup --exclude "*.log" --exclude "temp_*"

# Custom debounce delay (watch waits 5 seconds after the last change before the backup)
trs-file-backup watch --source ./myproject --destination ./backup --debounce 5

# Preview without copying
trs-file-backup run --source ./myproject --destination ./backup --dry-run

# Get help
trs-file-backup --help
trs-file-backup run --help
```

### Saved Settings

`init` saves the exclusion patterns and the debounce delay in `.backup_state.json`.
A later `run` or `watch` without `--exclude` or `--debounce` uses the saved value.
Giving the option replaces the saved value; it is not added to the saved patterns.
Patterns are matched against the file name only; a pattern that can never match one, such as `logs/*.log`, is rejected
(the full rule is AC-4.9 in the [feature specification](docs/features/file_backup.md)).
The new value is saved, also when `run` finds no modified files; only `run --dry-run` never writes the state file.
Without a state file, the defaults apply: no patterns of your own and a debounce delay of 2 seconds.
The state file belongs to the folder given with `--destination`: a copied or moved backup folder works on its own state file and never writes into the old folder.
A backup folder belongs to one source: `run` and `watch` with another `--source` stop with an error; use another backup folder, or run `init` again.

To see or change the saved settings without running `init` again, use `config`:

```bash
# Print the saved settings
trs-file-backup config show --destination ./backup

# Open a menu to change the debounce delay or add, remove and clear exclusion patterns
trs-file-backup config --destination ./backup
```

Nothing is written until you choose "save" in the menu.
The changes take effect at the next start of `run` or `watch`.
Stop a running `watch` and wait for a running `run` to finish first: both write their own settings back to the state file and would overwrite your changes.

### Example Output

Original file: `report.txt`
Backup file: `report_2026_01_13__14_30_22.txt`

## Commands

- **`init`**: Initialize backup tracking for a directory
- **`run`**: Execute a one-time backup of modified files
- **`watch`**: Continuously monitor and backup files in real-time
- **`config`**: Show and edit the saved settings (`config show` only prints them)

Use `trs-file-backup COMMAND --help` for detailed information on each command.

## Known Limitations

- Two backups of the same file within one second get the same name, and the newer backup replaces the older one.
  This is known and accepted for now; see KL-1 in the [specification](docs/features/file_backup.md#known-limitations).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, commit conventions, and the release process.
