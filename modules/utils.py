import glob
import os
import re
import pickle
import pprint
import inquirer

def save_data(data_to_save,name,directory):
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


def slupdate_version():
    '''
    Returns the version of the slupdate package
    '''
    return __version__
    
def list_menu(key, options, prompt):
    '''
    Simple wrapper for inquirer.List to create a list of options

    Parameters:
    key (str): The key to store the answer in
    options (list): The list of options to choose from
    prompt (str): The prompt to display to the user

    Returns:
    answer (dict): The answer to the prompt
    '''
    optconfirm = [
        inquirer.List(key,
                      message = prompt,
                      choices = options,
                      carousel = True),
                    ]
    answer = inquirer.prompt(optconfirm)
    return answer


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
