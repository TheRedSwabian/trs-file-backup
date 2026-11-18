"""File backup operations."""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from trs_file_backup.state import StateManager


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
            PermissionError: If file cannot be accessed
            OSError: If file is locked or other IO error occurs
        """
        # Ensure destination directory exists
        self.destination_path.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        backup_filename = self.generate_backup_filename(source_file.name, timestamp)
        destination_file = self.destination_path / backup_filename

        # Copy file (preserves metadata)
        shutil.copy2(source_file, destination_file)

        return destination_file
