
import xmltodict
import glob
import os
import re
import pickle
import pprint
import sys

def save_data(data_to_save,name,directory):
    with open(directory+os.sep+name+'.cache', 'wb') as f:
        pickle.dump(data_to_save, f)

def restore_dict(name):
    try:
        with open(name+'.cache', 'rb') as f:
            return pickle.load(f)
    except:
        return {}


def slupdate_version():
    return __version__


def get_dat_paths(platform, datpaths, sl_dat_map):
    slpath = datpaths['sl']+sl_dat_map[platform]['mame']
    redump_pattern = datpaths['redump']+sl_dat_map[platform]['redump']
    files = glob.glob(redump_pattern)
    redump_path = files[0]
    return [slpath, redump_path]
    
def convert_xml(file, comments=False):
    #read xml content from the file
    fileptr = open(file,"r",encoding='utf-8')
    xml_content= fileptr.read()
    #print("XML content is:")
    #print(xml_content)
    my_ordered_dict=xmltodict.parse(xml_content, process_comments=comments, force_list=('info','rom',))
    return my_ordered_dict
    
def history(search=None):
    import readline
    for i in range(readline.get_current_history_length()):
        if search:
            if re.search(search,readline.get_history_item(i + 1)):
                print (readline.get_history_item(i + 1))
        else:
            print (readline.get_history_item(i + 1))

def write_data(data):
    with open('output.txt','w') as output:
        output.write(pprint.pformat(data,width=400))
