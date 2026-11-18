"""Tests that the CLI survives console output in an encoding that cannot show every character.

The subprocess tests start the CLI through ``python -m trs_file_backup.main`` with stdout and stderr as pipes
and ``PYTHONIOENCODING=cp1252``, the setting of a Windows script that captures the output.
"""

import errno
import io
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockFixture

from trs_file_backup import __version__

UNENCODABLE_NAME = "日本.txt"


def _cp1252_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)
    # Rich wraps at 80 columns on a pipe; a wide console keeps each message on one line.
    env["COLUMNS"] = "300"
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "trs_file_backup.main", *args],
        capture_output=True,
        encoding="cp1252",
        env=_cp1252_env(),
        timeout=60,
        check=False,
    )


def _init_and_run(source: Path, destination: Path) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
    init = _run_cli("init", "--source", str(source), "--destination", str(destination), "--debounce", "0")
    run = _run_cli("run", "--source", str(source), "--destination", str(destination))
    return init, run


class TestCp1252Pipe:
    """The CLI exits 0 with readable output when stdout and stderr are cp1252 pipes."""

    def test_help(self) -> None:
        result = _run_cli("--help")

        assert result.returncode == 0, result.stderr
        assert "Usage" in result.stdout

    def test_version(self) -> None:
        result = _run_cli("--version")

        assert result.returncode == 0, result.stderr
        assert __version__ in result.stdout

    def test_init_and_run(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "report.txt").write_text("content")
        destination = tmp_path / "dest"

        init, run = _init_and_run(source, destination)

        assert init.returncode == 0, init.stdout + init.stderr
        assert "OK Initialized backup tracking" in init.stdout
        assert run.returncode == 0, run.stdout + run.stderr
        assert "OK report.txt -> report_" in run.stdout
        assert "Successfully backed up 1 files" in run.stdout

    def test_dry_run(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "report.txt").write_text("content")

        result = _run_cli("run", "--source", str(source), "--destination", str(tmp_path / "dest"), "--dry-run")

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Would backup: report.txt -> report_" in result.stdout

    def test_file_name_the_encoding_cannot_show(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        try:
            (source / UNENCODABLE_NAME).write_text("content")
        except (OSError, UnicodeEncodeError) as e:
            pytest.skip(f"the file system cannot create {UNENCODABLE_NAME!r}: {e}")
        destination = tmp_path / "dest"

        init, run = _init_and_run(source, destination)

        assert init.returncode == 0, init.stdout + init.stderr
        assert run.returncode == 0, run.stdout + run.stderr
        assert [path.name for path in destination.glob("日本_*.txt")], "the backup file is missing"
        assert "OK ??.txt -> ??_" in run.stdout

    def test_usage_error_with_a_path_the_encoding_cannot_show(self, tmp_path: Path) -> None:
        missing = tmp_path / "日本"

        result = _run_cli("run", "--source", str(missing), "--destination", str(tmp_path / "dest"))

        assert result.returncode == 2, result.stderr
        assert "does not exist" in result.stderr


@pytest.mark.parametrize(
    ("error", "expected_line"),
    [
        (PermissionError("Access denied"), "ERROR Permission denied: report.txt"),
        (BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable"), "WARNING File locked, skipping: report.txt"),
        (OSError(errno.ENOSPC, "No space left on device"), "ERROR Backup failed: report.txt (No space left on device)"),
    ],
    ids=["permission", "locked", "failed"],
)
def test_run_error_lines_are_ascii(mocker: MockFixture, tmp_path: Path, error: OSError, expected_line: str) -> None:
    from typer.testing import CliRunner

    from trs_file_backup.main import app

    source = tmp_path / "source"
    source.mkdir()
    (source / "report.txt").write_text("content")
    mocker.patch("time.sleep")
    mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=error)

    result = CliRunner().invoke(app, ["run", "--source", str(source), "--destination", str(tmp_path / "dest")])

    assert result.exit_code == 0, result.output
    assert expected_line in result.output
    assert result.output.isascii()


class TestReplaceUnencodable:
    """The helper makes a stream write ``?`` for a character its encoding cannot show."""

    def test_skips_a_missing_stream(self) -> None:
        from trs_file_backup.main import replace_unencodable

        replace_unencodable(None)

    def test_skips_a_stream_without_reconfigure(self) -> None:
        from trs_file_backup.main import replace_unencodable

        stream = io.StringIO()
        replace_unencodable(stream)
        stream.write("✓")

        assert stream.getvalue() == "✓"

    def test_replaces_a_character_cp1252_cannot_encode(self) -> None:
        from trs_file_backup.main import replace_unencodable

        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252")
        replace_unencodable(stream)
        stream.write("✓ done")
        stream.flush()

        assert raw.getvalue() == b"? done"

    def test_keeps_a_utf8_stream_working(self) -> None:
        from trs_file_backup.main import replace_unencodable

        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="utf-8")
        replace_unencodable(stream)
        stream.write("✓")
        stream.flush()

        assert raw.getvalue() == "✓".encode()


class TestCliEntryPoint:
    """The entry point protects stdout and stderr before the Typer app starts."""

    def test_protects_both_streams_before_the_app_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import trs_file_backup.main as main_module

        stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        monkeypatch.setattr(sys, "stdout", stdout)
        monkeypatch.setattr(sys, "stderr", stderr)
        seen_errors: list[str | None] = []
        app = Mock(side_effect=lambda: seen_errors.extend([stdout.errors, stderr.errors]))
        monkeypatch.setattr(main_module, "app", app)

        main_module.cli()

        app.assert_called_once_with()
        assert seen_errors == ["replace", "replace"]
