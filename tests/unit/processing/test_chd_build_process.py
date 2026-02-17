import pytest
import os
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
from rom_management.processing.chd_build_process import ChdBuildProcess
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
    MediaProcessingItem,
)
from rom_management import CHD
from optical_media.utils import OpticalMediaProcessor


class TestChdBuildProcess:
    """Test ChdBuildProcess refactoring"""

    @pytest.fixture
    def mock_platform(self):
        """Create a mock platform"""
        platform = Mock()
        platform.chd_path = "/test/chd/path"
        platform.matched_buildable_media = {}
        platform.validated_chds = set()
        platform.pm = Mock()
        platform.pm.tmpdsk = "/tmp"
        platform.chd_handling_preference = None
        platform.state = Mock()
        platform.state.validated_chds_paths = set()
        platform.state.remove_validated_chd_path = Mock()
        platform.state.add_validated_chd_path = Mock()
        return platform

    @pytest.fixture
    def mock_media(self):
        """Create a mock media item"""
        media = Mock()
        media.id = "test_media_id"
        media.zip_path = "/path/to/game.zip"
        media.dat_game_entry = Mock()
        media.dat_game_entry.name = "Test Game"

        # Mock softlist references
        media.softlist_part = Mock()
        media.softlist_part.part_of = Mock()
        media.softlist_part.part_of.name = "TestTitle"
        media.softlist_part.disk_name = "disk1"

        return media

    @pytest.fixture
    def mock_media_no_softlist(self):
        """Create a mock media item without softlist reference"""
        media = Mock()
        media.id = "test_media_id"
        media.dat_game_entry = Mock()
        media.dat_game_entry.name = "Test Game"
        media.softlist_part = None
        return media

    @pytest.fixture
    def mock_chd(self):
        """Create a mock CHD object"""
        chd = Mock()
        chd.path = "/test/chd/path/TestTitle/disk1.chd"
        chd.exists = True
        chd.is_valid = True
        chd._get_chd_info = Mock(return_value={"file_version": "5.0"})
        return chd

    def test_initialization(self, mock_platform):
        """Test ChdBuildProcess initializes correctly"""
        process = ChdBuildProcess(mock_platform)

        assert process.platform == mock_platform
        assert process._chd_handler is None
        assert process._file_data is None

    def test_initialize_with_empty_platform(self, mock_platform):
        """Test initialize with no buildable media"""
        mock_platform.matched_buildable_media = {}

        process = ChdBuildProcess(mock_platform)
        process.initialize()

        assert process.total_items == 0
        assert process.items_to_process == []

    def test_initialize_with_buildable_media(self, mock_platform, mock_media):
        """Test initialize with buildable media"""
        mock_platform.matched_buildable_media = {mock_media: None}

        process = ChdBuildProcess(mock_platform)
        process.initialize()

        assert process.total_items == 1
        assert len(process.items_to_process) == 1
        assert isinstance(process.items_to_process[0], MediaProcessingItem)
        assert process.items_to_process[0].media == mock_media
        assert process._chd_handler is not None

    def test_register_handlers(self, mock_platform):
        """Test handler registration"""
        process = ChdBuildProcess(mock_platform)
        process.register_handlers()

        assert process._chd_handler is not None
        assert process._chd_handler.name == "chd_existence"

    def test_get_handler_for_action_chd_actions(self, mock_platform):
        """Test handler mapping for CHD-related actions"""
        process = ChdBuildProcess(mock_platform)
        process.register_handlers()

        chd_actions = [
            Action.OVERWRITE,
            Action.TRUST_EXISTING,
            Action.SET_OVERWRITE_PREFERENCE,
            Action.SET_TRUST_PREFERENCE,
            Action.SKIP,
            Action.SKIP_ALL,
            Action.STOP,
        ]

        for action in chd_actions:
            handler = process._get_handler_for_action(action)
            assert handler == process._chd_handler

    def test_get_handler_for_action_non_chd_actions(self, mock_platform):
        """Test handler mapping for non-CHD actions"""
        process = ChdBuildProcess(mock_platform)
        process.register_handlers()

        assert process._get_handler_for_action(Action.SCAN_MD5) is None

    @patch("os.path.exists")
    def test_execute_step_media_no_softlist(
        self, mock_exists, mock_platform, mock_media_no_softlist
    ):
        """Test execute step when media has no softlist reference"""
        mock_platform.matched_buildable_media = {mock_media_no_softlist: None}

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()  # Set current_item

        result = process.execute_step()

        assert result.is_success()
        assert "Skipped" in result.payload.message
        assert mock_exists.call_count == 0

    @patch("os.path.exists")
    @patch.object(CHD, "__init__", return_value=None)
    @patch.object(OpticalMediaProcessor, "__init__", return_value=None)
    def test_execute_step_chd_not_exists(
        self,
        mock_optical_init,
        mock_chd_init,
        mock_exists,
        mock_platform,
        mock_media,
    ):
        """Test execute step when CHD doesn't exist (should build)"""
        mock_exists.return_value = False
        mock_platform.matched_buildable_media = {mock_media: None}

        # Mock the _build_single_chd method
        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch.object(
            process, "_build_single_chd", return_value=ResultObject.success()
        ) as mock_build:
            result = process.execute_step()

            mock_build.assert_called_once()
            assert result.is_success()

    @patch("os.path.exists")
    def test_execute_step_chd_fully_validated(
        self, mock_exists, mock_platform, mock_media, mock_chd
    ):
        """Test execute step when CHD exists and is fully validated"""
        mock_exists.return_value = True
        mock_platform.matched_buildable_media = {mock_media: None}
        mock_platform.validated_chds = {mock_chd}

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        # Mock CHD creation
        with patch(
            "rom_management.processing.chd_build_process.CHD", return_value=mock_chd
        ):
            result = process.execute_step()

            assert result.is_success()
            assert "already validated" in result.payload.message

    @patch("os.path.exists")
    def test_execute_step_chd_exists_skip_preference(
        self, mock_exists, mock_platform, mock_media, mock_chd
    ):
        """Test execute step when CHD exists with skip preference"""
        mock_exists.return_value = True
        mock_platform.matched_buildable_media = {mock_media: None}
        mock_platform.validated_chds = set()  # Not in validated set
        mock_platform.chd_handling_preference = "skip"
        mock_chd.exists = True
        mock_chd.is_valid = True

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch(
            "rom_management.processing.chd_build_process.CHD", return_value=mock_chd
        ):
            result = process.execute_step()

            assert result.is_success()
            assert "Skipped existing CHD" in result.payload.message

    @patch("os.path.exists")
    @patch("os.remove")
    def test_execute_step_chd_exists_overwrite_preference(
        self, mock_remove, mock_exists, mock_platform, mock_media, mock_chd
    ):
        """Test execute step when CHD exists with overwrite preference"""
        mock_exists.return_value = True
        mock_platform.matched_buildable_media = {mock_media: None}
        mock_platform.validated_chds = set()  # Not in validated set
        mock_platform.chd_handling_preference = "overwrite"
        mock_chd.exists = True
        mock_chd.is_valid = True

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch(
            "rom_management.processing.chd_build_process.CHD", return_value=mock_chd
        ):
            with patch.object(
                process, "_build_single_chd", return_value=ResultObject.success()
            ) as mock_build:
                result = process.execute_step()

                mock_remove.assert_called_once()
                mock_build.assert_called_once()
                assert result.is_success()

    @patch("os.path.exists")
    def test_execute_step_chd_exists_file_removal_error(
        self, mock_exists, mock_platform, mock_media, mock_chd
    ):
        """Test execute step when file removal fails"""
        mock_exists.return_value = True
        mock_platform.matched_buildable_media = {mock_media: None}
        mock_platform.validated_chds = set()
        mock_platform.chd_handling_preference = "overwrite"
        mock_chd.exists = True
        mock_chd.is_valid = True

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch(
            "rom_management.processing.chd_build_process.CHD", return_value=mock_chd
        ):
            with patch("os.remove", side_effect=OSError("Permission denied")):
                result = process.execute_step()

                assert result.is_error()
                assert result.payload.error_type == "FileRemovalError"

    @patch("os.path.exists")
    def test_execute_step_chd_exists_pending_input(
        self, mock_exists, mock_platform, mock_media, mock_chd
    ):
        """Test execute step when CHD exists and needs user input"""
        mock_exists.return_value = True
        mock_platform.matched_buildable_media = {mock_media: None}
        mock_platform.validated_chds = set()  # Not in validated set
        mock_platform.chd_handling_preference = None  # No preference set
        mock_chd.exists = True
        mock_chd.is_valid = True

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch(
            "rom_management.processing.chd_build_process.CHD", return_value=mock_chd
        ):
            result = process.execute_step()

            assert result.requires_input()
            assert result.payload.query_id == "generic_query"
            assert Action.OVERWRITE in result.payload.valid_actions
            assert Action.TRUST_EXISTING in result.payload.valid_actions
            assert Action.SKIP in result.payload.valid_actions
            assert Action.SKIP_ALL in result.payload.valid_actions
            assert Action.STOP in result.payload.valid_actions

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    @patch("rom_management.processing.chd_build_process.CHD")
    def test_build_single_chd_success(
        self, mock_chd_class, mock_optical_class, mock_platform, mock_media
    ):
        """Test successful CHD building"""
        # Setup mocks
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = "/tmp/test/disc.toc"
        mock_optical_class.return_value = mock_optical

        mock_chd = Mock()
        mock_chd.exists = True
        mock_chd.is_valid = True
        mock_chd.path = "/test/chd/path/TestTitle/disk1.chd"
        mock_chd_class.return_value = mock_chd

        mock_platform.get_relevant_handlers.return_value = []

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_success()
        assert "Created CHD" in result.payload.message
        mock_optical.extract_and_process.assert_called_once()

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    def test_build_single_chd_temp_dir_error(
        self, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when temp directory creation fails"""
        mock_optical = Mock()
        mock_optical.temp_dir = None
        mock_optical_class.return_value = mock_optical

        mock_platform.get_relevant_handlers.return_value = []

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_error()
        assert result.payload.error_type == "TempDirectoryError"

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    def test_build_single_chd_no_toc_error(
        self, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when no TOC file is found"""
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = None
        mock_optical_class.return_value = mock_optical

        mock_platform.get_relevant_handlers.return_value = []

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_error()
        assert result.payload.error_type == "NoTOCError"

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    @patch("rom_management.processing.chd_build_process.CHD")
    def test_build_single_chd_creation_failure(
        self, mock_chd_class, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when CHD creation fails"""
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = "/tmp/test/disc.toc"
        mock_optical_class.return_value = mock_optical

        mock_chd = Mock()
        mock_chd.exists = False
        mock_chd_class.return_value = mock_chd

        mock_platform.get_relevant_handlers.return_value = []

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_error()
        assert result.payload.error_type == "CHDCreationError"

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    def test_build_single_chd_disk_space_error(
        self, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when disk space is insufficient"""
        mock_optical = Mock()
        mock_optical_class.return_value = mock_optical
        mock_optical.extract_and_process.side_effect = OSError(
            28, "No space left on device"
        )

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_error()
        assert result.payload.error_type == "DiskSpaceError"

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    @patch("rom_management.processing.chd_build_process.CHD")
    def test_build_single_chd_cleanup_temp_directory(
        self, mock_chd_class, mock_optical_class, mock_platform, mock_media
    ):
        """Test that temp directory is cleaned up after CHD building"""
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = "/tmp/test/disc.toc"
        mock_optical_class.return_value = mock_optical

        mock_platform.get_relevant_handlers.return_value = []

        process = ChdBuildProcess(mock_platform)

        # Mock CHD to raise an exception
        with patch("rom_management.processing.chd_build_process.CHD") as mock_chd_class:
            mock_chd = Mock()
            mock_chd.exists = False
            mock_chd_class.return_value = mock_chd

            result = process._build_single_chd(
                mock_media, "TestTitle", "/test/path/disk1.chd"
            )

        # Cleanup should have been called even on error
        mock_optical.cleanup.assert_called_once()
        assert result.is_error()

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    @patch("rom_management.processing.chd_build_process.CHD")
    def test_build_single_chd_handler_failure(
        self, mock_chd_class, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when a handler fails"""
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = "/tmp/test/disc.toc"
        mock_optical_class.return_value = mock_optical

        # Mock handler that fails
        mock_handler = Mock()
        mock_handler.name = "test_handler"
        mock_handler.execute.return_value = ResultObject.error(
            error_type="HandlerError", message="Handler failed"
        )

        mock_platform.get_relevant_handlers.return_value = [mock_handler]

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_error()
        assert result.payload.error_type == "HandlerFailed"
        assert "test_handler" in result.payload.context["handler"]

    @patch("rom_management.processing.chd_build_process.OpticalMediaProcessor")
    @patch("rom_management.processing.chd_build_process.CHD")
    def test_build_single_chd_handler_success(
        self, mock_chd_class, mock_optical_class, mock_platform, mock_media
    ):
        """Test CHD building when handlers succeed"""
        mock_optical = Mock()
        mock_optical.temp_dir = Mock()
        mock_optical.temp_dir.exists.return_value = True
        mock_optical.current_toc = "/tmp/test/disc.toc"
        mock_optical_class.return_value = mock_optical

        # Mock handler that succeeds
        mock_handler = Mock()
        mock_handler.name = "test_handler"
        mock_handler.execute.return_value = ResultObject.success()

        mock_platform.get_relevant_handlers.return_value = [mock_handler]

        mock_chd = Mock()
        mock_chd.exists = True
        mock_chd.is_valid = True
        mock_chd.path = "/test/chd/path/TestTitle/disk1.chd"
        mock_chd_class.return_value = mock_chd

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.is_success()
        mock_handler.execute.assert_called_once_with(mock_media, mock_optical)

    def test_get_progress(self, mock_platform):
        """Test get_progress returns correct information"""
        process = ChdBuildProcess(mock_platform)
        process.processed_items = 5
        process.total_items = 10

        progress = process.get_progress()

        assert progress["processed"] == 5
        assert progress["total"] == 10
        assert progress["percentage"] == 50.0

    def test_handle_user_action_stop(self, mock_platform):
        """Test STOP action handling"""
        process = ChdBuildProcess(mock_platform)
        process.processed_items = 5

        result = process.handle_user_action(Action.STOP)

        assert result.is_complete()
        assert result.payload.stopped_early is True
        assert result.payload.total_processed == 5

    def test_execute_step_completion(self, mock_platform):
        """Test execute_step returns COMPLETE when all items processed"""
        mock_platform.matched_buildable_media = {}

        process = ChdBuildProcess(mock_platform)
        process.initialize()

        result = process.execute_step()

        assert result.is_complete()
        assert result.payload.total_processed == 0
