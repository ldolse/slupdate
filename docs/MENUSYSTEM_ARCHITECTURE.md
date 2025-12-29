# MenuSystem Architecture Refactoring

## Overview

This document describes the refactored MenuSystem architecture that unifies declarative menus (MainMenu, SettingsMenu, etc.) and dynamic menus (query menus from processes) under a single interface.

**Goal**: Eliminate dual execution paths, centralize rendering logic, and prepare for future web UI implementation.

## Core Concepts

### Menu Types

1. **Declarative Menus**: Menus with static `MenuItem` options defined at class level
   - Examples: MainMenu, SettingsMenu, MapMenu, CHDBuildMenu
   - Good for: Static navigation menus with predefined options
   - Data source: `self.options` (list of MenuItem objects)

2. **Dynamic Menus**: Menus generated at runtime from process results
   - Examples: GenericQueryMenu (for MD5 scan prompts, etc.)
   - Good for: User interaction during long-running processes
   - Data source: `ResultObject.pending_input()` with `PendingInputPayload`

### Key Components

```
DisplayData          -> UX-specific data structure for rendering
BaseMenu             -> Abstract base for all menus
MenuSystem           -> Orchestrates navigation and rendering
DeclarativeMenuAdapter   -> Mixin for MenuItem-based menus
DynamicMenuAdapter     -> Mixin for process-based menus
```

## Class Diagram

```mermaid
classDiagram
    class MenuSystem {
        -Dict~str, BaseMenu~ menus
        -ProcessRunner runner
        -Dict~str, BaseMenu~ _query_handlers
        -Tuple~BaseMenu, ResultObject~ _pending_action_handler
        +render(menu: BaseMenu) Any
        +execute_menu_action(menu, action) ResultObject
        +navigate_to(navigation_info) void
        +run_process(process_class) ResultObject
        +resume_process(action, params) void
    }

    class BaseMenu {
        <<abstract>>
        +str name
        +str message
        +list~MenuItem~ options
        +get_display_data() DisplayData*
        +execute_custom_action(menu_system, action) ResultObject*
    }

    class DeclarativeMenuAdapter {
        <<mixin>>
        +get_display_data() DisplayData
        +execute_custom_action(menu_system, action) ResultObject
    }

    class DynamicMenuAdapter {
        <<mixin>>
        +get_display_data() DisplayData
        +execute_custom_action(menu_system, action) ResultObject
    }

    class MenuItem {
        +str text
        +str target_name
        +Callable action_func
        +bool requires_platform
        +bool is_back
        +execute(menu_system) ResultObject
    }

    class DisplayData {
        +str message
        +list~tuple~str, Any~~ choices
        +str question_text
    }

    class ResultObject {
        +ProcessStatus status
        +BasePayload payload
        +is_success() bool
        +requires_input() bool
        +is_complete() bool
        +is_error() bool
    }

    class Action {
        <<enumeration>>
        +SCAN_MD5
        +SKIP
        +SKIP_ALL
        +SCAN_ALL_MD5
        +RETRY
        +OVERWRITE
        +STOP
        +CONTINUE
    }

    class MainMenu {
        +list~MenuItem~ options
    }

    class SettingsMenu {
        +list~MenuItem~ options
    }

    class GenericQueryMenu {
        -ResultObject _pending_result
        +get_display_data() DisplayData
        +execute_custom_action(menu_system, action) ResultObject
    }

    MenuSystem o-- BaseMenu : manages
    BaseMenu <|-- MenuItem : contains
    MainMenu --|> DeclarativeMenuAdapter : uses
    SettingsMenu --|> DeclarativeMenuAdapter : uses
    GenericQueryMenu --|> DynamicMenuAdapter : uses
    DeclarativeMenuAdapter ..|> BaseMenu : implements
    DynamicMenuAdapter ..|> BaseMenu : implements
    DeclarativeMenuAdapter ..|> MainMenu : provides methods for
    DynamicMenuAdapter ..|> GenericQueryMenu : provides methods for
    MenuSystem --> DisplayData : uses
    MenuSystem --> ResultObject : returns/accepts
    ResultObject --> Action : contains
```

## Execution Flow Diagrams

### Declarative Menu Flow (MainMenu, SettingsMenu, etc.)

