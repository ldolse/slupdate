import os
from typing import Optional, Dict, Any, TYPE_CHECKING
from rom_management.processing.models import (
    ResultObject,
    Action,
    MediaProcessingItem,
    CHDExistingPreference,
)
from .base import SpecialHandler

if TYPE_CHECKING:
    from rom_management.processing.base_process import BaseProcess
    from media_registry import CDMedia


class CHDExistenceHandler(SpecialHandler):
    """
    Handles scenarios where a CHD already exists during CHD build process.

    Preferences (in precedence order):
    - TRUST: Trust existing CHD, add to validated_chds
    - OVERWRITE: Remove existing CHD and rebuild
    - SKIP: Skip without validating (don't add to validated_chds)
    - ASK: Prompt user each time (default)
    """

    PROCESS_CATEGORY = "existing CHD"

    def __init__(self):
        super().__init__("chd_existence")

    def validate_preconditions(
        self, media: "CDMedia", file_data: Any = None, process: Any = None
    ) -> "ResultObject":
        """Check if this handler should be applied.

        CHDExistenceHandler only applies during CHD build process AND when a CHD already exists.

        Returns:
            - ResultObject.not_applicable() for non-CHDBuildProcess, no existing CHD, or if already handled
            - ResultObject.skip() if preference is SKIP (skip without validating)
            - ResultObject.success() for CHDBuildProcess with existing CHD (handler will handle it)
        """
        # CHD existence handler only applies within CHDBuildProcess
        if process is None:
            return ResultObject.not_applicable(
                message="CHD existence handler requires a process context"
            )

        from rom_management.processing.chd_build_process import ChdBuildProcess

        if not isinstance(process, ChdBuildProcess):
            return ResultObject.not_applicable(
                message="CHD existence handler is for CHD build process only"
            )

        # CRITICAL: Check if CHD actually exists FIRST - if not, this handler is not applicable
        chd_path = self._get_expected_chd_path(process, media)
        if not chd_path or not os.path.exists(chd_path):
            return ResultObject.not_applicable(
                message="No existing CHD found - handler not applicable"
            )

        # Check if category already skipped via SKIP_ALL
        if self.PROCESS_CATEGORY in process._skipped_categories:
            return ResultObject.skip(message="Existing CHDs skipped via SKIP_ALL")

        # CHD exists - check preferences
        pref = process.platform.chd_handling_preference

        if pref == CHDExistingPreference.SKIP:
            # Preference is to skip without validating
            return ResultObject.skip(message="Skipping existing CHD per preference")

        # TRUST, OVERWRITE, or ASK - include handler, execute() will handle appropriately
        return ResultObject.success()

    def execute(
        self, media: "CDMedia", file_data: Any = None, process: Any = None
    ) -> "ResultObject":
        """Execute CHD existence handling.

        Called when validate_preconditions returned success (CHD exists).

        Args:
            media: The CDMedia object being processed
            file_data: Not used for CHD existence check
            process: The BaseProcess instance

        Returns:
            - ResultObject.success() if preference is TRUST or OVERWRITE (handled automatically)
            - ResultObject.pending_input() if preference is ASK (prompt user)
        """
        chd_path = self._get_expected_chd_path(process, media)
        pref = process.platform.chd_handling_preference

        # Handle automatic preferences
        if pref == CHDExistingPreference.TRUST:
            return self._do_trust(process, chd_path)

        if pref == CHDExistingPreference.OVERWRITE:
            return self._do_overwrite(process, chd_path)

        # Preference is ASK - prompt user
        from rom_management import CHD

        matched_chd = CHD(chd_path=chd_path)
        existing_version = None
        if matched_chd.is_valid:
            chd_info = matched_chd._get_chd_info()
            existing_version = chd_info.get("file_version")

        return ResultObject.pending_input(
            query_id="generic_query",
            message=f"CHD already exists for {media.dat_game_entry.name}",
            item=process.current_item,
            valid_actions=[
                Action.TRUST_EXISTING,
                Action.OVERWRITE,
                Action.SET_TRUST_PREFERENCE,
                Action.SET_OVERWRITE_PREFERENCE,
                Action.SKIP,
                Action.SKIP_ALL,
                Action.STOP,
            ],
            category=self.PROCESS_CATEGORY,
            options_context={
                "existing_version": existing_version,
                "chd_path": chd_path,
            },
        )

    def execute_action(
        self,
        action: "Action",
        process: "BaseProcess",
        params: Optional[Dict[str, Any]] = None,
    ) -> "ResultObject":
        """Execute CHD existence actions from user input.

        Args:
            action: The Action enum representing user's choice
            process: The BaseProcess instance
            params: Optional parameters for action

        Returns:
            ResultObject from executing the action
        """
        # Handle actions that don't need chd_path first
        if action == Action.STOP:
            return process._handle_stop()

        # Get chd_path for actions that need it
        if not isinstance(process.current_item, MediaProcessingItem):
            return ResultObject.error(
                error_type="InvalidState",
                message="Current item is not a MediaProcessingItem",
            )
        chd_path = self._get_expected_chd_path(process, process.current_item.media)

        if action == Action.TRUST_EXISTING:
            return self._do_trust(process, chd_path)

        if action == Action.OVERWRITE:
            return self._do_overwrite(process, chd_path)

        if action == Action.SET_TRUST_PREFERENCE:
            process.platform.set_chd_preference(CHDExistingPreference.TRUST)
            print("Set preference to trust all existing CHDs")
            return self._do_trust(process, chd_path)

        if action == Action.SET_OVERWRITE_PREFERENCE:
            process.platform.set_chd_preference(CHDExistingPreference.OVERWRITE)
            print("Set preference to overwrite all existing CHDs")
            return self._do_overwrite(process, chd_path)

        if action == Action.SKIP:
            return self._do_skip(process)

        if action == Action.SKIP_ALL:
            process.platform.set_chd_preference(CHDExistingPreference.SKIP)
            print("Set preference to skip all existing CHDs")
            return self._do_skip(process)

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action for CHDExistenceHandler: {action.value}",
        )

    def _do_trust(self, process: "BaseProcess", chd_path: str) -> "ResultObject":
        """Trust existing CHD: create CHD object, add to validated_chds, advance to next item.

        This skips extraction and CHD creation entirely.

        Args:
            process: The BaseProcess instance
            chd_path: Path to the existing CHD file

        Returns:
            ResultObject.success() after marking CHD as validated and advancing
        """
        from rom_management import CHD

        if not isinstance(process.current_item, MediaProcessingItem):
            return ResultObject.error(
                error_type="InvalidState",
                message="Current item is not a MediaProcessingItem",
            )

        media = process.current_item.media

        if chd_path and os.path.exists(chd_path):
            matched_chd = CHD(chd_path=chd_path, source=media)
            if matched_chd.exists and matched_chd.is_valid:
                process.platform.validated_chds.add(matched_chd)
                process.platform.state.add_validated_chd_path(str(matched_chd.path))
                print(f"✅ Trusted existing CHD: {chd_path}")

        print(f"Skipping existing CHD for {media.dat_game_entry.name}")
        process.current_item = None
        process.processed_items += 1
        return ResultObject.success(message="Trusted existing CHD")

    def _do_overwrite(self, process: "BaseProcess", chd_path: str) -> "ResultObject":
        """Overwrite existing CHD: remove file, return success so process continues to build.

        Args:
            process: The BaseProcess instance
            chd_path: Path to the existing CHD file

        Returns:
            ResultObject.success() after removing CHD (process will build new one)
        """
        if chd_path and os.path.exists(chd_path):
            try:
                os.remove(chd_path)
                print(f"Removed existing CHD: {chd_path}")
            except OSError as e:
                return ResultObject.error(
                    error_type="FileRemovalError",
                    message=f"Failed to remove existing CHD: {str(e)}",
                    exception=e,
                )

        # Return success - process will continue to build CHD normally
        return ResultObject.success(message="Removed existing CHD")

    def _do_skip(self, process: "BaseProcess") -> "ResultObject":
        """Skip existing CHD: advance to next item without adding to validated_chds.

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject.success() after skipping
        """
        if process.current_item and hasattr(process.current_item, "media"):
            print(
                f"Skipping existing CHD for {process.current_item.media.dat_game_entry.name}"
            )
        return process._handle_skip("Skipped existing CHD")

    def _get_expected_chd_path(
        self, process: "BaseProcess", media: "CDMedia"
    ) -> Optional[str]:
        """Get expected CHD path for a media item.

        Args:
            process: The BaseProcess instance
            media: The CDMedia object

        Returns:
            The expected CHD path as a string, or None if cannot be determined
        """
        if not media.dat_game_entry or not media.dat_game_entry.name:
            return None

        if not media.softlist_part or not media.softlist_part.part_of:
            return None

        title = media.softlist_part.part_of.name
        file_name = media.dat_game_entry.name

        return os.path.join(
            process.platform.chd_path,
            title,
            f"{file_name}.chd",
        )
