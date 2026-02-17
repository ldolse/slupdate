"""
Unit tests for Platform class in consoles.py

Tests cover all remaining functionality after Phase 4 cleanup:
- Properties and getters
- State management
- DAT management
- CHD preferences
- Handler registry integration
"""

import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from consoles import Platform
from consoles.platform_state import PlatformState
from media_registry import MediaRegistry, CDMedia
from dat import RomDat
from softwarelist import SoftwareList


@pytest.fixture
def mock_platform():
    """Create a mock Platform instance for testing"""
    platform = Platform(
        key="test_platform",
        name="Test Platform",
        softlist_xml_path="/tmp/test_softlist.xml",
        chd_path="/tmp/test_chd",
    )
    return platform


@pytest.fixture
def mock_platform_manager():
    """Create a mock PlatformManager"""
    from consoles.platform_manager import PlatformManager

    pm = Mock(spec=PlatformManager)
    pm.romroot = "/tmp/roms"
    pm.datroot = "/tmp/dats"
    pm.tmpdsk = "/tmp/tmpdsk"
    return pm


@pytest.fixture
def mock_softwarelist():
    """Create a mock SoftwareList"""
    sl = Mock(spec=SoftwareList)
    sl.software_items = []
    return sl


@pytest.fixture
def mock_dat():
    """Create a mock RomDat"""
    dat = Mock(spec=RomDat)
    dat.name = "Test DAT"
    dat.rom_path = "/tmp/roms/test"
    dat.roms = []
    return dat


class TestPlatformInitialization:
    """Test Platform initialization and basic attributes"""

    def test_initialization(self):
        """Test Platform initializes with correct attributes"""
        platform = Platform(
            key="psx",
            name="Sony PlayStation",
            softlist_xml_path="/path/to/softlist.xml",
            chd_path="/path/to/chds",
        )

        assert platform.key == "psx"
        assert platform.name == "Sony PlayStation"
        assert platform.softlist_xml_path == "/path/to/softlist.xml"
        assert platform.chd_path == "/path/to/chds"
        assert platform.softwarelist is None
        assert platform.redump_db is None
        assert platform.mr is None
        assert platform._chd_handling_preference is None
        assert platform._chd_build_index == 0

    def test_initialization_creates_platform_state(self):
        """Test Platform creates a PlatformState instance"""
        platform = Platform(
            key="test",
            name="Test",
            softlist_xml_path="/tmp/test.xml",
            chd_path="/tmp/chds",
        )

        assert isinstance(platform.state, PlatformState)

    def test_initialization_creates_handler_registry(self):
        """Test Platform initializes handler_registry attribute"""
        platform = Platform(
            key="test",
            name="Test",
            softlist_xml_path="/tmp/test.xml",
            chd_path="/tmp/chds",
        )

        assert platform.handler_registry is not None
        assert hasattr(platform.handler_registry, "handlers")


class TestPlatformState:
    """Test Platform state management"""

    def test_save_state_creates_state_object(self, mock_platform, mock_softwarelist):
        """Test save_state returns PlatformState object"""
        mock_platform.softwarelist = mock_softwarelist
        mock_platform.dat_directories = {"/tmp/dats": []}
        mock_platform._chd_build_index = 5
        mock_platform._chd_handling_preference = "overwrite"
        mock_platform.validated_chds = set()

        state = mock_platform.save_state()

        assert isinstance(state, PlatformState)
        assert state._chd_build_index == 5
        assert state._chd_handling_preference == "overwrite"

    def test_load_state_restores_platform_state(self, mock_platform):
        """Test load_state restores platform from saved state"""
        state = PlatformState()
        state._chd_build_index = 10
        state._chd_handling_preference = "skip"
        state.dat_directories = ["/tmp/dats1", "/tmp/dats2"]

        mock_platform.load_state(state)

        assert mock_platform._chd_build_index == 10
        assert mock_platform._chd_handling_preference == "skip"
        assert "/tmp/dats1" in mock_platform.dat_directories

    def test_reset_preserves_dat_directories(self, mock_platform):
        """Test reset preserves DAT directories but clears other state"""
        from rom_management import CHD

        mock_platform.dat_directories = {"/tmp/dats": []}
        mock_platform.softwarelist = Mock()
        mock_platform.redump_db = Mock()
        mock_platform.mr = Mock()
        mock_platform._chd_handling_preference = "overwrite"
        mock_platform._chd_build_index = 15

        mock_platform.reset()

        # DAT directories preserved
        assert "/tmp/dats" in mock_platform.dat_directories
        # Other state cleared
        assert mock_platform.softwarelist is None
        assert mock_platform.redump_db is None
        assert mock_platform.mr is None
        assert mock_platform._chd_handling_preference is None
        assert mock_platform._chd_build_index == 0


