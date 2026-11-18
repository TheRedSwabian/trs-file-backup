"""Tests for CLI commands."""

import errno
import importlib
import importlib.metadata
import io
import json
import os
import re
import stat
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import click
import pytest
import typer.main
from pytest_mock import MockFixture
from typer.testing import CliRunner, Result

runner = CliRunner()

# One case per cause of a failed backup (spec AC-6.18): error, Windows error code or None, log level, message for report.txt
BACKUP_ERROR_CASES = [
    pytest.param(PermissionError(errno.EACCES, "lock violation"), 33, "WARNING", "File locked, skipping: report.txt", id="windows-lock"),
    pytest.param(PermissionError(errno.EACCES, "Permission denied"), None, "ERROR", "Permission denied: report.txt", id="permission"),
    pytest.param(OSError(errno.ENOSPC, "No space left on device"), None, "ERROR", "Backup failed: report.txt (No space left on device)", id="disk-full"),
]


def _help_output(result: Result) -> str:
    """Get CLI output stripped of ANSI escape codes for reliable assertions."""
    return click.unstyle(result.output).lower()


class TestInitCommand:
    """Test suite for init command."""

    def test_init_creates_state_file(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that init command creates state file."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0
        assert (dest / ".backup_state.json").exists()

    def test_init_creates_log_file(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that init command creates log file."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0
        assert (dest / "backup.log").exists()

    def test_init_with_exclusion_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test init command with exclusion patterns."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            [
                "init",
                "--source",
                str(source),
                "--destination",
                str(dest),
                "--exclude",
                "*.log",
                "--exclude",
                "*.tmp",
            ],
        )

        assert result.exit_code == 0
        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log", "*.tmp"]

    def test_init_with_custom_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test init command with custom debounce setting."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(source), "--destination", str(dest), "--debounce", "5"],
        )

        assert result.exit_code == 0

    def test_init_missing_source(self, mocker: MockFixture) -> None:
        """Test init command fails without source parameter."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["init", "--destination", "/dest"])

        # Typer allows None in test context, so we check that it should have rejected it
        # In real usage, typer would reject this, but in test context check for None
        assert result.exit_code != 0 or "none" in result.stdout.lower()

    def test_init_missing_destination(self, mocker: MockFixture) -> None:
        """Test init command fails without destination parameter."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["init", "--source", "/source"])

        assert result.exit_code != 0

    def test_init_invalid_source_directory(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test init command handles non-existent source directory."""
        from trs_file_backup.main import app

        nonexistent = tmp_path / "nonexistent"
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(nonexistent), "--destination", str(dest)],
        )

        assert result.exit_code != 0

    def test_init_shows_success_message(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test init command shows success message."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(source), "--destination", str(dest)],
        )

        assert "initialized" in result.stdout.lower() or "init" in result.stdout.lower()

    def test_init_saves_state(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that init command saves state to disk."""
        from trs_file_backup.main import app
        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["init", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0

        # Verify state was saved by loading it back
        state_file = dest / ".backup_state.json"
        state = StateManager.load(state_file)
        assert state is not None
        assert str(state.source_path) == str(source)
        assert str(state.destination_path) == str(dest)


class TestRunCommand:
    """Test suite for run command."""

    def test_run_backs_up_modified_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that run command backs up modified files."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Create test file
        test_file = source / "test.txt"
        test_file.write_text("test content")

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0

    def test_run_state_keeps_the_mtime_of_the_backed_up_version(self, mocker: MockFixture, tmp_path: Path) -> None:
        """A write during the copy must not mark the newer version as backed up (spec AC-3.5)."""
        from trs_file_backup.backup import BackupManager
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        notes = source / "notes.txt"
        notes.write_text("first version")
        os.utime(notes, (1000.0, 1000.0))

        def write_during_copy(path: Path, timestamp: object) -> Path:
            notes.write_text("second version")
            os.utime(notes, (2000.0, 2000.0))
            return dest / "notes_backup.txt"

        mocker.patch.object(BackupManager, "backup_file", side_effect=write_during_copy)

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0
        saved = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert saved["files"] == {"notes.txt": 1000.0}

    @pytest.mark.parametrize("dry_run", [False, True], ids=["run", "dry-run"])
    def test_run_prints_file_names_literally(self, mocker: MockFixture, tmp_path: Path, dry_run: bool) -> None:
        """A file name that looks like Rich markup must be printed as it is."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        (source / "[red]notes.txt").write_text("content")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(tmp_path / "dest"), *(["--dry-run"] if dry_run else [])])

        assert result.exit_code == 0
        expected = "Would backup: [red]notes.txt -> [red]notes_" if dry_run else "OK [red]notes.txt -> [red]notes_"
        assert expected in click.unstyle(result.output)

    def test_run_with_exclusion_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command with exclusion patterns."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Create test files
        (source / "test.txt").write_text("test")
        (source / "debug.log").write_text("log")

        result = runner.invoke(
            app,
            [
                "run",
                "--source",
                str(source),
                "--destination",
                str(dest),
                "--exclude",
                "*.log",
            ],
        )

        assert result.exit_code == 0

    def test_run_dry_run_mode(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command in dry-run mode."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        (source / "test.txt").write_text("test")

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest), "--dry-run"],
        )

        assert result.exit_code == 0
        assert "dry" in result.stdout.lower() or "would" in result.stdout.lower()

    def test_run_shows_progress(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command shows progress."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        (source / "test.txt").write_text("test")

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0

    def test_run_missing_source(self, mocker: MockFixture) -> None:
        """Test run command fails without source parameter."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["run", "--destination", "/dest"])

        assert result.exit_code != 0

    def test_run_missing_destination(self, mocker: MockFixture) -> None:
        """Test run command fails without destination parameter."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["run", "--source", "/source"])

        assert result.exit_code != 0

    def test_run_handles_permission_errors(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command handles permission errors gracefully."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        (source / "test.txt").write_text("test")

        # Mock backup_file to raise PermissionError
        _mock_backup = mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=PermissionError("Access denied"))

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        # Should not crash, should handle error gracefully
        assert "error" in result.stdout.lower() or "permission" in result.stdout.lower()

    @pytest.mark.parametrize(("error", "winerror", "level", "message"), BACKUP_ERROR_CASES)
    def test_run_reports_a_failed_backup_by_its_cause(
        self, mocker: MockFixture, tmp_path: Path, with_winerror: Callable[[OSError, int], OSError], error: OSError, winerror: int | None, level: str, message: str
    ) -> None:
        """Spec AC-6.18: the console and backup.log name the cause, and run continues with the next file."""
        from trs_file_backup.backup import BackupManager
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        (source / "report.txt").write_text("content")
        (source / "other.txt").write_text("content")
        if winerror is not None:
            error = with_winerror(error, winerror)
        real_backup_file = BackupManager.backup_file

        def fail_for_report(manager: BackupManager, file: Path, timestamp: Any) -> Path:
            if file.name == "report.txt":
                raise error
            return real_backup_file(manager, file, timestamp)

        mocker.patch.object(BackupManager, "backup_file", autospec=True, side_effect=fail_for_report)

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        output = click.unstyle(result.output)
        assert f"  {level} {message}" in output.splitlines()
        assert "Successfully backed up 1 files to" in output
        assert "Failed: 1 files" in output.splitlines()
        log = (dest / "backup.log").read_text(encoding="utf-8")
        assert f"[{level}] {message}" in log
        assert "Backed up: other.txt" in log
        if level == "ERROR":
            assert "locked" not in output.lower()
            assert "locked" not in log.lower()

    def test_run_no_modified_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command when no files are modified."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Create state file with current timestamp to simulate no changes
        (source / "test.txt").write_text("test")

        # Run once to create state
        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        # Run again - no files should be modified
        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0
        assert "no modified files" in result.stdout.lower()


class TestWatchCommand:
    """Test suite for watch command."""

    def test_watch_starts_monitoring(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that watch command starts file system monitoring."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Mock Observer
        mock_observer_class = mocker.patch("trs_file_backup.main.Observer")
        mock_observer_instance = Mock()
        mock_observer_class.return_value = mock_observer_instance

        # Mock time.sleep to raise KeyboardInterrupt after first call
        _mock_sleep = mocker.patch("time.sleep", side_effect=KeyboardInterrupt())

        result = runner.invoke(
            app,
            ["watch", "--source", str(source), "--destination", str(dest)],
        )

        # Should handle Ctrl+C gracefully
        assert result.exit_code == 0

    def test_watch_with_custom_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test watch command with custom debounce setting."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        mock_observer_class = mocker.patch("trs_file_backup.main.Observer")
        mock_observer_instance = Mock()
        mock_observer_class.return_value = mock_observer_instance

        # Mock time.sleep to raise KeyboardInterrupt
        _mock_sleep = mocker.patch("time.sleep", side_effect=KeyboardInterrupt())

        result = runner.invoke(
            app,
            ["watch", "--source", str(source), "--destination", str(dest), "--debounce", "5"],
        )

        assert result.exit_code == 0

    def test_watch_with_exclusion_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test watch command with exclusion patterns."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        mock_observer_class = mocker.patch("trs_file_backup.main.Observer")
        mock_observer_instance = Mock()
        mock_observer_class.return_value = mock_observer_instance

        # Mock time.sleep to raise KeyboardInterrupt
        _mock_sleep = mocker.patch("time.sleep", side_effect=KeyboardInterrupt())

        result = runner.invoke(
            app,
            [
                "watch",
                "--source",
                str(source),
                "--destination",
                str(dest),
                "--exclude",
                "*.log",
            ],
        )

        assert result.exit_code == 0

    def test_watch_handles_exception_gracefully(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test that watch command handles exceptions and cleans up logger."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Mock Observer to raise an exception
        mock_observer_class = mocker.patch("trs_file_backup.main.Observer")
        mock_observer_class.return_value.start.side_effect = RuntimeError("Test error")

        # Mock logger close to verify cleanup
        mock_logger = mocker.patch("trs_file_backup.main.BackupLogger")
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        result = runner.invoke(
            app,
            ["watch", "--source", str(source), "--destination", str(dest)],
        )

        # Should exit with error code
        assert result.exit_code == 1
        # Should have closed the logger
        mock_logger_instance.close.assert_called_once()


def _init(source: Path, dest: Path, *options: str) -> None:
    """Run init and fail the test if it does not succeed."""
    from trs_file_backup.main import app

    result = runner.invoke(app, ["init", "--source", str(source), "--destination", str(dest), *options])
    assert result.exit_code == 0, result.output


def _saved_settings(dest: Path) -> tuple[list[str], int]:
    """Read the exclusion patterns and debounce delay from the state file on disk."""
    data = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
    return data["excluded_patterns"], data["debounce_seconds"]


def _last_session_header(dest: Path) -> str:
    """Return the log text of the last session in backup.log."""
    return (dest / "backup.log").read_text(encoding="utf-8").split("Session Started")[-1]


def _backed_up(dest: Path, stem: str, suffix: str) -> bool:
    """Tell whether a timestamped backup of stem+suffix exists in dest."""
    return any(dest.glob(f"{stem}_*{suffix}"))


class TestSavedSettings:
    """run and watch use the exclusion patterns and debounce delay saved in the state file (spec AC-3.6 to AC-3.10)."""

    def test_run_uses_saved_patterns_and_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")
        (source / "a.txt").write_text("a")
        (source / "b.log").write_text("b")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".txt")
        assert not _backed_up(dest, "b", ".log")
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 5)
        header = _last_session_header(dest)
        assert "Exclusion patterns: .backup_state.json, *.log\n" in header
        assert "Debounce delay: 5 seconds" in header

    def test_run_copies_without_waiting_for_the_debounce_delay(self, mocker: MockFixture, tmp_path: Path) -> None:
        """The debounce delay only applies to watch; run copies at once (spec AC-2.7)."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        (source / "a.txt").write_text("a")
        (source / "b.txt").write_text("b")
        sleep = mocker.patch("time.sleep")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest), "--debounce", "5"])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".txt")
        assert _backed_up(dest, "b", ".txt")
        sleep.assert_not_called()
        assert _saved_settings(dest) == ([".backup_state.json"], 5)

    def test_run_given_exclude_replaces_saved_patterns_and_keeps_saved_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")
        (source / "b.log").write_text("b")
        (source / "c.tmp").write_text("c")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest), "--exclude", "*.tmp"])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "b", ".log")
        assert not _backed_up(dest, "c", ".tmp")
        assert _saved_settings(dest) == ([".backup_state.json", "*.tmp"], 5)

    def test_run_given_debounce_zero_replaces_saved_debounce_and_keeps_saved_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")
        (source / "a.txt").write_text("a")
        (source / "b.log").write_text("b")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest), "--debounce", "0"])

        assert result.exit_code == 0, result.output
        assert not _backed_up(dest, "b", ".log")
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 0)
        assert "Debounce delay: 0 seconds" in _last_session_header(dest)

    def test_run_without_state_file_uses_defaults(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        (source / "a.txt").write_text("a")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _saved_settings(dest) == ([".backup_state.json"], 2)
        assert "Debounce delay: 2 seconds" in _last_session_header(dest)

    def test_run_given_state_file_pattern_is_saved_once(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest)
        (source / "a.txt").write_text("a")

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest), "--exclude", ".backup_state.json", "--exclude", "*.log"],
        )

        assert result.exit_code == 0, result.output
        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log"]

    def test_run_saved_state_file_pattern_is_used_once(self, mocker: MockFixture, tmp_path: Path) -> None:
        """A saved list that holds the state file pattern twice (written by init --exclude .backup_state.json) is cleaned up."""
        from trs_file_backup.main import app
        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        StateManager(source, dest, 5, [".backup_state.json", "*.log", ".backup_state.json"], {}).save()
        (source / "a.txt").write_text("a")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 5)
        assert "Exclusion patterns: .backup_state.json, *.log\n" in _last_session_header(dest)

    @pytest.mark.parametrize("initialized", [True, False], ids=["saved-state", "no-state-file"])
    def test_run_given_options_are_saved_without_modified_files(self, mocker: MockFixture, tmp_path: Path, initialized: bool) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        if initialized:
            _init(source, dest, "--exclude", "*.log", "--debounce", "5")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest), "--exclude", "*.tmp", "--debounce", "3"])

        assert result.exit_code == 0, result.output
        assert "no modified files" in result.output.lower()
        assert _saved_settings(dest) == ([".backup_state.json", "*.tmp"], 3)

    @pytest.mark.parametrize("modified_file", [True, False], ids=["modified-file", "no-modified-file"])
    def test_run_dry_run_leaves_state_file_unchanged(self, mocker: MockFixture, tmp_path: Path, modified_file: bool) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")
        if modified_file:
            (source / "a.txt").write_text("a")
        state_before = (dest / ".backup_state.json").read_bytes()

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest), "--dry-run", "--exclude", "*.tmp", "--debounce", "3"],
        )

        assert result.exit_code == 0, result.output
        assert (dest / ".backup_state.json").read_bytes() == state_before

    def test_init_saves_state_file_pattern_once_and_removes_duplicates(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        _init(source, dest, "--exclude", ".backup_state.json", "--exclude", "*.log", "--exclude", "*.log")

        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log"]
        assert "Exclusion patterns: .backup_state.json, *.log\n" in _last_session_header(dest)

    def test_init_help_shows_debounce_default_once(self) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, ["init", "--help"], env={"COLUMNS": "400"})

        assert result.exit_code == 0
        debounce_row = next(line for line in _help_output(result).splitlines() if "--debounce" in line and "seconds to wait" in line)
        assert debounce_row.count("default") == 1
        assert "[default: 2]" in debounce_row

    @staticmethod
    def _invoke_watch(mocker: MockFixture, source: Path, dest: Path, *options: str) -> Mock:
        """Start watch with a mocked observer and stop it at once; return the spy on BackupEventHandler."""
        from trs_file_backup.main import BackupEventHandler, app

        mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt())
        handler_spy = mocker.patch("trs_file_backup.main.BackupEventHandler", wraps=BackupEventHandler)

        result = runner.invoke(app, ["watch", "--source", str(source), "--destination", str(dest), *options])

        assert result.exit_code == 0, result.output
        return handler_spy

    def test_watch_uses_saved_patterns_and_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")

        handler_spy = self._invoke_watch(mocker, source, dest)

        kwargs = handler_spy.call_args.kwargs
        assert kwargs["debounce_seconds"] == 5
        assert kwargs["backup_manager"].excluded_patterns == [".backup_state.json", "*.log"]
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 5)
        header = _last_session_header(dest)
        assert "Exclusion patterns: .backup_state.json, *.log\n" in header
        assert "Debounce delay: 5 seconds" in header

    def test_watch_given_exclude_replaces_saved_patterns_and_keeps_saved_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")

        handler_spy = self._invoke_watch(mocker, source, dest, "--exclude", "*.tmp", "--exclude", ".backup_state.json")

        kwargs = handler_spy.call_args.kwargs
        assert kwargs["debounce_seconds"] == 5
        assert kwargs["backup_manager"].excluded_patterns == [".backup_state.json", "*.tmp"]
        assert _saved_settings(dest) == ([".backup_state.json", "*.tmp"], 5)

    def test_watch_given_debounce_zero_replaces_saved_debounce_and_keeps_saved_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")

        handler_spy = self._invoke_watch(mocker, source, dest, "--debounce", "0")

        kwargs = handler_spy.call_args.kwargs
        assert kwargs["debounce_seconds"] == 0
        assert kwargs["backup_manager"].excluded_patterns == [".backup_state.json", "*.log"]
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 0)

    def test_watch_without_state_file_uses_defaults(self, mocker: MockFixture, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        handler_spy = self._invoke_watch(mocker, source, dest)

        assert handler_spy.call_args.kwargs["debounce_seconds"] == 2
        assert _saved_settings(dest) == ([".backup_state.json"], 2)

    @pytest.mark.parametrize("command", ["run", "watch"])
    def test_debounce_help_names_saved_value_and_fallback(self, command: str) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, [command, "--help"], env={"COLUMNS": "400"})

        assert result.exit_code == 0
        debounce_row = next(line for line in _help_output(result).splitlines() if "--debounce" in line and "seconds to wait" in line)
        assert "if not given, the saved value is used" in debounce_row
        assert "[default: (saved value, else 2)]" in debounce_row


