import os
from typing import Optional, Dict, Any, TYPE_CHECKING
from rom_management.processing.models import ResultObject

from .base import SpecialHandler

if TYPE_CHECKING:
    from rom_management.processing.models import Action, MediaProcessingItem
    from rom_management.processing.base_process import BaseProcess
    from media_registry import CDMedia
else:
    from rom_management.processing.models import MediaProcessingItem


class CHDExistenceHandler(SpecialHandler):
    """
    Handles scenarios where a CHD already exists during CHD build process.
    Provides options to overwrite, skip, or set preferences.

    This handler follows the MD5ScanHandler pattern for user interaction.
    """

    def __init__(self):
        super().__init__("chd_existence")

    def execute_action(
        self,
        action: "Action",
        process: "BaseProcess",
        params: Optional[Dict[str, Any]] = None,
    ) -> "ResultObject":
        """Execute CHD existence actions

        Args:
            action: The Action enum representing user's choice
            process: The BaseProcess instance
            params: Optional parameters for action

        Returns:
            ResultObject from executing the action
        """
        from rom_management.processing.models import (
            ProcessStatus,
            Action,
        )

        if action == Action.TRUST_EXISTING:
            return self._handle_trust_existing(process)

        if action == Action.OVERWRITE:
            return self._handle_overwrite(process)

        elif action == Action.SET_OVERWRITE_PREFERENCE:
            return self._handle_set_overwrite_preference(process)

        elif action == Action.SET_TRUST_PREFERENCE:
            return self._handle_set_trust_preference(process)

        elif action == Action.SKIP:
            return self._handle_skip_existing(process)

        elif action == Action.SKIP_ALL:
            return self._handle_skip_all(process)

        elif action == Action.STOP:
            return ResultObject.complete(
                total_processed=process.processed_items,
                stopped_early=True,
            )

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action for CHDExistenceHandler: {action.value}",
        )

    def _handle_trust_existing(self, process: "BaseProcess") -> "ResultObject":
        """Handle TRUST_EXISTING action - mark existing CHD as validated and continue

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject.success() after marking CHD as validated
        """
        from rom_management.processing.models import ResultObject
        from rom_management import CHD

        if not isinstance(process.current_item, MediaProcessingItem):
            return ResultObject.error(
                error_type="InvalidState",
                message="Current item is not a MediaProcessingItem",
            )

        media = process.current_item.media
        chd_path = self._get_expected_chd_path(process, media)

        if chd_path and os.path.exists(chd_path):
            matched_chd = CHD(chd_path=chd_path)
            if matched_chd.exists and matched_chd.is_valid:
                process.platform.validated_chds.add(matched_chd)
                process.platform.state.add_validated_chd_path(str(matched_chd.path))
                print(f"✅ Trusted existing CHD: {chd_path}")

        print(f"Skipping existing CHD for {media.dat_game_entry.name}")
        process.current_item = None
        process.processed_items += 1
        return ResultObject.success(message="Trusted existing CHD")

    def _handle_overwrite(self, process: "BaseProcess") -> "ResultObject":
        """
        Handle OVERWRITE action - remove existing CHD and retry

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject from executing step (will re-build CHD)
        """
        from rom_management.processing.models import ResultObject
        from rom_management.processing.models import MediaProcessingItem

        # Get CHD path from current item's media
        if not isinstance(process.current_item, MediaProcessingItem):
            return ResultObject.error(
                error_type="InvalidState",
                message="Current item is not a MediaProcessingItem",
            )

        media = process.current_item.media
        chd_path = self._get_expected_chd_path(process, media)

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

        # Retry CHD creation step
        return self._execute_step_and_advance(process)

    def _get_expected_chd_path(
        self, process: "BaseProcess", media: "CDMedia"
    ) -> Optional[str]:
        """Get expected CHD path for a media item

        Args:
            process: The BaseProcess instance
            media: The CDMedia object

        Returns:
            The expected CHD path as a string
        """
        import os

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

    def _handle_skip_existing(self, process: "BaseProcess") -> "ResultObject":
        """Handle SKIP action - skip current CHD and continue

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject.success() after skipping
        """
        from rom_management.processing.models import ResultObject

        if process.current_item and hasattr(process.current_item, "media"):
            print(
                f"Skipping existing CHD for {process.current_item.media.dat_game_entry.name}"
            )
        process.current_item = None
        process.processed_items += 1
        return ResultObject.success(message="Skipped existing CHD")

    def _handle_set_overwrite_preference(
        self, process: "BaseProcess"
    ) -> "ResultObject":
        """
        Handle SET_OVERWRITE_PREFERENCE action - set preference to overwrite all existing CHDs

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject from executing step (will overwrite without prompting again)
        """
        process.platform.set_chd_preference("overwrite")
        print("Set preference to overwrite all existing CHDs")
        return self._execute_step_and_advance(process)

    def _handle_set_trust_preference(self, process: "BaseProcess") -> "ResultObject":
        """Handle SET_TRUST_PREFERENCE action - set preference to trust all existing CHDs

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject.success() after setting preference
        """
        from rom_management.processing.models import ResultObject

        process.platform.set_chd_preference("skip")
        if process.current_item and hasattr(process.current_item, "media"):
            print(
                f"Skipping existing CHD for {process.current_item.media.dat_game_entry.name}"
            )
        print("Set preference to trust existing CHDs for remaining items")
        process.current_item = None
        process.processed_items += 1
        return ResultObject.success(message="Set trust preference for remaining CHDs")

    def _handle_skip_all(self, process: "BaseProcess") -> "ResultObject":
        """Handle SKIP_ALL action - set skip_all flag and skip current item

        Args:
            process: The BaseProcess instance

        Returns:
            ResultObject.success() after skipping current and setting skip_all
        """
        from rom_management.processing.models import ResultObject

        process.skip_all = True
        if process.current_item and hasattr(process.current_item, "media"):
            print(
                f"Skipping existing CHD for {process.current_item.media.dat_game_entry.name}"
            )
        print("Set to skip all remaining existing CHDs")
        process.current_item = None
        process.processed_items += 1
        return ResultObject.success(message="Skipped current, will skip all remaining")
