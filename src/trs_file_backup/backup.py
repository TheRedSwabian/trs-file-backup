"""File backup operations."""

import contextlib
import errno
import os
import secrets
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from trs_file_backup.state import StateManager

# ERROR_SHARING_VIOLATION and ERROR_LOCK_VIOLATION: Windows raises PermissionError with one of these for a locked file
_WINDOWS_LOCK_ERRORS = (32, 33)


class BackupErrorKind(Enum):
    """Cause of a failed backup, which decides the message and its log level (spec AC-6.18)."""

    LOCKED = "locked"
    PERMISSION_DENIED = "permission denied"
    OTHER = "other"


def classify_backup_error(error: OSError) -> BackupErrorKind:
    """Return the cause of an OS error raised while backing up a file (spec AC-6.18).

    A lock is checked first, because Windows reports a locked file as PermissionError (errno EACCES) and only its Windows error tells it apart.
    The attribute winerror exists only on Windows.
    """
    if getattr(error, "winerror", None) in _WINDOWS_LOCK_ERRORS or isinstance(error, BlockingIOError) or error.errno == errno.EBUSY:
        return BackupErrorKind.LOCKED
    if isinstance(error, PermissionError):
        return BackupErrorKind.PERMISSION_DENIED
    return BackupErrorKind.OTHER


def backup_error_reason(error: OSError) -> str:
    """Return the error text of the operating system, else the message, else the name of the error class."""
    return error.strerror or str(error) or type(error).__name__


@dataclass(frozen=True)
class ExclusionReason:
    """Why a file is excluded: the first matching pattern, or None for a hidden file (spec AC-4.1)."""

    pattern: str | None


class BackupManager:
    """Manages file backup operations."""

    def __init__(
        self,
        source_path: Path,
        destination_path: Path,
        excluded_patterns: list[str],
        state: StateManager | None,
    ):
        """Initialize backup manager.

        Args:
            source_path: Source directory path
            destination_path: Destination directory path
            excluded_patterns: List of exclusion patterns
            state: StateManager instance or None
        """
        self.source_path = source_path
        self.destination_path = destination_path
        self.excluded_patterns = excluded_patterns
        self.state = state

    @staticmethod
    def generate_backup_filename(filename: str, timestamp: datetime) -> str:
        """Generate timestamped backup filename.

        Args:
            filename: Original filename (can include path)
            timestamp: Timestamp for the backup

        Returns:
            Formatted filename: filename_YYYY_MM_DD__HH_MM_SS.ext
        """
        # Extract just the filename if path is included
        path = Path(filename)
        name_without_ext = path.stem
        extension = path.suffix
        timestamp_str = timestamp.strftime("%Y_%m_%d__%H_%M_%S")
        return f"{name_without_ext}_{timestamp_str}{extension}"

    @staticmethod
    def exclusion_reason(filename: str, patterns: list[str]) -> ExclusionReason | None:
        """Return why filename is excluded, or None if it is not excluded.

        Hidden files (starting with .) are always excluded (spec AC-4.1), before any pattern is checked.

        Args:
            filename: Filename to check
            patterns: List of exclusion patterns (supports wildcards)

        Returns:
            ExclusionReason(pattern=None) for a hidden file, ExclusionReason(pattern=...) with the first
            matching pattern, or None if the file is not excluded
        """
        if filename.startswith("."):
            return ExclusionReason(pattern=None)

        path = Path(filename)
        for pattern in patterns:
            if path.match(pattern):
                return ExclusionReason(pattern=pattern)

        return None

    @staticmethod
    def matches_exclusion_pattern(filename: str, patterns: list[str]) -> bool:
        """Check if filename is excluded (see exclusion_reason).

        Args:
            filename: Filename to check
            patterns: List of exclusion patterns (supports wildcards)

        Returns:
            True if filename should be excluded, False otherwise
        """
        return BackupManager.exclusion_reason(filename, patterns) is not None

    def get_files_to_backup(self) -> list[Path]:
        """Get list of files that need to be backed up.

        Returns:
            List of file paths that should be backed up
        """
        files_to_backup = []

        # Iterate only top-level files (no subdirectories)
        for item in self.source_path.iterdir():
            # Skip directories
            if item.is_dir():
                continue

            # Skip excluded files
            if self.matches_exclusion_pattern(item.name, self.excluded_patterns):
                continue

            # If no state exists, backup all files
            if self.state is None:
                files_to_backup.append(item)
                continue

            # Check if file is modified
            current_mtime = item.stat().st_mtime
            if self.state.is_modified(item.name, current_mtime):
                files_to_backup.append(item)

        return files_to_backup

    def backup_file(self, source_file: Path, timestamp: datetime) -> Path:
        """Backup a single file with timestamp.

        Args:
            source_file: Path to source file
            timestamp: Timestamp for backup filename

        Returns:
            Path to the created backup file

        Raises:
            OSError: If the data copy or the rename fails; classify_backup_error tells its cause.
                The temporary file is removed first, and a file that already has the backup name stays unchanged (spec AC-2.8).
        """
        # Ensure destination directory exists
        self.destination_path.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        backup_filename = self.generate_backup_filename(source_file.name, timestamp)
        destination_file = self.destination_path / backup_filename

        # The backup name appears only for a complete copy: a failed copy never leaves a partial file under it (spec AC-2.8).
        # The temporary name has a fixed length, so a long backup name cannot make it too long.
        temporary_file = self.destination_path / f".trs-file-backup-{secrets.token_hex(6)}.tmp"
        try:
            shutil.copyfile(source_file, temporary_file)
            # The data is complete, so a failed metadata copy does not fail the backup
            with contextlib.suppress(OSError):
                shutil.copystat(source_file, temporary_file)
            os.replace(temporary_file, destination_file)
        except OSError:
            # copystat copies the read-only bit, which on Windows blocks the removal
            with contextlib.suppress(OSError):
                os.chmod(temporary_file, stat.S_IWRITE)
            with contextlib.suppress(OSError):
                temporary_file.unlink(missing_ok=True)
            raise

        return destination_file