class TestPlatformCHDPreferences:
    """Test CHD handling preferences"""

    def test_chd_handling_preference_property(self, mock_platform):
        """Test chd_handling_preference property returns current preference"""
        mock_platform._chd_handling_preference = "skip"

        assert mock_platform.chd_handling_preference == "skip"

    def test_set_chd_preference_valid(self, mock_platform):
        """Test set_chd_preference accepts valid values"""
        mock_platform.set_chd_preference("overwrite")
        assert mock_platform._chd_handling_preference == "overwrite"

        mock_platform.set_chd_preference("skip")
        assert mock_platform._chd_handling_preference == "skip"

        mock_platform.set_chd_preference("ask")
        assert mock_platform._chd_handling_preference == "ask"

    def test_set_chd_preference_invalid_raises_error(self, mock_platform):
        """Test set_chd_preference raises ValueError for invalid values"""
        with pytest.raises(ValueError):
            mock_platform.set_chd_preference("invalid")

        with pytest.raises(ValueError):
            mock_platform.set_chd_preference("")


class TestPlatformProperties:
    """Test Platform properties and getters"""

    def test_all_dats_property_flattens_dats(self, mock_platform, mock_dat):
        """Test _all_dats property flattens DAT instances across directories"""
        dat1 = mock_dat
        dat2 = Mock(spec=RomDat)
        dat2.name = "Test DAT 2"

        mock_platform.dat_directories = {
            "/tmp/dats1": [dat1],
            "/tmp/dats2": [dat2],
        }

        all_dats = mock_platform._all_dats

        assert len(all_dats) == 2
        assert dat1 in all_dats
        assert dat2 in all_dats

    def test_media_to_process_property_slices_by_index(self, mock_platform):
        """Test _media_to_process property slices matched_buildable_media"""
        from collections import OrderedDict
        from media_registry import CDMedia

        media1 = Mock(spec=CDMedia)
        media2 = Mock(spec=CDMedia)
        media3 = Mock(spec=CDMedia)

        mock_platform.matched_buildable_media = OrderedDict(
            [(media1, None), (media2, None), (media3, None)]
        )
        mock_platform._chd_build_index = 1

        media_to_process = mock_platform._media_to_process

        assert len(media_to_process) == 2
        assert media1 not in media_to_process
        assert media2 in media_to_process
        assert media3 in media_to_process

    def test_chd_count_property(self, mock_platform):
        """Test chd_count property returns validated CHDs count"""
        from rom_management import CHD

        chd1 = Mock(spec=CHD)
        chd2 = Mock(spec=CHD)
        chd3 = Mock(spec=CHD)

        mock_platform.validated_chds = {chd1, chd2, chd3}

        assert mock_platform.chd_count == 3

    def test_total_source_rom_property(self, mock_platform):
        """Test total_source_rom returns matched_buildable_media count"""
        from collections import OrderedDict
        from media_registry import CDMedia

        media1 = Mock(spec=CDMedia)
        media2 = Mock(spec=CDMedia)

        mock_platform.matched_buildable_media = OrderedDict(
            [(media1, None), (media2, None)]
        )

        assert mock_platform.total_source_rom == 2


