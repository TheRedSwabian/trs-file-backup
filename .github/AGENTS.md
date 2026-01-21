# trs-file-backup - Agent Instructions

## Project Overview

This is a Python CLI tool for monitoring directories and creating timestamped backups of modified files. The project uses Poetry for dependency management and follows strict conventional commit standards.

## Key Technologies

- **Language**: Python 3.10+
- **CLI Framework**: Typer + Rich (for terminal UI)
- **File Watching**: Watchdog
- **Build Tool**: Poetry
- **Testing**: Pytest + Pester (PowerShell tests)
- **Linting**: Ruff
- **CI/CD**: Jenkins with pypeline-runner
- **Versioning**: Semantic Release (automatic based on conventional commits)

## Project Structure

- `src/trs_file_backup/` - Main source code
- `tests/` - Python and PowerShell tests
- `docs/` - Sphinx documentation
- `build.ps1` - Development setup script
- `deploy.ps1` - Deployment script for Jenkins
- `pyproject.toml` - Poetry configuration and dependencies

## Important Context

### CLI Commands

The tool provides three main commands:

- `trs-file-backup init` - Initialize backup tracking
- `trs-file-backup run` - One-time backup
- `trs-file-backup watch` - Continuous monitoring mode

### Backup Behavior

- Only monitors **top-level files** in source directory (no subdirectories)
- Stores all backups in a **flat structure** in destination directory
- Backup filename format: `original_YYYY_MM_DD__HH_MM_SS.ext`
- Tracks state in `.backup_state.json` (stored in backup directory)
- Logs to `backup.log`

### Development Workflow

1. **Setup**: Run `.\build.ps1 -install` to install dependencies
2. **Testing**: Run `.venv\Scripts\pytest` for all tests
3. **Pre-commit**: Run `.venv\Scripts\pre-commit run --all-files` before committing
4. **Commits**: MUST follow conventional commit format (enforced by commitlint)

### Commit Standards

This project uses **strict conventional commits**. Every commit message must follow:

```text
<type>(<scope>): <subject>
```

**Version Impact**:

- `feat:` → Minor version bump (1.0.0 → 1.1.0)
- `fix:` → Patch version bump (1.0.0 → 1.0.1)
- `feat!:` or `fix!:` → Major version bump (breaking change)
- `docs:`, `style:`, `refactor:`, `test:`, `chore:` → No version bump

### Release Process

- **Automatic**: Jenkins builds on `develop` branch
- **Semantic Release**: Analyzes commits and auto-bumps version
- **Version Files**: Synchronized in `pyproject.toml`, `src/trs_file_backup/__init__.py`, `docs/conf.py`
- **Changelog**: Auto-generated in `CHANGELOG.md`
- **Publishing**: Tag builds publish to PyPI repository

## Code Guidelines

- **Ruff Configuration**: Line length 180, specific ignores for docstrings
- **Type Hints**: Required (mypy strict mode)
- **Test Coverage**: Required with pytest-cov
- **Python Version**: Minimum 3.10

## When Making Changes

1. **Code Changes**: Keep modifications minimal and surgical
2. **Tests**: Update or add tests as needed
3. **Documentation**: Update README.md if user-facing features change
4. **Version**: Never manually change version numbers (automatic via semantic-release)
5. **Commits**: Use correct conventional commit type for version bumping

## Package Distribution

- **Internal**: Published to PyPI (public)
- **License**: MIT
- **Installation**: `pip install trs-file-backup` (from internal repository)

## PowerShell Integration

The project includes PowerShell scripts and Pester tests. Pester 5.x is required for development.