```mermaid
sequenceDiagram
    actor User
    participant Main as Main Loop (slupdate.py)
    participant MS as MenuSystem
    participant Menu as DeclarativeMenu
    participant Adapter as DeclarativeMenuAdapter
    participant Item as MenuItem

    User->>Main: Start application
    Main->>MS: render(current_menu)
    MS->>Menu: get_display_data()
    Menu->>Adapter: get_display_data()
    Adapter-->>Menu: DisplayData{message, choices=[(text, MenuItem)...]}

    Menu-->>MS: DisplayData

    MS->>MS: Display with inquirer.list_input()
    MS-->>User: Show menu options

    User->>MS: Select option
    MS-->>Main: Return selected MenuItem

    Main->>MS: execute_menu_action(menu, MenuItem)
    MS->>Menu: execute_custom_action(system, MenuItem)
    Menu->>Adapter: execute_custom_action(system, MenuItem)
    Adapter->>Item: item.execute(system)
    Item-->>Adapter: ResultObject

    Adapter-->>Menu: ResultObject
    Menu-->>MS: ResultObject

    MS->>MS: Handle navigation (if COMPLETE/ERROR)
    MS-->>Main: Return ResultObject

    Main->>Main: Loop to render next menu
```

### Dynamic Menu Flow (GenericQueryMenu for process queries)

```mermaid
sequenceDiagram
    actor User
    participant Process as ArchiveValidationProcess
    participant Runner as ProcessRunner
    participant MS as MenuSystem
    participant Query as GenericQueryMenu
    participant Adapter as DynamicMenuAdapter

    Note over User,Process: 1. PROCESS EXECUTION
    Process->>Runner: execute_next_step()
    Runner->>Process: _handle_step(item)
    Process-->>Runner: ResultObject{PENDING_INPUT, payload={query_id, valid_actions...}}

    Note over User,Process: 2. PROCESS PAUSES
    Runner-->>MS: ResultObject

    MS->>MS: _handle_result_navigation(result)
    MS->>Query: Set _pending_result = result
    MS->>MS: Navigate to query menu

    Note over User,MS: 3. QUERY MENU DISPLAY
    MS->>Query: render(QueryMenu)
    Query->>Adapter: get_display_data()
    Adapter->>Adapter: Build from _pending_result.payload
    Adapter-->>Query: DisplayData{message, choices=[(Action.display_name, Action)...]}

    Query-->>MS: DisplayData
    MS->>MS: Display with inquirer.list_input()
    MS-->>User: Show query options

    User->>MS: Select Action (e.g., SCAN_MD5)
    MS-->>Query: Return Action enum

    Query->>MS: execute_menu_action(QueryMenu, Action)
    Query->>Adapter: execute_custom_action(system, Action)
    Adapter->>MS: resume_process(Action, None)

    Note over User,Process: 4. PROCESS RESUMES
    MS->>Runner: handle_user_action(Action, params)
    Runner->>Process: handle_user_action(Action, params)

    Process->>Process: Continue processing
    Process-->>Runner: ResultObject{SUCCESS or COMPLETE}

    Runner-->>MS: ResultObject
    MS->>MS: Continue run_process loop
```

## Implementation Details

### DisplayData Structure

```python
@dataclass
class DisplayData:
    """Data needed to render a menu to the user.

    This is format-agnostic - could be rendered by:
    - Current: inquirer CLI
    - Future: React web UI (return as JSON)
    - Future: Other frontend frameworks

    Attributes:
        message: The main message/title to display
        choices: List of (display_name, value) tuples
        question_text: The prompt text for user selection
    """
    message: str
    choices: list[Tuple[str, Any]]
    question_text: str = "What would you like to do?"
```

### BaseMenu Interface

```python
class BaseMenu(ABC):
    """Base class for all menus.

    All menus must implement:
    - get_display_data(): Returns DisplayData for rendering
    - execute_custom_action(): Handles user action from menu

    This allows MenuSystem to render all menus the same way
    without knowing menu implementation details.
    """

    @property
    def options(self) -> list[MenuItem]:
        """Declarative menus: list of MenuItem objects"""
        pass

    @abstractmethod
    def get_display_data(self) -> DisplayData:
        """Return display data for rendering by MenuSystem."""
        pass

    @abstractmethod
    def execute_custom_action(
        self,
        menu_system: "MenuSystem",
        action: Any
    ) -> ResultObject:
        """Execute a user action selected from the menu."""
        pass
```

### DeclarativeMenuAdapter Implementation

