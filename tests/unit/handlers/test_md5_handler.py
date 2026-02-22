import pytest
from unittest.mock import Mock
from rom_management.handlers.md5_handler import MD5ScanHandler
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
)


class TestMD5ScanHandler:
    """Test MD5ScanHandler actions"""

    def test_handler_initialization(self):
        """Test handler initializes correctly"""
        handler = MD5ScanHandler()

        assert handler.name == "md5_scan_handler"
        assert handler.menu is None
        assert handler.PROCESS_CATEGORY == "MD5 hash"
        assert handler.HANDLER_STATE_KEY == "md5_enabled"

    def test_action_handle(self):
        """Test HANDLE action sets handler state and executes step"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process._handler_state = {}
        mock_process._execute_step = Mock(return_value=ResultObject.success())
        mock_process.processed_items = 5
        mock_process.current_item = "test_item"

        result = handler.execute_action(Action.HANDLE, mock_process, {})

        assert result.is_success()
        assert mock_process._handler_state["md5_enabled"] is True
        mock_process._execute_step.assert_called_once()

    def test_action_handle_all(self):
        """Test HANDLE_ALL action sets process-level handler state"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process._handler_state = {}
        mock_process._execute_step = Mock(return_value=ResultObject.success())
        mock_process.processed_items = 5
        mock_process.current_item = "test_item"

        result = handler.execute_action(Action.HANDLE_ALL, mock_process, {})

        assert result.is_success()
        assert mock_process._handler_state["md5_enabled"] is True
        mock_process._execute_step.assert_called_once()

    def test_action_skip_returns_none(self):
        """Test SKIP action returns None for default handling"""
        handler = MD5ScanHandler()
        mock_process = Mock()

        result = handler.execute_action(Action.SKIP, mock_process, {})

        assert result is None

    def test_action_skip_all_returns_none(self):
        """Test SKIP_ALL action returns None for default handling"""
        handler = MD5ScanHandler()
        mock_process = Mock()

        result = handler.execute_action(Action.SKIP_ALL, mock_process, {})

        assert result is None

    def test_action_stop_returns_none(self):
        """Test STOP action returns None for default handling"""
        handler = MD5ScanHandler()
        mock_process = Mock()

        result = handler.execute_action(Action.STOP, mock_process, {})

        assert result is None

    def test_action_unknown_returns_none(self):
        """Test unknown action returns None (will be handled by default handler)"""
        handler = MD5ScanHandler()
        mock_process = Mock()

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        # Unknown actions should return None for default handling
        assert result is None
