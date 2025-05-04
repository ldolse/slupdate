import inquirer
import inspect

# key for the menu correlates to the key for the menu's item list
menu_msgs = {'main_menu' : 'Main Menu, select an option',
             'map_menu' : 'Process software lists and dat files, mapping source files to build chds',
             'map_stage_two' : 'Next steps after auto-mapping',
             'map_stage_three' : 'Assisted Mapping Functions',
             'chd_builder' : 'Choose a console to build CHD\'s for current match list',
             'new' : 'This function will look for DAT entries which don\'t appear in software lists and assist with creating Software List records, continue?',
             '5' : 'MAME hash directory and dat directories for at least one platform must be configured.',
             'save' : 'Save asisted mapping answers and other user generated data?  This will overwrite anything previously written to disk',
             '2a' : 'Begin building CHDs?',
             '2b' : 'Update the Software List with new hashes?',
             'soft' : 'Please select the MAME Software List XML directory',
             'chd' : 'CHD Builder Destination Directory',
             'dat_menu' : 'DAT Source Directories',
             'rom' : 'ROM Source Directories',
             'settings_menu' : 'Settings',
             'select_console' : 'Select a console to configure ',
             'select_platform_menu' : 'Platform Selection: Select a console to to work with ',
             'dat_remove' : 'Select a DAT to remove',
             'dir_d' : 'Select a Directory to Remove',
             'romvault' : 'Are you using ROMVault to manage DATs and ROMs?',
             'url_commit' : 'Updates based on Redump source URLs successful. Proceed to update the Softlist data?',
             'tosec_commit' : 'Proceed to update the Softlist data?',
             'fuzzy_commit' : 'Proceed to update the Softlist data?'
    }

# Core Classes for Navigation System
class MenuItem:
    """Represents a single menu option"""
    def __init__(self, text: str, 
                 target: str = None, 
                 action_func = None,
                 requires_platform: bool = True,
                 is_back: bool = False):
        self.text = text  # Displayed text in the menu
        self.target_name = target  # Menu name to navigate to (e.g., "map_menu")
        self.action = action_func  # Callable function (must return a string menu name)
        self.requires_platform = requires_platform
        self.is_back = is_back  # Indicates if this option is a "back" action  

    def execute(self, menu_system: "MenuSystem") -> str:
        """Execute option logic and return next target"""
        # Handle back action
        if self.is_back:
            menu_system.navigate_back()  # Navigate back in history
            return None
        # Handle platform requirement
        if self.requires_platform and not menu_system.current_platform:
            print(f"platform required but not set - in first check, platform is {menu_system.current_platform}")
            return "select_platform_menu"  # Redirect to select platform
        try:
            print(f"inspecting action, platform is {menu_system.current_platform}")
            # Analyze action function's required parameters
            sig = inspect.signature(self.action) if self.action else None
            params_needed = list(sig.parameters.keys()) if self.action else []
            
            args = []
            
            # Check for 'platform' parameter and supply it
            if "platform" in params_needed:
                if not menu_system.current_platform:
                    raise ValueError("Platform required but not set")
                args.append(menu_system.current_platform)

            # Check if action expects the full MenuSystem instance
            elif "menu_system" in params_needed:
                args.append(menu_system)
            
        except Exception as e:
            print(f"Error preparing arguments for {self.text}: {e}")
            return self.target_name  # Default to target
            
        try:
            # Call the function with detected parameters
            result = self.action(*args) if self.action else None
        except TypeError as te:
            print(f"TypeError in action: {te}. Using default.")
            result = None
        
        # Determine next menu based on return value or target
        next_target = (
            result 
            if isinstance(result, str) and result != ""  
            else self.target_name  # Fallback to target name
        )
        
        return next_target


class BaseMenu:
    """Base class for all menus"""
    def __init__(self, name: str):
        self.name = name  # Matches keys from original "menu_msgs"
        self.message_key = name  
        self._options = []
    
    @property
    def options(self) -> list[MenuItem]:
        return self._options
    
    @options.setter
    def options(self, new_options: list[MenuItem]):
        """Setter ensures all items are MenuItem instances and sets default targets"""
        if not all(isinstance(item, MenuItem) for item in new_options):
            raise TypeError("All menu items must be MenuItem instances")
        
        # Set default target to the current menu's name if not provided
        for item in new_options:
            if not item.target_name:  
                item.target_name = self.name  # Default back to own menu
        
        self._options = new_options

    @property
    def message(self) -> str:
        return menu_msgs.get(self.message_key, f"NO MESSAGE FOUND: {self.name}")


class MenuSystem:
    """Manages navigation state and history"""
    def __init__(self):
        self.stack = []  # Navigation history (LIFO)
        self.current_menu_name = None
        self.current_platform = None
        self.menus = {}  # Registry of all menus by name
        
    def register(self, menu: BaseMenu):
        """Adds a new menu to the system"""
        if not isinstance(menu, BaseMenu):
            raise TypeError("Only instances of BaseMenu can be registered")
        self.menus[menu.name] = menu

    @property
    def current_menu(self) -> BaseMenu:
        return self.menus.get(self.current_menu_name)

    def navigate_to(self, target):
        """Pushes current menu to stack and navigates"""
        
        # Only add previous state to stack if current menu exists (not initial run)
        if self.current_menu:
            self.stack.append({
                'menu_name': self.current_menu.name,
            })
        
        self.current_menu_name = target


    def navigate_back(self) -> str:
        """Pops from stack to return to previous menu"""
        if not self.stack:
            return None # Already at root
        
        last_state = self.stack.pop()
        self.current_menu_name = last_state['menu_name']
        return self.current_menu.name


def list_menu(key, options, prompt, type='list'):
    '''
    Simple wrapper for inquirer.List to create a list of options

    Parameters:
    key (str): The key to store the answer in
    options (list): The list of options to choose from
    prompt (str): The prompt to display to the user

    Returns:
    answer (dict): The answer to the prompt
    '''
    if type == 'list':
        optconfirm = [
            inquirer.List(key,
                          message = prompt,
                          choices = options,
                          carousel = True),
                        ]
    elif type == 'checkbox':
        optconfirm = [
            inquirer.Checkbox(key,
                          message = prompt,
                          choices = options),
                        ]
    answer = inquirer.prompt(optconfirm)
    return answer
