# CHANGELOG


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
