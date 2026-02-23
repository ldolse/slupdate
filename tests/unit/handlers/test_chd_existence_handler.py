import pytest
import os
from unittest.mock import Mock, MagicMock, patch
from rom_management.handlers.chd_existence_handler import CHDExistenceHandler
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
    MediaProcessingItem,
    CHDExistingPreference,
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
        process.platform.chd_handling_preference = CHDExistingPreference.ASK
        process.platform.state = Mock()
        process.platform.validated_chds = set()
        process._skipped_categories = set()
        process._handle_skip = Mock(
            return_value=ResultObject.success(message="Skipped existing CHD")
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
        assert handler.PROCESS_CATEGORY == "existing CHD"

    @patch("os.path.exists")
    def test_action_overwrite_removes_file(
        self, mock_exists, handler, mock_process, mock_media
    ):
        """Test OVERWRITE action removes existing CHD and returns success"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        chd_path = "/test/chd/path/TestTitle/Test Game.chd"
        mock_exists.return_value = True

        with patch("os.remove") as mock_remove:
            result = handler.execute_action(Action.OVERWRITE, mock_process, {})

            assert result.is_success()
            mock_remove.assert_called_once_with(chd_path)

    @patch("os.path.exists")
    @patch("os.remove")
    def test_action_overwrite_file_removal_error(
        self, mock_remove, mock_exists, handler, mock_process, mock_media
    ):
        """Test OVERWRITE action when file removal fails"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_exists.return_value = True
        mock_remove.side_effect = OSError("Permission denied")

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        assert result.is_error()
        assert result.payload.error_type == "FileRemovalError"
        assert "Failed to remove" in result.payload.message

    @patch("os.path.exists", return_value=False)
    def test_action_overwrite_no_file_exists(
        self, mock_exists, handler, mock_process, mock_media
    ):
        """Test OVERWRITE action when file doesn't exist returns success"""
        mock_process.current_item = MediaProcessingItem(mock_media)

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        assert result.is_success()
        assert "Removed existing CHD" in result.payload.message

    def test_action_trust_existing(self, handler, mock_process, mock_media):
        """Test TRUST_EXISTING action adds to validated_chds and advances"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5

        with patch("os.path.exists", return_value=True):
            with patch("rom_management.CHD") as mock_chd_class:
                mock_chd = Mock()
                mock_chd.exists = True
                mock_chd.is_valid = True
                mock_chd.path = "/test/chd/path/TestTitle/Test Game.chd"
                mock_chd_class.return_value = mock_chd

                result = handler.execute_action(Action.TRUST_EXISTING, mock_process, {})

                assert result.is_success()
                assert mock_process.current_item is None
                assert mock_process.processed_items == 6
                mock_chd in mock_process.platform.validated_chds

    def test_action_skip_existing(self, handler, mock_process, mock_media):
        """Test SKIP action calls _handle_skip"""
        mock_process.current_item = MediaProcessingItem(mock_media)

        result = handler.execute_action(Action.SKIP, mock_process, {})

        assert result.is_success()
        mock_process._handle_skip.assert_called_once_with("Skipped existing CHD")

    def test_action_skip_all(self, handler, mock_process, mock_media):
        """Test SKIP_ALL action sets preference and skips"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.platform.set_chd_preference = Mock()

        result = handler.execute_action(Action.SKIP_ALL, mock_process, {})

        assert result.is_success()
        mock_process.platform.set_chd_preference.assert_called_once_with(
            CHDExistingPreference.SKIP
        )
        mock_process._handle_skip.assert_called_once()

    def test_action_set_overwrite_preference(self, handler, mock_process, mock_media):
        """Test SET_OVERWRITE_PREFERENCE action sets preference and removes CHD"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.platform.set_chd_preference = Mock()

        with patch("os.path.exists", return_value=False):
            result = handler.execute_action(
                Action.SET_OVERWRITE_PREFERENCE, mock_process, {}
            )

            assert result.is_success()
            mock_process.platform.set_chd_preference.assert_called_once_with(
                CHDExistingPreference.OVERWRITE
            )

    def test_action_set_trust_preference(self, handler, mock_process, mock_media):
        """Test SET_TRUST_PREFERENCE action sets preference and trusts CHD"""
        mock_process.current_item = MediaProcessingItem(mock_media)
        mock_process.processed_items = 5
        mock_process.platform.set_chd_preference = Mock()

        with patch("os.path.exists", return_value=True):
            with patch("rom_management.CHD") as mock_chd_class:
                mock_chd = Mock()
                mock_chd.exists = True
                mock_chd.is_valid = True
                mock_chd.path = "/test/chd/path/TestTitle/Test Game.chd"
                mock_chd_class.return_value = mock_chd

                result = handler.execute_action(
                    Action.SET_TRUST_PREFERENCE, mock_process, {}
                )

                assert result.is_success()
                mock_process.platform.set_chd_preference.assert_called_once_with(
                    CHDExistingPreference.TRUST
                )
                assert mock_process.current_item is None
                assert mock_process.processed_items == 6

    def test_action_stop(self, handler, mock_process, mock_media):
        """Test STOP action"""
        mock_process.current_item = MediaProcessingItem(mock_media)

        result = handler.execute_action(Action.STOP, mock_process, {})

        assert result.is_complete()
        mock_process._handle_stop.assert_called_once()

    def test_action_unknown(self, handler, mock_process, mock_media):
        """Test unknown action returns error"""
        mock_process.current_item = MediaProcessingItem(mock_media)

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

    def test_handler_extends_special_handler(self, handler):
        """Test that handler properly extends SpecialHandler"""
        assert hasattr(handler, "name")
        assert hasattr(handler, "execute_action")
        assert hasattr(handler, "execute")

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
            mock_process.processed_items = 0
            mock_process.platform = Mock()
            mock_process.platform.set_chd_preference = Mock()
            mock_process._handle_skip = Mock(return_value=ResultObject.success())
            mock_process._handle_stop = Mock(
                return_value=ResultObject.complete(total_processed=0)
            )

            with patch("os.path.exists", return_value=False):
                result = handler.execute_action(action, mock_process, {})
                # Should not raise UnknownAction error
                if result.is_error():
                    assert result.payload.error_type != "UnknownAction"
