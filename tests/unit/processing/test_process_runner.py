import pytest
from unittest.mock import Mock, MagicMock, call
from rom_management.processing.process_runner import ProcessRunner
from rom_management.processing.models import (
    Action,
    ProcessStatus,
    ResultObject,
    BaseProcessingItem,
)


class MockProcess:
    """Mock BaseProcess for testing"""

    def __init__(self, platform):
        self.platform = platform
        self.initialized = False

    def initialize(self):
        self.initialized = True

    def execute_step(self):
        pass

    def handle_user_action(self, action: Action, params=None):
        pass


class TestProcessRunner:
    """Test ProcessRunner lifecycle management"""

    def test_process_runner_initialization(self):
        """Test ProcessRunner can be initialized with a platform"""
        mock_platform = Mock()
        runner = ProcessRunner(mock_platform)

        assert runner.platform == mock_platform
        assert runner._active_process is None

    def test_start_new_process(self):
        """Test starting a new process initializes and executes first step"""
        mock_platform = Mock()
        runner = ProcessRunner(mock_platform)

        # Mock the execute_step method to return a success then complete
        call_count = 0

        def mock_execute_step():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ResultObject.success(message="First step")
            else:
                return ResultObject.complete(total_processed=1)

        original_execute_step = MockProcess.execute_step
        MockProcess.execute_step = MagicMock(side_effect=mock_execute_step)

        try:
            result = runner.start_new_process(MockProcess)

            assert runner._active_process is not None
            assert runner._active_process.initialized is True
            assert call_count == 2
            assert result.is_complete()
        finally:
            # Restore original method
            MockProcess.execute_step = original_execute_step

    def test_execute_next_step_without_active_process(self):
        """Test execute_next_step returns error when no active process"""
        mock_platform = Mock()
        runner = ProcessRunner(mock_platform)

        result = runner.execute_next_step()

        assert result.is_error()
        assert result.payload.message == "No active process"

    def test_execute_next_step_auto_continues_on_success(self):
        """Test execute_next_step auto-continues on SUCCESS status"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ResultObject.success()
            elif call_count == 2:
                return ResultObject.success()
            else:
                return ResultObject.complete(total_processed=2)

        mock_process.execute_step = MagicMock(side_effect=side_effect)

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.execute_next_step()

        assert result.is_complete()
        assert call_count == 3

    def test_execute_next_step_stops_on_pending_input(self):
        """Test execute_next_step stops on PENDING_INPUT status"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.execute_step = MagicMock(
            return_value=ResultObject.pending_input(
                query_id="test_query",
                message="Test",
                item=BaseProcessingItem("test"),
                valid_actions=[Action.STOP],
            )
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.execute_next_step()

        assert result.requires_input()
        mock_process.execute_step.assert_called_once()

    def test_execute_next_step_stops_on_complete(self):
        """Test execute_next_step stops on COMPLETE status"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.execute_step = MagicMock(
            return_value=ResultObject.complete(total_processed=10)
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.execute_next_step()

        assert result.is_complete()
        mock_process.execute_step.assert_called_once()

    def test_execute_next_step_stops_on_error(self):
        """Test execute_next_step stops on ERROR status"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.execute_step = MagicMock(
            return_value=ResultObject.error(
                error_type="TestError", message="Test error"
            )
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.execute_next_step()

        assert result.is_error()
        mock_process.execute_step.assert_called_once()

    def test_handle_user_action_without_active_process(self):
        """Test handle_user_action returns error when no active process"""
        mock_platform = Mock()
        runner = ProcessRunner(mock_platform)

        result = runner.handle_user_action(Action.STOP)

        assert result.is_error()
        assert result.payload.message == "No active process"

    def test_handle_user_action_auto_continues_on_success(self):
        """Test handle_user_action auto-continues after handling action"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.handle_user_action = MagicMock(return_value=ResultObject.success())
        mock_process.execute_step = MagicMock(
            return_value=ResultObject.complete(total_processed=1)
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.handle_user_action(Action.SKIP)

        assert result.is_complete()
        mock_process.handle_user_action.assert_called_once_with(Action.SKIP, None)
        assert mock_process.execute_step.call_count == 1

    def test_handle_user_action_with_params(self):
        """Test handle_user_action passes params to process"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.handle_user_action = MagicMock(return_value=ResultObject.success())
        mock_process.execute_step = MagicMock(
            return_value=ResultObject.complete(total_processed=1)
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        params = {"option": "value"}
        result = runner.handle_user_action(Action.OVERWRITE, params)

        assert result.is_complete()
        mock_process.handle_user_action.assert_called_once_with(
            Action.OVERWRITE, params
        )

    def test_handle_user_action_stops_on_complete(self):
        """Test handle_user_action stops if action returns COMPLETE"""
        mock_platform = Mock()
        mock_process = MockProcess(mock_platform)

        mock_process.handle_user_action = MagicMock(
            return_value=ResultObject.complete(total_processed=0, stopped_early=True)
        )

        # Make execute_step a MagicMock to track calls
        mock_process.execute_step = MagicMock(
            return_value=ResultObject.complete(total_processed=0)
        )

        runner = ProcessRunner(mock_platform)
        runner._active_process = mock_process

        result = runner.handle_user_action(Action.STOP)

        assert result.is_complete()
        assert result.payload.stopped_early is True
        mock_process.execute_step.assert_not_called()
