import glob
import os, sys
import re
import pickle
import pprint
import builtins
import inquirer
from requests.adapters import HTTPAdapter, Retry
import requests

def requests_retry_session(
    retries=4,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_script_path():
    '''
    Returns the path to the current script's __main__ module
    '''
    try:
        # Get the __file__ of the __main__ module
        main_file = sys.modules['__main__'].__file__
        return os.path.dirname(os.path.realpath(main_file))
    except AttributeError:
        # set it to current working dir for this scenario, which is most likely when running from interpreter
        script_dir =  os.getcwd()

    # bit of a hack to pass the script dir to the chd module
    builtins.script_dir = script_dir
    return script_dir

def save_data(data_to_save,name,directory=get_script_path()):
    with open(directory+os.sep+name+'.cache', 'wb') as f:
        pickle.dump(data_to_save, f)

def restore_dict(name):
    '''
    Restores a dictionary from a pickle file
    '''
    try:
        with open(name+'.cache', 'rb') as f:
            return pickle.load(f)
    except:
        return {}

def slupdate_version(__version__):
    '''
    Returns the version of the slupdate package
    '''
    return __version__
    

def get_dat_paths(platform, datpaths, sl_dat_map):
    '''
    Returns the paths to the dat files for the specified platform
    '''
    slpath = datpaths['sl']+sl_dat_map[platform]['mame']
    redump_pattern = datpaths['redump']+sl_dat_map[platform]['redump']
    files = glob.glob(redump_pattern)
    redump_path = files[0]
    return [slpath, redump_path]
    
def history(search=None):
    '''
    Prints the history of the current session
    '''
    import readline
    for i in range(readline.get_current_history_length()):
        if search:
            if re.search(search,readline.get_history_item(i + 1)):
                print (readline.get_history_item(i + 1))
        else:
            print (readline.get_history_item(i + 1))

def write_data(data,filename='output.txt'):
    if not filename.endswith('.txt'):
        filename = filename+'.txt'
    with open(filename,'w') as output:
        output.write(pprint.pformat(data,width=400))

def list_menu(key: str, options: list[str], prompt: str, type: str = 'list') -> dict:
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

def get_os_dirs(path):
    """
    Returns a list of directories in the given path
    """
    try:
        directories = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        directories.sort()
        # If no directories found, reverse the order of special options
        if len(directories) == 0:
            directories.insert(0, 'Select the current directory')
            directories.append('Parent Directory')
        else:
            directories.insert(0, 'Parent Directory')
            directories.append('Select the current directory')
        return directories
    except FileNotFoundError as e:
        print(f"Error: Directory not found - {path}")
        raise

def get_start_dir(filetype=None):
    start_path = None

    while not start_path:
        path_query = [
            inquirer.Path(name='path', message=filetype+" Path (or starting point to browse filesystem)")]
        path_entry = inquirer.prompt(path_query)

        # remove any trailing slash, if the user enters
        pattern = os.sep+'$'
        path_entry = re.sub(pattern,'',path_entry['path'])
        if not os.path.exists(path_entry):
            print('invalid path, try again')
            # could potentially count failures and switch to working dir
            #current_path = os.getcwd()
            continue
        else:
            start_path = path_entry
    return start_path


def select_directory(filetype=None,start_dir=None):
    """
    Displays a list of directories in the current directory and prompts the user to select one
    """
    selected = False
    origin_path = os.getcwd()
    if not start_dir:
        current_path = get_start_dir(filetype)
    else:
        current_path = start_dir
    while not selected:
        try:
            message = "Select a directory - current: ["+current_path+"]"
            choices = get_os_dirs(current_path)
            answers = list_menu(filetype,choices,message)
            if answers[filetype] == 'Select the current directory':
                selected = True
                os.chdir(origin_path)
                return current_path
            elif answers[filetype] == 'Parent Directory':
                current_path = os.path.dirname(current_path)
                os.chdir(os.path.dirname(current_path))
            else:
                parent_path = current_path
                current_path = current_path+os.sep+answers[filetype]
                os.chdir(current_path)
        except FileNotFoundError as e:
            print(f"Error: Directory not found - {current_path}")
            # Return to the origin path and re-prompt
            os.chdir(origin_path)
            current_path = origin_path


def reconfigure_settings(instance: object, settings_list: list[tuple[str, str, str]]):
    """
    Generic function to edit attributes of an object via user selection.
    
    Each setting tuple is in the format:
        (attribute_key, human_readable_name, input_type)
    Supported `input_type` values: "directory", "boolean"
    """

    def update_directory(setting_key: str):
        current_value = getattr(instance, setting_key)
        new_value = select_directory(start_dir=current_value)
        if new_value and new_value != current_value:
            setattr(instance, setting_key, new_value)

    def update_boolean(setting_key: str):
        current_value = getattr(instance, setting_key)
        new_value = inquirer.confirm(f"Set '{setting_key}' to True?", default=bool(current_value))
        if new_value != current_value:
            setattr(instance, setting_key, new_value)

    while True:
        choices = []
        for key, desc, input_type in settings_list:
            value = getattr(instance, key, None)
            display_text = f"{desc}: {value}" if value is not None else f"{desc} is not set."
            choices.append((display_text, key))
        choices.append(("Finish", "Finish"))

        selected = list_menu("setting", [(text, key) for text, key in choices], "Choose an option")
        choice_key = selected.get('setting')

        if choice_key == "Finish":
            instance.save()  # Save only when user chooses to exit
            return

        if any(key[0] == choice_key and key[2] == "directory" for key in settings_list):
            update_directory(choice_key)
        elif any(key[0] == choice_key and key[2] == "boolean" for key in settings_list):
            update_boolean(choice_key)
