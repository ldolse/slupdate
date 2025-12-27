# Structured Payload System - Usage Examples

This document shows how to use the structured payload system with `ResultObject` and typed payloads.

## Overview

The new system provides:
- **Type safety** - IDE autocomplete and type checking
- **Clear contracts** - Each payload type has defined fields
- **Self-documenting** - No more guessing what keys exist in a dict
- **Extensible** - Easy to add new interaction types
- **Decoupled UI** - Action enum owns both internal IDs and display strings

## Key Components

### 1. Status and ResultObject

```python
from rom_management.processing import ResultObject, ProcessStatus, Action

# Create various result types
success_result = ResultObject.success(message="File validated")
progress_result = ResultObject.progress(processed=5, total=10, percentage=50.0)
complete_result = ResultObject.complete(total_processed=10, succeeded=10)
error_result = ResultObject.error(error_type="FileNotFound", message="File not found")
```

### 2. Processing Items

Wrap your data objects in typed processing items:

```python
from rom_management.processing import MediaProcessingItem, PartProcessingItem
from media_registry import CDMedia
from softwarelist import Part

# Wrap CDMedia objects
media = CDMedia(...)  # Your existing object
media_item = MediaProcessingItem(media)
print(media_item.display_name)  # Auto-extracts name from dat_game_entry

# Wrap Part objects
part = Part(...)  # Your existing object
part_item = PartProcessingItem(part)
print(part_item.display_name)  # Auto-extracts name from part.name

# For custom objects
from rom_management.processing import BaseProcessingItem
custom_item = BaseProcessingItem(custom_object)
```

### 3. Pending Input with Query ID Mapping

When a process needs user input, it creates a `PendingInputPayload` with a `query_id` that maps to a `BaseMenu` handler.

```python
from rom_management.processing import (
    ResultObject,
    Action,
    PendingInputPayload,
    MediaProcessingItem
)

# In your process class (e.g., ArchiveValidationProcess)
def _validate_single_media(self, media: CDMedia) -> ResultObject:
    """Validate a single media item"""

    if media.missing_crc:
        # Request user input - scan full file with MD5?
        return ResultObject.pending_input(
            query_id="confirm_scan_md5",  # Maps to ConfirmScanMd5Menu
            message=f"DAT is missing CRC for {media.dat_game_entry.name}. Scan full file (slow)?",
            item=MediaProcessingItem(media),
            valid_actions=[Action.SCAN_MD5, Action.SKIP, Action.SKIP_ALL, Action.STOP],
            options_context=None  # Optional additional context
        )

    # Continue processing...
    return ResultObject.success(message="Validated successfully")
```

### 4. Menu Handler Registration in MenuSystem

The `MenuSystem` uses the `query_id` to find the appropriate `BaseMenu` subclass:

```python
from menus.menu_system import MenuSystem
from rom_management.processing import ResultObject, Action

class MenuSystem:
    def __init__(self):
        self.query_handlers = {
            'confirm_scan_md5': ConfirmScanMd5Menu(),
            'chd_already_exists': ExistingCHDMenu(),
            'handler_error': HandlerErrorMenu(),
        }

    def handle_pending_input(self, result: ResultObject) -> tuple[str, dict]:
        """Handle a pending input result by showing appropriate menu"""
        if result.requires_input():
            payload = result.payload  # type: PendingInputPayload

            # Get the handler based on query_id
            handler = self.query_handlers[payload.query_id]

            # Let the handler display options and get user input
            action, params = handler.display_and_get_input(payload)

            # Return the action to the process
            return (action, params)
```

### 5. BaseMenu Handler Implementation

Each menu handler implements `display_and_get_input()` that receives a typed payload:

```python
from menus.menu_system import BaseMenu
from rom_management.processing import PendingInputPayload, Action
import inquirer

class ConfirmScanMd5Menu(BaseMenu):
    """Menu for confirming MD5 scan of archive"""

    def display_and_get_input(self, payload: PendingInputPayload) -> tuple[str, dict]:
        """Display menu and get user action"""

        # Type-safe access to payload fields
        message = payload.message  # str
        item = payload.item  # MediaProcessingItem
        valid_actions = payload.valid_actions  # List[Action]

        # Build choices directly from action.display_name
        choices = [action.display_name for action in valid_actions]

        # Display using inquirer
        answers = inquirer.list(
            "action",
            message=message,
            choices=choices
        )

        # Map user choice back to Action enum using display_name
        selected_display = answers["action"]
        selected_action = next(
            action for action in valid_actions
            if action.display_name == selected_display
        )

        # Return action (no params needed for this menu)
        return (selected_action.value, {})
```

### 6. Process Handling User Actions

The process receives the action via `handle_user_action()`:

