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
    CHDExistingPreference,
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
        platform.chd_handling_preference = CHDExistingPreference.ASK
        platform.state = Mock()
        platform.state.validated_chds_paths = set()
        platform.state.remove_validated_chd_path = Mock()
        platform.state.add_validated_chd_path = Mock()
        platform._skipped_categories = set()
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

        assert process._get_handler_for_action(Action.HANDLE) is None
        assert process._get_handler_for_action(Action.HANDLE_ALL) is None

    def test_execute_step_media_no_softlist(
        self, mock_platform, mock_media_no_softlist
    ):
        """Test execute step when media has no softlist reference"""
        mock_platform.matched_buildable_media = {mock_media_no_softlist: None}

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()  # Set current_item

        result = process.execute_step()

        assert result.is_success()
        assert "Skipped" in result.payload.message

    def test_execute_step_no_chd_exists(self, mock_platform, mock_media):
        """Test execute step when no CHD exists - should build"""
        mock_platform.matched_buildable_media = {mock_media: None}
        # Handler returns not_applicable (no existing CHD)
        mock_platform.get_relevant_handlers.return_value = ([], None)

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch.object(
            process, "_build_single_chd", return_value=ResultObject.success()
        ) as mock_build:
            result = process.execute_step()

            mock_build.assert_called_once()
            assert result.is_success()

    def test_execute_step_handler_returns_skip(self, mock_platform, mock_media):
        """Test execute step when handler returns skip (SKIP preference set)"""
        mock_platform.matched_buildable_media = {mock_media: None}
        # Handler returns skip result
        skip_result = ResultObject.skip(message="Skipping existing CHD per preference")
        mock_platform.get_relevant_handlers.return_value = ([], skip_result)

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        result = process.execute_step()

        # Skip result should advance the item
        assert result.is_skip() or result.is_success()

    def test_execute_step_handler_returns_pending_input(
        self, mock_platform, mock_media
    ):
        """Test execute step when handler returns pending_input (ASK preference, CHD exists)"""
        mock_platform.matched_buildable_media = {mock_media: None}

        mock_handler = Mock()
        mock_handler.name = "chd_existence"
        mock_handler.has_completed = Mock(return_value=False)
        mock_handler.execute.return_value = ResultObject.pending_input(
            query_id="generic_query",
            message="CHD already exists",
            item=MediaProcessingItem(mock_media),
            valid_actions=[
                Action.TRUST_EXISTING,
                Action.OVERWRITE,
                Action.SKIP,
                Action.STOP,
            ],
        )
        mock_platform.get_relevant_handlers.return_value = ([mock_handler], None)

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()
        # Initialize the _completed_handlers set
        process.current_item._completed_handlers = set()

        result = process.execute_step()

        assert result.requires_input()
        assert Action.TRUST_EXISTING in result.payload.valid_actions

    def test_execute_step_handler_trust_existing(self, mock_platform, mock_media):
        """Test execute step when handler trusts existing CHD (TRUST preference)"""
        mock_platform.matched_buildable_media = {mock_media: None}

        mock_handler = Mock()
        mock_handler.name = "chd_existence"
        mock_handler.has_completed = Mock(return_value=False)

        # Handler's execute returns success and advances the item
        def trust_side_effect(media, file_data, process):
            process.current_item = None
            process.processed_items += 1
            return ResultObject.success(message="Trusted existing CHD")

        mock_handler.execute.side_effect = trust_side_effect
        mock_platform.get_relevant_handlers.return_value = ([mock_handler], None)

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()
        # Initialize the _completed_handlers set
        process.current_item._completed_handlers = set()

        result = process.execute_step()

        assert result.is_success()
        assert process.current_item is None  # Item was advanced

    def test_execute_step_handler_overwrite(self, mock_platform, mock_media):
        """Test execute step when handler removes existing CHD (OVERWRITE preference)"""
        mock_platform.matched_buildable_media = {mock_media: None}

        mock_handler = Mock()
        mock_handler.name = "chd_existence"
        # Handler's execute returns success (CHD removed, process should continue to build)
        mock_handler.execute.return_value = ResultObject.success(
            message="Removed existing CHD"
        )
        mock_platform.get_relevant_handlers.return_value = ([mock_handler], None)

        process = ChdBuildProcess(mock_platform)
        process.initialize()
        process._get_next_item()

        with patch.object(
            process, "_build_single_chd", return_value=ResultObject.success()
        ) as mock_build:
            result = process.execute_step()

            mock_build.assert_called_once()
            assert result.is_success()

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

        mock_platform.get_relevant_handlers.return_value = ([], None)

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

        mock_platform.get_relevant_handlers.return_value = ([], None)

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.requires_input()
        assert result.payload.query_id == "generic_query"
        assert "Temp directory creation" in result.payload.message

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

        mock_platform.get_relevant_handlers.return_value = ([], None)

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.requires_input()
        assert result.payload.query_id == "generic_query"
        assert "No TOC file" in result.payload.message

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

        mock_platform.get_relevant_handlers.return_value = ([], None)

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.requires_input()
        assert result.payload.query_id == "generic_query"
        assert "CHD creation failed" in result.payload.message

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

        assert result.requires_input()
        assert result.payload.query_id == "generic_query"
        assert "disk space" in result.payload.message.lower()

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

        mock_platform.get_relevant_handlers.return_value = ([], None)

        process = ChdBuildProcess(mock_platform)

        with patch("rom_management.processing.chd_build_process.CHD") as mock_chd_class:
            mock_chd = Mock()
            mock_chd.exists = False
            mock_chd_class.return_value = mock_chd

            result = process._build_single_chd(
                mock_media, "TestTitle", "/test/path/disk1.chd"
            )

        mock_optical.cleanup.assert_called_once()
        assert result.requires_input()

    def test_build_single_chd_no_zip_path(self, mock_platform, mock_media):
        """Test CHD building when no zip_path is set"""
        mock_media.zip_path = None

        process = ChdBuildProcess(mock_platform)

        result = process._build_single_chd(
            mock_media, "TestTitle", "/test/path/disk1.chd"
        )

        assert result.requires_input()
        assert "ZIP path not set" in result.payload.message
