#!/usr/bin/env python

""" slupdate.py: Interactively Update Optical Media based Software Lists 
against[Redump](http://redump.org/) dats.

https://github.com/ldolse/slupdate
"""
import os
import re
import sys
import inquirer
from modules.utils import save_data,restore_dict
from modules.dat import get_dat_name


__version__ = '.1'

# Require at least Python 3.2
assert sys.version_info >= (3, 2)


settings = restore_dict('settings')
user_answers = restore_dict('user_answers')

softlist_dict = {}
dat_dict = {}

# disabled by default, allows the script to populate chd sha1s on subsequent runs
# only enable if CHD destination folder ONLY contains chds created by this script
get_sha_from_existing_chd = False


mapping_stage = { 'source_map' : [],
             'name_serial_map' : [],
                 'tosec_remap' : [],
                  'manual_map' : []
                  }

consoles = {  #'Atari Jaguar' : 'jaguar',
                'Amiga CDTV' : 'cdtv',
                'Amiga CD32' : 'cd32',
               'FM Towns CD' : 'fmtowns_cd',
          'IBM PC/AT CD-ROM' : 'ibm5170_cdrom',
 'PC Engine / TurboGrafx CD' : 'pcecd',
              #'Philips CD-i' : 'cdi',
            'Pippin CD-ROMs' : 'pippin',
                 'NEC PC-FX' : 'pcfx',
                   'Sega CD' : 'segacd',
     'Sega Mega CD (Europe)' : 'megacd',
      'Sega Mega CD (Japan)' : 'megacdj',
               'Sega Saturn' : 'saturn',
            'Sega Dreamcast' : 'dc',
             'SNK NeoGeo CD' : 'neocd',
          'Sony Playstation' : 'psx',
                       '3DO' : '3do_m2'
        }
# key for the menu correlates to the key for the menu's item list
menu_msgs = {'0' : 'Main Menu, select an option',
             'map' : 'These functions will process software lists and dat files, mapping source files to build chds',
             '2' : 'Choose a console to build CHD\'s for current match list',
             '3' : 'Choose an assisted mapping task to identify other sources for softlist entries',
             'new' : 'This function will look for DAT entries which don\'t appear in software lists and assist with creating Software List records, continue?',
             '5' : 'MAME hash directory and dat directories for at least one platform must be configured.',
             'save' : 'Save asisted mapping answers and other user generated data?  This will overwrite anything previously written to disk',
             '2a' : 'Begin building CHDs?',
             '2b' : 'Update the Software List with new hashes?',
             '4a' : 'Do you want to create alternate softlist entries for both redump and TOSEC, or do you want to avoid duplicating entries?  In order to avoid duplicating entries TOSEC sourced entries must first be matched to redump.',
             'soft' : 'Please select the MAME Software List XML directory',
             'chd' : 'CHD Builder Destination Directory',
             'dat' : 'DAT Source Directories',
             'rom' : 'ROM Source Directories',
             '5b' : 'Select a console to configure',
             '5c' : 'Select a DAT to remove',
             'dir_d' : 'Select a Directory to Remove',
             'romvault' : 'Are you using ROMVault to manage DATs and ROMs?'
    }
