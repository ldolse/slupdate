import pytest
from unittest.mock import Mock, patch
from menus.main import MainMenu
from menus.settings import SettingsMenu, DatMenu
from menus.mapping import MapMenu, MapStageTwo, MapStageThree
from menus.chd_menus import (
    CHDBuildMenu,
    HandlerErrorMenu,
    CHDErrorMenu,
    ExistingCHDMenu,
)
from menus.progress import ValidationProgressMenu
from rom_management.processing.models import PendingInputPayload, Action
from rom_management.exceptions import HandlerException


class TestMainMenu:
    """Tests for MainMenu"""

    def test_menu_initialization(self):
        """Test that MainMenu initializes correctly"""
        menu = MainMenu()
        assert menu.name == "main_menu"
        assert menu.message == "Main Menu"
        assert len(menu.options) == 5

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that MainMenu raises NotImplementedError for user input"""
        menu = MainMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestSettingsMenu:
    """Tests for SettingsMenu"""

    def test_menu_initialization(self):
        """Test that SettingsMenu initializes correctly"""
        menu = SettingsMenu()
        assert menu.name == "settings_menu"
        assert menu.message == "Settings Menu"
        assert len(menu.options) == 6

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that SettingsMenu raises NotImplementedError for user input"""
        menu = SettingsMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestDatMenu:
    """Tests for DatMenu"""

    def test_menu_initialization(self):
        """Test that DatMenu initializes correctly"""
        menu = DatMenu()
        assert menu.name == "dat_menu"
        assert "Configure DAT Directories" in menu.message
        assert len(menu.options) == 3

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that DatMenu raises NotImplementedError for user input"""
        menu = DatMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestMapMenu:
    """Tests for MapMenu"""

    def test_menu_initialization(self):
        """Test that MapMenu initializes correctly"""
        menu = MapMenu()
        assert menu.name == "map_menu"
        assert "Process software lists and dat files" in menu.message
        assert len(menu.options) == 6

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that MapMenu raises NotImplementedError for user input"""
        menu = MapMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestMapStageTwo:
    """Tests for MapStageTwo"""

    def test_menu_initialization(self):
        """Test that MapStageTwo initializes correctly"""
        menu = MapStageTwo()
        assert menu.name == "map_stage_two"
        assert "Use other reference datapoints" in menu.message
        assert len(menu.options) == 7

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that MapStageTwo raises NotImplementedError for user input"""
        menu = MapStageTwo()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestMapStageThree:
    """Tests for MapStageThree"""

    def test_menu_initialization(self):
        """Test that MapStageThree initializes correctly"""
        menu = MapStageThree()
        assert menu.name == "map_stage_three"
        assert menu.message == "Assisted Mapping Functions"
        assert len(menu.options) == 7

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that MapStageThree raises NotImplementedError for user input"""
        menu = MapStageThree()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP],
        )

        with pytest.raises(
            NotImplementedError, match="does not support process-based user input"
        ):
            menu.display_and_get_input(payload)


class TestCHDBuildMenu:
    """Tests for CHDBuildMenu"""

    def test_menu_initialization(self):
        """Test that CHDBuildMenu initializes correctly"""
        menu = CHDBuildMenu()
        assert menu.name == "chd_build_menu"
        assert menu.message == "Create CHDs from ROMs"
        assert len(menu.options) == 4


class TestHandlerErrorMenu:
    """Tests for HandlerErrorMenu"""

    def test_menu_initialization(self):
        """Test that HandlerErrorMenu initializes correctly"""
        menu = HandlerErrorMenu()
        assert menu.name == "handler_error_menu"
        assert "Handler Error" in menu.message
        assert len(menu.options) == 3

    def test_display_and_get_input_returns_skip(self):
        """Test that HandlerErrorMenu display_and_get_input returns SKIP"""
        menu = HandlerErrorMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP, Action.RETRY, Action.STOP],
        )

        action, params = menu.display_and_get_input(payload)
        assert action == Action.SKIP
        assert params is None

    def test_set_payload_updates_message(self):
        """Test that set_payload updates the message"""
        menu = HandlerErrorMenu()
        menu.set_payload("Test error message")
        assert "Test error message" in menu.message


class TestCHDErrorMenu:
    """Tests for CHDErrorMenu"""

    def test_menu_initialization(self):
        """Test that CHDErrorMenu initializes correctly"""
        menu = CHDErrorMenu()
        assert menu.name == "chd_error_menu"
        assert "Error processing CHD" in menu.message
        assert len(menu.options) == 3

    def test_display_and_get_input_returns_skip(self):
        """Test that CHDErrorMenu display_and_get_input returns SKIP"""
        menu = CHDErrorMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[Action.SKIP_EXISTING, Action.STOP, Action.RETRY],
        )

        action, params = menu.display_and_get_input(payload)
        # CHDErrorMenu returns SKIP (deprecated menu returns generic action)
        assert action == Action.SKIP
        assert params is None


class TestExistingCHDMenu:
    """Tests for ExistingCHDMenu"""

    def test_menu_initialization(self):
        """Test that ExistingCHDMenu initializes correctly"""
        menu = ExistingCHDMenu()
        assert menu.name == "existing_chd_menu"
        assert "CHD already exists" in menu.message
        assert len(menu.options) == 4

    def test_display_and_get_input_returns_skip_existing(self):
        """Test that ExistingCHDMenu display_and_get_input returns SKIP_EXISTING"""
        menu = ExistingCHDMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[
                Action.OVERWRITE,
                Action.SKIP_EXISTING,
                Action.SET_OVERWRITE_PREFERENCE,
                Action.SET_SKIP_PREFERENCE,
            ],
        )

        action, params = menu.display_and_get_input(payload)
        assert action == Action.SKIP_EXISTING
        assert params is None


class TestValidationProgressMenu:
    """Tests for ValidationProgressMenu (deprecated)"""

    def test_menu_initialization(self):
        """Test that ValidationProgressMenu initializes correctly"""
        menu = ValidationProgressMenu()
        assert menu.name == "validation_progress_menu"
        assert "Full Scan Required" in menu.message
        assert len(menu.options) == 5

    def test_display_and_get_input_returns_skip(self):
        """Test that ValidationProgressMenu display_and_get_input returns SKIP"""
        menu = ValidationProgressMenu()
        payload = PendingInputPayload(
            query_id="test",
            message="Test message",
            item=Mock(),
            valid_actions=[
                Action.SKIP,
                Action.SCAN_MD5,
                Action.SKIP_ALL,
                Action.SCAN_ALL_MD5,
                Action.STOP,
            ],
        )

        action, params = menu.display_and_get_input(payload)
        assert action == Action.SKIP
        assert params is None
