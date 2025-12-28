import pytest
from unittest.mock import Mock, patch
from menus.main import MainMenu
from menus.settings import SettingsMenu, DatMenu
from menus.mapping import MapMenu, MapStageTwo, MapStageThree
from menus.chd_menus import CHDBuildMenu
from rom_management.processing.models import PendingInputPayload, Action
from typing import Optional, Tuple


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

    def test_display_and_get_input_raises_not_implemented(self):
        """Test that CHDBuildMenu raises NotImplementedError for user input"""
        menu = CHDBuildMenu()
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
