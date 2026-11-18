"""Tests for file backup operations."""

import errno
import os
import re
import stat
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockFixture


def _windows_long_paths_disabled() -> bool:
    """Tell whether Windows limits a full path to 260 characters (registry value LongPathsEnabled not 1)."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
                return bool(winreg.QueryValueEx(key, "LongPathsEnabled")[0] != 1)
        except OSError:
            return True
    else:
        return False


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

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            (".gitignore", "hidden"),
            (".backup_state.json", "hidden"),
            ("debug.log", "*.log"),
            ("temp_debug.log", "temp_*"),
            ("report.txt", None),
        ],
    )
    def test_exclusion_reason(self, filename: str, expected: str | None) -> None:
        """A hidden name gives the hidden-file reason (AC-4.1); otherwise the first matching pattern (AC-6.17)."""
        from trs_file_backup.backup import BackupManager, ExclusionReason

        reason = BackupManager.exclusion_reason(filename, [".backup_state.json", "temp_*", "*.log"])

        if expected is None:
            assert reason is None
        elif expected == "hidden":
            assert reason == ExclusionReason(pattern=None)
        else:
            assert reason == ExclusionReason(pattern=expected)

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

    def test_backup_file_copies_file(self, tmp_path: Path) -> None:
        """Test that backup_file copies the file with correct name."""
        from trs_file_backup.backup import BackupManager

        source = tmp_path / "source"
        source.mkdir()
        source_file = source / "file.txt"
        source_file.write_text("content", encoding="utf-8")
        dest = tmp_path / "dest"
        dest.mkdir()

        manager = BackupManager(source_path=source, destination_path=dest, excluded_patterns=[], state=None)

        result = manager.backup_file(source_file, datetime(2026, 1, 13, 14, 30, 22))

        assert result == dest / "file_2026_01_13__14_30_22.txt"
        assert result.read_text(encoding="utf-8") == "content"

    def test_backup_file_creates_destination_dir(self, tmp_path: Path) -> None:
        """Test that backup_file creates destination directory if needed."""
        from trs_file_backup.backup import BackupManager

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content", encoding="utf-8")
        dest = tmp_path / "missing" / "dest"

        manager = BackupManager(source_path=source, destination_path=dest, excluded_patterns=[], state=None)

        result = manager.backup_file(source / "file.txt", datetime(2026, 1, 13, 14, 30, 22))

        assert result.is_file()

    def test_backup_file_handles_permission_error(self, mocker: MockFixture) -> None:
        """Test that backup_file handles permission errors gracefully."""
        from trs_file_backup.backup import BackupManager

        _mock_copy = mocker.patch("shutil.copyfile", side_effect=PermissionError("Access denied"))
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

    def test_backup_file_passes_other_os_errors_on(self, mocker: MockFixture) -> None:
        """Test that backup_file raises an OSError of the copy to its caller."""
        from trs_file_backup.backup import BackupManager

        _mock_copy = mocker.patch("shutil.copyfile", side_effect=OSError(errno.ENOSPC, "No space left on device"))
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


class TestFailedCopy:
    """The data is copied to a temporary file and renamed to the backup name when complete (spec AC-2.8)."""

    BACKUP_NAME = "report_2026_01_13__14_30_22.txt"
    TEMPORARY_NAME = re.compile(r"\.trs-file-backup-[0-9a-f]{12}\.tmp")

    @staticmethod
    def _copy_half_then_fail(source: Path, destination: Path, **_: object) -> None:
        """Stand-in for shutil.copyfile that writes part of the file and then fails like a full disk."""
        destination.write_bytes(source.read_bytes()[:3])
        raise OSError(errno.ENOSPC, "No space left on device")

    @staticmethod
    def _source_and_destination(tmp_path: Path) -> tuple[Path, Path]:
        source = tmp_path / "source"
        source.mkdir()
        (source / "report.txt").write_text("full content", encoding="utf-8")
        dest = tmp_path / "dest"
        dest.mkdir()
        return source, dest

    def _backup(self, source: Path, dest: Path) -> Path:
        from trs_file_backup.backup import BackupManager

        manager = BackupManager(source_path=source, destination_path=dest, excluded_patterns=[], state=None)
        return manager.backup_file(source / "report.txt", datetime(2026, 1, 13, 14, 30, 22))

    def test_a_failed_data_copy_leaves_no_file_behind(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        copyfile = mocker.patch("shutil.copyfile", side_effect=self._copy_half_then_fail)

        with pytest.raises(OSError, match="No space left on device"):
            self._backup(source, dest)

        temporary_file = copyfile.call_args.args[1]
        assert temporary_file.parent == dest
        assert self.TEMPORARY_NAME.fullmatch(temporary_file.name)
        assert list(dest.iterdir()) == []

    def test_a_failed_rename_of_a_read_only_copy_leaves_no_temporary_file(self, mocker: MockFixture, tmp_path: Path) -> None:
        """On Windows the copied read-only bit blocks the removal until the cleanup clears it."""
        source, dest = self._source_and_destination(tmp_path)
        source_file = source / "report.txt"
        source_file.chmod(stat.S_IREAD)
        mocker.patch("os.replace", side_effect=PermissionError(errno.EACCES, "Access is denied"))

        try:
            with pytest.raises(PermissionError, match="Access is denied"):
                self._backup(source, dest)
        finally:
            source_file.chmod(stat.S_IREAD | stat.S_IWRITE)

        assert list(dest.iterdir()) == []

    # The full path of a 255-character name in the pytest temp folder is longer than 260 characters
    @pytest.mark.skipif(_windows_long_paths_disabled(), reason="Windows long paths are disabled")
    def test_a_backup_name_of_255_characters_works(self, tmp_path: Path) -> None:
        from trs_file_backup.backup import BackupManager

        source, dest = self._source_and_destination(tmp_path)
        source_file = source / ("n" * 230 + ".txt")
        source_file.write_text("full content", encoding="utf-8")
        manager = BackupManager(source_path=source, destination_path=dest, excluded_patterns=[], state=None)

        backup = manager.backup_file(source_file, datetime(2026, 1, 13, 14, 30, 22))

        assert len(backup.name) == 255
        assert backup.read_text(encoding="utf-8") == "full content"
        assert list(dest.iterdir()) == [backup]

    def test_a_failed_data_copy_leaves_an_older_backup_of_the_same_name_unchanged(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        older = dest / self.BACKUP_NAME
        older.write_text("earlier backup", encoding="utf-8")
        mocker.patch("shutil.copyfile", side_effect=self._copy_half_then_fail)

        with pytest.raises(OSError, match="No space left on device"):
            self._backup(source, dest)

        assert older.read_text(encoding="utf-8") == "earlier backup"
        assert list(dest.iterdir()) == [older]

    def test_a_failed_rename_leaves_no_temporary_file(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        mocker.patch("os.replace", side_effect=PermissionError(errno.EACCES, "Access is denied"))

        with pytest.raises(PermissionError, match="Access is denied"):
            self._backup(source, dest)

        assert list(dest.iterdir()) == []

    def test_raises_the_copy_error_when_the_removal_fails_too(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        mocker.patch("shutil.copyfile", side_effect=self._copy_half_then_fail)
        mocker.patch("pathlib.Path.unlink", side_effect=PermissionError("in use"))

        with pytest.raises(OSError, match="No space left on device"):
            self._backup(source, dest)

    def test_a_failed_metadata_copy_keeps_the_complete_backup(self, mocker: MockFixture, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        mocker.patch("shutil.copystat", side_effect=PermissionError(errno.EPERM, "Operation not permitted"))

        backup = self._backup(source, dest)

        assert backup == dest / self.BACKUP_NAME
        assert backup.read_text(encoding="utf-8") == "full content"
        assert list(dest.iterdir()) == [backup]

    def test_a_normal_backup_leaves_no_temporary_file_and_keeps_the_times(self, tmp_path: Path) -> None:
        source, dest = self._source_and_destination(tmp_path)
        os.utime(source / "report.txt", (1_700_000_000, 1_700_000_000))

        backup = self._backup(source, dest)

        assert backup.read_text(encoding="utf-8") == "full content"
        assert list(dest.iterdir()) == [backup]
        assert backup.stat().st_mtime == 1_700_000_000

    def test_a_successful_backup_replaces_a_file_of_the_same_name(self, tmp_path: Path) -> None:
        """Characterizes the same-second name collision: a complete copy takes the name, as shutil.copy2 did before."""
        source, dest = self._source_and_destination(tmp_path)
        (dest / self.BACKUP_NAME).write_text("earlier backup", encoding="utf-8")

        backup = self._backup(source, dest)

        assert backup.read_text(encoding="utf-8") == "full content"


class TestClassifyBackupError:
    """Each OS error of a backup gets one of three causes (spec AC-6.18)."""

    @pytest.mark.parametrize(
        ("error", "winerror", "expected"),
        [
            (PermissionError(errno.EACCES, "sharing violation"), 32, "LOCKED"),
            (PermissionError(errno.EACCES, "lock violation"), 33, "LOCKED"),
            (PermissionError(errno.EACCES, "Permission denied"), None, "PERMISSION_DENIED"),
            (PermissionError(errno.EACCES, "Access is denied"), 5, "PERMISSION_DENIED"),
            (BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable"), None, "LOCKED"),
            (OSError(errno.EBUSY, "Device or resource busy"), None, "LOCKED"),
            (OSError(errno.ENOSPC, "No space left on device"), None, "OTHER"),
            (OSError(errno.ENAMETOOLONG, "File name too long"), None, "OTHER"),
            (FileNotFoundError(errno.ENOENT, "No such file or directory"), None, "OTHER"),
            (OSError("x"), None, "OTHER"),
            (OSError(), None, "OTHER"),
        ],
        ids=["winerror-32", "winerror-33", "permission", "winerror-5", "blocking", "ebusy", "enospc", "enametoolong", "vanished", "bare", "empty"],
    )
    def test_classifies(self, with_winerror: Callable[[OSError, int], OSError], error: OSError, winerror: int | None, expected: str) -> None:
        from trs_file_backup.backup import BackupErrorKind, classify_backup_error

        if winerror is not None:
            error = with_winerror(error, winerror)

        assert classify_backup_error(error) is BackupErrorKind[expected]

    @pytest.mark.parametrize(
        ("error", "reason"),
        [
            (OSError(errno.ENOSPC, "No space left on device"), "No space left on device"),
            (OSError("[WinError 33] cannot copy"), "[WinError 33] cannot copy"),
            (OSError(), "OSError"),
        ],
        ids=["strerror", "message", "empty"],
    )
    def test_reason(self, error: OSError, reason: str) -> None:
        from trs_file_backup.backup import backup_error_reason

        assert backup_error_reason(error) == reason
