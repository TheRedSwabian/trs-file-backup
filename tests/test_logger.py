"""Tests for logging functionality."""

from pathlib import Path
from unittest.mock import Mock, call, mock_open, patch

import pytest


class TestBackupLogger:
    """Test suite for BackupLogger class."""

    def test_logger_initialization_creates_log_file(self, mocker):
        """Test that logger creates log file on initialization."""
        from trs_file_backup.logger import BackupLogger

        mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        mock_handler = mocker.patch("logging.FileHandler")
        mock_logger = mocker.patch("logging.getLogger")

        logger = BackupLogger(Path("/dest"))

        mock_mkdir.assert_called_once()
        mock_handler.assert_called_once()

    def test_log_session_start(self, mocker):
        """Test logging session start with configuration."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []  # Set handlers as empty list for iteration
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_session_start(
            command="run",
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            excluded_patterns=["*.log"],
            debounce_seconds=2,
        )

        # Check that session started log was written
        calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Session Started" in str(call) for call in calls)
        assert any("Command: run" in str(call) for call in calls)
        assert any("Source:" in str(call) for call in calls)
        assert any("Destination:" in str(call) for call in calls)
        assert any("Exclusion patterns:" in str(call) for call in calls)
        assert any("Debounce delay: 2" in str(call) for call in calls)

    def test_log_session_end(self, mocker):
        """Test logging session end with summary."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_session_end(files_backed_up=5, files_total=10)

        calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Session Ended" in str(call) for call in calls)

    def test_log_file_backed_up(self, mocker):
        """Test logging successful file backup."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_file_backed_up("file.txt", "2026_01_13__14_30_22__file.txt")

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "Backed up:" in call_str
        assert "file.txt" in call_str

    def test_log_file_excluded(self, mocker):
        """Test logging excluded file with pattern."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_file_excluded("debug.log", "*.log")

        mock_logger.warning.assert_called()
        call_str = str(mock_logger.warning.call_args)
        assert "excluded" in call_str.lower()
        assert "debug.log" in call_str

    def test_log_file_locked(self, mocker):
        """Test logging locked file warning."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_file_locked("database.db")

        mock_logger.warning.assert_called()
        call_str = str(mock_logger.warning.call_args)
        assert "locked" in call_str.lower()
        assert "database.db" in call_str

    def test_log_error(self, mocker):
        """Test logging errors."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_error("Permission denied: secure.dat")

        mock_logger.error.assert_called()
        call_str = str(mock_logger.error.call_args)
        assert "Permission denied" in call_str

    def test_log_file_modified_watch_mode(self, mocker):
        """Test logging file modification in watch mode."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_file_modified("config.yaml")

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "modified" in call_str.lower()
        assert "config.yaml" in call_str

    def test_log_watch_started(self, mocker):
        """Test logging watch mode started."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_watch_started()

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "watch" in call_str.lower() or "monitor" in call_str.lower()

    def test_log_watch_stopped(self, mocker):
        """Test logging watch mode stopped."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_watch_stopped()

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "stopped" in call_str.lower()

    def test_logger_uses_utf8_encoding(self, mocker):
        """Test that logger uses UTF-8 encoding for log file."""
        from trs_file_backup.logger import BackupLogger

        mock_handler = mocker.patch("logging.FileHandler")
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.getLogger")

        logger = BackupLogger(Path("/dest"))

        # Check that FileHandler was called with encoding parameter
        call_kwargs = mock_handler.call_args[1] if mock_handler.call_args else {}
        assert call_kwargs.get("encoding") == "utf-8"

    def test_logger_appends_to_existing_file(self, mocker):
        """Test that logger appends to existing log file."""
        from trs_file_backup.logger import BackupLogger

        mock_handler = mocker.patch("logging.FileHandler")
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.getLogger")

        logger = BackupLogger(Path("/dest"))

        # Check that FileHandler was called with append mode
        call_args = mock_handler.call_args[0] if mock_handler.call_args else ()
        call_kwargs = mock_handler.call_args[1] if mock_handler.call_args else {}
        mode = call_kwargs.get("mode", "a")
        assert mode == "a"

    def test_log_init_success(self, mocker):
        """Test logging successful initialization."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_init_success()

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "initialized" in call_str.lower() or "init" in call_str.lower()

    def test_log_found_files(self, mocker):
        """Test logging number of files found."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_found_files(15)

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "15" in call_str
        assert "files" in call_str.lower() or "found" in call_str.lower()

    def test_log_backup_completed(self, mocker):
        """Test logging backup operation completion."""
        from trs_file_backup.logger import BackupLogger

        mock_logger = Mock()
        mock_logger.handlers = []
        mocker.patch("logging.getLogger", return_value=mock_logger)
        mocker.patch("pathlib.Path.mkdir")
        mocker.patch("logging.FileHandler")

        logger = BackupLogger(Path("/dest"))
        logger.log_backup_completed(13, 15)

        mock_logger.info.assert_called()
        call_str = str(mock_logger.info.call_args)
        assert "13" in call_str
        assert "15" in call_str
        assert "completed" in call_str.lower()
