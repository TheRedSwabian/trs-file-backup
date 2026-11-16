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

Pre-commit checks every commit message against the rule in [Commit Message Format](#commit-message-format).
The check runs in the [commitizen](https://github.com/commitizen-tools/commitizen) hook.
Install the git hooks once per clone:

```shell
uv run pre-commit install
```

`.pre-commit-config.yaml` sets `default_install_hook_types`,
so this installs the `commit-msg` hook for the message check as well as the `pre-commit` hook for the checks on the staged files.
CI runs the same commitizen hook on every pull request to `develop`, so a commit made without the hooks is caught there.
The `commit-messages` job checks each commit that the pull request adds on top of `develop`, one message at a time, and fails if any message breaks the rule.

### Commit Message Format

This rule is binding: the `commit-msg` hook and the CI check reject every message that breaks it.
It follows [Conventional Commits](https://www.conventionalcommits.org/en), with the restrictions below.
`[tool.commitizen]` in `pyproject.toml` holds it as a regular expression, and `tests/test_commit_message_rule.py` tests it.

```text
<type>(<scope>)!: <subject> (#<issue>, #<issue>)

<body>

<footer>
```

- `<type>` is one of the types in the list below, in lowercase. No other word is accepted.
- `(<scope>)` is optional, for example `fix(cli): ...`. It has no spaces.
- `!` marks a breaking change. Only `feat`, `fix` and `build` may carry it.
- A `BREAKING CHANGE:` or `BREAKING-CHANGE:` footer also marks a breaking change, and only the same three types may carry it.
  The footer is a paragraph of its own: the line directly before it must be empty, because semantic-release does not see it otherwise.
  For the other types, no line may start with these words, not even an indented line or the subject itself, because semantic-release would read them as a breaking change.
- After the colon comes exactly one space, then the subject.
- The subject must not contain `)` directly followed by `:` or `!:`, as in `x (b)!: y`.
  In a message with a scope, semantic-release would read everything up to that point as the scope, and with `!` as a breaking change.
- The subject may end with issue references in parentheses, such as ` (#12)` or ` (#12, #15)`.
  Any other `#` followed by a number in the subject fails, for example `fix: x #30` or `fix: x (#30) more`.
  The body and the footer may mention issues freely, such as `Closes #3`.
- Spaces or tabs at the end of the subject line are allowed.
- An empty line separates the body from the subject; a body line directly below the subject fails.
  Empty means empty: a line that holds only spaces does not count.
- No special prefixes exist: messages that start with `Merge`, `Revert "`, `Pull request`, `fixup!`, `squash!` or `amend!` fail.

**Commit Types and Version Impact:**

- `feat:` - New feature → **Minor version bump** (1.0.0 → 1.1.0)
- `fix:` - Bug fix → **Patch version bump** (1.0.0 → 1.0.1)
- `docs:` - Documentation only → No version bump
- `style:` - Code style/formatting → No version bump
- `refactor:` - Code refactoring → No version bump
- `test:` - Adding tests → No version bump
- `build:` - Build system, packaging or dependencies → No version bump
- `ci:` - CI configuration → No version bump
- `chore:` - Maintenance tasks → No version bump
- `revert:` - Reverting an earlier commit that is not released yet → No version bump, because semantic-release does not know this type
- `feat!:`, `fix!:` or `build!:`, or a breaking change footer on one of these types - Breaking change → **Major version bump** (1.0.0 → 2.0.0)

Reverting a change that is already released on PyPI is typed `fix:`, for example `fix: revert debounce change from 3.1.0`.
`revert:` triggers no release, so users would keep the released change.

There is no `perf` type: use `fix` for a speed-up that users notice, `refactor` for one they do not.
The type list in `[tool.semantic_release.commit_parser_options]` in `pyproject.toml` must match this list, apart from `revert`.

semantic-release reads the type from the subject line only: a body line that starts with `fix:` or `feat:` bumps nothing.
`pyproject.toml` sets this with `parse_squash_commits = false`, because the repository only rebase-merges and so has no squash commits.

**Git actions whose messages fail, and what to do instead:**

- `git revert` writes `Revert "feat: x"` and does not run the `commit-msg` hook, so only CI rejects it.
  Rewrite the message right after the revert with `git commit --amend`: `revert: x`, or `fix: ...` when the reverted change is already released.
- `git merge`, or `git pull` without `--rebase` on a branch that has diverged, creates a merge commit, and merge messages fail.
  Use `git pull --rebase`, and rebase your branch onto `develop` instead of merging `develop` into it.
- `git commit --fixup` and `git commit --squash` create `fixup!` and `squash!` commits, and the hook rejects them.
  Fold the change into the earlier commit instead, for example with `git commit --amend` when that commit is the last one.
- On GitHub, the "Update branch" button merges `develop` into the pull request, and the "Revert" button creates `Revert "…"` commits: the CI check fails on both.
  Rebase the branch locally instead, and write revert commits by hand as described above.

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
3. **Automatic Updates**: Version is updated in `pyproject.toml` and `uv.lock`, see [Version Files](#version-files)
4. **CHANGELOG.md**: Automatically generated with all changes grouped by type
5. **Git Tag**: A new version tag is created automatically

semantic-release adds each new release to `CHANGELOG.md` directly below the line `<!-- version list -->`.
Keep that line: without it, semantic-release leaves `CHANGELOG.md` unchanged and the release has no changelog entry.

### Version Files

The version is set in one place only, `pyproject.toml`, and semantic-release updates it there:

```toml
# pyproject.toml
[project]
version = "1.2.3"
```

`uv.lock` and `CHANGELOG.md` contain the number as well, but uv and semantic-release write them; nobody edits a version number by hand.
semantic-release runs `uv lock` in its build command, before `uv build`, and puts the updated `uv.lock` into the release commit (`assets` in `[tool.semantic_release]`).
So after each release, `uv.lock` on `develop` carries the released version.
The build command joins its steps with `&&`: if any step fails, the release stops before it commits, tags or pushes anything.
Keep it on one line joined by `&&`; with the steps on separate lines, semantic-release runs on after a failed step and commits a stale `uv.lock`.

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