# unless a list entry maps to a function it should always map to another menu in the tree
# This allows completed functions to go back to their parent menu automatically
menu_lists = {'0' : [('1. Mapping Functions', 'map'),
                     ('2. CHD Builder', '2'),
                     #('3. Assisted Title/Disc Mapping', '3'),
                     #('4. Create New Entries','entry_create_function'),
                     ('5. Settings','5'),
                     #('6. Save Session','save_function'),
                     ('7. Exit', 'Exit')],
             'map' : [('a. Automatically map based on source rom info','automap_function'),
                      #('b. Map Based on Disc Serial & Name','name_serial_automap_function'),
                      #('c. Remap entries with TOSEC sources to Redump','tosec_map_function'),
                      #('d. Map entries with no source reference to Redump','no_src_map_function'),
                      ('e. Back', '0')],
             '2' : [('a. Console List','chd_build_function'),
                    ('b. Back', '0')],
             '3' : [('Map entries with no source information to Redump sources','no_src_map_function'),
                    ('Remap entries with TOSEC sources to Redump sources','tosec_map_function'),
                    ('Back', '0')],
             '5' : [('a. MAME Software List XML Directory', 'slist_dir_function'),
                    ('b. Configure Root DAT/ROM Directories (ROMvault)', 'root_dirs_function'),
                    ('c. Configure DAT/ROM Directories', 'dat'),
                    ('d. Destination folder for CHDs', 'chd_dir_function'),
                    ('e. Back', '0')],
             'dat' : [('Add Directories','platform_dat_rom_function'),
                      ('Remove DATs','del_dats_function'),
                      ('Back', '5')],
    }


def main_menu():
    global settings
    dir_types = ('dat','rom','map')
    if len(settings) == 0:
        menu_sel = '5'
    else:
        menu_sel = '0'
    complete = False
    while not complete:
        answer = list_menu(menu_sel,menu_lists[menu_sel],menu_msgs[menu_sel])
        if any(file in answer.values() for file in dir_types):
            platform = platform_select(list(answer)[0])

        if answer[menu_sel].endswith('function'):
            if any(f in answer for f in dir_types):     
                globals()[answer[menu_sel]](platform['platforms'])
                # return to the previous menu after completing the function
                menu_sel = list(answer)[0]
            else:
                globals()[answer[menu_sel]]()
                # return to the previous menu after completing the function
                menu_sel = list(answer)[0]

        elif menu_sel == '5' and answer[menu_sel] == '0':
            # save settings when exiting settings and returning to main menu
            save_data(settings,'settings')
            menu_sel = answer[menu_sel]
        elif answer[menu_sel] == 'Exit':
            complete = True
        else:
            menu_sel = answer[menu_sel]


def list_menu(key, options, prompt):
    optconfirm = [
        inquirer.List(key,
                      message = prompt,
                      choices = options,
                      carousel = True),
                    ]
    answer = inquirer.prompt(optconfirm)
    return answer


def find_dat_matches(platform,sl_platform_dict,dathash_platform_dict):
    '''
    matches source hash fingerprints to the dat fingerprint dicts
    updates the softlist dict to point to the dat for that source
    '''
    from modules.chd import find_rom_zips
    title_dat_matches = 0
    disc_matches = 0
    dat_matches = 0
    zips = 0
    for datfile, dathashdict in dathash_platform_dict['hashes'].items():
        for sl_title, sl_data in sl_platform_dict.items():
            sl_title_match = False
            dat_name_list = []
            for disc, disc_data in sl_data['parts'].items():
                if 'source_rom' in disc_data:
                    continue # skip when a source ROM was identified from an earlier DAT
                if 'source_sha' in disc_data and disc_data['source_sha'] in dathashdict:
                    sourcehash = disc_data['source_sha']
                    disc_matches += 1
                    sl_title_match = True
                    dat_name_list.append(dathashdict[sourcehash]['name'])
                elif 'source_crc_sha' in disc_data and disc_data['source_crc_sha'] in dathashdict:
                    sourcehash = disc_data['source_crc_sha']
                    disc_matches += 1
                    sl_title_match = True
                    dat_name_list.append(dathashdict[sourcehash]['name'])
            if sl_title_match and 'sourcedat' not in sl_title:
                title_dat_matches += 1
            if sl_title_match: 
                sl_platform_dict[sl_title].update({'sourcedat':datfile})
                if dathashdict[sourcehash]['name'] in dathash_platform_dict['redump_unmatched'][datfile]:
                    dathash_platform_dict['redump_unmatched'][datfile].pop(dathashdict[sourcehash]['name'])
        # check to see if there is a valid zip for this rom
            zip_name = find_rom_zips(datfile,sl_data,dathashdict,settings[platform])
            if zip_name:
                dat_zips = dict(zip(dat_name_list,zip_name))
                print('\nMatch Found:\n  Softlist: '+sl_data['description'])
                for datname,zipname in dat_zips.items():
                    print('       Dat: '+datname+'\n       Zip: '+zipname)
                    zips += 1
    print('found:\n  '+str(title_dat_matches)+' title matches out of '+str(len(sl_platform_dict))+' total entries\n  '+str(disc_matches)+' disc matches\n  '+str(zips)+' valid zip files')


