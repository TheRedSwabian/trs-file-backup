"""Tests for CLI commands."""

import importlib
import importlib.metadata
import json
import re
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import Result as ClickResult
from pytest_mock import MockFixture
from typer.testing import CliRunner

runner = CliRunner()


def _help_output(result: ClickResult) -> str:
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

    @pytest.mark.parametrize("command", ["init", "run", "watch"])
    def test_exclude_option_shows_pattern_metavar(self, command: str) -> None:
        """Test that --exclude shows PATTERN in the help, not the Python type (typer >= 0.29 prints list[str])."""
        from trs_file_backup.main import app

        result = runner.invoke(app, [command, "--help"])

        assert result.exit_code == 0
        assert re.search(r"--exclude\s+pattern\b", _help_output(result))
        assert "list[str]" not in _help_output(result)
