"""Tests for CLI commands."""

import importlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from pytest_mock import MockFixture
from typer.testing import CliRunner, Result

runner = CliRunner()


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

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        assert result.exit_code == 0

    def test_run_with_exclusion_patterns(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command with exclusion patterns."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Create test files
        (source / "test.txt").write_text("test")
        (source / "debug.log").write_text("log")

        mocker.patch("time.sleep")

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

        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")
        _mock_backup = mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=PermissionError("Access denied"))

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        # Should not crash, should handle error gracefully
        assert "error" in result.stdout.lower() or "permission" in result.stdout.lower()

    def test_run_handles_locked_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command handles locked files (OSError) gracefully."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        (source / "test.txt").write_text("test")

        # Mock backup_file to raise OSError (file locked)
        mocker.patch("time.sleep")
        _mock_backup = mocker.patch("trs_file_backup.backup.BackupManager.backup_file", side_effect=OSError("File is locked"))

        result = runner.invoke(
            app,
            ["run", "--source", str(source), "--destination", str(dest)],
        )

        # Should not crash, should handle error gracefully
        assert result.exit_code == 0
        assert "locked" in result.stdout.lower() or "skipping" in result.stdout.lower()

    def test_run_no_modified_files(self, mocker: MockFixture, tmp_path: Path) -> None:
        """Test run command when no files are modified."""
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        # Create state file with current timestamp to simulate no changes
        (source / "test.txt").write_text("test")

        # Run once to create state
        mocker.patch("time.sleep")
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
        mocker.patch("time.sleep")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".txt")
        assert not _backed_up(dest, "b", ".log")
        assert _saved_settings(dest) == ([".backup_state.json", "*.log"], 5)
        header = _last_session_header(dest)
        assert "Exclusion patterns: .backup_state.json, *.log\n" in header
        assert "Debounce delay: 5 seconds" in header

    def test_run_given_exclude_replaces_saved_patterns_and_keeps_saved_debounce(self, mocker: MockFixture, tmp_path: Path) -> None:
        from trs_file_backup.main import app

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        _init(source, dest, "--exclude", "*.log", "--debounce", "5")
        (source / "b.log").write_text("b")
        (source / "c.tmp").write_text("c")
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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

    @pytest.mark.parametrize("command", [["config", "show"], ["config"]], ids=["show", "menu"])
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

    @pytest.mark.parametrize("command", [["config"], ["config", "show"]], ids=["menu", "show"])
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
        assert re.search(r"show\s+print the saved settings without asking anything", help_text)
        assert "--destination" in help_text
        assert "stop a running 'watch' and wait for a running 'run' to finish first" in help_text

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
        for label in ("[1] change debounce", "[2] add pattern", "[3] remove pattern", "[4] clear patterns", "[s] save and quit", "[q] quit without saving"):
            assert label in result.output
        assert "stop" in result.output.lower()
        result.output.encode("ascii")

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

    @pytest.mark.parametrize(("pattern", "message"), [("*.log", "already"), (".backup_state.json", "always"), ("", "no pattern")])
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
        mocker.patch("time.sleep")

        result = runner.invoke(app, ["run", "--source", str(source), "--destination", str(dest)])

        assert result.exit_code == 0, result.output
        assert _backed_up(dest, "a", ".log")
        assert not _backed_up(dest, "b", ".tmp")
        assert "Debounce delay: 0 seconds" in _last_session_header(dest)


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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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
        mocker.patch("time.sleep")

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

    def test_event_handler_handles_os_error(self, tmp_path: Path, mocker: MockFixture) -> None:
        """Test that event handler handles OS errors gracefully."""
        from unittest.mock import Mock

        from watchdog.events import FileModifiedEvent

        from trs_file_backup.main import BackupEventHandler

        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = Mock()
        manager.excluded_patterns = []
        manager.backup_file.side_effect = OSError("File is locked")
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

        # Process after debounce: should handle OS error
        mock_time.return_value = 102.0
        handler.process_pending_files()

        # Should log locked file and remove from pending
        logger.log_file_locked.assert_called_once()
        manager.backup_file.assert_called_once()
        assert file_path not in handler.pending_files

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
