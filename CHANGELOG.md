# CHANGELOG

<!-- version list -->

## v3.0.1 (2026-11-13)

### Bug Fixes

- Show PATTERN as the value of --exclude in the help
  ([`4ba9c56`](https://github.com/TheRedSwabian/trs-file-backup/commit/4ba9c5675dbeabde90a5ed9d2ad240ce15d5315f))

typer 0.29 prints the Python type of a list option, so the help of init, run and watch showed
  "--exclude <list[str]>". An explicit metavar keeps the help readable on every typer version the
  package allows (typer>=0.16).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

### Testing

- Patch only the backup logger in logger tests
  ([`ad4b027`](https://github.com/TheRedSwabian/trs-file-backup/commit/ad4b0270c5d98f490be04b293e5f9df78d4e7ef1))

The tests replaced logging.getLogger for every logger name. pytest 9.2 looks up the root logger
  between tests for its log capture and then got a Mock, which ended the run with a TypeError. The
  tests now return the mock for the "trs_file_backup" logger only.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>


## v3.0.0 (2026-11-13)

### Build System

- Require python 3.13.17 or newer
  ([`b24dfc7`](https://github.com/TheRedSwabian/trs-file-backup/commit/b24dfc754938aef8d74d59dd5d68dac27eed9fe3))

Raise requires-python from >=3.10 to >=3.13.17 and update uv.lock. The lock drops exceptiongroup,
  tomli and the older pins that only Python 3.10 used; no version changes on 3.13. Name the new
  minimum in README, CONTRIBUTING and the feature specification; AGENTS points to requires-python
  instead. Add the commit types build, ci, perf and revert to CONTRIBUTING, with their effect on the
  version. AGENTS now points to that list instead of repeating it.

BREAKING CHANGE: trs-file-backup now needs Python 3.13.17 or newer. The reason is the emSign CA
  incident: Python 3.13.17 bundles pip 26.2.2, and older pip versions trust compromised certificate
  authorities through their bundled CA list. On Python 3.10 up to 3.13.16, pip keeps installing
  2.0.1, which stays available there.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

### Documentation

- Remove Pester and build.ps1 references from contributor docs
  ([`0330b5f`](https://github.com/TheRedSwabian/trs-file-backup/commit/0330b5ffbe9585de50d706437bdd0c7f80fff66b))

The Pester tests were removed earlier and the repository has no build.ps1, so the setup steps sent
  contributors and agents looking for files that do not exist. Also describe the real mypy settings
  instead of claiming strict mode.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

### Refactoring

- Let ruff take its target version from requires-python
  ([`8014ce4`](https://github.com/TheRedSwabian/trs-file-backup/commit/8014ce4211f86b71c67cd91ec97549e7894dd139))

ruff checked the code against Python 3.8 while the package requires 3.13.17. Without target-version
  ruff reads requires-python, so the supported version is set in one place. known-first-party named
  the distribution instead of the module and had no effect.

Rewrite typing.List, Dict and Optional to built-in generics and X | None (pyupgrade UP006, UP035,
  UP045). The CLI built by typer is unchanged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

### Breaking Changes

- Trs-file-backup now needs Python 3.13.17 or newer. The reason is the emSign CA incident: Python
  3.13.17 bundles pip 26.2.2, and older pip versions trust compromised certificate authorities
  through their bundled CA list. On Python 3.10 up to 3.13.16, pip keeps installing 2.0.1, which
  stays available there.


## v2.0.1 (2026-06-11)

### Bug Fixes

- **ci**: Add PyPI publishing via OIDC trusted publishing
  ([#17](https://github.com/TheRedSwabian/trs-file-backup/pull/17),
  [`399de9e`](https://github.com/TheRedSwabian/trs-file-backup/commit/399de9ef36f6955f5ee2b890b3ebf400acf27916))

- Add Codecov coverage badge (develop branch) below Build Status badge - Add PyPI version and Python
  version badges - Add 'why use this' intro paragraph - Add Requirements section (Python >= 3.10,
  Windows/Linux/macOS) - Fix Top-Level Monitoring description (subdirectory support planned) - Move
  commit conventions and release docs to new CONTRIBUTING.md - Replace Credits boilerplate with
  short Contributing link - Fix test/pre-commit commands to use uv run (cross-platform) - Add
  pypa/gh-action-pypi-publish step for automated PyPI publishing via OIDC

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

### Documentation

- Add Codecov badge, improve README for open source, and add CONTRIBUTING.md
  ([#17](https://github.com/TheRedSwabian/trs-file-backup/pull/17),
  [`ed9de3e`](https://github.com/TheRedSwabian/trs-file-backup/commit/ed9de3ec79c32da4779855bf8ff0185f439794e6))

- Add Codecov coverage badge (develop branch) below Build Status badge - Add 'why use this' intro
  paragraph - Add PyPI version and Python version badges - Add Requirements section (Python >= 3.10,
  Windows/Linux/macOS) - Fix Top-Level Monitoring description (subdirectory support planned) - Move
  commit conventions and release docs to new CONTRIBUTING.md - Replace Credits boilerplate with
  short Contributing link - Fix test/pre-commit commands to use uv run (cross-platform)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>


## v2.0.0 (2026-06-11)

### Bug Fixes

- Resolve CI test failures and lint issues
  ([#3](https://github.com/TheRedSwabian/trs-file-backup/pull/3),
  [`9bedb2e`](https://github.com/TheRedSwabian/trs-file-backup/commit/9bedb2e25c81608daf64659256a18dad06546670))

- Remove obsolete Pester tests (create-portable.ps1 no longer exists) - Strip ANSI escape codes in
  help tests via click.unstyle() to handle Rich rendering on Linux CI runners - Fix import ordering
  in test_cli.py (ruff isort) - Add missing newline at end of .gitignore and LICENSE

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- **ci**: Grant write permissions and id-token for release job
  ([#11](https://github.com/TheRedSwabian/trs-file-backup/pull/11),
  [`d366467`](https://github.com/TheRedSwabian/trs-file-backup/commit/d3664677e52c0b5db5e73737f2c2e218a56cf22e))

PSR needs contents:write to push the release commit and tag to develop. id-token:write is required
  for OIDC-based PyPI publishing.

Also: existing git tags (v0.1.0-v1.0.4) converted from annotated to lightweight tags so PSR v9 can
  correctly detect them in branch history. GitPython's tag.commit dereference for annotated tags
  fails silently in Docker environments, causing PSR to fall back to v0.0.0 as baseline.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- **release**: Install uv inside PSR Docker container before build
  ([#11](https://github.com/TheRedSwabian/trs-file-backup/pull/11),
  [`038f9a0`](https://github.com/TheRedSwabian/trs-file-backup/commit/038f9a067cfbd346514d9bac07ea8ad25e86af1e))

The python-semantic-release GitHub Action runs inside a Docker container that does not have uv
  installed. The build_command is executed within that container, so uv must be installed first.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

- **release**: Restore main branch group name for semantic-release tag recognition
  ([#11](https://github.com/TheRedSwabian/trs-file-backup/pull/11),
  [`bd1a10b`](https://github.com/TheRedSwabian/trs-file-backup/commit/bd1a10b99780807bb3544bd875cabf440e5520ba))

The branch group was renamed from 'main' to 'develop' in a prior simplification, which has semantic
  meaning in python-semantic-release. The 'main' group name identifies the primary release branch.
  Without it, existing tags are not recognized as full releases.

- Rename branch group back to 'main' (matching on 'develop') - Add explicit prerelease = false

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

### Build System

- Migrate package manager from Poetry to uv
  ([#1](https://github.com/TheRedSwabian/trs-file-backup/pull/1),
  [`a84c5cb`](https://github.com/TheRedSwabian/trs-file-backup/commit/a84c5cb741bc19c29925bf7403557aa7ff3bed8e))

Replace Poetry with uv and hatchling as build backend. Migrate pyproject.toml to PEP 621 project
  table with dependency-groups. Remove internal Artifactory source, pypeline-runner, and
  pypeline-semantic-release. Update semantic-release config for GitHub remote. Remove obsolete
  files: Jenkinsfile, build.bat, pypeline.yaml, poetry.lock, poetry.toml. Update
  .pre-commit-config.yaml, .vscode/tasks.json, README.md, AGENTS.md, and docs/conf.py.

BREAKING CHANGE: Poetry is no longer supported. Use uv for dependency management.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

### Documentation

- Move AGENTS.md to root and remove obsolete skills
  ([#3](https://github.com/TheRedSwabian/trs-file-backup/pull/3),
  [`2cd8887`](https://github.com/TheRedSwabian/trs-file-backup/commit/2cd8887393726027b8314ffd70c9729933c45ecf))

- Move .github/AGENTS.md to repository root (required location for Copilot CLI) - Delete
  .github/skills/ directory (replaced by marketplace extensions) - Delete .github/prompts/ directory

Closes #3

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

### Breaking Changes

- Poetry is no longer supported. Use uv for dependency management.


## v1.0.4 (2026-01-20)

### Bug Fixes

- Add blank lines after session end for better log readability
  ([`354db04`](https://github.com/TheRedSwabian/trs-file-backup/commit/354db04904b67ebecaabd523d52bdd2e5db5cb31))


## v1.0.3 (2026-01-20)

### Bug Fixes

- Windows atomic write and test compatibility
  ([`a30a736`](https://github.com/TheRedSwabian/trs-file-backup/commit/a30a736b040bdffd562a3d1e26c62c3bd1d7ca31))


## v1.0.2 (2026-01-20)

### Bug Fixes

- Improve version handling and remove redundant output
  ([`b590ff1`](https://github.com/TheRedSwabian/trs-file-backup/commit/b590ff1f4827aab2a040b39fdff78aa7313c1ec0))

- Show --version flag in help output and make it functional - Remove duplicate session summary
  message on watch stop - Clean dist directory before build to prevent stale wheel packages


## v1.0.1 (2026-01-20)

### Bug Fixes

- Prevent duplicate backups from rapid filesystem events on Windows
  ([`219bae0`](https://github.com/TheRedSwabian/trs-file-backup/commit/219bae0e1264bd0a704db1a5d89406a2a852027b))

Implement debounce mechanism to consolidate multiple events per file into single backup.


## v1.0.0 (2026-01-19)

### Features

- Change backupfile name extend help information
  ([`e2e5fb5`](https://github.com/TheRedSwabian/trs-file-backup/commit/e2e5fb516d806e6a574752d51ea9f8336f7666b2))


## v0.1.0 (2026-01-16)

### Bug Fixes

- Add pester test and fix some stuff
  ([`fc508fc`](https://github.com/TheRedSwabian/trs-file-backup/commit/fc508fcd4dfa390683d86a7a9cfc22a238e795a8))

- Add portable creation
  ([`20e9a46`](https://github.com/TheRedSwabian/trs-file-backup/commit/20e9a46e5c7530b208ef973a13276abcfc3a4401))

- Corrected tests and setup
  ([`4c521ea`](https://github.com/TheRedSwabian/trs-file-backup/commit/4c521eaa8dc542fb79b749bc9cc45e7c974b0e87))

### Documentation

- Add features
  ([`6ca1171`](https://github.com/TheRedSwabian/trs-file-backup/commit/6ca11712040ac4cb8655773f9c56799cfba3276c))

### Features

- Add correct version in wheel file
  ([`e56daed`](https://github.com/TheRedSwabian/trs-file-backup/commit/e56daed058195d5ce71be3c78ccc4a1996e9ef01))

- Implementation with claude sonnet 4.5
  ([`4f7dd05`](https://github.com/TheRedSwabian/trs-file-backup/commit/4f7dd0584897c436c475acdcaa2050603925bbe2))