def get_configured_platforms(action_type):
    '''
    Builds a tuple list of the configured platforms
    action_type variable is based on what type pre-config
    for the sub-function
    '''
    configured = []
    for name, platform in consoles.items():
        if platform in settings and len(settings[platform]) > 0:
            configured.append((name,platform))
    return configured

def platform_select(list_type):
    if list_type == 'dat':
        platforms = [(k, v) for k, v in consoles.items()]
    else:
        platforms = get_configured_platforms(list_type)
    answer = list_menu('platforms', platforms, menu_msgs['5b']+menu_msgs[list_type])
    return answer


# placeholder functions
def no_src_map_function(platform):
    print('no source mapping placeholder')

def tosec_map_function(platform):
    print('tosec to redump placeholder')
    # flag that this stage is completed for this platform
    #if platform not in mapping_stage['tosec_remap']:
    #    mapping_stage['tosec_remap'].append(platform)

def entry_create_function(platform):
    print('new entry placeholder')
    proceed = inquirer.confirm(menu_msgs['new'], default=False)


def automap_function(platform):
    from modules.dat import build_dat_dict, build_sl_dict
    from modules.utils import convert_xml
    # process the software list into a dict, creating hash based fingerprints
    print('processing '+platform+' software list')
    process_comments = True
    raw_sl_dict = convert_xml(settings['sl_dir']+os.sep+platform+'.xml',process_comments)
    softdict = dict(raw_sl_dict['softwarelist'])
    if platform not in softlist_dict:
        softlist_dict.update({platform:{}})
    crc_hashlookup = build_sl_dict(softdict['software'], softlist_dict[platform])
    # process each DAT to build a list of fingerprints
    print('processing '+platform+' DAT Files')
    if platform not in dat_dict:
        dat_dict.update({platform:{}})
    for dat in settings[platform]:
        raw_dat_dict = convert_xml(dat)
        build_dat_dict(dat,raw_dat_dict['datafile'],dat_dict[platform],crc_hashlookup)
    # iterate through each fingerprint in the software list and search for matching hashes
    find_dat_matches(platform,softlist_dict[platform],dat_dict[platform])
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['source_map']:
        mapping_stage['source_map'].append(platform)
    print('Next step will be to map entries based on name and disc serial number')
    print('This will require connecting to redump once for each platform to get additional info')
    print('If you want to proceed just based on the hash matches already found then this')
    print('step can be skipped')
    name_serial = inquirer.confirm('Begin Serial/Name Mapping?', default=False)
    if name_serial:
        name_serial_automap_function(platform)

def name_serial_automap_function(platform):
    from modules.mapping import name_serial_map
    name_serial_map(platform, softlist_dict[platform],dat_dict[platform])
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['name_serial_map']:
        mapping_stage['name_serial_map'].append(platform)

