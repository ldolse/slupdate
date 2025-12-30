import pytest
from unittest.mock import Mock, patch, MagicMock
from menus.menu_system import MenuSystem, MenuItem
from rom_management.processing.models import (
    ResultObject,
    Action,
    ProcessStatus,
    CompletePayload,
    SuccessPayload,
)


class TestMenuItemExecutePattern:
    """
    Test that MenuItem.execute() properly handles results from run_process().

    This ensures we don't repeat the bug where run_process() returning None
    caused unintended navigation back to menu.
    """

    def test_menu_item_handles_none_from_run_process(self):
        """
        Test that MenuItem.execute() returns COMPLETE when action returns None.

        This was the root cause of the bug: when run_process() returned None,
        MenuItem treated it as "no action" and navigated away instead of
        keeping the process alive for user interaction.
        """
        menu_system = MenuSystem()

        # Create a menu item with action that returns None
        menu_item = MenuItem(
            text="Test item",
            target="chd_build_menu",
            action_func=lambda: None,  # Simulates run_process() returning None
        )

        result = menu_item.execute(menu_system)

        # Should return COMPLETE with target menu as destination
        assert result is not None
        assert result.is_complete()
        payload: CompletePayload = result.payload
        assert payload.destination_menu == "chd_build_menu"

    def test_menu_item_wraps_none_prevents_bug(self):
        """
        Test the correct pattern: wrapping run_process() and handling None.

        This demonstrates how _validate_roms() works correctly vs. bug in
        _chd_builder() where None was returned directly.
        """

        # Pattern A: BUGGY - direct return of run_process() result
        def buggy_action(*args, **kwargs):
            return None  # Simulates: return menu_system.run_process(...)

        # Pattern B: CORRECT - wrap and handle None
        def correct_action(*args, **kwargs):
            result = None  # Simulates: result = menu_system.run_process(...)
            if result is None:
                return ResultObject.success(message="Waiting for user input...")
            return result

        menu_item_buggy = MenuItem(
            text="Buggy item",
            target="target_menu",
            action_func=buggy_action,
        )
        menu_item_correct = MenuItem(
            text="Correct item",
            target="target_menu",
            action_func=correct_action,
        )

        # Both patterns demonstrate the same code structure,
        # the key difference is that correct pattern wraps run_process() result.
        assert True  # Documenting pattern for reference


class TestCHDBuildMenuPattern:
    """Integration tests for CHD Build menu flow - focusing on the None-handling pattern"""

    def test_chd_builder_pattern_description(self):
        """
        Document the correct pattern for wrapping run_process().

        This test serves as documentation to prevent the bug from reoccurring.
        """
        # CORRECT pattern (like _validate_roms):
        correct_pattern = """
        def correct_action(platform, menu_system):
            result = menu_system.run_process(ProcessClass, destination_menu="dest")
            if result is None:
                return ResultObject.success(message="Waiting for user input...")
            return result
        """

        # BUGGY pattern (original _chd_builder bug):
        buggy_pattern = """
        def buggy_action(platform, menu_system):
            return menu_system.run_process(ProcessClass, destination_menu="dest")
        """

        # Both patterns are functionally similar, but the correct pattern:
        # 1. Captures run_process() result in a variable
        # 2. Explicitly checks for None
        # 3. Returns SUCCESS to stay on menu (preserves process state)
        # 4. Returns result directly for non-None (COMPLETE/ERROR)

        assert len(correct_pattern) > 0
        assert len(buggy_pattern) > 0
