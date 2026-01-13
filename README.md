# trs-file-backup

Script to backup changed filed in a given Folder.

![maintained](https://img.shields.io/badge/maintained-yes-success?style=flat-square)
![license](https://img.shields.io/badge/license-MQ--internal-009b9b?style=flat-square)
![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![pypeline](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cuinixam/pypeline/main/assets/badge/v0.json)
[![Build Status](https://jenkins.example.com/buildStatus/icon?job=SD-RM%2FSD-RM%2Ftrs-file-backup%2Fdevelop)](https://jenkins.example.com/job/SD-RM/job/SD-RM/job/trs-file-backup/job/develop/)

## Installation

Install this via pip (or your favorite package manager):

`pip install trs-file-backup`

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

Before pushing one shall run the `pre-commit` checks to format, lint and spell check all files. Just run the `run pre-commit checks` VS Code task or from command line:

```shell
.venv/Scripts/pre-commit run --all-files
```

## Release

This repository uses [semantic release](https://python-semantic-release.readthedocs.io/en/latest/) to automate versioning the Python projects.
The package version will be automatically updated when the ``develop`` branch is built.

When the tag build is triggered on Jenkins, the `release.bat` will publish the new version to the PyPI repository.

## Credits

This package was created with [Copier](https://copier.readthedocs.io/) and the [sple/pypackage-template](https://git.example.com/projects/SPLE/repos/pypackage-template) project template.