def _state_bytes(dest: Path) -> bytes:
    return (dest / ".backup_state.json").read_bytes()


def _initialized(tmp_path: Path, *options: str) -> tuple[Path, Path]:
    """Create a source directory and run init into tmp_path/dest with the given options."""
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "dest"
    _init(source, dest, *options)
    return source, dest


class TestConfigShow:
    """config show prints the saved settings without prompting (spec FR-7)."""

    def test_show_prints_source_debounce_and_numbered_user_patterns(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*", "--debounce", "5")
        state_before = _state_bytes(dest)

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert str(source) in result.output
        assert "(read-only)" in result.output
        assert "Debounce:  5 s" in result.output
        assert "1) *.log" in result.output
        assert "2) temp_*" in result.output
        assert ".backup_state.json" not in result.output
        assert "Choose" not in result.output
        assert _state_bytes(dest) == state_before
        result.output.encode("ascii")

    def test_show_without_user_patterns_prints_none(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path)

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert "Excluded:  (none)" in result.output
        assert "1)" not in result.output

    def test_show_prints_brackets_in_patterns_literally(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path, "--exclude", "[abc]*.txt")

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert "1) [abc]*.txt" in result.output

    @pytest.mark.parametrize(
        "saved_patterns",
        [[".backup_state.json", "*.log", ".backup_state.json", "*.log"], ["*.log"]],
        ids=["state-pattern-twice", "state-pattern-missing"],
    )
    def test_show_handles_state_written_by_older_versions(self, tmp_path: Path, saved_patterns: list[str]) -> None:
        from trs_file_backup.main import app
        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        StateManager(source, dest, 2, saved_patterns, {}).save()

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert "1) *.log" in result.output
        assert "2)" not in result.output

    @pytest.mark.parametrize(
        "command",
        [["config", "show"], ["config"], ["config", "show", "debounce"], ["config", "set", "retention.days", "7"]],
        ids=["show", "menu", "show-key", "set"],
    )
    def test_without_state_file_says_run_init_first_and_creates_nothing(self, mocker: MockFixture, tmp_path: Path, command: list[str]) -> None:
        from trs_file_backup.main import app

        mocker.patch("trs_file_backup.main._stdin_is_terminal", return_value=True)
        dest = tmp_path / "dest"

        result = runner.invoke(app, [*command, "--destination", str(dest)], input="q\n")

        assert result.exit_code == 1
        assert "Run 'trs-file-backup init' first." in result.output
        assert "Choose" not in result.output
        assert not dest.exists()

    def test_unreadable_state_file_is_an_error(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / ".backup_state.json").write_text("{not json", encoding="utf-8")

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_config_without_terminal_behaves_like_show(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        state_before = _state_bytes(dest)

        result = runner.invoke(app, ["config", "--destination", str(dest)], input="4\ns\n")

        assert result.exit_code == 0, result.output
        assert "1) *.log" in result.output
        assert "Choose" not in result.output
        assert _state_bytes(dest) == state_before

    def test_destination_is_accepted_before_show(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path, "--exclude", "*.log")

        result = runner.invoke(app, ["config", "--destination", str(dest), "show"])

        assert result.exit_code == 0, result.output
        assert "1) *.log" in result.output

    @pytest.mark.parametrize(
        "command",
        [["config"], ["config", "show"], ["config", "show", "debounce"], ["config", "set", "debounce", "3"]],
        ids=["menu", "show", "show-key", "set"],
    )
    def test_missing_destination_is_a_usage_error(self, command: list[str]) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, command)

        assert result.exit_code == 2
        assert "--destination" in click.unstyle(result.output)

    def test_config_help_names_show_and_says_to_stop_watch_and_run(self) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, ["config", "--help"], env={"COLUMNS": "400"})

        assert result.exit_code == 0
        help_text = _help_output(result)
        assert re.search(r"show\s+print the saved settings, or only the value of one setting\.", help_text)
        assert re.search(r"set\s+change one setting and save it at once\.", help_text)
        assert "--destination" in help_text
        assert "stop a running 'watch' and wait for a running 'run' to finish first" in help_text

    def test_config_help_names_the_retention_rules_in_the_menu_and_cleanup(self) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, ["config", "--help"], env={"COLUMNS": "400"})

        assert result.exit_code == 0
        help_text = " ".join(_help_output(result).split())
        assert "add, remove or clear exclusion patterns and to change the retention rules." in help_text
        assert "saved changes take effect at the next start of 'run', 'watch' or 'cleanup'." in help_text

    def test_main_help_lists_config(self) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "config" in _help_output(result)


