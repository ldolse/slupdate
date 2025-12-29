"""UX-specific dataclasses for menu rendering and user interaction.

This module contains data structures that bridge between menu definitions
(MenuItem or ResultObject payloads) and rendering logic (inquirer CLI or future
web UI).

Separating these from rom_management.models because:
1. They are UI-specific, not ROM processing specific
2. They serve as an abstraction layer for multiple frontends
3. Keeps rom_management/models.py focused on processing logic
"""

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass
class DisplayData:
    """Data needed to render a menu to the user.

    This is the output of get_display_data() and the input to rendering logic.
    It's format-agnostic - could be rendered by inquirer (CLI), React (web),
    or any future UI framework.

    Attributes:
        message: The main message/title to display
        choices: List of tuples (display_name, value) - display_name is what
            the user sees, value is what gets passed to execute_custom_action()
        question_text: The prompt text for the user selection
    """

    message: str
    choices: list[Tuple[str, Any]]
    question_text: str = "What would you like to do?"
