"""Shared pytest configuration and fixtures.

NO_COLOR is set as a best-effort hint to Rich/Typer, but does not reliably
prevent ANSI escape codes in Typer's help renderer on all platforms.
Tests that parse CLI output should use click.unstyle() for robustness.
See: https://no-color.org/
"""

import os

os.environ["NO_COLOR"] = "1"
