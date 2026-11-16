"""Tests for the commit message rule in [tool.commitizen] of pyproject.toml.

The commitizen commit-msg hook and the CI commit check use this rule; CONTRIBUTING.md, section "Commit Message Format", describes it.
commitizen drops comment lines and strips the message before it matches the pattern, so the messages below are given in that form.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
from semantic_release.commit_parser.conventional import ConventionalCommitParser, ConventionalCommitParserOptions
from semantic_release.enums import LevelBump

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

VALID_MESSAGES = [
    "feat: x",
    "fix(cli): x",
    "feat!: x",
    "build!: x",
    "fix(cli)!: x (#7)",
    "ci: x (#12)",
    "docs: x (#12, #15)",
    "revert: x",
    "feat: x\n\nBody.\n\nBREAKING CHANGE: y",
    "build: x\n\nBREAKING-CHANGE: y",
    "feat: BREAKING CHANGE: drop Python 3.12",
    "fix: x\n\nCloses #3",
    "chore: x\n\nRefs #4, see #5.",
    "chore: x mentions BREAKING CHANGE: in the middle",
    "fix: x (#12) \n\nBody.",
    "fix: x \t\n\nBody.",
    "fix(cli): handle (optional) args",
    "docs: mention f(x) usage",
    "docs(readme): explain f(x) usage (#12)",
    "fix(cli)!: x (#7)\n\nBody.\n\nBREAKING CHANGE: y",
    "feat: x\n\nBody.\n\n  BREAKING CHANGE: indented footer",
]

INVALID_MESSAGES = [
    "perf: x",
    "bump: x",
    "docs!: x",
    "refactor!: x",
    "chore: x\n\nBody.\n\nBREAKING CHANGE: y",
    "chore: x\n\nBREAKING-CHANGE: y",
    "chore: x\nBREAKING CHANGE: y",
    "docs(readme): x\n\nBREAKING CHANGE: y",
    "chore: BREAKING CHANGE: drop Python 3.12",
    "chore(cli): BREAKING-CHANGE: x",
    "chore: x\n\n  BREAKING CHANGE: y",
    "docs: x\n\nText.\n\tBREAKING-CHANGE: y",
    "test: x\n\nRefs: #3\nBREAKING CHANGE: y",
    "feat: x\nBREAKING CHANGE: y",
    "feat: x\nbody",
    "fix: x\n \nBody after a blank line that holds a space.",
    "feat: x\n\nBody.\n \nBREAKING CHANGE: y",
    "feat: x\n\nBody.\nBREAKING CHANGE: y",
    "fix: x\n\nBody.\n  BREAKING-CHANGE: y",
    "chore(a): x (b)!: y",
    "docs(readme): explain foo(bar)!: syntax",
    "chore(a): x (b): BREAKING CHANGE: y",
    "fix: x (b): y",
    "Merge branch 'develop'",
    'Revert "feat: x"',
    "Pull request #5",
    "fixup! feat: x",
    "squash! fix: x",
    "amend! feat: x",
    "fix: x #30",
    "fix: #30 x",
    "fix: x (#30) more",
    "fix: x (# 30)",
    "fix: x (#30,#31)",
    "fix;broken",
    "feat : x",
    "feat:x",
    "feat:  x",
    "feat: ",
    "Feat: x",
]

BREAKING_MARKER = re.compile(r"BREAKING[ -]CHANGE:")


def _pyproject() -> dict[str, Any]:
    with PYPROJECT.open("rb") as file:
        return tomllib.load(file)


def _is_valid(message: str) -> bool:
    """Mirror commitizen's check: allowed prefixes first, then pattern.match on the stripped message."""
    commitizen = _pyproject()["tool"]["commitizen"]
    if any(message.startswith(prefix) for prefix in commitizen["allowed_prefixes"]):
        return True
    return re.compile(commitizen["customize"]["schema_pattern"]).match(message.strip()) is not None


def _rule_type(message: str) -> str:
    """The type as the rule sees it: the first word before '(', '!' or ':'."""
    return re.split(r"[(!:]", message, maxsplit=1)[0]


def _expected_major(message: str) -> bool:
    """Breaking: type feat, fix or build, and '!' before the colon, or the subject or a later paragraph starts with the marker."""
    header, _, description = message.partition("\n")[0].partition(": ")
    paragraphs = [paragraph.strip() for paragraph in message.split("\n\n")[1:]]
    has_marker = any(BREAKING_MARKER.match(text) for text in [description, *paragraphs])
    return _rule_type(message) in ("feat", "fix", "build") and (header.endswith("!") or has_marker)


@pytest.mark.parametrize("message", VALID_MESSAGES)
def test_valid_message_passes(message: str) -> None:
    assert _is_valid(message)


@pytest.mark.parametrize("message", INVALID_MESSAGES)
def test_invalid_message_fails(message: str) -> None:
    assert not _is_valid(message)


def test_no_prefix_escapes_the_pattern() -> None:
    assert _pyproject()["tool"]["commitizen"]["allowed_prefixes"] == []


@pytest.mark.parametrize("message", VALID_MESSAGES)
def test_semantic_release_reads_valid_message_as_intended(message: str) -> None:
    """semantic-release sees the same type as the rule and bumps the major version exactly when the rule marks a breaking change."""
    options = _pyproject()["tool"]["semantic_release"]["commit_parser_options"]
    parser = ConventionalCommitParser(options=ConventionalCommitParserOptions(**options))
    parsed = parser.parse_message(message)
    if _rule_type(message) == "revert":
        # semantic-release does not know revert, so it neither bumps nor reads a breaking marker.
        assert parsed is None
        return
    assert parsed is not None
    assert parsed.type == _rule_type(message)
    assert (parsed.bump == LevelBump.MAJOR) == _expected_major(message)


def test_types_match_semantic_release() -> None:
    """Every type semantic-release knows passes, plus revert; perf, which semantic-release would bump, fails."""
    allowed_tags = _pyproject()["tool"]["semantic_release"]["commit_parser_options"]["allowed_tags"]
    for commit_type in [*allowed_tags, "revert"]:
        assert _is_valid(f"{commit_type}: x"), commit_type
    assert "perf" not in allowed_tags
