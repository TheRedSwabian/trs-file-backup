# trs-file-backup

Script to monitor directories and create timestamped backups of modified files automatically.

![maintained](https://img.shields.io/badge/maintained-yes-success?style=flat-square)
![license](https://img.shields.io/badge/license-MQ--internal-009b9b?style=flat-square)
![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![pypeline](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cuinixam/pypeline/main/assets/badge/v0.json)
[![Build Status](https://jenkins.example.com/buildStatus/icon?job=SD-RM%2FSD-RM%2Ftrs-file-backup%2Fdevelop)](https://jenkins.example.com/job/SD-RM/job/SD-RM/job/trs-file-backup/job/develop/)

## Features

- 📁 **Top-Level Monitoring**: Only monitors files in the main directory, ignores subdirectories
- 📦 **Flat Backup Structure**: All backups stored in one directory for easy access
- 🔄 **Incremental Backups**: Only backup files that have changed
- 🕐 **Timestamped Files**: Each backup uses format `YYYY_MM_DD__HH_MM_SS__filename.ext`
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
Backup file: `2026_01_13__14_30_22__report.txt`

## Commands

- **`init`**: Initialize backup tracking for a directory
- **`run`**: Execute a one-time backup of modified files
- **`watch`**: Continuously monitor and backup files in real-time

Use `trs-file-backup COMMAND --help` for detailed information on each command.

## Start developing

The project uses Poetry for dependencies management and packaging.
Run the `build.ps1` script to install Python and create the virtual environment.

```powershell
.\build.ps1 -install
```

This will also generate a `poetry.lock` file, you should track this file in version control.

To execute the test suite, call pytest from the virtual environment:

```shell
.venv/Scripts/pytest
```

For those using [VS Code](https://code.visualstudio.com/) there are tasks defined for the most common commands:

- install dependencies
- run tests
- run all checks configured for pre-commit
- generate documentation

See the `.vscode/tasks.json` for more details.

## Committing changes

This repository uses [commitlint](https://github.com/conventional-changelog/commitlint) for checking if the commit message meets the [conventional commit format](https://www.conventionalcommits.org/en).

### Commit Message Format

Commit messages must follow the Conventional Commits format. The commit type determines how the version is bumped:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Commit Types and Version Impact:**

- `feat:` - New feature → **Minor version bump** (1.0.0 → 1.1.0)
- `fix:` - Bug fix → **Patch version bump** (1.0.0 → 1.0.1)
- `docs:` - Documentation only → No version bump
- `style:` - Code style/formatting → No version bump
- `refactor:` - Code refactoring → No version bump
- `test:` - Adding tests → No version bump
- `chore:` - Maintenance tasks → No version bump
- `feat!:` or `fix!:` - Breaking change → **Major version bump** (1.0.0 → 2.0.0)

**Examples:**

```bash
# Minor version bump (new feature)
git commit -m "feat: add configurable debounce parameter for backup delay"

# Patch version bump (bug fix)
git commit -m "fix: correct timestamp format in backup filenames"

# Major version bump (breaking change with !)
git commit -m "feat!: change CLI parameter names from --src/--dst to --source/--destination"
```

### Pre-Commit Checks

Before pushing one shall run the `pre-commit` checks to format, lint and spell check all files. Just run the `run pre-commit checks` VS Code task or from command line:

```shell
.venv/Scripts/pre-commit run --all-files
```

## Release

This repository uses [semantic release](https://python-semantic-release.readthedocs.io/en/latest/) to automate versioning and changelog generation.

### Automatic Versioning

The version is automatically determined by analyzing commit messages since the last release:

1. **Jenkins Build**: When the `develop` branch is built, semantic-release analyzes all commits
2. **Version Calculation**: Based on commit types (feat, fix, BREAKING CHANGE)
3. **Automatic Updates**: Version is updated in:
   - `pyproject.toml`
   - `src/trs_file_backup/__init__.py`
   - `docs/conf.py`
4. **CHANGELOG.md**: Automatically generated with all changes grouped by type
5. **Git Tag**: A new version tag is created automatically

### Version Files

The version is maintained in multiple files (automatically synchronized by semantic-release):

```python
# src/trs_file_backup/__init__.py
__version__ = "1.2.3"
```

```toml
# pyproject.toml
[tool.poetry]
version = "1.2.3"
```

### Release Process

1. Develop on feature branches with conventional commits
2. Merge to `develop` branch
3. Jenkins automatically:
   - Analyzes commits
   - Bumps version
   - Updates CHANGELOG.md
   - Creates git tag
4. When the tag build is triggered on Jenkins, the `release.bat` publishes the new version to the PyPI repository

### Manual Version Check

To check the current version:

```bash
poetry version
# or
python -c "from trs_file_backup import __version__; print(__version__)"
```

## Credits

This package was created with [Copier](https://copier.readthedocs.io/) and the [sple/pypackage-template](https://git.example.com/projects/SPLE/repos/pypackage-template) project template.
