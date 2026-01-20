"""Tests for state management functionality."""

import json
from pathlib import Path
from unittest.mock import mock_open

import pytest
from pytest_mock import MockFixture


class TestStateManager:
    """Test suite for StateManager class."""

    def test_load_state_file_exists(self, mocker: MockFixture) -> None:
        """Test loading an existing state file."""
        mock_state_data = {
            "source_path": "/source",
            "destination_path": "/dest",
            "log_file": "backup.log",
            "debounce_seconds": 2,
            "excluded_patterns": [".backup_state.json", "*.log"],
            "files": {"file1.txt": 1736772622.5, "file2.txt": 1736772625.8},
        }

        mock_file = mock_open(read_data=json.dumps(mock_state_data))
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("builtins.open", mock_file)

        from trs_file_backup.state import StateManager

        state = StateManager.load("/dest/.backup_state.json")

        assert state is not None
        assert state.source_path == Path("/source")
        assert state.destination_path == Path("/dest")
        assert state.debounce_seconds == 2
        assert state.excluded_patterns == [".backup_state.json", "*.log"]
        assert len(state.files) == 2
        assert state.files["file1.txt"] == 1736772622.5

    def test_load_state_file_not_exists(self, mocker: MockFixture) -> None:
        """Test loading when state file doesn't exist returns None."""
        mocker.patch("pathlib.Path.exists", return_value=False)

        from trs_file_backup.state import StateManager

        state = StateManager.load("/dest/.backup_state.json")

        assert state is None

    def test_load_state_invalid_json(self, mocker: MockFixture) -> None:
        """Test loading state file with invalid JSON raises error."""
        mock_file = mock_open(read_data="invalid json {")
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("builtins.open", mock_file)

        from trs_file_backup.state import StateManager

        with pytest.raises(json.JSONDecodeError):
            StateManager.load("/dest/.backup_state.json")

    def test_save_state_creates_file(self, mocker: MockFixture) -> None:
        """Test saving state creates the state file."""
        from trs_file_backup.state import StateManager

        mock_file = mock_open()
        mocker.patch("pathlib.Path.mkdir", return_value=None)
        mocker.patch("builtins.open", mock_file)
        mocker.patch("os.replace", return_value=None)
        mocker.patch("pathlib.Path.exists", return_value=False)

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[".backup_state.json"],
            files={"file1.txt": 1736772622.5},
        )

        state.save()

        mock_file.assert_called()
        handle = mock_file()
        written_data = "".join(call.args[0] for call in handle.write.call_args_list)
        saved_data = json.loads(written_data)

        assert saved_data["source_path"] == str(Path("/source"))
        assert saved_data["destination_path"] == str(Path("/dest"))
        assert saved_data["debounce_seconds"] == 2
        assert saved_data["log_file"] == "backup.log"

    def test_save_state_atomic_write(self, mocker: MockFixture) -> None:
        """Test that save uses atomic write (temp file + os.replace)."""
        from trs_file_backup.state import StateManager

        mock_file = mock_open()
        _mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        mock_open_func = mocker.patch("builtins.open", mock_file)
        mock_replace = mocker.patch("os.replace")
        mocker.patch("pathlib.Path.exists", return_value=False)

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={},
        )

        state.save()

        # Check that we write to a temp file
        call_args = mock_open_func.call_args_list
        assert len(call_args) > 0
        temp_file_path = str(call_args[0][0][0])
        assert ".tmp" in temp_file_path or "tmp" in temp_file_path.lower()

        # Check that os.replace was called (atomic operation)
        mock_replace.assert_called_once()

    def test_update_file_timestamp(self, mocker: MockFixture) -> None:
        """Test updating timestamp for a file."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={"file1.txt": 1000.0},
        )

        state.update_file_timestamp("file1.txt", 2000.0)

        assert state.files["file1.txt"] == 2000.0

    def test_add_new_file_timestamp(self, mocker: MockFixture) -> None:
        """Test adding a new file timestamp."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={},
        )

        state.update_file_timestamp("newfile.txt", 1500.0)

        assert "newfile.txt" in state.files
        assert state.files["newfile.txt"] == 1500.0

    def test_is_modified_file_newer(self) -> None:
        """Test that file is considered modified if newer than tracked timestamp."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={"file1.txt": 1000.0},
        )

        assert state.is_modified("file1.txt", 1500.0) is True

    def test_is_modified_file_older(self) -> None:
        """Test that file is not modified if older than tracked timestamp."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={"file1.txt": 1000.0},
        )

        assert state.is_modified("file1.txt", 500.0) is False

    def test_is_modified_file_not_tracked(self) -> None:
        """Test that untracked file is always considered modified."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={},
        )

        assert state.is_modified("newfile.txt", 1000.0) is True

    def test_state_file_path_property(self) -> None:
        """Test that state_file_path returns correct path."""
        from trs_file_backup.state import StateManager

        state = StateManager(
            source_path=Path("/source"),
            destination_path=Path("/dest"),
            debounce_seconds=2,
            excluded_patterns=[],
            files={},
        )

        expected_path = Path("/dest") / ".backup_state.json"
        assert state.state_file_path == expected_path
