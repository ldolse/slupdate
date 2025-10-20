from media_registry import CDMedia
from optical_media.utils import OpticalMediaProcessor as file_data
from typing import List, Type
from .base import SpecialHandler



class HandlerRegistry:
    def __init__(self):
        self.handlers = {
            'platform': {},      # Platform-specific handlers
            'format': {},        # File format handlers (e.g., CCD, CUE)
            'dat_group': {}      # DAT group-specific handlers (e.g., redump, no-intro)
        }

    def get_relevant_handlers(self, media: CDMedia, file_data: file_data) -> List[SpecialHandler]:
        handlers = []

        # Add platform handler if exists
        if media.platform in self.handlers['platform']:
            handlers.append(self.handlers['platform'][media.platform]())

        # Add format handler if exists
        format_type = file_data.format
        if format_type and format_type in self.handlers['format']:
            handlers.append(self.handlers['format'][format_type]())

        # Add DAT group handler if exists
        if (media.dat_game_entry and
            media.dat_game_entry.dat and
            media.dat_game_entry.dat.dat_group in self.handlers['dat_group']):
            handlers.append(self.handlers['dat_group'][media.dat_game_entry.dat.dat_group]())

        return handlers

    def register_platform_handler(self, platform_key: str, handler_class: Type[SpecialHandler]):
        self.handlers['platform'][platform_key] = handler_class

    def register_format_handler(self, format_type: str, handler_class: Type[SpecialHandler]):
        self.handlers['format'][format_type] = handler_class

    def register_dat_group_handler(self, dat_group: str, handler_class: Type[SpecialHandler]):
        self.handlers['dat_group'][dat_group] = handler_class

    def register_special_handler(self, name: str, handler_class: Type[SpecialHandler]):
        """Register a special case handler"""
        # Special handlers are stored separately and checked in ProcessManager
        if not hasattr(self, 'special_handlers'):
            self.special_handlers = {}
        self.special_handlers[name] = handler_class

    def get_special_handlers(self) -> List[SpecialHandler]:
        """Get all registered special handlers"""
        if not hasattr(self, 'special_handlers'):
            return []
        
        handlers = []
        for handler_class in self.special_handlers.values():
            handlers.append(handler_class())
        return handlers
