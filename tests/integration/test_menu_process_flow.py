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
                valid_actions=[Action.SKIP, Action.SCAN_MD5],
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

    def test_generic_query_menu_display_and_get_input(self, menu_system):
        """Test that GenericQueryMenu builds options from valid_actions"""
        generic_menu = GenericQueryMenu()

        payload = PendingInputPayload(
            query_id="test_query",
            message="Test message",
            item=Mock(display_name="Test Item"),
            valid_actions=[Action.SKIP, Action.SCAN_MD5, Action.STOP],
        )

        with patch("inquirer.prompt") as mock_prompt:
            mock_prompt.return_value = {"action": Action.SCAN_MD5}

            action, params = generic_menu.display_and_get_input(payload)

            assert action == Action.SCAN_MD5
            assert params is None
            mock_prompt.assert_called_once()

            # Check that options were built with display_name
            # call_args is a tuple, call_args[0] is a list of questions
            questions_list = mock_prompt.call_args[0][0]
            question = questions_list[0]
            choices = question.choices
            assert len(choices) == 3
            assert {
                "name": "Scan this archive with MD5 (slow)",
                "value": Action.SCAN_MD5,
            } in choices
