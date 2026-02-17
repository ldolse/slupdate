import pytest
from unittest.mock import Mock, MagicMock
from rom_management.processing.base_process import BaseProcess
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
    BaseProcessingItem,
)


class TestBaseProcess:
    """Test BaseProcess refactoring"""

    def test_base_process_initialization(self):
        """Test BaseProcess initializes correctly"""
        mock_platform = Mock()

        # Create a concrete subclass for testing
        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)

        assert process.platform == mock_platform
        assert process.total_items == 0
        assert process.processed_items == 0
        assert process.current_item is None
        assert process.items_to_process == []
        assert process.skip_all is False
        assert process._items_iterator is None

    def test_get_next_item(self):
        """Test iterator management"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        items = ["item1", "item2", "item3"]
        process.set_items_to_process(items)

        # First item
        assert process._get_next_item() is True
        assert process.current_item == "item1"

        # Second item
        assert process._get_next_item() is True
        assert process.current_item == "item2"

        # Third item
        assert process._get_next_item() is True
        assert process.current_item == "item3"

        # No more items
        assert process._get_next_item() is False
        assert process.current_item is None

    def test_set_items_to_process(self):
        """Test setting items to process"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        items = ["item1", "item2"]
        process.set_items_to_process(items)

        assert process.items_to_process == items
        assert process.total_items == 2
        assert process._items_iterator is None

    def test_execute_step_without_items(self):
        """Test execute_step returns COMPLETE when no items"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        process.set_items_to_process([])

        result = process.execute_step()

        assert result.is_complete()
        assert result.payload.total_processed == 0

    def test_execute_step_advances_on_success(self):
        """Test execute_step advances on SUCCESS"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        process.set_items_to_process(["item1", "item2"])

        # First step
        result = process.execute_step()
        assert result.is_success()
        assert process.processed_items == 1
        assert process.current_item is None

    def test_execute_step_does_not_advance_on_pending_input(self):
        """Test execute_step doesn't advance on PENDING_INPUT"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.pending_input(
                    "query",
                    "message",
                    BaseProcessingItem("test"),
                    [Action.STOP],
                )

        process = ConcreteProcess(mock_platform)
        process.set_items_to_process(["item1", "item2"])

        result = process.execute_step()

        assert result.requires_input()
        assert process.processed_items == 0
        assert process.current_item == "item1"  # Not advanced

    def test_handle_default_action_stop(self):
        """Test default STOP action handling"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

            def _get_handler_for_action(self, action):
                return None  # No handler, use default

        process = ConcreteProcess(mock_platform)
        process.processed_items = 5

        result = process.handle_user_action(Action.STOP)

        assert result.is_complete()
        assert result.payload.stopped_early is True
        assert result.payload.total_processed == 5

    def test_handle_default_action_unknown(self):
        """Test default handling for CONTINUE action"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

            def _get_handler_for_action(self, action):
                return None

        process = ConcreteProcess(mock_platform)
        # Set a current item to verify it gets cleared
        process.current_item = "test_item"

        result = process.handle_user_action(Action.CONTINUE)

        assert result.is_success()
        assert result.payload.message == "Continuing to next item"
        assert process.current_item is None

    def test_handle_default_action_skip(self):
        """Test default handling for SKIP action"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

            def _get_handler_for_action(self, action):
                return None

        process = ConcreteProcess(mock_platform)
        # Set a current item to verify it gets cleared
        process.current_item = "test_item"

        result = process.handle_user_action(Action.SKIP)

        assert result.is_success()
        assert result.payload.message == "Skipped current item"
        assert process.current_item is None

    def test_get_progress(self):
        """Test get_progress returns correct information"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        process.processed_items = 5
        process.total_items = 10

        progress = process.get_progress()

        assert progress["processed"] == 5
        assert progress["total"] == 10
        assert progress["percentage"] == 50.0

    def test_get_progress_with_zero_total(self):
        """Test get_progress with zero total items"""
        mock_platform = Mock()

        class ConcreteProcess(BaseProcess):
            def initialize(self):
                pass

            def register_handlers(self):
                pass

            def _execute_step(self):
                return ResultObject.success()

        process = ConcreteProcess(mock_platform)
        process.processed_items = 0
        process.total_items = 0

        progress = process.get_progress()

        assert progress["processed"] == 0
        assert progress["total"] == 0
        assert progress["percentage"] == 0.0
