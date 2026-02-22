import pytest
import os
from unittest.mock import Mock, MagicMock, patch
from rom_management.handlers.chd_existence_handler import CHDExistenceHandler
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
    MediaProcessingItem,
)


class TestCHDExistenceHandler:
    """Test CHDExistenceHandler actions"""

    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return CHDExistenceHandler()

    @pytest.fixture
    def mock_process(self):
        """Create mock process with properly configured methods"""
        process = Mock()
        process.processed_items = 0
        process.current_item = None
        process.platform = Mock()
        process.platform.chd_path = "/test/chd/path"
        process.platform.state = Mock()
        process._handle_skip = Mock(
            return_value=ResultObject.success(message="Skipped existing CHD")
        )
        process._handle_skip_all = Mock(
            return_value=ResultObject.success(message="Skip all remaining items")
        )
        process._handle_stop = Mock(
            return_value=ResultObject.complete(total_processed=0, stopped_early=True)
        )
        return process

    @pytest.fixture
    def mock_media(self):
        """Create mock media"""
        media = Mock()
        media.dat_game_entry = Mock()
        media.dat_game_entry.name = "Test Game"
        media.softlist_part = Mock()
        media.softlist_part.part_of = Mock()
        media.softlist_part.part_of.name = "TestTitle"
        media.softlist_part.disk_name = "disk1"
        return media

    def test_handler_initialization(self, handler):
        """Test handler initializes correctly"""
        assert handler.name == "chd_existence"
        assert handler.menu is None

    def test_action_overwrite_success(self, handler, mock_process, mock_media):
        """Test OVERWRITE action with successful CHD rebuild"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5

        # Mock _execute_step to return success
        with patch.object(handler, "_execute_step_and_advance") as mock_execute_step:
            mock_execute_step.return_value = ResultObject.success()

            result = handler.execute_action(Action.OVERWRITE, mock_process, {})

            assert result.is_success()
            mock_execute_step.assert_called_once()

    @patch("os.path.exists")
    @patch("os.remove")
    def test_action_overwrite_removes_file(
        self, mock_remove, mock_exists, handler, mock_process, mock_media
    ):
        """Test OVERWRITE action removes existing CHD"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        chd_path = "/test/chd/path/TestTitle/Test Game.chd"
        mock_exists.return_value = True

        with patch.object(handler, "_execute_step_and_advance") as mock_execute_step:
            mock_execute_step.return_value = ResultObject.success()

            result = handler.execute_action(Action.OVERWRITE, mock_process, {})

            assert result.is_success()
            mock_remove.assert_called_once_with(chd_path)

    @patch("os.path.exists")
    @patch("os.remove")
    def test_action_overwrite_file_removal_error(
        self, mock_remove, mock_exists, handler, mock_process, mock_media
    ):
        """Test OVERWRITE action when file removal fails"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_exists.return_value = True
        mock_remove.side_effect = OSError("Permission denied")

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        assert result.is_error()
        assert result.payload.error_type == "FileRemovalError"
        assert "Failed to remove" in result.payload.message

    def test_action_overwrite_no_file_exists(self, handler, mock_process, mock_media):
        """Test OVERWRITE action when file doesn't exist"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)

        with patch.object(handler, "_execute_step_and_advance") as mock_execute_step:
            mock_execute_step.return_value = ResultObject.success()
            with patch("os.path.exists", return_value=False):
                result = handler.execute_action(Action.OVERWRITE, mock_process, {})

                assert result.is_success()
                # Should still call execute_step even if file doesn't exist
                mock_execute_step.assert_called_once()

    def test_action_overwrite_invalid_current_item(self, handler, mock_process):
        """Test OVERWRITE action when current_item is not MediaProcessingItem"""
        mock_process.current_item = Mock()  # Not MediaProcessingItem

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        assert result.is_error()
        assert result.payload.error_type == "InvalidState"

    def test_action_skip_existing(self, handler, mock_process, mock_media):
        """Test SKIP action"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5

        result = handler.execute_action(Action.SKIP, mock_process, {})

        assert result.is_success()
        mock_process._handle_skip.assert_called_once_with("Skipped existing CHD")
        assert (
            mock_process.current_item is not None
        )  # Not cleared directly, handled by _handle_skip
        assert (
            mock_process.processed_items == 5
        )  # Not incremented directly, handled by _handle_skip

    def test_action_skip_all(self, handler, mock_process, mock_media):
        """Test SKIP_ALL action passes category to process._handle_skip_all"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5

        result = handler.execute_action(Action.SKIP_ALL, mock_process, {})

        assert result.is_success()
        mock_process._handle_skip_all.assert_called_once_with(
            f"Skip all {handler.PROCESS_CATEGORY}", category=handler.PROCESS_CATEGORY
        )

    def test_action_set_overwrite_preference(self, handler, mock_process, mock_media):
        """Test SET_OVERWRITE_PREFERENCE action"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.platform.set_chd_preference = Mock()

        with patch.object(handler, "_execute_step_and_advance") as mock_execute_step:
            mock_execute_step.return_value = ResultObject.success()

            result = handler.execute_action(
                Action.SET_OVERWRITE_PREFERENCE, mock_process, {}
            )

            assert result.is_success()
            mock_process.platform.set_chd_preference.assert_called_once_with(
                "overwrite"
            )
            mock_execute_step.assert_called_once()

    def test_action_set_trust_preference(self, handler, mock_process, mock_media):
        """Test SET_TRUST_PREFERENCE action"""
        # Setup
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5
        mock_process.platform.set_chd_preference = Mock()

        result = handler.execute_action(Action.SET_TRUST_PREFERENCE, mock_process, {})

        assert result.is_success()
        assert "Set trust preference" in result.payload.message
        mock_process.platform.set_chd_preference.assert_called_once_with("skip")
        assert mock_process.current_item is None
        assert mock_process.processed_items == 6

    def test_action_stop(self, handler, mock_process):
        """Test STOP action"""
        # Setup
        mock_process.processed_items = 10

        result = handler.execute_action(Action.STOP, mock_process, {})

        assert result.is_complete()
        mock_process._handle_stop.assert_called_once()

    def test_action_unknown(self, handler, mock_process):
        """Test unknown action returns error"""
        result = handler.execute_action(Action.HANDLE, mock_process, {})

        assert result.is_error()
        assert result.payload.error_type == "UnknownAction"
        assert "Unknown action" in result.payload.message

    def test_get_expected_chd_path(self, handler, mock_process, mock_media):
        """Test _get_expected_chd_path returns correct path"""
        chd_path = handler._get_expected_chd_path(mock_process, mock_media)

        expected = "/test/chd/path/TestTitle/Test Game.chd"
        assert chd_path == expected

    def test_get_expected_chd_path_no_dat_entry(self, handler, mock_process):
        """Test _get_expected_chd_path when dat_game_entry is None"""
        mock_media = Mock()
        mock_media.dat_game_entry = None

        chd_path = handler._get_expected_chd_path(mock_process, mock_media)

        assert chd_path is None

    def test_get_expected_chd_path_no_dat_name(self, handler, mock_process, mock_media):
        """Test _get_expected_chd_path when dat_game_entry.name is None"""
        mock_media.dat_game_entry = Mock()
        mock_media.dat_game_entry.name = None

        chd_path = handler._get_expected_chd_path(mock_process, mock_media)

        assert chd_path is None

    def test_execute_step_and_advance_success(self, handler, mock_process, mock_media):
        """Test _execute_step_and_advance on success"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5
        mock_process._execute_step = Mock(return_value=ResultObject.success())

        result = handler._execute_step_and_advance(mock_process)

        assert result.is_success()
        assert mock_process.current_item is None
        assert mock_process.processed_items == 6

    def test_execute_step_and_advance_error(self, handler, mock_process, mock_media):
        """Test _execute_step_and_advance on error doesn't advance"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5
        mock_process._execute_step = Mock(
            return_value=ResultObject.error(
                error_type="TestError", message="Test error"
            )
        )

        result = handler._execute_step_and_advance(mock_process)

        assert result.is_error()
        assert mock_process.current_item is not None  # Not advanced
        assert mock_process.processed_items == 5  # Not incremented

    def test_execute_step_and_advance_pending_input(
        self, handler, mock_process, mock_media
    ):
        """Test _execute_step_and_advance on pending input doesn't advance"""
        from rom_management.processing.models import BaseProcessingItem

        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5
        mock_process._execute_step = Mock(
            return_value=ResultObject.pending_input(
                "test_query",
                "test message",
                BaseProcessingItem("test"),
                [Action.STOP],
            )
        )

        result = handler._execute_step_and_advance(mock_process)

        assert result.requires_input()
        assert mock_process.current_item is not None  # Not advanced
        assert mock_process.processed_items == 5  # Not incremented

    def test_action_order_preserved(self, handler, mock_process, mock_media):
        """Test that actions are executed in the correct order"""
        # Test OVERWRITE first
        mock_process.current_item = MediaProcessingItem(mock_media)
        with patch.object(handler, "_execute_step_and_advance") as mock_execute_step:
            with patch("os.remove"):
                result = handler.execute_action(Action.OVERWRITE, mock_process, {})
                assert result.is_success()

        # Test SKIP - verify _handle_skip is called
        mock_process.current_item = MediaProcessingItem(mock_media)
        result = handler.execute_action(Action.SKIP, mock_process, {})
        assert result.is_success()
        mock_process._handle_skip.assert_called_once_with("Skipped existing CHD")

        # Test STOP
        result = handler.execute_action(Action.STOP, mock_process, {})
        assert result.is_complete()

    def test_handler_extends_special_handler(self, handler):
        """Test that handler properly extends SpecialHandler"""
        assert hasattr(handler, "name")
        assert hasattr(handler, "execute_action")
        assert hasattr(handler, "_execute_step_and_advance")

    def test_all_implemented_actions(self, handler):
        """Test that all documented actions are implemented"""
        documented_actions = [
            Action.OVERWRITE,
            Action.TRUST_EXISTING,
            Action.SET_OVERWRITE_PREFERENCE,
            Action.SET_TRUST_PREFERENCE,
            Action.SKIP,
            Action.SKIP_ALL,
            Action.STOP,
        ]

        for action in documented_actions:
            mock_process = Mock()
            mock_process.processed_items = 0  # Initialize as int
            with patch.object(handler, "_execute_step_and_advance"):
                result = handler.execute_action(action, mock_process, {})
                # Should not raise UnknownAction error
                if result.is_error():
                    assert result.payload.error_type != "UnknownAction"