```python
class DeclarativeMenuAdapter:
    """Adapter for MenuItem-based declarative menus.

    Usage:
        class MainMenu(DeclarativeMenuAdapter, BaseMenu):
            def __init__(self):
                super().__init__("main_menu")
                self.options = [
                    MenuItem(text="Settings", target="settings_menu"),
                    ...
                ]

            # No need to implement get_display_data() or execute_custom_action()
            # Adapter provides the implementation!
    """

    def get_display_data(self) -> DisplayData:
        """Convert MenuItem.options to DisplayData."""
        choices = [(item.text, item) for item in self.options]
        return DisplayData(message=self.message, choices=choices)

    def execute_custom_action(
        self,
        menu_system: "MenuSystem",
        action: Any
    ) -> ResultObject:
        """Execute a MenuItem action."""
        if isinstance(action, MenuItem):
            return action.execute(menu_system)
        raise ValueError(f"Expected MenuItem, got {type(action)}")
```

### DynamicMenuAdapter Implementation

```python
class DynamicMenuAdapter:
    """Adapter for dynamic query menus from process results.

    Usage:
        class GenericQueryMenu(DynamicMenuAdapter, BaseMenu):
            def __init__(self):
                super().__init__("generic_query_menu")
                self._pending_result = None

            # No need to implement get_display_data() or execute_custom_action()
            # Adapter provides the implementation!

        # MenuSystem sets _pending_result before navigating to this menu
        menu._pending_result = ResultObject.pending_input(
            query_id="md5_scan",
            message="Hash missing - scan entire file?",
            item=ProcessingItem(...),
            valid_actions=[Action.SCAN_MD5, Action.SKIP]
        )
    """

    def get_display_data(self) -> DisplayData:
        """Convert PendingInputPayload to DisplayData."""
        if not hasattr(self, "_pending_result") or not self._pending_result:
            return DisplayData(message="No pending query", choices=[])

        payload = self._pending_result.payload
        choices = [(act.display_name, act) for act in payload.valid_actions]

        message = payload.message
        if hasattr(payload.item, "display_name"):
            message += f"\nItem: {payload.item.display_name}"

        return DisplayData(message=message, choices=choices)

    def execute_custom_action(
        self,
        menu_system: "MenuSystem",
        action: Any
    ) -> ResultObject:
        """Resume process with user's action."""
        menu_system.resume_process(action, None)
        return ResultObject.success()
```

### MenuSystem Rendering

```python
class MenuSystem:
    """Manages navigation state and history with platform integration."""

    def render(self, menu: BaseMenu) -> Any:
        """
        Display menu and return selected action/value.

        This method centralizes ALL rendering logic for menus.

        In the future, this could be replaced with web UI API endpoints
        that return DisplayData as JSON.
        """
        display_data = menu.get_display_data()

        print(f"\n{display_data.message}")

        import inquirer
        questions = [
            inquirer.List(
                "action",
                message=display_data.question_text,
                choices=display_data.choices,
            )
        ]

        answers = inquirer.prompt(questions)
        return answers["action"]

    def execute_menu_action(
        self,
        menu: BaseMenu,
        action: Any
    ) -> ResultObject:
        """
        Execute a menu action and handle navigation.

        Delegates execution to menu's execute_custom_action(),
        then handles navigation based on ResultObject.
        """
        result = menu.execute_custom_action(self, action)

        if result.is_complete() or result.is_error():
            self.navigate_to(result)

        return result
```

## Testing

### Unit Test Structure

```python
def test_menu_get_display_data():
    """Test that menu returns DisplayData via adapter"""
    menu = MainMenu()
    display_data = menu.get_display_data()

    assert display_data.message == "Main Menu"
    assert len(display_data.choices) == 5
    assert display_data.question_text == "What would you like to do?"

def test_menu_execute_custom_action():
    """Test that menu executes MenuItem actions via adapter"""
    menu = MainMenu()
    system = Mock(spec=MenuSystem)
    result = menu.execute_custom_action(system, menu.options[0])

    assert result.is_complete() or result.is_success()
```

### Integration Test Structure

```python
def test_query_menu_with_process():
    """Test that query menu integrates with process execution"""
    # Setup
    system = MenuSystem()
    system.runner = ProcessRunner(mock_platform)
    system.runner.start_new_process(ArchiveValidationProcess)

    # Execute step that triggers query
    result = system.runner.execute_next_step()
    assert result.requires_input()

    # Navigate to query menu
    system.navigate_to(result)
    assert system.current_menu_name == "generic_query_menu"

    # Simulate user action
    system.resume_process(Action.SCAN_MD5, None)

    # Verify process resumed
    final_result = system.runner.execute_next_step()
    assert final_result.is_success()
```

