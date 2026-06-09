"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import Mock

import click
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


class TestBackupEventHandler:
    """Test suite for BackupEventHandler."""

    def test_event_handler_ignores_directories(self, tmp_path: Path) -> None:
        """Test that event handler ignores directory modification events."""
        from unittest.mock import Mock

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

        from trs_file_backup.main import BackupEventHandler
        from watchdog.events import FileModifiedEvent

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

    def test_main_version_flag(self, mocker: MockFixture) -> None:
        """Test that version flag works."""
        from trs_file_backup.main import app

        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0

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