def chd_build_function():
    '''
    checks the mapped fingerprints against available ROMs, converts complete ROMs
    to CHD.  CHD hash is added to the soft-dict.  If a CHD already exists in the
    build directory then only the hash is checked.
    '''
    from modules.chd import find_softlist_zips,create_chd_from_zip,chdman_info
    from modules.dat import update_softlist_chd_sha1s
    # get configured platforms and map selected from the returned key
    platform = platform_select('chd')['platforms']
    build = inquirer.confirm('Begin Creating CHDs?', default=False)
    print(build)
    if build:
        new_hashes = False
        built_sources = {}
        for soft, soft_data in softlist_dict[platform].items():
            for disc_data in soft_data['parts'].values():
                if 'source_rom' in disc_data:
                    # create platform directory
                    if not os.path.exists(os.path.join(settings['chd'],platform)):
                        os.mkdir(os.path.join(settings['chd'],platform))
                    chd_dir = os.path.join(settings['chd'],platform,soft)
                    if not os.path.exists(chd_dir):
                        os.mkdir(chd_dir)
                    chd_name = disc_data['chd_filename']+'.chd'
                    chd_path = os.path.join(chd_dir,chd_name)
                    print('building chd for '+soft_data['description']+':')
                    print('            CHD: '+chd_name)
                    print('     Source Zip: '+os.path.basename(disc_data['source_rom']))
                    if not os.path.isfile(chd_path):
                        if disc_data['source_rom'] not in built_sources:
                            try:
                                create_chd_from_zip(disc_data['source_rom'],chd_path,settings)
                                built_sources.update({disc_data['source_rom']:chd_path})
                            except:
                                print('CHD Creation Failed')
                                try:
                                    os.remove(chd_path)
                                except:
                                    print('Failed to delete partial file:\n'+chd_path)
                                    print('Please ensure this is deleted to avoid corrupted files/hashes')
                                continue_build = inquirer.confirm('Do you want to continue?', default=False)
                                if continue_build:
                                    continue
                                else:
                                    break
                        # if the exact same chd was built earlier then just symlink to it
                        elif disc_data['source_rom'] in built_sources:
                            os.symlink(built_sources[disc_data['source_rom']],chd_path)
                            built_sources.update({disc_data['source_rom']:chd_path})
                    # if the chd was created as a part of this run or if the flag to trust existing chds is enabled check the sha1 against the softlist
                    if os.path.isfile(chd_path):
                        if disc_data['source_rom'] in built_sources or get_sha_from_existing_chd:
                            new_chd_hash = chdman_info(chd_path)
                            if new_chd_hash == disc_data['chd_sha1']:
                                print('     Hash matches softlist: '+chd_name+'\n')
                            else:
                                new_hashes = True
                                print('     Updated hash for softlist: '+chd_name+'\n')
                                disc_data.update({'new_sha1':new_chd_hash})
                        else:
                            print('     Chd file already exists in this location\n')
                            
        if new_hashes:
            write_new_hashes = inquirer.confirm('Update the Software List with new CHD Hashes?', default=False)
            if write_new_hashes:
                update_softlist_chd_sha1s(settings['sl_dir']+os.sep+platform+'.xml',softlist_dict[platform])


def save_function():
    confirm_message = menu_msgs['save']
    save = inquirer.confirm(confirm_message, default=False)
    if save:
        save_data(user_answers,'answers')
    return

def restore_function():
    confirm_message = menu_msgs['restore']
    load = inquirer.confirm(confirm_message, default=False)
    if load:
        user_answers = restore_dict('user_answers')

'''
directory selection functions
'''
def root_dirs_function():
    single_dir_function('datroot','Root DAT Directory')
    single_dir_function('romroot','Root ROM Directory')
    confirm_message = menu_msgs['romvault']
    romvault = inquirer.confirm(confirm_message, default=False)
    settings.update({'romvault' : romvault})

def del_dats_function(platform):
    datlist = []
    for dat in settings[platform].keys():
        print('deleting '+settings['datroot']+'\nfrom '+dat)
        datlist.append(dat.replace(settings['datroot'], ''))
    datlist.append('back')
    answer = list_menu('dat', datlist, menu_msgs['5c'])
    if answer['dat'] == 'back':
        return
    else:
        dat_path = settings['datroot']+dat
        settings[platform].pop(answer[dat_path])


def slist_dir_function():
    single_dir_function('sl_dir','MAME Software List')

def chd_dir_function():
    single_dir_function('chd','CHD Destination Directory')
    single_dir_function('zip_temp','Temporary Directory for uncompressed ZIP data')

