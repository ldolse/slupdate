from .menu_system import BaseMenu, MenuItem
from rom_management.processing import ArchiveValidationProcess
from rom_management.archive import MD5ScanRequiredException

class ValidationProgressMenu(BaseMenu):
    def __init__(self):
        super().__init__("validation_progress_menu")
        self.message = "Full Scan Required for Media"
        self.options = [
            MenuItem(text="Skip current item", action_func=self.skip),
            MenuItem(text="Scan this archive with MD5 (slow)", action_func=self.scan_md5),
            MenuItem(text="Skip all archives requiring MD5 scanning", action_func=self.skip_all),
            MenuItem(text="Scan all archives requiring MD5 scanning", action_func=self.scan_all_md5),
            MenuItem(text="Stop validation", action_func=self.stop)
        ]

    def set_payload(self, process: ArchiveValidationProcess):
        self.payload = process
        progress = process.get_progress()
        
        # Get current item for filename display
        current_item = process.get_current_item()
        file_name = ""
        if current_item and hasattr(current_item, 'dat_game_entry') and current_item.dat_game_entry:
            file_name = f" ({current_item.dat_game_entry.name})"

        # Update message based on preference and exception type
        if isinstance(process.state['exception_payload'], MD5ScanRequiredException):
            self.message = f"MD5 scan required{file_name}: {process.state['exception_payload'].message}"
        elif process.user_preference == 'skip_all':
            self.message = f"Skipping all remaining bad ROMs: {progress['failed']}/{progress['total']} skipped"
        elif process.user_preference == 'continue_all':
            self.message = f"Continuing without asking: {progress['processed']}/{progress['total']} completed"
        elif process.user_preference == 'scan_all_md5':
            self.message = f"Scanning all with MD5: {progress['processed']}/{progress['total']} completed"
        else:
            self.message = f"Validating ROMs: {progress['processed']}/{progress['total']} completed"

    @staticmethod
    def skip(self, menu_system) -> str:
        return menu_system.current_platform_obj.process_manager.continue_processing('skip')

    @staticmethod
    def scan_md5(self, menu_system) -> str:
        return menu_system.current_platform_obj.process_manager.continue_processing('scan_md5')

    @staticmethod
    def skip_all(self, menu_system) -> str:
        return menu_system.current_platform_obj.process_manager.continue_processing('skip_all')

    @staticmethod
    def scan_all_md5(self, menu_system) -> str:
        return menu_system.current_platform_obj.process_manager.continue_processing('scan_all_md5')

    @staticmethod
    def stop(self, menu_system) -> str:
        return menu_system.current_platform_obj.process_manager.continue_processing('stop')
