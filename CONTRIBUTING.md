# Contributing

## Start developing

The project uses [uv](https://docs.astral.sh/uv/) for dependency management and packaging.

```powershell
uv sync --all-groups
```

### Prerequisites

**PowerShell Modules:**
The project requires [Pester](https://pester.dev/) 5.x for PowerShell tests. Install via Scoop:

```powershell
scoop install pester
```

Or from PowerShell Gallery:

```powershell
Install-Module -Name Pester -MinimumVersion 5.0.0 -Force
```

The `build.ps1 -install` script will check for Pester and attempt to install it via Scoop if missing.

### Running Tests

```shell
uv run pytest
```

This will run both Python tests (`test_*.py`) and PowerShell Pester tests (`*.Tests.ps1`).

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

Before pushing, run the `pre-commit` checks to format, lint and spell check all files. Just run the `run pre-commit checks` VS Code task or from the command line:

```shell
uv run pre-commit run --all-files
```

## Release

This repository uses [semantic release](https://python-semantic-release.readthedocs.io/en/latest/) to automate versioning and changelog generation.

### Automatic Versioning

The version is automatically determined by analyzing commit messages since the last release:

1. **GitHub Actions**: When the `develop` branch is pushed, semantic-release analyzes all commits
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
[project]
version = "1.2.3"
```

### Release Process

1. Develop on feature branches with conventional commits
2. Merge to `develop` branch
3. GitHub Actions automatically:
   - Analyzes commits
   - Bumps version
   - Updates CHANGELOG.md
   - Creates git tag and GitHub release

### Manual Version Check

To check the current version:

```bash
python -c "from trs_file_backup import __version__; print(__version__)"
```
