from typing import List, TYPE_CHECKING
import os
from .base_process import BaseProcess
from .models import (
    ResultObject,
    Action,
    ProcessStatus,
    PartProcessingItem,
    ProgressPayload,
)
from rom_management.archive.zip_processor import ZipProcessor, MD5ScanRequiredException

if TYPE_CHECKING:
    from media_registry import CDMedia
    from consoles import Platform
    from softwarelist import Part


class ArchiveValidationProcess(BaseProcess):
    """Process for validating matched entries"""

    def __init__(self, platform: "Platform"):
        super().__init__(platform)
        self.zip_processor = ZipProcessor()
        self._md5_handler = None
        self.use_md5 = False  # Default to fast validation
        self.skip_all = False

    @property
    def progress(self) -> dict:
        """Return current progress information"""
        success_count = 0
        failure_count = 0

        for i, item in enumerate(self.items_to_process):
            if i < self.processed_items:
                # Check if this item was processed successfully
                media = self.items_to_process[i].media
                if media in self.platform.matched_buildable_media:
                    success_count += 1
                else:
                    failure_count += 1

        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "processed": success_count,
            "failed": failure_count,
            "percentage": self._calculate_progress_percentage(),
        }

    def initialize(self):
        """Initialize with all media from MediaRegistry"""
        if not self.platform.mr:
            raise Exception("MediaRegistry not initialized")

        # Get all media items to process
        self.items_to_process = [
            PartProcessingItem(part) for part in self.platform.all_parts
        ]

        self.total_items = len(self.items_to_process)
        print(f"{self.total_items} to process")

        # Register handlers
        self.register_handlers()

    def register_handlers(self):
        """Register MD5 scan handler for this process"""
        from rom_management.handlers.md5_handler import MD5ScanHandler

        self._md5_handler = MD5ScanHandler()

    def _get_handler_for_action(self, action: Action):
        """Map MD5-related actions to MD5ScanHandler"""
        md5_actions = [
            Action.SCAN_MD5,
            Action.SKIP,
            Action.SKIP_ALL,
            Action.SCAN_ALL_MD5,
        ]
        if action in md5_actions:
            return self._md5_handler
        return None

    def _execute_step(self) -> ResultObject:
        """Execute one validation step"""
        # Get current media item
        current_part: "Part" = self.current_item.part
        media: "CDMedia" = current_part.cdmedia

        # Check if already validated
        media_sig = media.sha1_signature or media.crc_signature
        if media_sig in self.platform.state.matched_media_sigs:
            print(
                f". ✅ {media.dat_game_entry.name} already validated, skipping zip check"
            )
            return ResultObject.success(
                message=f"Already validated: {media.dat_game_entry.name}",
                metadata={"media_id": media.id},
            )

        # Find ROM directory for this DAT
        rom_dir = media.dat_game_entry.dat.rom_path
        if not os.path.isdir(rom_dir):
            print(
                f"  ⚠️  ROM directory does not exist for {media.dat_game_entry.name}: Skipping - {rom_dir}"
            )
            return ResultObject.success(
                message=f"ROM directory missing: {media.dat_game_entry.name}",
                metadata={"rom_dir": rom_dir},
            )

        # Try to find valid zip
        try:
            zip_path = self.zip_processor.find_valid_zip(
                media.dat_game_entry, rom_dir, md5=self.use_md5
            )
        except MD5ScanRequiredException:
            # Check skip_all preference
            if self.skip_all:
                print(f"skipping md5 scan for {media.dat_game_entry.name}")
                return ResultObject.success(
                    message=f"Skipped MD5 scan (skip_all)",
                    metadata={"media_id": media.id},
                )

            # Return pending input for user decision
            return ResultObject.pending_input(
                query_id="confirm_scan_md5",
                message="This DAT requires full MD5 scan (slow)",
                item=PartProcessingItem(current_part),
                valid_actions=[
                    Action.SCAN_MD5,
                    Action.SKIP,
                    Action.SKIP_ALL,
                    Action.SCAN_ALL_MD5,
                    Action.STOP,
                ],
                options_context={"existing_use_md5": self.use_md5},
            )
        except Exception as e:
            # Return error for unexpected exceptions
            return ResultObject.error(
                error_type="ValidationError",
                message=f"Error validating {media.dat_game_entry.name}: {str(e)}",
                exception=e,
                context={"media_id": media.id},
            )

        if not zip_path:
            print(f"  ⚠️  No valid zip found: {media.dat_game_entry.name}")
            return ResultObject.success(
                message=f"No valid zip found: {media.dat_game_entry.name}",
                metadata={"media_id": media.id},
            )
        else:
            print(f"  ✅ Found valid zip: {media.dat_game_entry.name}")
            media.zip_path = zip_path
            self.platform.matched_buildable_media[media] = None
            return ResultObject.success(
                message=f"Found valid zip: {media.dat_game_entry.name}",
                metadata={"zip_path": zip_path, "media_id": media.id},
            )
