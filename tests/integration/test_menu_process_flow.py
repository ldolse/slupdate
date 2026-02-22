import pytest
from unittest.mock import Mock, patch, MagicMock
from menus.menu_system import MenuSystem
from rom_management.processing.models import (
    ResultObject,
    Action,
    PendingInputPayload,
    ProcessStatus,
)
from rom_management.processing.archive_validation import ArchiveValidationProcess
from menus.query_menus import GenericQueryMenu


class TestMenuProcessFlow:
    """Integration tests for MenuSystem-Process-Menu flow"""

    @pytest.fixture
    def mock_platform(self):
        platform = Mock()
        platform.media_directory = {}
        platform.software_list_data = {}
        platform.dat_hashes = {}
        platform.validated_chds = []
        return platform

    @pytest.fixture
    def menu_system(self, mock_platform):
        system = MenuSystem()
        # Set _current_key to get our mock platform
        system.platform_manager._current_key = "test_platform"
        system.platform_manager.platforms["test_platform"] = mock_platform

        # Register generic query handler
        generic_menu = GenericQueryMenu()
        system.register(generic_menu)

        return system

    def test_run_process_auto_continues_on_success(self, menu_system):
        """Test that process auto-continues on SUCCESS results"""
        # Mock ArchiveValidationProcess to return success
        with patch(
            "rom_management.processing.process_runner.ProcessRunner"
        ) as MockRunner:
            mock_runner = Mock()
            mock_runner.execute_next_step.side_effect = [
                ResultObject.success("Item 1 validated"),
                ResultObject.success("Item 2 validated"),
                ResultObject.complete(total_processed=2, succeeded=2),
            ]
            MockRunner.return_value = mock_runner

            result = menu_system.run_process(ArchiveValidationProcess)

            # Should process all items and return complete
            assert result.is_complete()
            assert result.payload.total_processed == 2
            assert mock_runner.execute_next_step.call_count == 3

    def test_run_process_navigates_on_pending_input(self, menu_system):
        """Test that PENDING_INPUT triggers navigate_to()"""
        with patch(
            "rom_management.processing.process_runner.ProcessRunner"
        ) as MockRunner:
            mock_runner = Mock()
            mock_runner.execute_next_step.return_value = ResultObject.pending_input(
                query_id="generic_query",
                message="Test message",
                item=Mock(),
                valid_actions=[Action.SKIP, Action.HANDLE],
            )
            MockRunner.return_value = mock_runner

            # Spy on navigate_to
            with patch.object(menu_system, "navigate_to") as mock_navigate:
                result = menu_system.run_process(ArchiveValidationProcess)

                # Should return None (waiting for user)
                assert result is None
                # navigate_to should have been called with the PENDING_INPUT result
                mock_navigate.assert_called_once()
                call_arg = mock_navigate.call_args[0][0]
                assert call_arg.requires_input()

    def test_resume_process_continues_after_user_action(self, menu_system):
        """Test that process resumes after user selects action"""
        with patch(
            "rom_management.processing.process_runner.ProcessRunner"
        ) as MockRunner:
            mock_runner = Mock()

            # First call: pending input
            # handle_user_action: success
            # Second call: complete
            mock_runner.execute_next_step.side_effect = [
                ResultObject.pending_input(
                    query_id="generic_query",
                    message="Test",
                    item=Mock(),
                    valid_actions=[Action.SKIP],
                ),
                ResultObject.complete(total_processed=1),
            ]

            mock_runner.handle_user_action.return_value = ResultObject.success()

            MockRunner.return_value = mock_runner

            # Start process
            result1 = menu_system.run_process(ArchiveValidationProcess)
            assert result1 is None

            # Simulate user selecting SKIP
            menu_system.resume_process(Action.SKIP, None)

            # Process should have completed
            assert menu_system.current_menu_name == "main_menu"

    def test_generic_query_menu_get_display_data(self, menu_system):
        """Test that GenericQueryMenu builds options from valid_actions"""
        generic_menu = GenericQueryMenu()

        # Set up a mock ResultObject as pending result
        mock_result = ResultObject.pending_input(
            query_id="test_query",
            message="Test message",
            item=Mock(display_name="Test Item"),
            valid_actions=[Action.SKIP, Action.HANDLE, Action.STOP],
        )

        generic_menu._pending_result = mock_result

        # Get display data
        display_data = generic_menu.get_display_data()

        # Verify message and choices
        assert display_data.message == "Test message\nItem: Test Item"

        # Check that options were built with display_name as tuples (display_name, value)
        assert len(display_data.choices) == 3
        expected_choices = [
            (Action.SKIP.display_name, Action.SKIP),
            (Action.HANDLE.display_name, Action.HANDLE),
            (Action.STOP.display_name, Action.STOP),
        ]
        assert display_data.choices == expected_choices

    def test_run_process_from_result_continues_on_success(self, menu_system):
        """Test that run_process_from_result() auto-continues on SUCCESS results after user action"""
        from rom_management.processing.process_runner import ProcessRunner

        # Setup: Create a real runner instance
        runner = ProcessRunner(menu_system.platform_manager.platforms["test_platform"])
        menu_system.runner = runner

        # Mock the process
        with patch.object(
            runner,
            "execute_next_step",
            side_effect=[
                ResultObject.success("MD5 scan completed"),
                ResultObject.complete(total_processed=1),
            ],
        ):
            # Simulate result from handle_user_action (which auto-continued)
            success_result = ResultObject.success("MD5 scan completed")

            # Call run_process_from_result with SUCCESS
            menu_system.run_process_from_result(success_result)

            # Should have called execute_next_step twice:
            # 1. To continue after SUCCESS
            # 2. To get the COMPLETE result
            assert runner.execute_next_step.call_count == 2

            # Should have navigated to main_menu on completion
            assert menu_system.current_menu_name == "main_menu"
