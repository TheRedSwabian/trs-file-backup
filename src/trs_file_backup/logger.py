"""Logging functionality for backup operations."""

import logging
from pathlib import Path
from typing import List


class BackupLogger:
    """Handles logging of backup operations to file."""

    def __init__(self, destination_path: Path):
        """Initialize logger.

        Args:
            destination_path: Destination directory where log file will be created
        """
        self.destination_path = destination_path
        self.log_file_path = destination_path / "backup.log"

        # Ensure destination directory exists
        destination_path.mkdir(parents=True, exist_ok=True)

        # Configure logger
        self.logger = logging.getLogger("trs_file_backup")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        # Close handlers properly to avoid ResourceWarning
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

        # Create file handler with UTF-8 encoding and append mode
        handler = logging.FileHandler(
            self.log_file_path,
            mode="a",
            encoding="utf-8",
        )

        # Set format
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def log_session_start(
        self,
        command: str,
        source_path: Path,
        destination_path: Path,
        excluded_patterns: List[str],
        debounce_seconds: int,
    ) -> None:
        """Log session start with configuration.

        Args:
            command: Command being executed (init, run, watch)
            source_path: Source directory path
            destination_path: Destination directory path
            excluded_patterns: List of exclusion patterns
            debounce_seconds: Debounce delay in seconds
        """
        self.logger.info("=" * 10 + " Session Started " + "=" * 10)
        self.logger.info(f"Command: {command}")
        self.logger.info(f"Source: {source_path}")
        self.logger.info(f"Destination: {destination_path}")
        self.logger.info(f"Exclusion patterns: {', '.join(excluded_patterns)}")
        self.logger.info(f"Debounce delay: {debounce_seconds} seconds")

    def log_session_end(self, files_backed_up: int = 0, files_total: int = 0) -> None:
        """Log session end with summary.

        Args:
            files_backed_up: Number of files successfully backed up
            files_total: Total number of files processed
        """
        if files_total > 0:
            self.logger.info(f"Session summary: {files_backed_up} of {files_total} files backed up")
        self.logger.info("=" * 10 + " Session Ended " + "=" * 10)
        # Add three blank lines for better session separation
        self.logger.info("")
        self.logger.info("")
        self.logger.info("")

    def log_init_success(self) -> None:
        """Log successful initialization."""
        self.logger.info("Backup tracking initialized successfully")

    def log_found_files(self, count: int) -> None:
        """Log number of files found.

        Args:
            count: Number of modified files found
        """
        self.logger.info(f"Found {count} modified files")

    def log_file_backed_up(self, source_name: str, backup_name: str) -> None:
        """Log successful file backup.

        Args:
            source_name: Original filename
            backup_name: Backup filename with timestamp
        """
        self.logger.info(f"Backed up: {source_name} → {backup_name}")

    def log_file_excluded(self, filename: str, pattern: str) -> None:
        """Log excluded file.

        Args:
            filename: Name of excluded file
            pattern: Pattern that matched
        """
        self.logger.warning(f"File excluded: {filename} (matches: {pattern})")

    def log_file_locked(self, filename: str) -> None:
        """Log locked file warning.

        Args:
            filename: Name of locked file
        """
        self.logger.warning(f"File locked, skipping: {filename}")

    def log_error(self, message: str) -> None:
        """Log error message.

        Args:
            message: Error message
        """
        self.logger.error(message)

    def log_file_modified(self, filename: str) -> None:
        """Log file modification event (watch mode).

        Args:
            filename: Name of modified file
        """
        self.logger.info(f"File modified: {filename}")

    def log_watch_started(self) -> None:
        """Log watch mode started."""
        self.logger.info("Watch mode started, monitoring for changes...")

    def log_watch_stopped(self) -> None:
        """Log watch mode stopped."""
        self.logger.info("Watch mode stopped by user (Ctrl+C)")

    def log_backup_completed(self, backed_up: int, total: int) -> None:
        """Log backup operation completion.

        Args:
            backed_up: Number of files backed up successfully
            total: Total number of files attempted
        """
        self.logger.info(f"Backup operation completed: {backed_up} of {total} files backed up")

    def close(self) -> None:
        """Close all handlers and clean up resources."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
