import glob
import os, sys
import re
import pickle
import pprint
import builtins

def get_script_path():
    '''
    Returns the path to the current script's __main__ module
    '''
    try:
        # Get the __file__ of the __main__ module
        main_file = sys.modules['__main__'].__file__
        return os.path.dirname(os.path.realpath(main_file))
    except NameError:
        # set it to current working dir for this scenario, which is most likely when running from interpreter
        script_dir =  os.getcwd()

    # bit of a hack to pass the script dir to the chd module
    builtins.script_dir = script_dir
    return script_dir

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