```python
from rom_management.processing import (
    BaseProcess,
    ResultObject,
    Action
)

class ArchiveValidationProcess(BaseProcess):
    def handle_user_action(self, action: str, params: dict) -> ResultObject:
        """Handle user actions from menus"""

        # Convert string action back to Action enum for comparison
        user_action = Action(action)

        if user_action == Action.SCAN_MD5:
            # Enable MD5 scanning for this item
            self.use_md5 = True
            # Don't advance iterator - retry current item
            return self._execute_step()

        elif user_action == Action.SKIP:
            # Move to next item
            self.current_item = None
            return ResultObject.success(message="Skipped")

        elif user_action == Action.SKIP_ALL:
            self.skip_all = True
            self.current_item = None
            return ResultObject.success(message="Skipping all")

        elif user_action == Action.STOP:
            return ResultObject.complete(
                total_processed=self.processed_items,
                stopped_early=True
            )
```

### 7. Progress Updates (Automatic Continuation)

Use `ProgressPayload` for automatic continuation:

```python
def _validate_single_media(self, media: CDMedia) -> ResultObject:
    """Validate media with progress reporting"""

    # Update progress automatically
    percentage = self._calculate_progress_percentage()
    return ResultObject.progress(
        processed=self.processed_items + 1,
        total=self.total_items,
        percentage=percentage,
        message=f"Validating: {media.dat_game_entry.name}",
        failed=self.failed_count,
        succeeded=self.success_count
    )
```

The `MenuSystem` will automatically continue to the next step when receiving a `PROGRESS` status (as per AGENTS.md sequence diagram).

## Complete Example: CHD Already Exists

Here's a complete flow from process to menu to action:

```python
# 1. Process creates pending input
class ChdBuildProcess(BaseProcess):
    def _build_single_chd(self, media: CDMedia) -> ResultObject:
        if os.path.exists(chd_path):
            existing = CHD(chd_path)
            return ResultObject.pending_input(
                query_id="chd_already_exists",
                message=f"CHD already exists at {chd_path}",
                item=MediaProcessingItem(media),
                valid_actions=[
                    Action.OVERWRITE,
                    Action.SKIP_EXISTING,
                    Action.STOP
                ],
                options_context={
                    "existing_version": existing.version,
                    "chd_path": chd_path
                }
            )

# 2. Menu displays options
class ExistingCHDMenu(BaseMenu):
    def display_and_get_input(self, payload: PendingInputPayload) -> tuple[str, dict]:
        version = payload.options_context["existing_version"]
        message = f"{payload.message}\nExisting version: {version}"

        # Build choices directly from action.display_name
        choices = [action.display_name for action in payload.valid_actions]

        # ... inquirer code ...
        return (selected_action.value, {})

# 3. Process handles action
class ChdBuildProcess(BaseProcess):
    def handle_user_action(self, action: str, params: dict) -> ResultObject:
        user_action = Action(action)

        if user_action == Action.OVERWRITE:
            os.remove(self._current_chd_path)
            return self._execute_step()  # Retry

        elif user_action == Action.SKIP_EXISTING:
            self.current_item = None
            return ResultObject.success(message="Skipped existing CHD")

        elif user_action == Action.STOP:
            return ResultObject.complete(
                total_processed=self.processed_items,
                stopped_early=True
            )
```

## Benefits of This Approach

1. **Type Safety**: PyLance/VSCode provides autocomplete on all payload fields
2. **Self-Documenting**: No more guessing what keys exist in a dict
3. **Compile-Time Errors**: Catch missing/incorrect fields before running
4. **Easy Refactoring**: Rename fields safely with IDE tools
5. **Clear Separation**: Process logic stays separate from UI logic
6. **Extensible**: Add new query_ids and menu handlers without changing core
7. **Decoupled UI**: Action enum owns display strings, menus use `action.display_name`

## Decoupling with display_name Property

The `Action` enum uses tuple syntax `(value, display_name)` to provide both:
- **value**: Internal identifier passed to processes (e.g., `"scan_md5"`)
- **display_name**: Human-readable string for menu display (e.g., `"Scan this archive with MD5 (slow)"`)

**Benefits:**
- **Single source of truth** - Action enum owns both internal ID and display text
- **No manual mapping** - Menus don't create their own display strings
- **Easy updates** - Change display text without touching menu code
- **Consistency** - Same action always has same display text across all menus

**Usage pattern:**
```python
# In process - return actions
valid_actions = [Action.SCAN_MD5, Action.SKIP, Action.STOP]

# In menu - use display_name directly
choices = [action.display_name for action in valid_actions]

# Map back from display to action
selected_display = answers["action"]
selected_action = next(
    action for action in valid_actions
    if action.display_name == selected_display
)
```

**If you need customization:** You can still create custom BaseMenu subclasses with custom display logic, but the default pattern covers most use cases.
