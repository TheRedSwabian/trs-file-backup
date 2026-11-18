"""Shared pytest configuration and fixtures.

NO_COLOR is set as a best-effort hint to Rich/Typer, but does not reliably
prevent ANSI escape codes in Typer's help renderer on all platforms.
Tests that parse CLI output should use click.unstyle() for robustness.
See: https://no-color.org/
"""

import os
from collections.abc import Callable

import pytest

os.environ["NO_COLOR"] = "1"


@pytest.fixture
def with_winerror() -> Callable[[OSError, int], OSError]:
    """Return a function that gives an OSError the Windows error code ``winerror``.

    The attribute is set on the instance, not through the constructor: on Windows the constructor derives ``errno`` from it,
    on Linux it ignores it. So a test gets the same exception on both systems.
    """

    def set_winerror(error: OSError, code: int) -> OSError:
        # typeshed declares winerror on Windows only, so mypy on Linux rejects a plain assignment
        setattr(error, "winerror", code)  # noqa: B010
        return error

    return set_winerror
