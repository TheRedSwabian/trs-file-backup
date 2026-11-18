"""Validity of exclusion patterns, shared by the CLI options, the config menu and the state file (spec AC-4.9)."""

NAME_ONLY = "patterns are matched against the file name only"


def pattern_problem(pattern: str) -> str | None:
    """Return why pattern can never match a bare file name (spec AC-4.6), or None if it is usable.

    A pattern is not usable if it is empty or consists of whitespace only, contains a path separator (/ or \\),
    or is "." or ".." (ignoring surrounding whitespace). Every other pattern is usable.
    """
    stripped = pattern.strip()
    if not stripped:
        return "empty pattern"
    if "/" in stripped or "\\" in stripped:
        return NAME_ONLY
    if stripped in {".", ".."}:
        return "'.' and '..' name folders, not files"
    return None


def is_usable_pattern(pattern: str) -> bool:
    """Return True if pattern_problem finds nothing wrong with pattern."""
    return pattern_problem(pattern) is None
