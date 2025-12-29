"""Test for query menu handling in main loop"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from menus.query_menus import GenericQueryMenu
from menus.menu_system import MenuSystem
from rom_management.processing.models import (
    PendingInputPayload,
    Action,
    ResultObject,
    PartProcessingItem,
)


def test_query_menu_has_display_and_get_input():
    """Verify GenericQueryMenu has the required methods"""
    menu = GenericQueryMenu()
    assert hasattr(menu, "display_and_get_input")
    assert hasattr(menu, "execute")


def test_query_menu_execute_calls_resume_process():
    """Verify query menu execute() calls resume_process on menu_system"""
    # Setup
    menu = GenericQueryMenu()
    menu_system = Mock(spec=MenuSystem)
    menu_system._pending_action_handler = (menu, Mock())

    payload = PendingInputPayload(
        query_id="generic_query",
        message="Test message",
        item=Mock(),
        valid_actions=[Action.SKIP, Action.STOP],
    )
    menu_system._pending_action_handler = (menu, Mock(payload=payload))

    # Mock display_and_get_input to return an action
    with patch.object(menu, "display_and_get_input", return_value=(Action.SKIP, None)):
        # Execute
        result = menu.execute(menu_system)

        # Verify
        assert result.is_success()
        menu_system.resume_process.assert_called_once_with(Action.SKIP, None)


def test_query_menu_execute_returns_to_main_menu_if_no_pending_handler():
    """Verify query menu returns to main menu if no pending process"""
    menu = GenericQueryMenu()
    menu_system = Mock(spec=MenuSystem)
    # No _pending_action_handler set

    result = menu.execute(menu_system)

    assert result.is_complete()
    assert result.payload.destination_menu == "main_menu"
    assert result.payload.total_processed == 0