class TestConfigMenu:
    """config opens a menu to change the saved settings when stdin is a terminal (spec FR-7)."""

    @staticmethod
    def _menu(mocker: MockFixture, dest: Path, keys: str) -> Result:
        from trs_file_backup.main import app

        mocker.patch("trs_file_backup.main._stdin_is_terminal", return_value=True)
        return runner.invoke(app, ["config", "--destination", str(dest)], input=keys)

    def test_menu_shows_settings_and_actions(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _initialized(tmp_path, "--exclude", "*.log", "--debounce", "5")

        result = self._menu(mocker, dest, "q\n")

        assert result.exit_code == 0, result.output
        assert str(source) in result.output
        assert "1) *.log" in result.output
        assert (
            "  [1] change debounce   [2] add pattern   [3] remove pattern\n"
            "  [4] clear patterns    [5] change retention\n"
            "  [s] save and quit     [q] quit without saving\n"
            "Choose [1/2/3/4/5/s/q]: "
        ) in result.output
        assert "stop" in result.output.lower()
        result.output.encode("ascii")

    def test_menu_shows_an_emoji_code_in_a_pattern_as_text(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", ":thumbs_up:*.log")

        result = self._menu(mocker, dest, "q\n")

        assert result.exit_code == 0, result.output
        assert "1) :thumbs_up:*.log" in result.output

    def test_change_debounce_to_zero_and_save(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--debounce", "5")

        result = self._menu(mocker, dest, "1\n0\ns\n")

        assert result.exit_code == 0, result.output
        assert "Debounce:  0 s   (changed)" in result.output
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 0)
        result.output.encode("ascii")

    def test_save_writes_a_session_block_to_the_log(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*", "--debounce", "5")

        result = self._menu(mocker, dest, "1\n0\n3\n2\n2\n*.tmp\ns\n")

        assert result.exit_code == 0, result.output
        session = _last_session_header(dest)
        assert "Command: config\n" in session
        assert "Exclusion patterns: .backup_state.json, *.log, *.tmp\n" in session
        assert "Debounce delay: 0 seconds\n" in session
        assert "Settings changed: debounce delay 5 -> 0 seconds; added pattern *.tmp; removed pattern temp_*\n" in session
        assert "Session Ended" in session

    def test_save_without_changes_logs_that_nothing_changed(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log")

        result = self._menu(mocker, dest, "s\n")

        assert result.exit_code == 0, result.output
        assert "Settings saved without changes\n" in _last_session_header(dest)

    @pytest.mark.parametrize(("command", "keys"), [(["config"], "2\n*.tmp\nq\ny\n"), (["config", "show"], "")], ids=["quit", "show"])
    def test_quit_and_show_write_nothing_to_the_log(self, mocker: MockFixture, tmp_path: Path, command: list[str], keys: str) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        log_before = (dest / "backup.log").read_bytes()
        mocker.patch("trs_file_backup.main._stdin_is_terminal", return_value=True)

        result = runner.invoke(app, [*command, "--destination", str(dest)], input=keys)

        assert result.exit_code == 0, result.output
        assert (dest / "backup.log").read_bytes() == log_before

    def test_negative_debounce_is_rejected_and_asked_again(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--debounce", "5")

        result = self._menu(mocker, dest, "1\n-3\n7\ns\n")

        assert result.exit_code == 0, result.output
        assert "0 or more" in result.output
        assert _saved_settings(dest)[1] == 7

    def test_add_pattern_marks_it_new_and_saves_it(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log")

        result = self._menu(mocker, dest, "2\n*.tmp\ns\n")

        assert result.exit_code == 0, result.output
        assert "2) *.tmp   (new)" in result.output
        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log", "*.tmp"]

    @pytest.mark.parametrize(
        ("pattern", "message"),
        [
            ("*.log", "already"),
            (".backup_state.json", "always"),
            ("", "no pattern"),
            ("logs/*.log", "logs/*.log is not usable: patterns are matched against the file name only"),
            ("..", ".. is not usable"),
            ("./", "./ is not usable"),
        ],
    )
    def test_add_duplicate_state_or_empty_pattern_leaves_list_unchanged(self, mocker: MockFixture, tmp_path: Path, pattern: str, message: str) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log")

        result = self._menu(mocker, dest, f"2\n{pattern}\ns\n")

        assert result.exit_code == 0, result.output
        assert message in result.output.lower()
        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log"]

    def test_remove_pattern_by_number(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*")

        result = self._menu(mocker, dest, "3\n1\ns\n")

        assert result.exit_code == 0, result.output
        assert "Removed:   *.log" in result.output
        assert _saved_settings(dest)[0] == [".backup_state.json", "temp_*"]

    @pytest.mark.parametrize("number", ["0", "3", "-1"])
    def test_remove_with_invalid_number_leaves_list_unchanged(self, mocker: MockFixture, tmp_path: Path, number: str) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*")

        result = self._menu(mocker, dest, f"3\n{number}\ns\n")

        assert result.exit_code == 0, result.output
        assert f"no pattern with number {number}" in result.output.lower()
        assert _saved_settings(dest)[0] == [".backup_state.json", "*.log", "temp_*"]

    def test_remove_without_patterns_says_so(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path)

        result = self._menu(mocker, dest, "3\nq\n")

        assert result.exit_code == 0, result.output
        assert "no patterns to remove" in result.output.lower()

    def test_clear_keeps_state_file_pattern(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*")

        result = self._menu(mocker, dest, "4\ns\n")

        assert result.exit_code == 0, result.output
        assert "Excluded:  (none)" in result.output
        assert _saved_settings(dest)[0] == [".backup_state.json"]

    def test_quit_with_unsaved_changes_asks_and_writes_nothing(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.state import StateManager

        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        state_before = _state_bytes(dest)
        save_spy = mocker.spy(StateManager, "save")

        result = self._menu(mocker, dest, "2\n*.tmp\nq\nn\nq\ny\n")

        assert result.exit_code == 0, result.output
        assert result.output.count("Discard the unsaved changes?") == 2
        assert save_spy.call_count == 0
        assert _state_bytes(dest) == state_before

    def test_quit_without_changes_does_not_ask(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        state_before = _state_bytes(dest)

        result = self._menu(mocker, dest, "q\n")

        assert result.exit_code == 0, result.output
        assert "Discard" not in result.output
        assert _state_bytes(dest) == state_before

    @pytest.mark.parametrize(("keys", "exit_code"), [("2\n*.tmp\n", 1), ("", 0)], ids=["unsaved-changes", "no-changes"])
    def test_end_of_input_saves_nothing(self, mocker: MockFixture, tmp_path: Path, keys: str, exit_code: int) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        state_before = _state_bytes(dest)

        result = self._menu(mocker, dest, keys)

        assert result.exit_code == exit_code, result.output
        assert "nothing saved" in result.output.lower()
        assert _state_bytes(dest) == state_before

    def test_save_goes_through_state_manager_and_keeps_source_and_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        StateManager(source, dest, 5, [".backup_state.json", "*.log"], {"a.txt": 1.5}).save()
        save_spy = mocker.spy(StateManager, "save")

        result = self._menu(mocker, dest, "1\n3\ns\n")

        assert result.exit_code == 0, result.output
        assert save_spy.call_count == 1
        data = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert data["source_path"] == str(source)
        assert data["files"] == {"a.txt": 1.5}
        assert data["debounce_seconds"] == 3
        assert not (dest / ".backup_state.json.tmp").exists()

    def test_failed_save_is_an_error_and_keeps_the_state_file(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.state import StateManager

        _, dest = _initialized(tmp_path, "--exclude", "*.log")
        state_before = _state_bytes(dest)
        mocker.patch.object(StateManager, "save", side_effect=PermissionError("locked"))

        result = self._menu(mocker, dest, "4\ns\n")

        assert result.exit_code == 1
        assert "Error: cannot save" in result.output
        assert _state_bytes(dest) == state_before

    def test_unwritable_log_after_save_says_the_settings_were_saved(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--debounce", "5")
        mocker.patch("trs_file_backup.main.BackupLogger", side_effect=PermissionError("backup.log is locked"))

        result = self._menu(mocker, dest, "1\n0\ns\n")

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "settings were saved" in result.output.lower()
        assert "backup.log" in result.output
        assert "Traceback" not in result.output
        assert _saved_settings(dest)[1] == 0

    def test_save_keeps_tracked_files_written_while_the_menu_was_open(self, mocker: MockFixture, tmp_path: Path) -> None:
        from rich.prompt import IntPrompt

        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        StateManager(source, dest, 5, [".backup_state.json"], {}).save()

        def backup_happens_meanwhile(*args: object, **kwargs: object) -> int:
            StateManager(source, dest, 5, [".backup_state.json"], {"a.txt": 2.5}).save()
            return 3

        mocker.patch.object(IntPrompt, "ask", side_effect=backup_happens_meanwhile)

        result = self._menu(mocker, dest, "1\ns\n")

        assert result.exit_code == 0, result.output
        data = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert data["files"] == {"a.txt": 2.5}
        assert data["debounce_seconds"] == 3

    def test_run_uses_settings_saved_by_config(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path, "--exclude", "*.log", "--debounce", "5")
        self._menu(mocker, dest, "1\n0\n4\n2\n*.tmp\ns\n")
        (source / "a.log").write_text("a")
        (source / "b.tmp").write_text("b")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".log")
        assert not _backed_up(dest, "b", ".tmp")
        assert "Debounce delay: 0 seconds" in _last_session_header(dest)


def _store_retention(dest: Path, retention: object) -> None:
    """Write retention into the state file in dest as a hand edit would, keeping all other fields."""
    path = dest / ".backup_state.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["retention"] = retention
    path.write_text(json.dumps(data), encoding="utf-8")


def _remove_retention(dest: Path) -> None:
    """Remove retention from the state file in dest, as versions before the retention rules wrote it."""
    path = dest / ".backup_state.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["retention"]
    path.write_text(json.dumps(data), encoding="utf-8")


def _saved_retention(dest: Path) -> object:
    return json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))["retention"]


ALL_RULES_OFF = {"hours": 0, "days": 0, "weeks": 0, "months": 0}
EXAMPLE_RULES = {"hours": 24, "days": 7, "weeks": 4, "months": -1}


class TestRetentionRulesInSettings:
    """The retention rules live in the state file (spec AC-8.15, AC-8.16), in the session header (AC-6.13) and in config show (AC-7.1, AC-7.16)."""

    def test_init_saves_all_rules_as_zero_and_logs_them(self, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path)

        assert _saved_retention(dest) == ALL_RULES_OFF
        assert "Retention rules: hours 0, days 0, weeks 0, months 0\n" in _last_session_header(dest)

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [(EXAMPLE_RULES, EXAMPLE_RULES), ({"days": 7}, {**ALL_RULES_OFF, "days": 7}), (None, ALL_RULES_OFF)],
        ids=["all-rules", "one-rule", "older-state-file"],
    )
    def test_run_writes_the_rules_back_as_it_read_them_and_logs_them(self, tmp_path: Path, stored: dict[str, int] | None, expected: dict[str, int]) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path)
        if stored is None:
            _remove_retention(dest)
        else:
            _store_retention(dest, stored)
        (source / "a.txt").write_text("a")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _saved_retention(dest) == expected
        header = _last_session_header(dest)
        rules_line = "Retention rules: " + ", ".join(f"{name} {value}" for name, value in expected.items())
        # The rules are the last line of the header, before the first line of the work (spec AC-6.13)
        assert f"{rules_line}\n" in header
        assert header.index("Debounce delay:") < header.index(rules_line) < header.index("Found 1 modified files")

    def test_watch_writes_the_rules_back_as_it_read_them_and_logs_them(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _initialized(tmp_path)
        _store_retention(dest, {"weeks": 4, "months": -1})

        TestSavedSettings._invoke_watch(mocker, source, dest)

        assert _saved_retention(dest) == {"hours": 0, "days": 0, "weeks": 4, "months": -1}
        assert "Retention rules: hours 0, days 0, weeks 4, months -1\n" in _last_session_header(dest)

    @pytest.mark.parametrize(
        ("retention", "key"),
        [
            pytest.param({"hours": -2}, "retention.hours = -2", id="below-minus-one"),
            pytest.param({"days": "7"}, 'retention.days = "7"', id="string"),
            pytest.param({"hourz": 7}, "retention.hourz = 7", id="unknown-key"),
            pytest.param(5, "retention = 5", id="not-an-object"),
        ],
    )
    @pytest.mark.parametrize("command", ["run", "watch", "config show", "config show key", "config set", "config without terminal", "config menu"])
    def test_invalid_stored_rule_stops_the_command_before_anything_is_written(self, mocker: MockFixture, tmp_path: Path, command: str, retention: object, key: str) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path)
        (source / "a.txt").write_text("a")
        _store_retention(dest, retention)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()
        observer = mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt())
        mocker.patch("trs_file_backup.main._stdin_is_terminal", return_value=command == "config menu")
        arguments = {
            "run": ["run", "--source", str(source), "--destination", str(dest)],
            "watch": ["watch", "--source", str(source), "--destination", str(dest)],
            "config show": ["config", "show", "--destination", str(dest)],
            "config show key": ["config", "show", "debounce", "--destination", str(dest)],
            "config set": ["config", "set", "debounce", "3", "--destination", str(dest)],
            "config without terminal": ["config", "--destination", str(dest)],
            "config menu": ["config", "--destination", str(dest)],
        }[command]

        result = runner.invoke(app, arguments, input="s\n")

        assert result.exit_code == 1
        output = click.unstyle(result.output)
        # Rich wraps the error line at the console width and drops the space where it breaks, so compare without whitespace
        compact = re.sub(r"\s", "", output)
        for expected in ("Error:", str(dest / ".backup_state.json"), key, "0 or more, or -1"):
            assert re.sub(r"\s", "", expected) in compact
        # The error is the message of AC-8.16, not the generic "cannot read" error with the exception's name
        assert "cannot read" not in output
        assert "InvalidRetentionRuleError" not in compact
        assert "Choose" not in output
        assert "Traceback" not in output
        observer.assert_not_called()
        assert not _backed_up(dest, "a", ".txt")
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    def test_show_prints_the_rules_as_a_block(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path, "--exclude", "*.log", "--exclude", "temp_*")
        _store_retention(dest, EXAMPLE_RULES)

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert result.output.endswith(
            "  Excluded:  1) *.log\n"
            "             2) temp_*\n"
            "  Retention: keep all backups of the last 24 hours\n"
            "             keep the last backup per day for 7 days\n"
            "             keep the last backup per week for 4 weeks\n"
            "             keep the last backup per month forever\n"
        )
        result.output.encode("ascii")

    def test_show_prints_off_when_all_rules_are_zero(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path)

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert result.output.endswith("  Excluded:  (none)\n  Retention: off (no backup is ever deleted)\n")

    def test_show_prints_off_for_a_state_file_without_rules(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest = _initialized(tmp_path)
        _remove_retention(dest)

        result = runner.invoke(app, ["config", "show", "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert result.output.endswith("  Retention: off (no backup is ever deleted)\n")

    @pytest.mark.parametrize(
        ("rules", "lines"),
        [
            pytest.param(
                {"hours": 1, "days": 1, "weeks": 1, "months": 1},
                [
                    "  Retention: keep all backups of the last 1 hour",
                    "             keep the last backup per day for 1 day",
                    "             keep the last backup per week for 1 week",
                    "             keep the last backup per month for 1 month",
                ],
                id="singular",
            ),
            pytest.param(
                {"hours": -1, "days": -1, "weeks": -1, "months": -1},
                [
                    "  Retention: keep all backups",
                    "             keep the last backup per day forever",
                    "             keep the last backup per week forever",
                    "             keep the last backup per month forever",
                ],
                id="no-limit",
            ),
            pytest.param({"weeks": 2}, ["  Retention: keep the last backup per week for 2 weeks"], id="only-non-zero-rules"),
            pytest.param(
                {"hours": 48, "months": 12},
                ["  Retention: keep all backups of the last 48 hours", "             keep the last backup per month for 12 months"],
                id="gap",
            ),
            pytest.param({}, ["  Retention: off (no backup is ever deleted)"], id="off"),
        ],
    )
    def test_retention_lines_follow_the_rule_texts(self, rules: dict[str, int], lines: list[str]) -> None:
        from trs_file_backup.main import retention_lines
        from trs_file_backup.retention import RetentionRules

        assert retention_lines(RetentionRules(**rules)) == lines

    def test_menu_shows_the_rules_and_keeps_them_when_it_saves(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path, "--debounce", "5")
        _store_retention(dest, EXAMPLE_RULES)

        result = TestConfigMenu._menu(mocker, dest, "1\n0\ns\n")

        assert result.exit_code == 0, result.output
        assert "  Retention: keep all backups of the last 24 hours\n" in result.output
        assert _saved_retention(dest) == EXAMPLE_RULES
        assert "Retention rules: hours 24, days 7, weeks 4, months -1\n" in _last_session_header(dest)

    @pytest.mark.parametrize("command", ["init", "run", "watch", "config"])
    def test_no_command_takes_a_rule_as_an_option(self, command: str) -> None:
        """The rules are changed with config only (spec AC-8.15)."""
        from trs_file_backup.main import app

        options = [option for param in typer.main.get_group(app).commands[command].params for option in param.opts]

        assert not [option for option in options if any(word in option for word in ("retention", "hours", "days", "weeks", "months", "keep"))]


class TestConfigMenuRetention:
    """The config menu changes the retention rules (spec AC-7.9 to AC-7.13, AC-7.16, AC-7.17)."""

    @staticmethod
    def _menu_with_rules(mocker: MockFixture, tmp_path: Path, keys: str, rules: dict[str, int] = EXAMPLE_RULES, *options: str) -> tuple[Result, Path]:
        _, dest = _initialized(tmp_path, *options)
        _store_retention(dest, rules)
        return TestConfigMenu._menu(mocker, dest, keys), dest

    def test_change_a_rule_asks_with_the_spec_texts_and_marks_it(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n2\n9\nq\ny\n")

        assert result.exit_code == 0, result.output
        assert (
            "Choose [1/2/3/4/5/s/q]: "
            "  [1] hours   [2] days   [3] weeks   [4] months\n"
            "Choose [1/2/3/4]: "
            "Keep the last backup per day for how many days (0 = off, -1 = no limit) (7): "
        ) in result.output
        assert (
            "  Retention: keep all backups of the last 24 hours\n"
            "             keep the last backup per day for 9 days   (changed)\n"
            "             keep the last backup per week for 4 weeks\n"
            "             keep the last backup per month forever\n"
            "Unsaved changes: choose s to save them.\n"
        ) in result.output
        result.output.encode("ascii")

    @pytest.mark.parametrize(
        ("choice", "prompt"),
        [
            ("1", "Keep every backup younger than how many hours (0 = off, -1 = no limit) (24): "),
            ("2", "Keep the last backup per day for how many days (0 = off, -1 = no limit) (7): "),
            ("3", "Keep the last backup per week for how many weeks (0 = off, -1 = no limit) (4): "),
            ("4", "Keep the last backup per month for how many months (0 = off, -1 = no limit) (-1): "),
        ],
        ids=["hours", "days", "weeks", "months"],
    )
    def test_each_rule_has_its_prompt_on_one_line(self, mocker: MockFixture, tmp_path: Path, choice: str, prompt: str) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, f"5\n{choice}\n\nq\n")

        assert result.exit_code == 0, result.output
        assert f"Choose [1/2/3/4]: {prompt}" in result.output

    def test_enter_keeps_the_value_and_marks_nothing(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, dest = self._menu_with_rules(mocker, tmp_path, "5\n2\n\nq\n")

        assert result.exit_code == 0, result.output
        assert "for how many days (0 = off, -1 = no limit) (7): " in result.output
        assert "(changed)" not in result.output
        assert "Discard" not in result.output
        assert _saved_retention(dest) == EXAMPLE_RULES

    def test_the_default_is_the_value_of_the_menu(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n2\n9\n5\n2\n\nq\ny\n")

        assert result.exit_code == 0, result.output
        assert "for how many days (0 = off, -1 = no limit) (9): " in result.output

    def test_a_rule_set_back_to_its_saved_value_loses_the_mark(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n2\n9\n5\n2\n7\nq\n")

        assert result.exit_code == 0, result.output
        last_list = result.output.rsplit("Saved settings\n", 1)[1]
        assert "keep the last backup per day for 7 days\n" in last_list
        assert "(changed)" not in last_list
        assert "Discard" not in result.output

    def test_invalid_choices_and_values_are_asked_again(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, dest = self._menu_with_rules(mocker, tmp_path, "5\n7\nx\n2\nabc\n1.5\n-2\n-1\ns\n")

        assert result.exit_code == 0, result.output
        assert result.output.count("Choose [1/2/3/4]: ") == 3
        assert result.output.count("for how many days (0 = off, -1 = no limit) (7): ") == 4
        assert "The value must be 0 or more, or -1 (no limit).\n" in result.output
        assert _saved_retention(dest) == {**EXAMPLE_RULES, "days": -1}
        result.output.encode("ascii")

    def test_a_rule_set_to_zero_is_listed_as_off_and_marked(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n2\n0\nq\ny\n")

        assert result.exit_code == 0, result.output
        assert (
            "  Retention: keep all backups of the last 24 hours\n"
            "             days rule: off   (changed)\n"
            "             keep the last backup per week for 4 weeks\n"
            "             keep the last backup per month forever\n"
        ) in result.output

    def test_the_first_rule_set_to_zero_carries_the_label(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n1\n0\nq\ny\n", {"hours": 24, "months": 3})

        assert result.exit_code == 0, result.output
        assert "  Retention: hours rule: off   (changed)\n             keep the last backup per month for 3 months\nUnsaved" in result.output

    def test_all_rules_set_to_zero_mark_the_off_line(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, dest = self._menu_with_rules(mocker, tmp_path, "5\n2\n0\ns\n", {"days": 7})

        assert result.exit_code == 0, result.output
        assert "  Retention: off (no backup is ever deleted)   (changed)\n" in result.output
        assert _saved_retention(dest) == ALL_RULES_OFF

    def test_a_new_rule_from_off_is_marked(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, _ = self._menu_with_rules(mocker, tmp_path, "5\n3\n2\nq\ny\n", ALL_RULES_OFF)

        assert result.exit_code == 0, result.output
        assert "  Retention: keep the last backup per week for 2 weeks   (changed)\nUnsaved" in result.output
        assert "rule: off" not in result.output

    def test_save_writes_the_rules_and_logs_them(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, dest = self._menu_with_rules(mocker, tmp_path, "1\n0\n5\n2\n9\n5\n4\n0\ns\n", EXAMPLE_RULES, "--debounce", "5")

        assert result.exit_code == 0, result.output
        assert _saved_retention(dest) == {"hours": 24, "days": 9, "weeks": 4, "months": 0}
        session = _last_session_header(dest)
        assert "Command: config\n" in session
        assert "Retention rules: hours 24, days 9, weeks 4, months 0\n" in session
        assert "Settings changed: debounce delay 5 -> 0 seconds; retention.days 7 -> 9; retention.months -1 -> 0\n" in session
        assert "Saved to " in result.output
        assert ". The changes take effect at the next start of 'run', 'watch' or 'cleanup'.\n" in result.output

    def test_save_keeps_tracked_files_written_while_the_menu_was_open(self, mocker: MockFixture, tmp_path: Path) -> None:
        from rich.prompt import IntPrompt

        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        StateManager(source, dest, 5, [".backup_state.json"], {}).save()

        def backup_happens_meanwhile(*args: object, **kwargs: object) -> int:
            StateManager(source, dest, 5, [".backup_state.json"], {"a.txt": 2.5}).save()
            return 9

        mocker.patch.object(IntPrompt, "ask", side_effect=backup_happens_meanwhile)

        result = TestConfigMenu._menu(mocker, dest, "5\n2\ns\n")

        assert result.exit_code == 0, result.output
        data = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert data["files"] == {"a.txt": 2.5}
        assert data["retention"] == {**ALL_RULES_OFF, "days": 9}
        assert data["source_path"] == str(source)

    def test_quit_after_a_rule_change_asks_and_writes_nothing(self, mocker: MockFixture, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path)
        _store_retention(dest, EXAMPLE_RULES)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()

        result = TestConfigMenu._menu(mocker, dest, "5\n2\n9\nq\nn\nq\ny\n")

        assert result.exit_code == 0, result.output
        assert "keep the last backup per day for 9 days   (changed)\n" in result.output
        assert result.output.count("Discard the unsaved changes?") == 2
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    def test_end_of_input_after_a_rule_change_exits_with_one(self, mocker: MockFixture, tmp_path: Path) -> None:
        result, dest = self._menu_with_rules(mocker, tmp_path, "5\n2\n9\n")

        assert result.exit_code == 1, result.output
        assert "keep the last backup per day for 9 days   (changed)\n" in result.output
        assert "nothing saved" in result.output.lower()
        assert _saved_retention(dest) == EXAMPLE_RULES

    def test_run_uses_the_rules_saved_by_config(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path)
        TestConfigMenu._menu(mocker, dest, "5\n2\n12\ns\n")
        (source / "a.txt").write_text("a")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert "Retention rules: hours 0, days 12, weeks 0, months 0\n" in _last_session_header(dest)


# The rules before a config set: months is 3, so that setting it to -1 is a change
RULES_BEFORE_SET = {**EXAMPLE_RULES, "months": 3}


class TestConfigShowAndSetKey:
    """config show KEY prints one value and config set KEY VALUE saves one value at once (spec AC-7.13, AC-7.15, AC-7.18, AC-7.19)."""

    KEYS_MESSAGE = "Valid keys: debounce, retention.hours, retention.days, retention.weeks, retention.months."

    @staticmethod
    def _with_rules(tmp_path: Path) -> Path:
        _, dest = _initialized(tmp_path, "--debounce", "5")
        _store_retention(dest, RULES_BEFORE_SET)
        return dest

    @staticmethod
    def _config(dest: Path, *arguments: str) -> Result:
        from trs_file_backup.main import app

        return runner.invoke(app, ["config", *arguments, "--destination", str(dest)])

    @pytest.mark.parametrize(
        ("key", "value"),
        [("debounce", "5"), ("retention.hours", "24"), ("retention.days", "7"), ("retention.weeks", "4"), ("retention.months", "3")],
    )
    def test_show_key_prints_only_the_value(self, tmp_path: Path, key: str, value: str) -> None:
        dest = self._with_rules(tmp_path)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()

        result = self._config(dest, "show", key)

        assert result.exit_code == 0, result.output
        assert result.output == f"{value}\n"
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    def test_show_key_prints_minus_one_for_no_limit(self, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path)
        _store_retention(dest, EXAMPLE_RULES)

        result = self._config(dest, "show", "retention.months")

        assert result.exit_code == 0, result.output
        assert result.output == "-1\n"

    def test_show_key_after_destination(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        dest = self._with_rules(tmp_path)

        result = runner.invoke(app, ["config", "--destination", str(dest), "show", "retention.days"])

        assert result.exit_code == 0, result.output
        assert result.output == "7\n"

    @pytest.mark.parametrize("key", ["retention", "Debounce", "retention.hourz", "hours", "exclude", "retention.däys"])
    def test_show_unknown_key_names_the_valid_keys(self, tmp_path: Path, key: str) -> None:
        dest = self._with_rules(tmp_path)

        result = self._config(dest, "show", key)

        assert result.exit_code == 1
        assert result.output.startswith("Error: unknown key ")
        assert self.KEYS_MESSAGE in " ".join(result.output.split())
        result.output.encode("ascii")

    @pytest.mark.parametrize(
        ("key", "value", "old", "change"),
        [
            ("debounce", "0", 5, "debounce delay 5 -> 0 seconds"),
            ("debounce", "12", 5, "debounce delay 5 -> 12 seconds"),
            ("retention.hours", "48", 24, "retention.hours 24 -> 48"),
            ("retention.days", "12", 7, "retention.days 7 -> 12"),
            ("retention.weeks", "0", 4, "retention.weeks 4 -> 0"),
            ("retention.months", "-1", 3, "retention.months 3 -> -1"),
            ("retention.months", "6", 3, "retention.months 3 -> 6"),
        ],
    )
    def test_set_saves_logs_and_prints_the_note(self, tmp_path: Path, key: str, value: str, old: int, change: str) -> None:
        from trs_file_backup.main import STOP_WATCH_NOTE

        dest = self._with_rules(tmp_path)

        result = self._config(dest, "set", key, value)

        assert result.exit_code == 0, result.output
        if key == "debounce":
            assert _saved_settings(dest)[1] == int(value)
            assert _saved_retention(dest) == RULES_BEFORE_SET
        else:
            assert _saved_settings(dest)[1] == 5
            assert _saved_retention(dest) == {**RULES_BEFORE_SET, key.removeprefix("retention."): int(value)}
        session = _last_session_header(dest)
        assert "Command: config\n" in session
        assert f"Settings changed: {change}\n" in session
        assert "Session Ended" in session
        lines = result.output.splitlines()
        assert lines[0] == STOP_WATCH_NOTE
        expected = f"Saved {key} = {value} to {dest / '.backup_state.json'}. The change takes effect at the next start of 'run', 'watch' or 'cleanup'."
        # Rich may wrap the line at the console width, so compare without whitespace
        assert re.sub(r"\s", "", "".join(lines[1:])) == re.sub(r"\s", "", expected)
        result.output.encode("ascii")

    def test_set_after_destination_and_with_leading_zeros(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        dest = self._with_rules(tmp_path)

        result = runner.invoke(app, ["config", "--destination", str(dest), "set", "retention.days", "012"])

        assert result.exit_code == 0, result.output
        assert _saved_retention(dest) == {**RULES_BEFORE_SET, "days": 12}
        assert "Saved retention.days = 12 to " in result.output

    def test_set_keeps_patterns_source_and_tracked_files(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path, "--exclude", "*.log")
        (source / "a.txt").write_text("a")
        runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])
        files_before = json.loads(_state_bytes(dest))["files"]

        result = self._config(dest, "set", "retention.days", "3")

        assert result.exit_code == 0, result.output
        data = json.loads(_state_bytes(dest))
        assert files_before
        assert data["files"] == files_before
        assert data["excluded_patterns"] == [".backup_state.json", "*.log"]
        assert data["source_path"] == str(source)

    @pytest.mark.parametrize(("key", "value"), [("debounce", "5"), ("retention.hours", "24"), ("retention.months", "3"), ("retention.days", "007")])
    def test_set_the_saved_value_writes_nothing(self, tmp_path: Path, key: str, value: str) -> None:
        dest = self._with_rules(tmp_path)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()

        result = self._config(dest, "set", key, value)

        assert result.exit_code == 0, result.output
        assert result.output == f"{key} is already {int(value)}; nothing was written.\n"
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    def test_set_minus_one_when_already_saved_writes_nothing(self, tmp_path: Path) -> None:
        _, dest = _initialized(tmp_path)
        _store_retention(dest, EXAMPLE_RULES)
        state_before = _state_bytes(dest)

        result = self._config(dest, "set", "retention.months", "-1")

        assert result.exit_code == 0, result.output
        assert result.output == "retention.months is already -1; nothing was written.\n"
        assert _state_bytes(dest) == state_before

    @pytest.mark.parametrize("key", ["retention", "Debounce", "retention.hourz", "exclude", "retention.däys"])
    def test_set_unknown_key_names_the_valid_keys_and_writes_nothing(self, tmp_path: Path, key: str) -> None:
        dest = self._with_rules(tmp_path)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()

        result = self._config(dest, "set", key, "3")

        assert result.exit_code == 1
        assert result.output.startswith("Error: unknown key ")
        assert self.KEYS_MESSAGE in " ".join(result.output.split())
        assert "Stop a running" not in result.output
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before
        result.output.encode("ascii")

    @pytest.mark.parametrize(
        ("key", "value", "allowed"),
        [
            ("debounce", "-1", "Valid values: a whole number of 0 or more (seconds)."),
            ("debounce", "abc", "Valid values: a whole number of 0 or more (seconds)."),
            ("debounce", "1.5", "Valid values: a whole number of 0 or more (seconds)."),
            ("retention.days", "-2", "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.hours", "+5", "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.weeks", "1_000", "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.weeks", " 5", "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.months", "", "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.months", chr(0xFF11) + chr(0xFF12), "Valid values: 0 or more, or -1 (no limit)."),
            ("retention.days", "9" * 5000, "Valid values: 0 or more, or -1 (no limit)."),
        ],
        ids=["debounce-negative", "debounce-text", "debounce-decimal", "rule-below-minus-one", "plus-sign", "underscore", "space", "empty", "fullwidth-digits", "too-long"],
    )
    def test_set_invalid_value_names_the_valid_values_and_writes_nothing(self, tmp_path: Path, key: str, value: str, allowed: str) -> None:
        dest = self._with_rules(tmp_path)
        state_before = _state_bytes(dest)
        log_before = (dest / "backup.log").read_bytes()

        result = self._config(dest, "set", key, value)

        assert result.exit_code == 1, result.output
        assert result.output.startswith("Error: invalid value ")
        assert f"for {key}. {allowed}" in " ".join(result.output.split())
        assert "Stop a running" not in result.output
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before
        result.output.encode("ascii")

    def test_set_when_the_state_file_cannot_be_written(self, mocker: MockFixture, tmp_path: Path) -> None:
        dest = self._with_rules(tmp_path)
        state_before = _state_bytes(dest)
        mocker.patch("trs_file_backup.state.StateManager.save", side_effect=PermissionError(errno.EACCES, "Permission denied"))

        result = self._config(dest, "set", "retention.days", "3")

        assert result.exit_code == 1
        assert result.output.startswith("Error: cannot save ")
        assert "Stop a running" not in result.output
        assert _state_bytes(dest) == state_before

    def test_set_with_an_unwritable_log_says_the_settings_were_saved(self, mocker: MockFixture, tmp_path: Path) -> None:
        dest = self._with_rules(tmp_path)
        mocker.patch("trs_file_backup.main.BackupLogger", side_effect=PermissionError("backup.log is locked"))

        result = self._config(dest, "set", "retention.days", "3")

        assert result.exit_code == 1
        assert result.output.startswith("Error: ")
        assert "settings were saved" in result.output.lower()
        assert "backup.log" in result.output
        assert "Traceback" not in result.output
        assert _saved_retention(dest) == {**RULES_BEFORE_SET, "days": 3}

    def test_config_help_lists_the_keys_and_the_set_examples(self) -> None:
        from trs_file_backup.main import app

        result = runner.invoke(app, ["config", "--help"], env={"COLUMNS": "400"})

        assert result.exit_code == 0
        help_text = click.unstyle(result.output)
        assert "Keys for 'show KEY' and 'set KEY VALUE':" in help_text
        # One key per line, each with its meaning (the help must not join the key table into one paragraph)
        for key, meaning in [
            ("debounce", r"Seconds that watch waits before a backup \(0 or more\)"),
            ("retention.hours", "Keep every backup younger than N hours"),
            ("retention.days", "Keep the last backup per day for N days"),
            ("retention.weeks", "Keep the last backup per week for N weeks"),
            ("retention.months", "Keep the last backup per month for N months"),
        ]:
            assert re.search(rf"^\W*{re.escape(key)} +{meaning}\W*$", help_text, re.MULTILINE), key
        assert "A retention rule is 0 (off), a positive number, or -1 (no limit)." in help_text
        assert "trs-file-backup config show retention.days --destination ./backup" in help_text
        assert "trs-file-backup config set retention.days 12 --destination ./backup" in help_text
        assert "trs-file-backup config set retention.months -1 --destination ./backup" in help_text

    def test_set_help_and_show_help(self) -> None:
        from trs_file_backup.main import app

        show_help = _help_output(runner.invoke(app, ["config", "show", "--help"], env={"COLUMNS": "400"}))
        set_help = _help_output(runner.invoke(app, ["config", "set", "--help"], env={"COLUMNS": "400"}))

        assert "print the saved settings, or only the value of one setting." in show_help
        assert "change one setting and save it at once." in set_help
        assert "trs-file-backup config set retention.months -1 --destination ./backup" in set_help


class TestDestinationIsTheTruth:
    """The folder given with --destination holds the state file that is read and written (spec AC-3.11)."""

    @staticmethod
    def _copied_backup(tmp_path: Path) -> tuple[Path, Path, Path, bytes]:
        """Init into dest, copy dest to dest2, and add a file to back up; return source, dest, dest2 and dest's state bytes."""
        import shutil

        source, dest = _initialized(tmp_path, "--exclude", "*.log", "--debounce", "5")
        dest2 = tmp_path / "dest2"
        shutil.copytree(dest, dest2)
        (source / "a.txt").write_text("a")
        return source, dest, dest2, _state_bytes(dest)

    @staticmethod
    def _stored_destination(dest: Path) -> str:
        return json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))["destination_path"]

    def test_run_on_a_copied_folder_changes_only_the_copy(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest, dest2, dest_state = self._copied_backup(tmp_path)

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest2), "--debounce", "0"])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest2, "a", ".txt")
        assert not _backed_up(dest, "a", ".txt")
        assert _state_bytes(dest) == dest_state
        assert self._stored_destination(dest2) == str(dest2)
        assert _saved_settings(dest2)[1] == 0

    def test_watch_on_a_copied_folder_changes_only_the_copy(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest, dest2, dest_state = self._copied_backup(tmp_path)

        TestSavedSettings._invoke_watch(mocker, source, dest2, "--debounce", "0")

        assert _state_bytes(dest) == dest_state
        assert self._stored_destination(dest2) == str(dest2)
        assert _saved_settings(dest2)[1] == 0

    def test_config_save_on_a_copied_folder_changes_only_the_copy(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, dest, dest2, dest_state = self._copied_backup(tmp_path)
        dest_log = (dest / "backup.log").read_bytes()
        mocker.patch("trs_file_backup.main._stdin_is_terminal", return_value=True)

        result = runner.invoke(app, ["config", "--destination", str(dest2)], input="1\n0\ns\n")

        assert result.exit_code == 0, result.output
        assert str(dest2 / ".backup_state.json") in result.output
        assert _state_bytes(dest) == dest_state
        assert (dest / "backup.log").read_bytes() == dest_log
        assert self._stored_destination(dest2) == str(dest2)
        assert _saved_settings(dest2)[1] == 0


class TestSourceMustMatchTheStateFile:
    """run and watch refuse a --source other than the one saved in the state file (spec AC-3.12)."""

    @staticmethod
    def _other_source(tmp_path: Path) -> tuple[Path, Path, Path, bytes, bytes]:
        """Init source into dest and make a second source with a file; return source, other, dest and dest's state and log bytes."""
        source, dest = _initialized(tmp_path)
        other = tmp_path / "other"
        other.mkdir()
        (other / "a.txt").write_text("a")
        return source, other, dest, _state_bytes(dest), (dest / "backup.log").read_bytes()

    def test_run_with_another_source_aborts_before_doing_anything(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, other, dest, state_before, log_before = self._other_source(tmp_path)

        result = runner.invoke(app, ["run", "--source", str(other), "--destination", str(dest), "--debounce", "0"])

        assert result.exit_code == 1
        output = click.unstyle(result.output).replace("\n", "")  # Rich wraps the error line at the console width
        assert "Error:" in output
        assert "belongs to" in output
        assert str(source) in output
        assert "init" in output
        assert not _backed_up(dest, "a", ".txt")
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    def test_watch_with_another_source_aborts_before_doing_anything(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        _, other, dest, state_before, log_before = self._other_source(tmp_path)
        observer = mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt())

        result = runner.invoke(app, ["watch", "--source", str(other), "--destination", str(dest), "--debounce", "0"])

        assert result.exit_code == 1
        assert "belongs to" in click.unstyle(result.output)
        observer.assert_not_called()
        assert _state_bytes(dest) == state_before
        assert (dest / "backup.log").read_bytes() == log_before

    @pytest.mark.skipif(sys.platform != "win32", reason="paths differ only in case on a case-insensitive file system")
    def test_run_accepts_the_saved_source_in_other_letter_case(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source, dest = _initialized(tmp_path)
        (source / "a.txt").write_text("a")

        result = runner.invoke(app, ["run", "--source", str(source).swapcase(), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".txt")

    def test_run_accepts_a_saved_source_written_another_way(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app
        from trs_file_backup.state import StateManager

        source = tmp_path / "source"
        source.mkdir()
        (source / "a.txt").write_text("a")
        dest = tmp_path / "dest"
        StateManager(tmp_path / "x" / ".." / "source", dest, 0, [".backup_state.json"], {}).save()

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".txt")


class TestBackupEventHandler:
    """Test suite for BackupEventHandler."""

    def test_event_handler_ignores_directories(self, tmp_path: Path) -> None:
        """Test that event handler ignores directory modification events."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = []
        logger = Mock()
        state = Mock()

        handler = BackupEventHandler(manager, state, logger, 1)

        # Create directory event
        dir_path = source / "subdir"
        dir_path.mkdir()
        event = FileModifiedEvent(str(dir_path))
        event.is_directory = True

        handler.on_modified(event)

        # Should not attempt backup
        manager.backup_file.assert_not_called()

    def test_event_handler_ignores_excluded_files(self, tmp_path: Path) -> None:
        """Test that event handler ignores files matching exclusion patterns."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = ["*.log"]
        logger = Mock()
        state = Mock()

        handler = BackupEventHandler(manager, state, logger, 1)

        # Create file event
        file_path = source / "test.log"
        file_path.touch()
        event = FileModifiedEvent(str(file_path))
        event.is_directory = False

        handler.on_modified(event)

        # Should log exclusion and not add to pending
        logger.log_file_excluded.assert_called_once()
        assert file_path not in handler.pending_files
        manager.backup_file.assert_not_called()

    def test_event_handler_debounces_rapid_changes(self, tmp_path: Path, mocker: MockFixture) -> None:
        """Test that event handler tracks file modification time for debouncing."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = []
        backup_result = dest / "test_backup.txt"
        manager.backup_file.return_value = backup_result
        logger = Mock()
        state = Mock()

        # Mock time.time for debounce control
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 100.0

        handler = BackupEventHandler(manager, state, logger, 2)

        # Create file event
        file_path = source / "test.txt"
        file_path.write_text("content")
        event = FileModifiedEvent(str(file_path))
        event.is_directory = False

        # First event: should add to pending
        handler.on_modified(event)
        assert file_path in handler.pending_files
        assert handler.pending_files[file_path] == 100.0

        # Second event immediately after: should update timestamp
        mock_time.return_value = 100.5
        handler.on_modified(event)
        assert handler.pending_files[file_path] == 100.5

        # Process before debounce window: should not backup
        mock_time.return_value = 101.0
        handler.process_pending_files()
        manager.backup_file.assert_not_called()
        assert file_path in handler.pending_files

        # Process after debounce window: should backup and remove from pending
        mock_time.return_value = 103.0
        handler.process_pending_files()
        manager.backup_file.assert_called_once()
        assert file_path not in handler.pending_files

    def test_event_handler_handles_permission_error(self, tmp_path: Path, mocker: MockFixture) -> None:
        """Test that event handler handles permission errors gracefully."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = []
        manager.backup_file.side_effect = PermissionError("Access denied")
        logger = Mock()
        state = Mock()

        # Mock time.time
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 100.0

        handler = BackupEventHandler(manager, state, logger, 1)

        # Create file event
        file_path = source / "locked.txt"
        file_path.touch()
        event = FileModifiedEvent(str(file_path))
        event.is_directory = False

        # Trigger event
        handler.on_modified(event)
        assert file_path in handler.pending_files

        # Process after debounce: should handle permission error
        mock_time.return_value = 102.0
        handler.process_pending_files()

        # Should log error and remove from pending
        logger.log_error.assert_called_once()
        manager.backup_file.assert_called_once()
        assert file_path not in handler.pending_files

    @pytest.mark.parametrize(("error", "winerror", "level", "message"), BACKUP_ERROR_CASES)
    def test_event_handler_reports_a_failed_backup_by_its_cause(
        self, tmp_path: Path, mocker: MockFixture, with_winerror: Callable[[OSError, int], OSError], error: OSError, winerror: int | None, level: str, message: str
    ) -> None:
        """Spec AC-6.18: the console and backup.log name the cause, and the file leaves the pending files."""
        from rich.console import Console
        from watchdog.events import FileModifiedEvent

        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        output = io.StringIO()
        mocker.patch("trs_file_backup.main.console", Console(file=output, width=300, color_system=None))
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        if winerror is not None:
            error = with_winerror(error, winerror)
        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = []
        manager.backup_file.side_effect = error
        state = Mock()
        logger = BackupLogger(dest)
        mocker.patch("time.time", return_value=100.0)
        handler = BackupEventHandler(manager, state, logger, 1)
        file_path = source / "report.txt"
        file_path.write_text("content")
        handler.on_modified(FileModifiedEvent(str(file_path)))

        mocker.patch("time.time", return_value=102.0)
        try:
            handler.process_pending_files()
        finally:
            logger.close()

        assert file_path not in handler.pending_files
        assert handler.backed_up_count == 0
        state.update_file_timestamp.assert_not_called()
        assert f"{level} {message}" in output.getvalue().splitlines()
        log = (dest / "backup.log").read_text(encoding="utf-8")
        assert f"[{level}] {message}" in log
        if level == "ERROR":
            assert "locked" not in output.getvalue().lower()
            assert "locked" not in log.lower()

    def test_event_handler_reports_a_state_file_that_cannot_be_saved(self, tmp_path: Path, mocker: MockFixture) -> None:
        """Spec AC-5.11: a failed state save after a good copy is its own error, not a failed backup."""
        from rich.console import Console
        from watchdog.events import FileModifiedEvent

        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        output = io.StringIO()
        mocker.patch("trs_file_backup.main.console", Console(file=output, width=300, color_system=None))
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = []
        manager.backup_file.return_value = dest / "report_backup.txt"
        state = Mock()
        state.save.side_effect = OSError(errno.ENOSPC, "No space [left] on device")
        logger = BackupLogger(dest)
        mocker.patch("time.time", return_value=100.0)
        handler = BackupEventHandler(manager, state, logger, 1)
        file_path = source / "report.txt"
        file_path.write_text("content")
        handler.on_modified(FileModifiedEvent(str(file_path)))

        mocker.patch("time.time", return_value=102.0)
        try:
            handler.process_pending_files()
        finally:
            logger.close()

        assert file_path not in handler.pending_files
        assert handler.backed_up_count == 1
        lines = output.getvalue().splitlines()
        assert "ERROR Cannot save state file: No space [left] on device" in lines
        assert not any("report.txt" in line for line in lines if "ERROR" in line or "WARNING" in line)
        log = (dest / "backup.log").read_text(encoding="utf-8")
        assert "[INFO] Backed up: report.txt → report_backup.txt" in log
        assert "[ERROR] Cannot save state file: No space [left] on device" in log
        assert "Backup failed" not in log

    def test_event_handler_successful_backup(self, tmp_path: Path, mocker: MockFixture) -> None:
        """Test that event handler successfully backs up modified files."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = []
        backup_result = dest / "test_backup.txt"
        manager.backup_file.return_value = backup_result
        logger = Mock()
        state = Mock()

        # Mock time.time
        mock_time = mocker.patch("time.time")
        mock_time.return_value = 100.0

        handler = BackupEventHandler(manager, state, logger, 1)

        # Create file event
        file_path = source / "test.txt"
        file_path.write_text("content")
        event = FileModifiedEvent(str(file_path))
        event.is_directory = False

        # Trigger event
        handler.on_modified(event)
        assert file_path in handler.pending_files

        # Process after debounce: should backup successfully
        mock_time.return_value = 102.0
        handler.process_pending_files()

        # Should backup and update state
        manager.backup_file.assert_called_once()
        logger.log_file_backed_up.assert_called_once()
        state.update_file_timestamp.assert_called_once()
        state.save.assert_called_once()
        assert file_path not in handler.pending_files


class TestNewAndMovedFiles:
    """Watch mode backs up created and moved-in files (spec AC-5.10) and logs the real exclusion reason (spec AC-6.17)."""

    @pytest.fixture
    def source(self, tmp_path: Path) -> Path:
        source = tmp_path / "source"
        source.mkdir()
        return source

    @staticmethod
    def _handler(source: Path, mocker: MockFixture, excluded_patterns: list[str] | None = None) -> tuple[Any, Mock, Mock]:
        """Return a handler with a mocked backup manager and a logger that only accepts real BackupLogger methods."""
        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = excluded_patterns if excluded_patterns is not None else [".backup_state.json"]
        manager.backup_file.side_effect = lambda path, timestamp: source.parent / f"backup_of_{path.name}"
        logger = mocker.Mock(spec=BackupLogger)
        mocker.patch("time.time", return_value=100.0)
        return BackupEventHandler(manager, Mock(), logger, 2), manager, logger

    @staticmethod
    def _after_debounce(handler: Any, mocker: MockFixture) -> None:
        mocker.patch("time.time", return_value=103.0)
        handler.process_pending_files()

    def test_created_file_is_backed_up_after_the_debounce(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileCreatedEvent

        handler, manager, _ = self._handler(source, mocker)
        new_file = source / "notes.txt"
        new_file.write_text("first version")

        handler.dispatch(FileCreatedEvent(str(new_file)))
        assert new_file in handler.pending_files

        self._after_debounce(handler, mocker)
        manager.backup_file.assert_called_once()
        assert manager.backup_file.call_args.args[0] == new_file

    def test_created_then_modified_file_is_backed_up_once(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileCreatedEvent, FileModifiedEvent

        handler, manager, _ = self._handler(source, mocker)
        new_file = source / "notes.txt"
        new_file.write_text("first version")

        handler.dispatch(FileCreatedEvent(str(new_file)))
        handler.dispatch(FileModifiedEvent(str(new_file)))
        self._after_debounce(handler, mocker)

        manager.backup_file.assert_called_once()

    def test_created_file_is_logged_as_created(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileCreatedEvent

        handler, _, logger = self._handler(source, mocker)
        new_file = source / "notes.txt"
        new_file.write_text("first version")

        handler.dispatch(FileCreatedEvent(str(new_file)))

        logger.log_file_changed.assert_called_once_with("notes.txt", "created")

    def test_renamed_file_is_queued_under_its_destination(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileMovedEvent

        handler, manager, logger = self._handler(source, mocker)
        old_file = source / "draft.txt"
        new_file = source / "report.txt"
        new_file.write_text("content")

        handler.dispatch(FileMovedEvent(str(old_file), str(new_file)))

        assert list(handler.pending_files) == [new_file]
        logger.log_file_changed.assert_called_once_with("report.txt", "moved")
        self._after_debounce(handler, mocker)
        assert manager.backup_file.call_args.args[0] == new_file

    def test_hidden_temp_file_renamed_to_visible_name_is_queued(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileMovedEvent

        handler, _, logger = self._handler(source, mocker)
        new_file = source / "doc.txt"
        new_file.write_text("saved by an editor")

        handler.dispatch(FileMovedEvent(str(source / ".~doc.tmp"), str(new_file)))

        assert list(handler.pending_files) == [new_file]
        logger.log_hidden_file_excluded.assert_not_called()

    def test_pending_file_renamed_before_the_debounce_ends_is_backed_up_once_under_the_new_name(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileModifiedEvent, FileMovedEvent

        handler, manager, logger = self._handler(source, mocker)
        old_file = source / "a.txt"
        old_file.write_text("content")
        handler.dispatch(FileModifiedEvent(str(old_file)))

        new_file = old_file.rename(source / "b.txt")
        handler.dispatch(FileMovedEvent(str(old_file), str(new_file)))
        self._after_debounce(handler, mocker)

        manager.backup_file.assert_called_once()
        assert manager.backup_file.call_args.args[0] == new_file
        assert handler.pending_files == {}
        logger.log_error.assert_not_called()

    def test_case_only_rename_of_a_pending_file_is_backed_up_under_the_new_name(self, source: Path, mocker: MockFixture) -> None:
        """On Windows both spellings are one dict key; the new spelling must replace the old one (AC-5.10)."""
        from watchdog.events import FileModifiedEvent, FileMovedEvent

        handler, manager, _ = self._handler(source, mocker)
        old_file = source / "Report.txt"
        old_file.write_text("content")
        handler.dispatch(FileModifiedEvent(str(old_file)))

        new_file = old_file.rename(source / "report.txt")
        handler.dispatch(FileMovedEvent(str(old_file), str(new_file)))
        self._after_debounce(handler, mocker)

        manager.backup_file.assert_called_once()
        assert manager.backup_file.call_args.args[0].name == "report.txt"

    def test_event_during_the_backup_keeps_the_file_pending_for_a_second_backup(self, source: Path, mocker: MockFixture) -> None:
        """A version written while the copy runs must not be lost (spec AC-5.4, AC-5.5)."""
        from watchdog.events import FileCreatedEvent, FileModifiedEvent

        handler, manager, _ = self._handler(source, mocker)
        new_file = source / "notes.txt"
        new_file.write_text("first version")
        handler.dispatch(FileCreatedEvent(str(new_file)))

        def write_during_copy(path: Path, timestamp: object) -> Path:
            if manager.backup_file.call_count == 1:
                handler.dispatch(FileModifiedEvent(str(new_file)))
            return source.parent / f"backup_{manager.backup_file.call_count}_of_{path.name}"

        manager.backup_file.side_effect = write_during_copy
        self._after_debounce(handler, mocker)  # time 103.0: first backup; the event during it is stamped 103.0

        manager.backup_file.assert_called_once()
        assert handler.pending_files == {new_file: 103.0}

        mocker.patch("time.time", return_value=106.0)
        handler.process_pending_files()

        assert manager.backup_file.call_count == 2
        assert handler.pending_files == {}

    @pytest.mark.parametrize("subpath", [("sub", "a.txt"), ("sub", "deeper", "a.txt")], ids=["subdirectory", "not-on-disk"])
    def test_file_moved_into_a_subdirectory_is_ignored(self, source: Path, mocker: MockFixture, subpath: tuple[str, ...]) -> None:
        """The macOS emitter can report a move from the top level into a subdirectory as a moved event (AC-1.3).

        The decision uses the paths only, so it also holds when the file is gone already.
        """
        from watchdog.events import FileMovedEvent

        handler, _, logger = self._handler(source, mocker)
        (source / "sub").mkdir()
        moved_file = source.joinpath(*subpath)
        if subpath == ("sub", "a.txt"):
            moved_file.write_text("content")

        handler.dispatch(FileMovedEvent(str(source / "a.txt"), str(moved_file)))

        assert handler.pending_files == {}
        logger.log_file_changed.assert_not_called()

    def test_moved_file_spelled_another_way_is_queued(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileMovedEvent

        handler, _, _ = self._handler(source, mocker)
        (source / "sub").mkdir()
        new_file = source / "report.txt"
        new_file.write_text("content")

        handler.dispatch(FileMovedEvent(str(source / "draft.txt"), str(source / "sub" / ".." / "report.txt")))

        assert [path.name for path in handler.pending_files] == ["report.txt"]

    def test_state_keeps_the_mtime_of_the_backed_up_version(self, source: Path, mocker: MockFixture) -> None:
        """A write during the copy must not mark the newer version as backed up (spec AC-3.5)."""
        from watchdog.events import FileCreatedEvent

        handler, manager, _ = self._handler(source, mocker)
        new_file = source / "notes.txt"
        new_file.write_text("first version")
        os.utime(new_file, (1000.0, 1000.0))
        handler.dispatch(FileCreatedEvent(str(new_file)))

        def write_during_copy(path: Path, timestamp: object) -> Path:
            new_file.write_text("second version")
            os.utime(new_file, (2000.0, 2000.0))
            return source.parent / "backup_of_notes.txt"

        manager.backup_file.side_effect = write_during_copy
        self._after_debounce(handler, mocker)

        handler.state.update_file_timestamp.assert_called_once_with("notes.txt", 1000.0)

    def test_watch_console_prints_file_names_literally(self, source: Path, mocker: MockFixture) -> None:
        """A file name that looks like Rich markup must be printed as it is."""
        from rich.console import Console
        from watchdog.events import FileCreatedEvent

        output = io.StringIO()
        mocker.patch("trs_file_backup.main.console", Console(file=output, width=300, color_system=None))
        handler, _, _ = self._handler(source, mocker)
        new_file = source / "[red]notes.txt"
        new_file.write_text("content")

        handler.dispatch(FileCreatedEvent(str(new_file)))
        self._after_debounce(handler, mocker)

        assert "File created: [red]notes.txt" in output.getvalue()
        assert "Backing up: [red]notes.txt -> backup_of_[red]notes.txt OK" in output.getvalue()

    def test_created_and_moved_directories_are_ignored(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import DirCreatedEvent, DirMovedEvent

        handler, _, logger = self._handler(source, mocker)
        subdir = source / "sub"
        subdir.mkdir()

        handler.dispatch(DirCreatedEvent(str(subdir)))
        handler.dispatch(DirMovedEvent(str(source / "old"), str(subdir)))

        assert handler.pending_files == {}
        logger.log_file_changed.assert_not_called()

    def test_hidden_file_is_logged_as_hidden_file(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileModifiedEvent

        handler, _, logger = self._handler(source, mocker, [".backup_state.json", "*.log"])
        hidden_file = source / ".gitignore"
        hidden_file.write_text("*.pyc")

        handler.dispatch(FileModifiedEvent(str(hidden_file)))

        logger.log_hidden_file_excluded.assert_called_once_with(".gitignore")
        logger.log_file_excluded.assert_not_called()
        assert handler.pending_files == {}

    def test_state_file_is_logged_as_hidden_file(self, source: Path, mocker: MockFixture) -> None:
        """The state file starts with a dot, so the hidden-file rule (AC-4.1) is the reason given."""
        from watchdog.events import FileCreatedEvent

        handler, _, logger = self._handler(source, mocker)
        state_file = source / ".backup_state.json"
        state_file.write_text("{}")

        handler.dispatch(FileCreatedEvent(str(state_file)))

        logger.log_hidden_file_excluded.assert_called_once_with(".backup_state.json")
        logger.log_file_excluded.assert_not_called()

    def test_pattern_exclusion_logs_the_matching_pattern(self, source: Path, mocker: MockFixture) -> None:
        from watchdog.events import FileCreatedEvent

        handler, _, logger = self._handler(source, mocker, [".backup_state.json", "temp_*", "*.log"])
        log_file = source / "debug.log"
        log_file.write_text("trace")

        handler.dispatch(FileCreatedEvent(str(log_file)))

        logger.log_file_excluded.assert_called_once_with("debug.log", "*.log")
        logger.log_hidden_file_excluded.assert_not_called()
        assert handler.pending_files == {}

    @pytest.mark.parametrize(
        ("filename", "expected_line"),
        [
            (".gitignore", "[WARNING] File excluded: .gitignore (hidden file)"),
            ("debug.log", "[WARNING] File excluded: debug.log (matches: *.log)"),
        ],
        ids=["hidden-file", "pattern"],
    )
    def test_exclusion_line_in_the_log_file(self, source: Path, tmp_path: Path, filename: str, expected_line: str) -> None:
        from watchdog.events import FileModifiedEvent

        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = [".backup_state.json", "*.log"]
        logger = BackupLogger(tmp_path / "dest")
        try:
            handler = BackupEventHandler(manager, Mock(), logger, 2)
            excluded_file = source / filename
            excluded_file.write_text("content")
            handler.dispatch(FileModifiedEvent(str(excluded_file)))
        finally:
            logger.close()

        log_lines = (tmp_path / "dest" / "backup.log").read_text(encoding="utf-8").splitlines()
        assert [line.split("] ", 1)[1] for line in log_lines] == [expected_line]


class TestExcludeOptionValues:
    """`--exclude` rejects an empty pattern and strips surrounding whitespace, as `config` does (spec AC-4.9)."""

    @pytest.mark.parametrize("command", ["init", "run", "watch"])
    @pytest.mark.parametrize("value", ["", "   "], ids=["empty", "spaces"])
    def test_empty_pattern_is_rejected(self, mocker: MockFixture, tmp_path: Path, command: str, value: str) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        observer = mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt)  # ends watch at once if the value were accepted

        result = runner.invoke(app, [command, "--source", str(source), "--destination", str(dest), "--exclude", "*.log", "--exclude", value])

        assert result.exit_code == 2
        assert "empty pattern" in _help_output(result)
        assert "--exclude" in _help_output(result)
        assert not (dest / ".backup_state.json").exists()
        observer.assert_not_called()

    @pytest.mark.parametrize("command", ["init", "run", "watch"])
    @pytest.mark.parametrize("value", ["logs/*.log", "sub\\*.log", "..", ".", "./", "\t"], ids=["slash", "backslash", "dotdot", "dot", "dot-slash", "tab"])
    def test_pattern_that_cannot_be_matched_is_rejected(self, mocker: MockFixture, tmp_path: Path, command: str, value: str) -> None:
        """A pattern with a path separator, "." or ".." never matches a bare file name (spec AC-4.6, AC-4.9)."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        observer = mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt)  # ends watch at once if the value were accepted

        result = runner.invoke(app, [command, "--source", str(source), "--destination", str(dest), "--exclude", value])

        assert result.exit_code == 2
        assert f"'{value.strip()}' is not usable" in _help_output(result)
        assert "--exclude" in _help_output(result)
        assert not (dest / ".backup_state.json").exists()
        observer.assert_not_called()

    def test_file_name_patterns_are_accepted(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(app, ["init", "--source", str(source), "--destination", str(dest), "--exclude", "*.log", "--exclude", "temp_*", "--exclude", ".env"])

        assert result.exit_code == 0, result.output
        saved = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert saved["excluded_patterns"] == [".backup_state.json", "*.log", "temp_*", ".env"]

    def test_pattern_is_saved_without_surrounding_spaces(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        result = runner.invoke(app, ["init", "--source", str(source), "--destination", str(dest), "--exclude", "  *.log ", "--exclude", "*.log"])

        assert result.exit_code == 0
        saved = json.loads((dest / ".backup_state.json").read_text(encoding="utf-8"))
        assert saved["excluded_patterns"] == [".backup_state.json", "*.log"]


class TestPathsInConsoleOutput:
    """Folder paths that look like Rich markup are printed as they are."""

    def test_init_prints_folder_paths_literally(self, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "[red]source"
        source.mkdir()
        dest = tmp_path / "[red]dest"

        result = runner.invoke(app, ["init", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0
        output = click.unstyle(result.output).replace("\n", "")  # Rich wraps long paths
        assert f"Initialized backup tracking for {source}" in output
        assert f"State file saved to {dest / '.backup_state.json'}" in output
        assert f"Log file created: {dest / 'backup.log'}" in output

    def test_init_prints_a_path_ending_in_a_backslash_once(self, tmp_path: Path) -> None:
        """A drive root such as C:\\ ends in a backslash; it must not be printed doubled."""
        from trs_file_backup.main import app

        root = tmp_path.anchor

        result = runner.invoke(app, ["init", "--source", root, "--destination", str(tmp_path / "dest")])

        assert result.exit_code == 0, result.output
        lines = click.unstyle(result.output).splitlines()
        assert f"OK Initialized backup tracking for {root}" in lines

    def test_emoji_codes_in_file_names_are_printed_as_text(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Rich would turn :fire: into an emoji, on a markup=False line ("File created") and on a Text line ("Backing up")."""
        from watchdog.events import FileCreatedEvent

        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler, console

        source = tmp_path / "source"
        new_file = source / ":fire:notes.txt"  # Windows forbids ":" in names, so the file system is mocked
        mocker.patch.object(Path, "exists", return_value=True)
        mocker.patch.object(Path, "stat", return_value=Mock(st_mtime=1000.0))
        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = [".backup_state.json"]
        manager.backup_file.return_value = tmp_path / ":fire:notes_backup.txt"
        mocker.patch("time.time", return_value=100.0)
        handler = BackupEventHandler(manager, Mock(), mocker.Mock(spec=BackupLogger), 2)

        output = io.StringIO()
        # Keep the real console, whose settings are under test. Its private _file is patched because
        # setting the public file property would pin it to the captured stdout of this test.
        mocker.patch.object(console, "_file", output)

        handler.dispatch(FileCreatedEvent(str(new_file)))
        mocker.patch("time.time", return_value=103.0)
        handler.process_pending_files()

        printed = click.unstyle(output.getvalue()).replace("\n", "")
        assert "File created: :fire:notes.txt" in printed
        assert "Backing up: :fire:notes.txt -> :fire:notes_backup.txt OK" in printed

    @pytest.mark.parametrize("command", ["init", "run", "watch"])
    def test_error_line_prints_the_message_literally(self, mocker: MockFixture, tmp_path: Path, command: str) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        message = "cannot write [red]notes in D:\\"
        mocker.patch("trs_file_backup.main.BackupLogger", side_effect=OSError(message))

        result = runner.invoke(app, [command, "--source", str(source), "--destination", str(tmp_path / "dest")])

        assert result.exit_code == 1
        assert f"Error: {message}" in click.unstyle(result.output).splitlines()

    @pytest.mark.parametrize(
        ("error", "winerror", "line", "tail"),
        [
            (PermissionError(errno.EACCES, "no access"), None, "ERROR Permission denied: ", ""),
            (PermissionError(errno.EACCES, "no access"), 32, "WARNING File locked, skipping: ", ""),
            (OSError(errno.EIO, "[red]bad[/red] sector"), None, "ERROR Backup failed: ", " ([red]bad[/red] sector)"),
        ],
        ids=["permission", "locked", "failed"],
    )
    def test_run_prints_paths_and_names_literally(
        self, mocker: MockFixture, tmp_path: Path, with_winerror: Callable[[OSError, int], OSError], error: OSError, winerror: int | None, line: str, tail: str
    ) -> None:
        from trs_file_backup.backup import BackupManager
        from trs_file_backup.main import app

        source = tmp_path / "[red]source"
        source.mkdir()
        (source / "[red]a.txt").write_text("content")
        dest = tmp_path / "[red]dest"
        if winerror is not None:
            error = with_winerror(error, winerror)
        mocker.patch.object(BackupManager, "backup_file", side_effect=error)

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        output = click.unstyle(result.output).replace("\n", "")  # Rich wraps long paths
        assert f"Scanning source directory: {source}" in output
        assert f"{line}[red]a.txt{tail}" in output
        assert f"Successfully backed up 0 files to {dest}" in output
        assert f"Logging to: {dest / 'backup.log'}" in output

    def test_watch_start_lines_print_paths_literally(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "[red]source"
        source.mkdir()
        dest = tmp_path / "[red]dest"
        mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt)

        result = runner.invoke(app, ["watch", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        output = click.unstyle(result.output).replace("\n", "")  # Rich wraps long paths
        assert f"Starting file system monitor for {source}" in output
        assert f"Logging to: {dest / 'backup.log'}" in output

    @pytest.mark.parametrize(
        ("error", "winerror", "line", "tail"),
        [
            (PermissionError(errno.EACCES, "no access"), None, "ERROR Permission denied: ", ""),
            (PermissionError(errno.EACCES, "no access"), 32, "WARNING File locked, skipping: ", ""),
            (OSError(errno.EIO, "[red]bad[/red] sector"), None, "ERROR Backup failed: ", " ([red]bad[/red] sector)"),
        ],
        ids=["permission", "locked", "failed"],
    )
    def test_watch_error_lines_print_file_names_literally(
        self, mocker: MockFixture, tmp_path: Path, with_winerror: Callable[[OSError, int], OSError], error: OSError, winerror: int | None, line: str, tail: str
    ) -> None:
        from rich.console import Console
        from watchdog.events import FileCreatedEvent

        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        output = io.StringIO()
        mocker.patch("trs_file_backup.main.console", Console(file=output, width=300, color_system=None))
        source = tmp_path / "source"
        source.mkdir()
        new_file = source / "[red]notes.txt"
        new_file.write_text("content")
        manager = Mock()
        manager.source_path = source
        manager.excluded_patterns = [".backup_state.json"]
        if winerror is not None:
            error = with_winerror(error, winerror)
        manager.backup_file.side_effect = error
        mocker.patch("time.time", return_value=100.0)
        handler = BackupEventHandler(manager, Mock(), mocker.Mock(spec=BackupLogger), 2)

        handler.dispatch(FileCreatedEvent(str(new_file)))
        mocker.patch("time.time", return_value=103.0)
        handler.process_pending_files()

        assert f"{line}[red]notes.txt{tail}" in output.getvalue().splitlines()


class TestMainApp:
    """Test suite for main app."""

    def test_main_help_shows_commands(self, mocker: MockFixture) -> None:
        """Test that main help shows all commands."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "run" in _help_output(result)
        assert "init" in _help_output(result)
        assert "watch" in _help_output(result)

    def test_package_installs_only_the_trs_file_backup_command(self) -> None:
        """The package installs one command; the old alias `bcs` is gone (spec NFR-3)."""
        commands = importlib.metadata.distribution("trs-file-backup").entry_points.select(group="console_scripts")

        assert sorted(command.name for command in commands) == ["trs-file-backup"]

    def test_main_version_flag(self) -> None:
        """Test that --version prints the version from the installed package metadata."""
        import trs_file_backup
        import trs_file_backup.main

        real_version = importlib.metadata.version

        def fake_version(distribution_name: str) -> str:
            return "9.8.7" if distribution_name == "trs-file-backup" else real_version(distribution_name)

        # The version is looked up once at import time, so both modules are reloaded under the patch and again afterwards.
        try:
            with patch("importlib.metadata.version", side_effect=fake_version):
                importlib.reload(trs_file_backup)
                importlib.reload(trs_file_backup.main)
                result = runner.invoke(trs_file_backup.main.app, ["--version"])
        finally:
            importlib.reload(trs_file_backup)
            importlib.reload(trs_file_backup.main)

        assert result.exit_code == 0
        assert result.output == "trs-file-backup version 9.8.7\n"

    def test_init_help(self, mocker: MockFixture) -> None:
        """Test init command help."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "source" in _help_output(result)
        assert "destination" in _help_output(result)
        assert "exclude" in _help_output(result)

    def test_run_help(self, mocker: MockFixture) -> None:
        """Test run command help."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["run", "--help"])

        assert result.exit_code == 0
        assert "source" in _help_output(result)
        assert "destination" in _help_output(result)
        assert "dry-run" in _help_output(result)

    def test_watch_help(self, mocker: MockFixture) -> None:
        """Test watch command help."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["watch", "--help"])

        assert result.exit_code == 0
        assert "source" in _help_output(result)
        assert "destination" in _help_output(result)
        assert "debounce" in _help_output(result)

    @pytest.mark.parametrize("command", [[], ["init"], ["run"], ["watch"], ["config"], ["config", "show"]], ids=["app", "init", "run", "watch", "config", "config-show"])
    def test_short_help_option_matches_long_one(self, command: list[str]) -> None:
        """Spec NFR-3: -h works like --help for the main command and every subcommand."""
        from trs_file_backup.main import app

        short = runner.invoke(app, [*command, "-h"], env={"COLUMNS": "200"})
        long = runner.invoke(app, [*command, "--help"], env={"COLUMNS": "200"})

        assert short.exit_code == 0, short.output
        assert short.output == long.output
        assert "-h" in _help_output(short)

    @pytest.mark.parametrize("command", ["init", "run", "watch"])
    def test_exclude_option_shows_pattern_metavar(self, command: str) -> None:
        """Test that --exclude shows PATTERN in the help, not the Python type (typer >= 0.29 prints list[str])."""
        from trs_file_backup.main import app

        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert re.search(r"--exclude\s+pattern\b", _help_output(result))
        assert "list[str]" not in _help_output(result)


OLD_TIME = datetime(2020, 5, 17, 8, 0, 0)
DAYS_ONE = {**ALL_RULES_OFF, "days": 1}


def _old_backups(dest: Path, original: str, count: int = 2) -> list[Path]:
    """Create count backups of original from 2020 in dest, one day apart, and return them."""
    from trs_file_backup.backup import BackupManager

    dest.mkdir(exist_ok=True)
    paths = []
    for offset in range(count):
        path = dest / BackupManager.generate_backup_filename(original, OLD_TIME + timedelta(days=offset))
        path.write_text("old")
        paths.append(path)
    return paths


def _with_rules(tmp_path: Path, rules: dict[str, int]) -> tuple[Path, Path]:
    """Initialize source and dest and store the retention rules."""
    source, dest = _initialized(tmp_path)
    _store_retention(dest, rules)
    return source, dest


def _new_backup_names(dest: Path, stem: str) -> list[str]:
    """Return the names of the backups of stem made in this test, that is neither from 2020 nor from the future year 2999."""
    return [path.name for path in dest.glob(f"{stem}_*") if not path.name.startswith((f"{stem}_2020_", f"{stem}_2999_"))]


def _log(dest: Path) -> str:
    return (dest / "backup.log").read_text(encoding="utf-8")


class TestRetentionInRun:
    """run applies the saved rules to the backups of each file it backed up (spec AC-8.3, AC-8.8 to AC-8.13)."""

    @pytest.fixture(autouse=True)
    def _wide_console(self, mocker: MockFixture) -> None:
        """Print to the runner's output without wrapping, so a long path stays on one line."""
        from rich.console import Console

        mocker.patch("trs_file_backup.main.console", Console(width=1000, emoji=False))

    @staticmethod
    def _run(source: Path, dest: Path, *options: str) -> Result:
        from trs_file_backup.main import app

        return runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest), *options])

    def test_deletes_old_backups_of_the_backed_up_file_and_keeps_the_new_one(self, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert not any(path.exists() for path in old)
        assert _backed_up(dest, "report", ".txt")
        lines = click.unstyle(result.output).splitlines()
        for path in old:
            assert f"  Deleted old backup: {path.name}" in lines
            assert f"[INFO] Deleted old backup: {path.name}" in _log(dest)
        assert "Successfully backed up 1 files to" in result.output

    def test_deletes_only_backups_of_the_backed_up_file(self, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        own = _old_backups(dest, "report.txt")
        # Same stem with another suffix, and another file: both are other groups (a case-only variant needs a case-sensitive file system)
        others = [*_old_backups(dest, "other.txt"), *_old_backups(dest, "report.md")]
        (source / "report.txt").write_text("new")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert not any(path.exists() for path in own)
        assert all(path.exists() for path in others)

    def test_never_deletes_files_that_are_no_backup(self, tmp_path: Path) -> None:
        from trs_file_backup.backup import BackupManager

        source, dest = _with_rules(tmp_path, DAYS_ONE)
        own = _old_backups(dest, "report.txt")
        foreign = [dest / "notes.txt", dest / ".trs-file-backup-0123456789ab.tmp", dest / "report_2020_02_30__08_00_00.txt"]
        for path in foreign:
            path.write_text("x")
        directory = dest / BackupManager.generate_backup_filename("report.txt", OLD_TIME.replace(year=2019))
        directory.mkdir()
        (source / "report.txt").write_text("new")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert not any(path.exists() for path in own)
        assert all(path.exists() for path in foreign)
        assert directory.is_dir()
        # The directory is no candidate at all (spec AC-8.6), so no deletion of it is even tried and reported
        assert directory.name not in result.output
        assert directory.name not in _log(dest)
        assert (dest / "backup.log").exists()
        assert (dest / ".backup_state.json").exists()

    def test_all_rules_zero_neither_lists_nor_deletes(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, ALL_RULES_OFF)
        old = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        listing.assert_not_called()
        assert all(path.exists() for path in old)

    def test_dry_run_neither_lists_nor_deletes(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")
        delete = mocker.patch("trs_file_backup.main.delete_backup")

        result = self._run(source, dest, "--dry-run")

        assert result.exit_code == 0, result.output
        listing.assert_not_called()
        delete.assert_not_called()
        assert all(path.exists() for path in old)

    def test_no_modified_file_lists_nothing(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        _old_backups(dest, "report.txt")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        listing.assert_not_called()

    def test_lists_the_destination_once_for_several_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.backup import list_backup_groups

        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = [*_old_backups(dest, "a.txt"), *_old_backups(dest, "b.txt"), *_old_backups(dest, "c.txt")]
        for name in ("a.txt", "b.txt", "c.txt"):
            (source / name).write_text("new")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups", wraps=list_backup_groups)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert listing.call_count == 1
        assert not any(path.exists() for path in old)
        for stem in ("a", "b", "c"):
            assert _backed_up(dest, stem, ".txt")

    def test_a_backup_made_after_the_listing_is_added_to_it(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.backup import BackupManager, list_backup_groups

        source, dest = _with_rules(tmp_path, DAYS_ONE)
        files = [source / "a.txt", source / "b.txt"]
        for file in files:
            file.write_text("new")
        (old_b,) = _old_backups(dest, "b.txt", count=1)
        # a.txt first: the only listing happens after the backup of a.txt, before the backup of b.txt
        mocker.patch.object(BackupManager, "get_files_to_backup", return_value=files)
        listing = mocker.patch("trs_file_backup.main.list_backup_groups", wraps=list_backup_groups)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert listing.call_count == 1
        # Only when the new backup of b.txt is added to the list does the old one stop being the newest, so days=1 deletes it
        assert not old_b.exists()
        assert len(_new_backup_names(dest, "b")) == 1

    def test_the_backup_just_made_is_kept_when_a_future_backup_sorts_as_newer(self, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        (older,) = _old_backups(dest, "report.txt", count=1)
        future = dest / "report_2999_01_01__00_00_00.txt"
        future.write_text("future")
        (source / "report.txt").write_text("new")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert future.exists()
        assert not older.exists()
        assert len(_new_backup_names(dest, "report")) == 1

    @pytest.mark.parametrize("error", [OSError(errno.EIO, "Input/output error"), RuntimeError("Input/output error")], ids=["oserror", "other-error"])
    def test_a_failed_listing_is_reported_once_and_changes_no_count(self, mocker: MockFixture, tmp_path: Path, error: Exception) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = [*_old_backups(dest, "a.txt"), *_old_backups(dest, "b.txt")]
        (source / "a.txt").write_text("new")
        (source / "b.txt").write_text("new")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups", side_effect=error)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert listing.call_count == 1
        assert all(path.exists() for path in old)
        output = click.unstyle(result.output)
        message = f"Cannot list backups in {dest}: Input/output error"
        assert f"  ERROR {message}" in output.splitlines()
        assert "Successfully backed up 2 files to" in output
        assert "Failed:" not in output
        log = _log(dest)
        assert log.count(f"[ERROR] {message}") == 1
        assert "Session summary: 2 of 2 files backed up" in log

    def test_a_failed_deletion_is_reported_and_the_next_backup_is_deleted(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        first, second = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")
        real_unlink = Path.unlink

        def fail_for_first(path: Path, missing_ok: bool = False) -> None:
            if path.name == first.name:
                raise OSError(errno.EIO, "Input/output error")
            real_unlink(path, missing_ok=missing_ok)

        mocker.patch.object(Path, "unlink", autospec=True, side_effect=fail_for_first)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert first.exists()
        assert not second.exists()
        message = f"Cannot delete backup: {first.name} (Input/output error)"
        assert f"  ERROR {message}" in click.unstyle(result.output).splitlines()
        assert f"[ERROR] {message}" in _log(dest)
        assert "Successfully backed up 1 files to" in result.output
        assert "Failed:" not in result.output

    def test_an_unexpected_error_while_deleting_skips_only_that_backup(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.backup import delete_backup

        source, dest = _with_rules(tmp_path, DAYS_ONE)
        first, second = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")

        def fail_for_first(path: Path) -> Any:
            if path.name == first.name:
                raise RuntimeError("boom")
            return delete_backup(path)

        mocker.patch("trs_file_backup.main.delete_backup", side_effect=fail_for_first)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert first.exists()
        assert not second.exists()
        assert f"[ERROR] Cannot delete backup: {first.name} (boom)" in _log(dest)

    def test_a_locked_backup_is_a_warning(self, mocker: MockFixture, tmp_path: Path, with_winerror: Callable[[OSError, int], OSError]) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        (old,) = _old_backups(dest, "report.txt", count=1)
        (source / "report.txt").write_text("new")
        mocker.patch.object(Path, "unlink", side_effect=with_winerror(PermissionError(errno.EACCES, "sharing violation"), 32))

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert old.exists()
        assert f"  WARNING Backup locked, not deleted: {old.name}" in click.unstyle(result.output).splitlines()
        assert f"[WARNING] Backup locked, not deleted: {old.name}" in _log(dest)

    def test_a_backup_already_gone_is_not_reported(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        (old,) = _old_backups(dest, "report.txt", count=1)
        (source / "report.txt").write_text("new")
        real_unlink = Path.unlink

        def vanish(path: Path, missing_ok: bool = False) -> None:
            real_unlink(path)
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")

        mocker.patch.object(Path, "unlink", autospec=True, side_effect=vanish)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert not old.exists()
        assert old.name not in result.output
        assert old.name not in _log(dest)

    def test_a_read_only_backup_is_deleted(self, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        (old,) = _old_backups(dest, "report.txt", count=1)
        os.chmod(old, stat.S_IREAD)
        (source / "report.txt").write_text("new")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert not old.exists()

    def test_an_error_while_applying_the_rules_is_reported(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")
        mocker.patch("trs_file_backup.main.plan_retention", side_effect=RuntimeError("boom"))

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert all(path.exists() for path in old)
        message = "Retention failed for report.txt: boom"
        assert f"  ERROR {message}" in click.unstyle(result.output).splitlines()
        assert f"[ERROR] {message}" in _log(dest)
        assert "Successfully backed up 1 files to" in result.output

    def test_a_failed_backup_applies_no_rules(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = _with_rules(tmp_path, DAYS_ONE)
        old = _old_backups(dest, "report.txt")
        (source / "report.txt").write_text("new")
        mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=OSError(errno.ENOSPC, "No space left on device"))
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        listing.assert_not_called()
        assert all(path.exists() for path in old)

    def test_the_rules_run_after_the_backup_and_the_state_update(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.backup import list_backup_groups
        from trs_file_backup.state import StateManager

        source, dest = _with_rules(tmp_path, DAYS_ONE)
        (source / "report.txt").write_text("new")
        update = mocker.spy(StateManager, "update_file_timestamp")
        seen: list[tuple[bool, int]] = []

        def check(destination: Path) -> Any:
            seen.append((_backed_up(destination, "report", ".txt"), update.call_count))
            return list_backup_groups(destination)

        mocker.patch("trs_file_backup.main.list_backup_groups", side_effect=check)

        result = self._run(source, dest)

        assert result.exit_code == 0, result.output
        assert seen == [(True, 1)]


class TestRetentionInWatch:
    """watch applies the rules it started with to the backups of each file it backed up (spec AC-8.9 to AC-8.13, AC-8.15)."""

    @staticmethod
    def _handler(mocker: MockFixture, tmp_path: Path, rules: Any, state: Any = None) -> tuple[Any, Path, Path, io.StringIO]:
        from rich.console import Console

        from trs_file_backup.backup import BackupManager
        from trs_file_backup.logger import BackupLogger
        from trs_file_backup.main import BackupEventHandler

        output = io.StringIO()
        mocker.patch("trs_file_backup.main.console", Console(file=output, width=300, color_system=None))
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        manager = BackupManager(source, dest, [], None)
        logger = BackupLogger(dest)
        handler = BackupEventHandler(manager, state if state is not None else Mock(), logger, 1, retention=rules)
        return handler, source, dest, output

    @staticmethod
    def _process(mocker: MockFixture, handler: Any, *files: Path) -> None:
        from watchdog.events import FileModifiedEvent

        mocker.patch("time.time", return_value=100.0)
        for file in files:
            handler.on_modified(FileModifiedEvent(str(file)))
        mocker.patch("time.time", return_value=102.0)
        try:
            handler.process_pending_files()
        finally:
            handler.logger.close()

    def test_deletes_old_backups_after_the_file_left_the_pending_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.backup import list_backup_groups
        from trs_file_backup.retention import RetentionRules

        state = Mock()
        handler, source, dest, output = self._handler(mocker, tmp_path, RetentionRules(days=1), state)
        old = _old_backups(dest, "report.txt")
        file = source / "report.txt"
        file.write_text("new")
        seen: list[tuple[bool, bool, bool]] = []

        def check(destination: Path) -> Any:
            seen.append((file in handler.pending_files, state.update_file_timestamp.called, state.save.called))
            return list_backup_groups(destination)

        mocker.patch("trs_file_backup.main.list_backup_groups", side_effect=check)

        self._process(mocker, handler, file)

        assert seen == [(False, True, True)]
        assert not any(path.exists() for path in old)
        assert _backed_up(dest, "report", ".txt")
        assert f"Deleted old backup: {old[0].name}" in output.getvalue().splitlines()
        assert f"[INFO] Deleted old backup: {old[0].name}" in _log(dest)

    def test_the_backup_just_made_is_kept_when_a_future_backup_sorts_as_newer(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.retention import RetentionRules

        handler, source, dest, _ = self._handler(mocker, tmp_path, RetentionRules(days=1))
        (older,) = _old_backups(dest, "report.txt", count=1)
        future = dest / "report_2999_01_01__00_00_00.txt"
        future.write_text("future")
        file = source / "report.txt"
        file.write_text("new")

        self._process(mocker, handler, file)

        assert handler.backed_up_count == 1
        assert future.exists()
        assert not older.exists()
        assert len(_new_backup_names(dest, "report")) == 1

    def test_a_failed_state_save_still_applies_the_rules(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.retention import RetentionRules

        state = Mock()
        state.save.side_effect = OSError(errno.ENOSPC, "No space left on device")
        handler, source, dest, _ = self._handler(mocker, tmp_path, RetentionRules(days=1), state)
        old = _old_backups(dest, "report.txt")
        file = source / "report.txt"
        file.write_text("new")

        self._process(mocker, handler, file)

        assert not any(path.exists() for path in old)

    @pytest.mark.parametrize("error", [OSError(errno.EIO, "Input/output error"), RuntimeError("Input/output error")], ids=["oserror", "other-error"])
    def test_a_failed_listing_is_reported_each_time_and_watch_goes_on(self, mocker: MockFixture, tmp_path: Path, error: Exception) -> None:
        from trs_file_backup.retention import RetentionRules

        handler, source, dest, output = self._handler(mocker, tmp_path, RetentionRules(days=1))
        old = _old_backups(dest, "a.txt")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups", side_effect=error)
        files = [source / "a.txt", source / "b.txt"]
        for file in files:
            file.write_text("new")

        self._process(mocker, handler, *files)

        assert handler.backed_up_count == 2
        assert handler.pending_files == {}
        assert listing.call_count == 2
        assert all(path.exists() for path in old)
        message = f"Cannot list backups in {dest}: Input/output error"
        assert output.getvalue().splitlines().count(f"ERROR {message}") == 2
        assert _log(dest).count(f"[ERROR] {message}") == 2

    def test_a_failed_deletion_does_not_end_watch(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.retention import RetentionRules

        handler, source, dest, output = self._handler(mocker, tmp_path, RetentionRules(days=1))
        (old,) = _old_backups(dest, "a.txt", count=1)
        mocker.patch.object(Path, "unlink", side_effect=OSError(errno.EIO, "Input/output error"))
        files = [source / "a.txt", source / "b.txt"]
        for file in files:
            file.write_text("new")

        self._process(mocker, handler, *files)

        assert handler.backed_up_count == 2
        assert old.exists()
        assert f"ERROR Cannot delete backup: {old.name} (Input/output error)" in output.getvalue().splitlines()

    def test_without_rules_nothing_is_listed(self, mocker: MockFixture, tmp_path: Path) -> None:
        handler, source, dest, _ = self._handler(mocker, tmp_path, None)
        old = _old_backups(dest, "a.txt")
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")
        file = source / "a.txt"
        file.write_text("new")

        self._process(mocker, handler, file)

        listing.assert_not_called()
        assert all(path.exists() for path in old)

    def test_a_failed_backup_applies_no_rules(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.retention import RetentionRules

        handler, source, dest, _ = self._handler(mocker, tmp_path, RetentionRules(days=1))
        old = _old_backups(dest, "a.txt")
        mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=OSError(errno.ENOSPC, "No space left on device"))
        listing = mocker.patch("trs_file_backup.main.list_backup_groups")
        file = source / "a.txt"
        file.write_text("new")

        self._process(mocker, handler, file)

        listing.assert_not_called()
        assert all(path.exists() for path in old)

    def test_watch_passes_the_rules_it_started_with(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import BackupEventHandler, app
        from trs_file_backup.retention import RetentionRules

        source, dest = _with_rules(tmp_path, EXAMPLE_RULES)
        mocker.patch("trs_file_backup.main.Observer")
        mocker.patch("time.sleep", side_effect=KeyboardInterrupt())
        handler_spy = mocker.patch("trs_file_backup.main.BackupEventHandler", wraps=BackupEventHandler)

        result = runner.invoke(app, ["watch", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert handler_spy.call_args.kwargs["retention"] == RetentionRules(**EXAMPLE_RULES)