def single_dir_function(dirtype,prompt):
    # queries and stores the software list hash directory
    directory = select_directory(prompt)
    settings.update({dirtype : directory})

def get_platform_dir(dirtype,platform):
    if dirtype not in settings[platform]:
        settings[platform].update({dirtype:[]})
    directory = select_directory(dirtype)
    if directory not in settings[platform][dirtype]:
        settings[platform][dirtype].append(directory)

def romvault_dat_to_romfolder(dat_directory,dat_files):
    '''
    RomVault maps the ROM directories based on the file structure in DATroot
    DAT directories with multiple DATs will create subfolders based on the DAT title
    returns a dict with the DAT to ROM folder mapping
    '''
    #print('dat dir is '+dat_directory)
    #rom_dir = settings['romroot']+re.sub(settings['datroot'],'',dat_directory)
    rom_dir = settings['romroot']+dat_directory.replace(settings['datroot'], '')
    #print('rom dir is '+rom_dir)
    if len(dat_files) == 1:
        if os.path.isdir(rom_dir):
            return {dat_directory+os.sep+dat_files[0] : rom_dir}
        else:
            print('Unable to locate '+rom_dir+' directory in ROMroot')
            if inquirer.confirm('Do you want to create the appropriate directory?', default=False):
                os.makedirs(rom_dir)
                return {dat_directory+os.sep+dat_files[0] : rom_dir}
            else:
                return {}
    else:
        dat_rom_dict = {}
        for dat in dat_files:
            if not dat.endswith('.xml'):
                dat_path = dat_directory+os.sep+dat
                # rom subfolder is based on dat name, get name
                print('checking dat '+dat)
                name = get_dat_name(dat_path)
                full_rom_dir = rom_dir+os.sep+name
                if not os.path.isdir(full_rom_dir):
                    print('Unable to locate "'+name+'" directory in platform ROM folder')
                    if inquirer.confirm('Do you want to create the appropriate directory?', default=False):
                        os.makedirs(full_rom_dir)
                    else:
                        continue
                dat_rom_dict.update({dat_path:full_rom_dir})
        return dat_rom_dict


def platform_dat_rom_function(platform):
    if platform not in settings:
        settings.update({platform : {}})
    # get the dat dir first
    if 'datroot' not in settings:
        single_dir_function('datroot','Root DAT Directory')
    dat_directory = select_directory('dat',settings['datroot'])
    dat_files = [f for f in os.listdir(dat_directory) if f.endswith('.dat') or f.endswith('.xml')]
    print(f"DAT files in {dat_directory}: {dat_files}")
    # if using romvault map the ROM directores for the DATs automatically
    if settings['romvault']:
        datrom_dirmap = romvault_dat_to_romfolder(dat_directory, dat_files)
        settings[platform].update(datrom_dirmap)

def get_os_dirs(path):
    """
    Returns a list of directories in the given path
    """
    directories = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    directories.sort()
    directories.insert(0,'Parent Directory')
    directories.append('Select the current directory')
    return directories

def select_directory(filetype=None,start_dir=None):
    """
    Displays a list of directories in the current directory and prompts the user to select one
    """
    selected = False
    origin_path = os.getcwd()
    if not start_dir:
        path_query = [
            inquirer.Path(name='path', message=filetype+" Path (or starting point)")]
        start_path = inquirer.prompt(path_query)  
        try:
            # remove any trailing slash, if the user enters anything that triggers an
            # exception then just use the current working directory as a starting point
            pattern = os.sep+'$'
            current_path = re.sub(pattern,'',start_path['path'])
        except:
            current_path = os.getcwd()
    else:
        current_path = start_dir
    while not selected:
        questions = [
            inquirer.List(filetype,
                          message="Select a directory current:("+current_path+")",
                          choices=get_os_dirs(current_path))
            ]
        answers = inquirer.prompt(questions)
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