class TestPlatformHandlers:
    """Test handler registry integration"""

    def test_get_relevant_handlers(self, mock_platform):
        """Test get_relevant_handlers calls handler registry"""
        from optical_media.utils import OpticalMediaProcessor
        from rom_management.handlers import registry

        # Create a more complete mock media object
        mock_media = Mock(spec=CDMedia)
        mock_media.platform = "test_platform"
        mock_media.id = "test_id"
        mock_media.dat_game_entry = Mock()
        mock_media.dat_game_entry.dat = Mock()
        mock_media.dat_game_entry.dat.dat_group = "test_group"

        mock_file_data = Mock(spec=OpticalMediaProcessor)
        mock_file_data.format = "ccd"
        mock_file_data.file_list = []  # Empty file list so format handlers return False

        mock_platform.handler_registry = registry

        # Should return handlers based on media and file_data
        handlers = mock_platform.get_relevant_handlers(mock_media, mock_file_data)

        # Verify handlers are returned (specific handlers depend on registry)
        # With empty file_list, CCD handler should be filtered out
        assert isinstance(handlers, list)

    def test_get_relevant_handlers_filters_by_validate_preconditions(
        self, mock_platform
    ):
        """Test get_relevant_handlers filters out handlers that return False from validate_preconditions"""
        from optical_media.utils import OpticalMediaProcessor
        from rom_management.handlers.base import SpecialHandler
        from rom_management.handlers import registry
        from rom_management.processing.models import ResultObject

        # Create a test handler that always returns False from validate_preconditions
        class TestFilterHandler(SpecialHandler):
            def __init__(self):
                super().__init__("TestFilter")

            def validate_preconditions(self, media, file_data):
                return False  # This handler should be filtered out

            def execute(self, media, file_data):
                return ResultObject.success(message="Test handler executed")

        # Temporarily register our test handler for redump dat_group
        registry.handlers["dat_group"]["test_filter"] = TestFilterHandler

        try:
            # Create mock media with test_filter dat_group
            mock_media = Mock(spec=CDMedia)
            mock_media.platform = "unknown_platform"
            mock_media.id = "test_id"
            mock_media.dat_game_entry = Mock()
            mock_media.dat_game_entry.dat = Mock()
            mock_media.dat_game_entry.dat.dat_group = "test_filter"

            mock_file_data = Mock(spec=OpticalMediaProcessor)
            mock_file_data.format = None  # No format handler

            mock_platform.handler_registry = registry

            # Should NOT return the TestFilterHandler because validate_preconditions returns False
            handlers = mock_platform.get_relevant_handlers(mock_media, mock_file_data)
            handler_names = [h.name for h in handlers]

            assert "TestFilter" not in handler_names, (
                "Handler with validate_preconditions=False should be filtered out"
            )
        finally:
            # Clean up: remove our test handler
            if "test_filter" in registry.handlers["dat_group"]:
                del registry.handlers["dat_group"]["test_filter"]

    def test_get_relevant_handlers_includes_valid_handlers(self, mock_platform):
        """Test get_relevant_handlers includes handlers that return True from validate_preconditions"""
        from optical_media.utils import OpticalMediaProcessor
        from rom_management.handlers.base import SpecialHandler
        from rom_management.handlers import registry
        from rom_management.processing.models import ResultObject

        # Create a test handler that returns True from validate_preconditions
        class TestValidHandler(SpecialHandler):
            def __init__(self):
                super().__init__("TestValid")

            def validate_preconditions(self, media, file_data):
                return True  # This handler should be included

            def execute(self, media, file_data):
                return ResultObject.success(message="Test handler executed")

        # Temporarily register our test handler for a unique platform
        test_platform_key = "unique_test_platform_xyz"
        registry.handlers["platform"][test_platform_key] = TestValidHandler

        try:
            # Create mock media with our test platform
            mock_media = Mock(spec=CDMedia)
            mock_media.platform = test_platform_key
            mock_media.id = "test_id"
            mock_media.dat_game_entry = None  # No dat_game_entry

            mock_file_data = Mock(spec=OpticalMediaProcessor)
            mock_file_data.format = None  # No format handler

            mock_platform.handler_registry = registry

            # Should return the TestValidHandler because validate_preconditions returns True
            handlers = mock_platform.get_relevant_handlers(mock_media, mock_file_data)
            handler_names = [h.name for h in handlers]

            assert "TestValid" in handler_names, (
                "Handler with validate_preconditions=True should be included"
            )
        finally:
            # Clean up: remove our test handler
            if test_platform_key in registry.handlers["platform"]:
                del registry.handlers["platform"][test_platform_key]


class TestPlatformDATManagement:
    """Test DAT management functionality"""

    def test_update_dats_skips_invalid_dats(self, mock_platform, mock_platform_manager):
        """Test update_dats skips DAT files that can't be parsed"""
        mock_platform.pm = mock_platform_manager
        mock_platform.dat_directories = {"/tmp/dats": []}

        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=["invalid.dat"]):
                    with patch("consoles.console.RomDat.from_file") as mock_from_file:
                        # Simulate invalid DAT file
                        mock_from_file.side_effect = Exception("Invalid DAT")

                        mock_platform.update_dats()

                        # Should skip invalid DAT and not raise error
                        assert mock_from_file.call_count == 1
                        # Directory should have empty dats list
                        assert len(mock_platform.dat_directories["/tmp/dats"]) == 0

    def test_update_dats_creates_valid_dats(self, mock_platform, mock_platform_manager):
        """Test update_dats creates RomDat instances for valid DAT files"""
        mock_platform.pm = mock_platform_manager
        mock_platform.pm.romvault = (
            True  # Set to True to skip interactive select_directory
        )
        mock_platform.pm.romroot = "/tmp/roms"
        mock_platform.dat_directories = {"/tmp/dats": []}

        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", return_value=["test1.dat", "test2.xml"]):
                    with patch("consoles.console.RomDat.from_file") as mock_from_file:
                        mock_dat1 = Mock(spec=RomDat)
                        mock_dat1.name = "Test1"
                        mock_dat2 = Mock(spec=RomDat)
                        mock_dat2.name = "Test2"
                        mock_from_file.side_effect = [mock_dat1, mock_dat2]

                        mock_platform.update_dats()

                        # Verify from_file was called for each DAT file
                        assert mock_from_file.call_count == 2
                        # Verify DATs were added to platform
                        assert len(mock_platform.dat_directories["/tmp/dats"]) == 2


