"""Tests for the validity rule of exclusion patterns (spec AC-4.9)."""

import pytest

from trs_file_backup.patterns import pattern_problem


@pytest.mark.parametrize("pattern", ["*.log", "temp_*", ".env", ".backup_state.json", "report.txt", "*", "..log"])
def test_file_name_patterns_are_usable(pattern: str) -> None:
    assert pattern_problem(pattern) is None


@pytest.mark.parametrize(
    ("pattern", "reason"),
    [
        ("", "empty pattern"),
        (" \t", "empty pattern"),
        ("logs/*.log", "patterns are matched against the file name only"),
        ("sub\\*.log", "patterns are matched against the file name only"),
        ("./", "patterns are matched against the file name only"),
        ("./.", "patterns are matched against the file name only"),
        (".", "'.' and '..' name folders, not files"),
        ("..", "'.' and '..' name folders, not files"),
        (" .. ", "'.' and '..' name folders, not files"),
    ],
)
def test_patterns_that_never_match_a_file_name_are_not_usable(pattern: str, reason: str) -> None:
    assert pattern_problem(pattern) == reason
