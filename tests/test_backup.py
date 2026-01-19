"""Tests for file backup operations."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockFixture


class TestFileOperations:
    """Test suite for file backup operations."""

    def test_generate_backup_filename(self) -> None:
        """Test generation of timestamped backup filename."""
        from trs_file_backup.backup import BackupManager

        test_time = datetime(2026, 1, 13, 14, 30, 22)

        result = BackupManager.generate_backup_filename("report.txt", test_time)

        assert result == "report_2026_01_13__14_30_22.txt"

    def test_generate_backup_filename_with_path(self) -> None:
        """Test backup filename generation strips path and keeps only filename."""
        from trs_file_backup.backup import BackupManager

        test_time = datetime(2026, 1, 13, 14, 30, 22)

        result = BackupManager.generate_backup_filename("subdir/report.txt", test_time)

        assert result == "report_2026_01_13__14_30_22.txt"

    def test_matches_exclusion_pattern_exact_match(self) -> None:
        """Test exact filename match in exclusion patterns."""
        from trs_file_backup.backup import BackupManager

        patterns = [".backup_state.json", "temp.txt"]

        assert BackupManager.matches_exclusion_pattern("temp.txt", patterns) is True
        assert BackupManager.matches_exclusion_pattern("other.txt", patterns) is False

    def test_matches_exclusion_pattern_wildcard(self) -> None:
        """Test wildcard matching in exclusion patterns."""
        from trs_file_backup.backup import BackupManager

        patterns = ["*.log", "temp_*"]

        assert BackupManager.matches_exclusion_pattern("debug.log", patterns) is True
        assert BackupManager.matches_exclusion_pattern("temp_file.txt", patterns) is True
        assert BackupManager.matches_exclusion_pattern("report.txt", patterns) is False

    def test_matches_exclusion_pattern_hidden_files(self) -> None:
        """Test that hidden files (starting with .) are excluded."""
        from trs_file_backup.backup import BackupManager

        patterns = [".backup_state.json"]

        assert BackupManager.matches_exclusion_pattern(".hidden", patterns) is True
        assert BackupManager.matches_exclusion_pattern(".gitignore", patterns) is True
        assert BackupManager.matches_exclusion_pattern("normal.txt", patterns) is False

    def test_get_files_to_backup_all_new_files(self, mocker: MockFixture) -> None:
        """Test getting files when no state exists (first run)."""
        from trs_file_backup.backup import BackupManager

        mock_source = Mock(spec=Path)
        mock_file1 = Mock(spec=Path)
        mock_file1.name = "file1.txt"
        mock_file1.is_dir.return_value = False
        mock_file1.stat.return_value.st_mtime = 1000.0

        mock_file2 = Mock(spec=Path)
        mock_file2.name = "file2.txt"
        mock_file2.is_dir.return_value = False
        mock_file2.stat.return_value.st_mtime = 1100.0

        mock_source.iterdir.return_value = [mock_file1, mock_file2]

        manager = BackupManager(
            source_path=mock_source,
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        files = manager.get_files_to_backup()

        assert len(files) == 2
        assert mock_file1 in files
        assert mock_file2 in files

    def test_get_files_to_backup_excludes_directories(self, mocker: MockFixture) -> None:
        """Test that subdirectories are excluded from backup."""
        from trs_file_backup.backup import BackupManager

        mock_source = Mock(spec=Path)
        mock_file = Mock(spec=Path)
        mock_file.name = "file.txt"
        mock_file.is_dir.return_value = False
        mock_file.stat.return_value.st_mtime = 1000.0

        mock_dir = Mock(spec=Path)
        mock_dir.name = "subdir"
        mock_dir.is_dir.return_value = True

        mock_source.iterdir.return_value = [mock_file, mock_dir]

        manager = BackupManager(
            source_path=mock_source,
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        files = manager.get_files_to_backup()

        assert len(files) == 1
        assert mock_file in files
        assert mock_dir not in files

    def test_get_files_to_backup_applies_exclusion_patterns(self, mocker: MockFixture) -> None:
        """Test that exclusion patterns are applied."""
        from trs_file_backup.backup import BackupManager

        mock_source = Mock(spec=Path)

        mock_file1 = Mock(spec=Path)
        mock_file1.name = "file.txt"
        mock_file1.is_dir.return_value = False
        mock_file1.stat.return_value.st_mtime = 1000.0

        mock_file2 = Mock(spec=Path)
        mock_file2.name = "debug.log"
        mock_file2.is_dir.return_value = False
        mock_file2.stat.return_value.st_mtime = 1100.0

        mock_source.iterdir.return_value = [mock_file1, mock_file2]

        manager = BackupManager(
            source_path=mock_source,
            destination_path=Path("/dest"),
            excluded_patterns=["*.log"],
            state=None,
        )

        files = manager.get_files_to_backup()

        assert len(files) == 1
        assert mock_file1 in files
        assert mock_file2 not in files

    def test_get_files_to_backup_only_modified(self, mocker: MockFixture) -> None:
        """Test that only modified files are returned when state exists."""
        from trs_file_backup.backup import BackupManager
        from trs_file_backup.state import StateManager

        mock_source = Mock(spec=Path)

        mock_file1 = Mock(spec=Path)
        mock_file1.name = "file1.txt"
        mock_file1.is_dir.return_value = False
        mock_file1.stat.return_value.st_mtime = 1500.0  # Modified

        mock_file2 = Mock(spec=Path)
        mock_file2.name = "file2.txt"
        mock_file2.is_dir.return_value = False
        mock_file2.stat.return_value.st_mtime = 500.0  # Not modified

        mock_source.iterdir.return_value = [mock_file1, mock_file2]

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={"file1.txt": 1000.0, "file2.txt": 1000.0},
        )

        manager = BackupManager(
            source_path=mock_source,
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=state,
        )

        files = manager.get_files_to_backup()

        assert len(files) == 1
        assert mock_file1 in files
        assert mock_file2 not in files

    def test_backup_file_copies_file(self, mocker: MockFixture) -> None:
        """Test that backup_file copies the file with correct name."""
        from trs_file_backup.backup import BackupManager

        mock_copy = mocker.patch("shutil.copy2")
        _mock_mkdir = mocker.patch("pathlib.Path.mkdir")

        source_file = Path("/source/file.txt")

        manager = BackupManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        test_time = datetime(2026, 1, 13, 14, 30, 22)
        result = manager.backup_file(source_file, test_time)

        expected_dest = Path("/dest") / "file_2026_01_13__14_30_22.txt"
        mock_copy.assert_called_once_with(source_file, expected_dest)
        assert result == expected_dest

    def test_backup_file_creates_destination_dir(self, mocker: MockFixture) -> None:
        """Test that backup_file creates destination directory if needed."""
        from trs_file_backup.backup import BackupManager

        _mock_copy = mocker.patch("shutil.copy2")
        mock_mkdir = mocker.patch("pathlib.Path.mkdir")

        source_file = Path("/source/file.txt")

        manager = BackupManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        test_time = datetime(2026, 1, 13, 14, 30, 22)
        manager.backup_file(source_file, test_time)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_backup_file_handles_permission_error(self, mocker: MockFixture) -> None:
        """Test that backup_file handles permission errors gracefully."""
        from trs_file_backup.backup import BackupManager

        _mock_copy = mocker.patch("shutil.copy2", side_effect=PermissionError("Access denied"))
        _mock_mkdir = mocker.patch("pathlib.Path.mkdir")

        source_file = Path("/source/file.txt")

        manager = BackupManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        test_time = datetime(2026, 1, 13, 14, 30, 22)

        with pytest.raises(PermissionError):
            manager.backup_file(source_file, test_time)

    def test_backup_file_handles_locked_file(self, mocker: MockFixture) -> None:
        """Test that backup_file handles locked files (OSError)."""
        from trs_file_backup.backup import BackupManager

        _mock_copy = mocker.patch("shutil.copy2", side_effect=OSError("File is locked"))
        _mock_mkdir = mocker.patch("pathlib.Path.mkdir")

        source_file = Path("/source/file.txt")

        manager = BackupManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            excluded_patterns=[],
            state=None,
        )

        test_time = datetime(2026, 1, 13, 14, 30, 22)

        with pytest.raises(OSError):
            manager.backup_file(source_file, test_time)