class TestPlatformSoftlist:
    """Test SoftwareList management"""

    @patch("consoles.console.SoftwareList.from_file")
    def test_register_softlist_loads_and_registers(self, mock_from_file, mock_platform):
        """Test register_softlist loads and registers SoftwareList"""
        mock_sl = Mock(spec=SoftwareList)
        mock_sl.software_items = []
        mock_from_file.return_value = mock_sl

        mock_platform.mr = Mock(spec=MediaRegistry)

        mock_platform.register_softlist()

        # Verify SoftwareList was loaded
        assert mock_platform.softwarelist == mock_sl
        # Verify extract_source_data was called
        mock_sl.extract_source_data.assert_called_once()
        # Verify register_to_media_registry was called
        mock_sl.register_to_media_registry.assert_called_once_with(mock_platform.mr)


class TestPlatformStats:
    """Test Platform statistics properties"""

    def test_total_parts_property(self, mock_platform):
        """Test total_parts returns sum of parts across software items"""
        mock_platform.softwarelist = Mock(spec=SoftwareList)
        mock_software1 = Mock()
        mock_software1.parts = [Mock(), Mock()]
        mock_software2 = Mock()
        mock_software2.parts = [Mock()]
        mock_platform.softwarelist.software_items = [
            mock_software1,
            mock_software2,
        ]

        assert mock_platform.total_parts == 3

    def test_total_softlist_entries_property(self, mock_platform):
        """Test total_softlist_entries returns software_items count"""
        mock_platform.softwarelist = Mock(spec=SoftwareList)
        mock_platform.softwarelist.software_items = [Mock(), Mock(), Mock()]

        assert mock_platform.total_softlist_entries == 3

    def test_get_source_stats_counts_by_group(self, mock_platform):
        """Test get_source_stats counts dumps by source group"""
        mock_platform.softwarelist = Mock(spec=SoftwareList)
        mock_part1 = Mock()
        mock_part1.source_group = "redump"
        mock_part2 = Mock()
        mock_part2.source_group = "redump"
        mock_part3 = Mock()
        mock_part3.source_group = "no-intro"

        mock_software1 = Mock()
        mock_software1.parts = [mock_part1, mock_part2]
        mock_software2 = Mock()
        mock_software2.parts = [mock_part3]

        mock_platform.softwarelist.software_items = [
            mock_software1,
            mock_software2,
        ]

        stats = mock_platform.get_source_stats()

        assert stats["redump"] == 2
        assert stats["no-intro"] == 1


class TestPlatformStateMethods:
    """Tests for PlatformState zip path persistence methods"""

    def test_add_validated_zip_path(self):
        """Test adding a validated zip path stores both signature and path"""
        state = PlatformState()

        state.add_validated_zip_path("sha1:abc123", "/path/to/game.zip")

        assert "sha1:abc123" in state.matched_media_sigs
        assert state.validated_zip_paths["sha1:abc123"] == "/path/to/game.zip"

    def test_add_validated_zip_path_appends_to_matched_sigs(self):
        """Test adding validated zip path doesn't duplicate matched_media_sigs"""
        state = PlatformState()
        state.matched_media_sigs = ["existing:sig"]

        state.add_validated_zip_path("new:sig", "/path/to/new.zip")

        assert len(state.matched_media_sigs) == 2
        assert "existing:sig" in state.matched_media_sigs
        assert "new:sig" in state.matched_media_sigs

    def test_get_zip_path_returns_path(self):
        """Test getting zip path for a signature"""
        state = PlatformState()
        state.validated_zip_paths["sig123"] = "/path/to/game.zip"

        result = state.get_zip_path("sig123")

        assert result == "/path/to/game.zip"

    def test_get_zip_path_returns_none_for_unknown(self):
        """Test getting zip path returns None for unknown signature"""
        state = PlatformState()

        result = state.get_zip_path("unknown:sig")

        assert result is None

    def test_is_validated_returns_true_for_known(self):
        """Test is_validated returns True for known signature"""
        state = PlatformState()
        state.matched_media_sigs = ["known:sig"]

        assert state.is_validated("known:sig") is True

    def test_is_validated_returns_false_for_unknown(self):
        """Test is_validated returns False for unknown signature"""
        state = PlatformState()

        assert state.is_validated("unknown:sig") is False

    def test_validated_zip_paths_defaults_to_empty_dict(self):
        """Test validated_zip_paths defaults to empty dict"""
        state = PlatformState()

        assert state.validated_zip_paths == {}
        assert isinstance(state.validated_zip_paths, dict)
