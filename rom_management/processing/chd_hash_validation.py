from typing import List, TYPE_CHECKING, Optional, Dict, Any
from .base_process import BaseProcess
from .models import (
    ResultObject,
    Action,
    ProcessStatus,
    PartProcessingItem,
)
from rom_management import CHD

if TYPE_CHECKING:
    from consoles import Platform
    from softwarelist import Part


class CHDHashValidationProcess(BaseProcess):
    """Process for validating CHD hashes and filenames against softwarelist entries"""

    def __init__(self, platform: "Platform"):
        super().__init__(platform)
        self.skip_all = False
        self.update_all = False
        self.pending_updates = {}

    @property
    def progress(self) -> dict:
        """Return current progress information"""
        validated_count = 0
        mismatch_count = 0
        updated_count = 0

        for chd in self.items_to_process:
            part = (
                chd.source.softlist_part
                if chd.source and chd.source.softlist_part
                else None
            )

            if part:
                chd_key = self._get_chd_key(chd)

                if chd_key in self.pending_updates:
                    updated_count += 1
                elif chd.sha1 and part.disk_sha1 and chd.name and part.disk_name:
                    if chd.sha1 != part.disk_sha1 or chd.name != part.disk_name:
                        mismatch_count += 1
                    else:
                        validated_count += 1

        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "validated": validated_count,
            "mismatched": mismatch_count,
            "updated": updated_count,
            "percentage": self._calculate_progress_percentage(),
        }

    def initialize(self):
        """Initialize with validated CHDs from platform"""
        if not self.platform.validated_chds:
            print("No validated CHDs found in platform")
            self.items_to_process = []
            self.total_items = 0
            return

        self.items_to_process = list(self.platform.validated_chds)
        self.total_items = len(self.items_to_process)
        print(f"{self.total_items} validated CHDs to validate")

    def register_handlers(self):
        """No handlers needed for this process"""
        pass

    def _get_chd_key(self, chd: CHD) -> str:
        """Get unique key for CHD"""
        return str(chd.path)

    def _execute_step(self) -> ResultObject:
        """Execute one validation step"""
        if not self.current_item:
            return ResultObject.error(
                error_type="NoItemError",
                message="No current item to process",
            )

        chd = self.current_item

        if not chd.source or not chd.source.softlist_part:
            print(f"  ⚠️  Skipping - CHD has no softlist reference")
            return ResultObject.success(
                message=f"Skipped - No softlist reference",
                metadata={"chd_path": str(chd.path)},
            )

        part = chd.source.softlist_part

        if not chd.sha1 or not chd.name:
            print(f"  ⚠️  Skipping - CHD missing sha1 or name")
            return ResultObject.success(
                message=f"Skipped - CHD incomplete",
                metadata={"chd_path": str(chd.path)},
            )

        if not part.disk_sha1 or not part.disk_name:
            print(f"  ⚠️  Skipping - Part missing disk_sha1 or disk_name")
            return ResultObject.success(
                message=f"Skipped - Part incomplete",
                metadata={"part_name": part.name},
            )

        hash_mismatch = chd.sha1 != part.disk_sha1
        filename_mismatch = chd.name != part.disk_name

        if not hash_mismatch and not filename_mismatch:
            print(f"✅ {chd.name} matches softwarelist")
            return ResultObject.success(
                message=f"Hash and filename match: {chd.name}",
                metadata={"chd_path": str(chd.path)},
            )

        mismatch_details = []
        if hash_mismatch:
            mismatch_details.append(f"hash mismatch")
        if filename_mismatch:
            mismatch_details.append(f"filename mismatch")

        print(f"⚠️  {chd.name}: {', '.join(mismatch_details)}")

        if self.skip_all:
            print(f"Skipping update for {chd.name} (skip_all)")
            return ResultObject.success(
                message=f"Skipped (skip_all): {chd.name}",
                metadata={"chd_path": str(chd.path)},
            )

        if self.update_all:
            print(f"Auto-updating {chd.name} (update_all)")
            self._apply_update(chd, part)
            return ResultObject.success(
                message=f"Updated (update_all): {chd.name}",
                metadata={"chd_path": str(chd.path)},
            )

        message = f"Hash/filename mismatch for {part.part_of.name}\n"
        message += f"  Software: {part.part_of.name}\n"
        message += f"  Part: {part.name}\n"

        if hash_mismatch:
            message += f"\n  HASH MISMATCH:\n"
            message += f"    CHD SHA1:     {chd.sha1}\n"
            message += f"    Part SHA1:    {part.disk_sha1}\n"

        if filename_mismatch:
            message += f"\n  FILENAME MISMATCH:\n"
            message += f"    CHD filename: {chd.name}\n"
            message += f"    Part filename:{part.disk_name}\n"

        if hasattr(part, "source_group") and part.source_group:
            message += f"\n  Source group: {part.source_group}\n"

        return ResultObject.pending_input(
            query_id="generic_query",
            message=message,
            item=PartProcessingItem(part),
            valid_actions=[
                Action.UPDATE,
                Action.UPDATE_ALL,
                Action.SKIP,
                Action.SKIP_ALL,
                Action.STOP,
            ],
        )

    def _apply_update(self, chd: CHD, part: "Part") -> None:
        """Apply update to Part"""
        chd_key = self._get_chd_key(chd)

        source_group = part.source_group if hasattr(part, "source_group") else None

        part.update_chd_metadata(
            new_sha1=chd.sha1,
            new_filename=chd.name,
            source_group=source_group,
        )

        self.pending_updates[chd_key] = {
            "sha1": chd.sha1,
            "filename": chd.name,
            "source_group": source_group,
        }

    def _handle_update_action(self, part: "Part", params: dict) -> ResultObject:
        """Handle UPDATE action"""
        if not self.current_item:
            return ResultObject.error(
                error_type="NoItemError",
                message="No current item to update",
            )

        chd = self.current_item
        self._apply_update(chd, part)

        return ResultObject.success(
            message=f"Updated: {part.disk_name}",
            metadata={"chd_path": str(chd.path)},
        )

    def _handle_skip_all_action(self, params: dict) -> ResultObject:
        """Handle SKIP_ALL action"""
        self.skip_all = True

        return ResultObject.success(
            message="Skip all remaining updates",
        )

    def _handle_stop_action(self, params: dict) -> ResultObject:
        """Handle STOP action"""
        if self.pending_updates:
            self._save_xml_updates()

        return ResultObject.complete(
            total_processed=self.processed_items,
            succeeded=len(self.pending_updates),
            stopped_early=True,
        )

    def _save_xml_updates(self) -> None:
        """Save pending updates to softwarelist XML"""
        if not self.pending_updates:
            print("No updates to save")
            return

        print(
            f"Saving {len(self.pending_updates)} updates to {self.platform.softlist_xml_path}"
        )
        self.platform.softwarelist.write_to_file(self.platform.softlist_xml_path)
        print("Updates saved successfully")

    def _complete_process(self) -> ResultObject:
        """Complete the process and save updates"""
        if self.pending_updates:
            self._save_xml_updates()

        progress = self.progress

        return ResultObject.complete(
            total_processed=self.processed_items,
            succeeded=len(self.pending_updates),
            metadata=progress,
        )

    def handle_user_action(
        self, action: Action, params: Optional[Dict[str, Any]] = None
    ) -> ResultObject:
        """Handle user action from query menu"""
        if params is None:
            params = {}

        part = (
            self.current_item.source.softlist_part
            if self.current_item and self.current_item.source
            else None
        )

        if action == Action.UPDATE:
            if part:
                return self._handle_update_action(part, params)

        elif action == Action.UPDATE_ALL:
            if part:
                self.update_all = True
                return self._handle_update_action(part, params)

        elif action == Action.SKIP:
            return ResultObject.success(
                message=f"Skipped: {part.disk_name if part else 'unknown'}",
            )

        elif action == Action.SKIP_ALL:
            return self._handle_skip_all_action(params)

        elif action == Action.STOP:
            return self._handle_stop_action(params)

        return ResultObject.error(
            error_type="UnknownAction",
            message=f"Unknown action: {action}",
        )
