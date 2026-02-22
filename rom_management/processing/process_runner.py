from typing import Optional, Type, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from consoles import Platform
    from .base_process import BaseProcess
    from .models import Action, ResultObject


class ProcessRunner:
    """
    Manages lifecycle of a single BaseProcess instance.
    UI-agnostic - handles only process orchestration.
    """

    def __init__(self, platform: "Platform"):
        self.platform = platform
        self._active_process: Optional["BaseProcess"] = None

    def start_new_process(
        self, process_class: Type["BaseProcess"], **kwargs
    ) -> "ResultObject":
        """
        Initialize and start a new process

        Args:
            process_class: The BaseProcess subclass to instantiate
            **kwargs: Additional arguments to pass to process constructor

        Returns:
            ResultObject from first step execution
        """
        self._active_process = process_class(self.platform, **kwargs)
        self._active_process.initialize()
        return self.execute_next_step()

    def execute_next_step(self) -> "ResultObject":
        """
        Execute next step of active process with auto-continue on SUCCESS/PROGRESS

        Returns:
            ResultObject from the executed step
        """
        if not self._active_process:
            from .models import ResultObject

            return ResultObject.error(
                error_type="NoActiveProcess", message="No active process"
            )

        # ITERATIVE loop instead of recursion to avoid hitting Python's recursion limit
        while True:
            result = self._active_process.execute_step()

            # Auto-continue on SUCCESS or PROGRESS
            if result.is_success() or result.is_progress():
                continue

            # Store category from pending_input for use in default action handling
            if result.requires_input() and hasattr(result.payload, "category"):
                self._active_process._current_category = result.payload.category

            return result

    def handle_user_action(
        self, action: "Action", params: Optional[Dict[str, Any]] = None
    ) -> "ResultObject":
        """
        Handle user action and auto-continue if needed

        Args:
            action: The Action enum representing user's choice
            params: Optional parameters for the action

        Returns:
            ResultObject from executing the action
        """
        if not self._active_process:
            from .models import ResultObject

            return ResultObject.error(
                error_type="NoActiveProcess", message="No active process"
            )

        result = self._active_process.handle_user_action(action, params)

        # Auto-continue after handling action - use iterative approach
        while result.is_success():
            result = self._active_process.execute_step()
            if not result.is_success() and not result.is_progress():
                break

        return result
