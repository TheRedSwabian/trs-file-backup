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

- **Python** 3.10 or higher
- **OS**: Windows, Linux, macOS

## Features

- 📁 **Top-Level Monitoring** *(subdirectory support planned)*: Monitors files directly in the source directory
- 📦 **Flat Backup Structure**: All backups stored in one directory for easy access
- 🔄 **Incremental Backups**: Only backup files that have changed
- 🕐 **Timestamped Files**: Each backup uses format `filename_YYYY_MM_DD__HH_MM_SS.ext`
- 👁️ **Watch Mode**: Continuously monitor directories and backup automatically
- ⏱️ **Configurable Debounce**: Adjustable delay before backup (default: 2 seconds)
- 🎯 **Smart Exclusions**: Automatically skip hidden files
- 🚫 **Custom Patterns**: Exclude specific files with wildcard patterns
- 📊 **State Tracking**: Maintain backup history in `.backup_state.json` (stored in backup directory)
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

# Custom debounce delay (wait 5 seconds before backup)
trs-file-backup run --source ./myproject --destination ./backup --debounce 5

# Preview without copying
trs-file-backup run --source ./myproject --destination ./backup --dry-run

# Get help
trs-file-backup --help
trs-file-backup run --help
```

### Example Output

Original file: `report.txt`
Backup file: `report_2026_01_13__14_30_22.txt`

## Commands

- **`init`**: Initialize backup tracking for a directory
- **`run`**: Execute a one-time backup of modified files
- **`watch`**: Continuously monitor and backup files in real-time

Use `trs-file-backup COMMAND --help` for detailed information on each command.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, commit conventions, and the release process.
