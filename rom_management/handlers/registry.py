from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor as file_data
from typing import List, Type, Optional, Tuple, TYPE_CHECKING, Any
from .base import SpecialHandler

if TYPE_CHECKING:
    from rom_management.processing.models import ResultObject


class HandlerRegistry:
    def __init__(self):
        self.handlers = {
            "platform": {},  # Platform-specific handlers
            "format": {},  # File format handlers (e.g., CCD, CUE)
            "dat_group": {},  # DAT group-specific handlers (e.g., redump, no-intro)
            "special_handlers": {},  # Common special handling cases
        }

    def get_relevant_handlers(
        self, media: CDMedia, file_data: file_data, process: Any = None
    ) -> Tuple[List[SpecialHandler], Optional["ResultObject"]]:
        """
        Get relevant handlers for a media item.

        Returns:
            Tuple of (handlers, skip_result)
            - handlers: List of handlers to apply
            - skip_result: ResultObject with SKIP status if item should be skipped, None otherwise
        """
        from rom_management.processing.models import ResultObject

        handlers = []
        skip_result = None

        # Add platform handler if exists
        if media.platform in self.handlers["platform"]:
            handler = self.handlers["platform"][media.platform]()
            result = handler.validate_preconditions(media, file_data, process)

            if result.is_not_applicable():
                pass  # Handler not relevant, don't include
            elif result.is_skip():
                return [], result  # Item should be skipped
            elif result.is_success():
                handlers.append(handler)
            elif result.requires_input():
                return [], result  # Handler needs user input

        # Add format handler if exists
        format_type = file_data.format if file_data else None
        if format_type and format_type in self.handlers["format"]:
            handler = self.handlers["format"][format_type]()
            result = handler.validate_preconditions(media, file_data, process)

            if result.is_not_applicable():
                pass  # Handler not relevant, don't include
            elif result.is_skip():
                return [], result  # Item should be skipped
            elif result.is_success():
                handlers.append(handler)
            elif result.requires_input():
                return [], result  # Handler needs user input

        # Add DAT group handler if exists
        if (
            media.dat_game_entry
            and media.dat_game_entry.dat
            and media.dat_game_entry.dat.dat_group in self.handlers["dat_group"]
        ):
            handler = self.handlers["dat_group"][media.dat_game_entry.dat.dat_group]()
            result = handler.validate_preconditions(media, file_data, process)

            if result.is_not_applicable():
                pass  # Handler not relevant, don't include
            elif result.is_skip():
                return [], result  # Item should be skipped
            elif result.is_success():
                handlers.append(handler)
            elif result.requires_input():
                return [], result  # Handler needs user input

        # Add special handlers (e.g., MD5ScanHandler, CHDExistenceHandler)
        special_handlers = self.get_special_handlers()
        for handler in special_handlers:
            result = handler.validate_preconditions(media, file_data, process)

            if result.is_not_applicable():
                pass  # Handler not relevant
            elif result.is_skip():
                return [], result  # Item should be skipped
            elif result.is_success():
                handlers.append(handler)
            elif result.requires_input():
                return [], result  # Handler needs user input

        return handlers, skip_result

    def get_all_handlers(self) -> List["SpecialHandler"]:
        """Get all registered handlers (platform, format, dat_group, and special)"""
        all_handlers = []

        # Add all platform handlers
        for handler_class in self.handlers["platform"].values():
            all_handlers.append(handler_class())

        # Add all format handlers
        for handler_class in self.handlers["format"].values():
            all_handlers.append(handler_class())

        # Add all DAT group handlers
        for handler_class in self.handlers["dat_group"].values():
            all_handlers.append(handler_class())

        # Add all special handlers
        for handler_class in self.handlers.get("special_handlers", {}).values():
            all_handlers.append(handler_class())

        return all_handlers

    def register_platform_handler(
        self, platform_key: str, handler_class: Type[SpecialHandler]
    ):
        self.handlers["platform"][platform_key] = handler_class

    def register_format_handler(
        self, format_type: str, handler_class: Type[SpecialHandler]
    ):
        self.handlers["format"][format_type] = handler_class

    def register_dat_group_handler(
        self, dat_group: str, handler_class: Type[SpecialHandler]
    ):
        self.handlers["dat_group"][dat_group] = handler_class

    def register_special_handler(self, name: str, handler_class: Type[SpecialHandler]):
        """Register a special case handler"""
        if "special_handlers" not in self.handlers:
            self.handlers["special_handlers"] = {}
        self.handlers["special_handlers"][name] = handler_class

    def get_special_handlers(self) -> List[SpecialHandler]:
        """Get all registered special handlers"""
        handlers = []
        special_dict = self.handlers.get("special_handlers", {})
        for handler_class in special_dict.values():
            handlers.append(handler_class())
        return handlers
