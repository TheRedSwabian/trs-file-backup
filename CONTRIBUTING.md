# Contributing

## Start developing

The project uses [uv](https://docs.astral.sh/uv/) for dependency management and packaging.

Both the package and its development need Python 3.13.17 or newer; for development, `.python-version` also sets an upper bound so that uv picks a 3.13 release.
The reason is the emSign CA incident:
Python 3.13.17 bundles pip 26.2.2, and older pip versions trust compromised certificate authorities (CAs) through their bundled CA list.

```powershell
uv sync --all-groups
```

Let `git blame` skip commits that only change formatting, such as line endings.
GitHub does this automatically; locally, run once per clone:

```shell
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

### Running Tests

```shell
uv run pytest
```

This runs the Python tests (`test_*.py`) in `tests/`.

For those using [VS Code](https://code.visualstudio.com/) there are tasks defined for the most common commands:

- install dependencies
- run tests
- run all checks configured for pre-commit
- generate documentation

See the `.vscode/tasks.json` for more details.

## Committing changes

Pre-commit checks every commit message against the [conventional commit format](https://www.conventionalcommits.org/en).
The check runs in the [commitizen](https://github.com/commitizen-tools/commitizen) hook.
Install the git hooks once per clone:

```shell
uv run pre-commit install
```

`.pre-commit-config.yaml` sets `default_install_hook_types`,
so this installs the `commit-msg` hook for the message check as well as the `pre-commit` hook for the checks on the staged files.
CI does not check commit messages: a commit made without the hooks goes through unchecked.

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
- `perf:` - Performance improvement → **Patch version bump** (1.0.0 → 1.0.1)
- `docs:` - Documentation only → No version bump
- `style:` - Code style/formatting → No version bump
- `refactor:` - Code refactoring → No version bump
- `test:` - Adding tests → No version bump
- `build:` - Build system, packaging or dependencies → No version bump
- `ci:` - CI configuration → No version bump
- `chore:` - Maintenance tasks → No version bump
- `revert:` - Reverting an earlier commit → No version bump, because semantic-release does not know this type
- `<type>!:` or a `BREAKING CHANGE:` footer, with any type above except `revert` - Breaking change → **Major version bump** (1.0.0 → 2.0.0)

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
2. **Version Calculation**: Based on commit types, see [Commit Message Format](#commit-message-format)
3. **Automatic Updates**: Version is updated in `pyproject.toml`, see [Version Files](#version-files)
4. **CHANGELOG.md**: Automatically generated with all changes grouped by type
5. **Git Tag**: A new version tag is created automatically

### Version Files

The version is set in one place only, `pyproject.toml`, and semantic-release updates it there:

```toml
# pyproject.toml
[project]
version = "1.2.3"
```

`uv.lock` and `CHANGELOG.md` contain the number as well, but uv and semantic-release write them; nobody edits a version number by hand.

`trs_file_backup.__version__` (and with it `trs-file-backup --version`) and `release` in `docs/conf.py` read the version from the installed package metadata.
So the package must be installed in the uv environment, as `uv sync` does it; otherwise the import fails with `importlib.metadata.PackageNotFoundError`.
After a version change, the editable install in `.venv` reports the old number until uv installs it again.
`uv run` does that before it starts the command, so run the tool and the docs build with `uv run`, not from `.venv` directly.

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
uv run trs-file-backup --version
```
