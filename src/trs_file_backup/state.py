"""State management for backup operations."""

import contextlib
import json
import time
from pathlib import Path

from trs_file_backup.patterns import is_usable_pattern

REPLACE_ATTEMPTS = 5
REPLACE_RETRY_DELAY_SECONDS = 0.1


class StateManager:
    """Manages the backup state including file timestamps and configuration."""

    def __init__(
        self,
        source_path: Path,
        destination_path: Path,
        debounce_seconds: int,
        excluded_patterns: list[str],
        files: dict[str, float],
    ):
        """Initialize state manager.

        Args:
            source_path: Source directory path
            destination_path: Destination directory path
            debounce_seconds: Debounce delay in seconds
            excluded_patterns: List of exclusion patterns
            files: Dictionary mapping filenames to their last backup timestamps
        """
        self.source_path = source_path
        self.destination_path = destination_path
        self.debounce_seconds = debounce_seconds
        self.excluded_patterns = excluded_patterns
        self.files = files

    @property
    def state_file_path(self) -> Path:
        """Get the path to the state file.

        Returns:
            Path to .backup_state.json in destination directory
        """
        return self.destination_path / ".backup_state.json"

    @classmethod
    def load(cls, state_file_path: str | Path) -> "StateManager | None":
        """Load state from file.

        Args:
            state_file_path: Path to the state file

        The destination is the folder that holds the state file, not the path stored in it,
        so that a copied or moved backup folder never writes into the old one (spec AC-3.11).
        The next save stores the corrected path.

        Returns:
            StateManager instance if file exists, None otherwise

        Raises:
            json.JSONDecodeError: If state file contains invalid JSON
        """
        path = Path(state_file_path)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            source_path=Path(data["source_path"]),
            destination_path=path.parent,
            debounce_seconds=data["debounce_seconds"],
            # Older versions saved patterns that cannot be used as file-name patterns; drop them (spec AC-4.9)
            excluded_patterns=[pattern for pattern in data["excluded_patterns"] if is_usable_pattern(pattern)],
            files=data["files"],
        )

    def save(self) -> None:
        """Save state to file using atomic write operation.

        Creates destination directory if it doesn't exist.
        Uses temp file + rename for atomic write.
        """
        # Ensure destination directory exists
        self.destination_path.mkdir(parents=True, exist_ok=True)

        # Prepare data
        data = {
            "source_path": str(self.source_path),
            "destination_path": str(self.destination_path),
            "log_file": "backup.log",
            "debounce_seconds": self.debounce_seconds,
            "excluded_patterns": self.excluded_patterns,
            "files": self.files,
        }

        # Write to temp file first (atomic operation)
        import os

        temp_file = self.state_file_path.with_suffix(".json.tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Rename temp file to actual file (atomic on most filesystems)
        # Use os.replace for cross-platform atomic replacement
        try:
            for attempt in range(1, REPLACE_ATTEMPTS + 1):
                try:
                    os.replace(str(temp_file), str(self.state_file_path))
                    return
                except PermissionError:
                    # On Windows an antivirus or the indexer may hold the new file for a moment
                    if attempt == REPLACE_ATTEMPTS:
                        raise
                    time.sleep(REPLACE_RETRY_DELAY_SECONDS)
        except OSError:
            # Do not leave the temp file behind; a failed cleanup must not hide the rename error
            with contextlib.suppress(OSError):
                temp_file.unlink(missing_ok=True)
            raise

    def update_file_timestamp(self, filename: str, timestamp: float) -> None:
        """Update or add file timestamp.

        Args:
            filename: Name of the file
            timestamp: Modification timestamp
        """
        self.files[filename] = timestamp

    def is_modified(self, filename: str, current_timestamp: float) -> bool:
        """Check if file is modified since last backup.

        Args:
            filename: Name of the file
            current_timestamp: Current modification timestamp

        Returns:
            True if file is new or modified, False otherwise
        """
        if filename not in self.files:
            return True
        return current_timestamp > self.files[filename]
