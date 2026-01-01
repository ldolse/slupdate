import pytest
from unittest.mock import Mock, patch
from menus.main import MainMenu
from menus.settings import SettingsMenu, DatMenu
from menus.mapping import MapMenu, MapStageTwo, MapStageThree
from menus.chd_menus import CHDBuildMenu
from rom_management.processing.models import ResultObject
from menus.ux_models import DisplayData


class TestMainMenu:
    """Tests for MainMenu"""

    def test_menu_initialization(self):
        """Test that MainMenu initializes correctly"""
        menu = MainMenu()
        assert menu.name == "main_menu"
        assert menu.message == "Main Menu"
        assert len(menu.options) == 5

    def test_get_display_data(self):
        """Test that MainMenu returns DisplayData via adapter"""
        menu = MainMenu()
        display_data = menu.get_display_data()

        assert display_data.message == "Main Menu"
        assert len(display_data.choices) == 5
        assert display_data.question_text == "What would you like to do?"

    def test_execute_custom_action(self):
        """Test that MainMenu executes MenuItem actions via adapter"""
        menu = MainMenu()
        system = Mock()
        result = menu.execute_custom_action(system, menu.options[0])

        assert result.is_complete() or result.is_success()


class TestSettingsMenu:
    """Tests for SettingsMenu"""

    def test_menu_initialization(self):
        """Test that SettingsMenu initializes correctly"""
        menu = SettingsMenu()
        assert menu.name == "settings_menu"
        assert menu.message == "Settings Menu"
        assert len(menu.options) == 6


class TestDatMenu:
    """Tests for DatMenu"""

    def test_menu_initialization(self):
        """Test that DatMenu initializes correctly"""
        menu = DatMenu()
        assert "Configure DAT Directories" in menu.message
        assert len(menu.options) == 3


class TestMapMenu:
    """Tests for MapMenu"""

    def test_menu_initialization(self):
        """Test that MapMenu initializes correctly"""
        menu = MapMenu()
        assert "Process software lists and dat files" in menu.message
        assert len(menu.options) == 6


class TestMapStageTwo:
    """Tests for MapStageTwo"""

    def test_menu_initialization(self):
        """Test that MapStageTwo initializes correctly"""
        menu = MapStageTwo()
        assert "Use other reference datapoints" in menu.message
        assert len(menu.options) == 7


class TestMapStageThree:
    """Tests for MapStageThree"""

    def test_menu_initialization(self):
        """Test that MapStageThree initializes correctly"""
        menu = MapStageThree()
        assert menu.message == "Assisted Mapping Functions"
        assert len(menu.options) == 7


class TestCHDBuildMenu:
    """Tests for CHDBuildMenu"""

    def test_menu_initialization(self):
        """Test that CHDBuildMenu initializes correctly"""
        menu = CHDBuildMenu()
        assert menu.name == "chd_build_menu"
        assert menu.message == "Create CHDs from ROMs"
        # Phase 4 removed "Validate source ROMs (old method)" option
        assert len(menu.options) == 3
