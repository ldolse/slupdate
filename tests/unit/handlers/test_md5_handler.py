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

    def test_action_scan_md5(self):
        """Test SCAN_MD5 action"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process.use_md5 = False
        mock_process._execute_step = Mock(return_value=ResultObject.success())
        mock_process.processed_items = 5
        mock_process.current_item = "test_item"

        result = handler.execute_action(Action.SCAN_MD5, mock_process, {})

        assert result.is_success()
        mock_process._execute_step.assert_called_once()
        # Verify item was advanced on success
        assert mock_process.current_item is None
        assert mock_process.processed_items == 6

    def test_action_scan_all_md5(self):
        """Test SCAN_ALL_MD5 action"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process._execute_step = Mock(return_value=ResultObject.success())
        mock_process.processed_items = 5
        mock_process.current_item = "test_item"

        result = handler.execute_action(Action.SCAN_ALL_MD5, mock_process, {})

        assert result.is_success()
        mock_process._execute_step.assert_called_once()
        # Verify item was advanced on success
        assert mock_process.current_item is None
        assert mock_process.processed_items == 6

    def test_action_skip(self):
        """Test SKIP action"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process.current_item = "test_item"
        mock_process.processed_items = 5
        mock_process._handle_skip = Mock(
            return_value=ResultObject.success(
                message="Skipped MD5 scan for current item"
            )
        )

        result = handler.execute_action(Action.SKIP, mock_process, {})

        assert result.is_success()
        mock_process._handle_skip.assert_called_once_with(
            "Skipped MD5 scan for current item"
        )

    def test_action_skip_all(self):
        """Test SKIP_ALL action"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process.current_item = "test_item"
        mock_process.processed_items = 5
        mock_process._handle_skip_all = Mock(
            return_value=ResultObject.success(message="Skip all remaining MD5 scans")
        )

        result = handler.execute_action(Action.SKIP_ALL, mock_process, {})

        assert result.is_success()
        mock_process._handle_skip_all.assert_called_once_with(
            "Skip all MD5 scanning", category="MD5 scanning"
        )

    def test_action_stop(self):
        """Test STOP action"""
        handler = MD5ScanHandler()
        mock_process = Mock()
        mock_process.processed_items = 10
        mock_process._handle_stop = Mock(
            return_value=ResultObject.complete(total_processed=10, stopped_early=True)
        )

        result = handler.execute_action(Action.STOP, mock_process, {})

        assert result.is_complete()
        mock_process._handle_stop.assert_called_once()

    def test_action_unknown(self):
        """Test unknown action returns error"""
        handler = MD5ScanHandler()
        mock_process = Mock()

        result = handler.execute_action(Action.OVERWRITE, mock_process, {})

        assert result.is_error()
        assert result.payload.error_type == "UnknownAction"
