#!/usr/bin/env python3

""" slupdate.py: Interactively Update MAME Optical Media based Software Lists
against[Redump](http://redump.org/) & TOSEC dats.

https://github.com/ldolse/slupdate
"""
import os
import re
import sys
import inquirer
import traceback
from importlib import reload
from modules.utils import save_data, restore_dict, get_script_path
from modules.menus import *
from modules.chd import *
from modules.mapping import *
from modules.dat import *


__version__ = '.2'

# Require at least Python 3.7
assert sys.version_info >= (3, 7)


settings = restore_dict('settings')
user_answers = restore_dict('user_answers')

softlist_dict = globals().get('softlist_dict', {})
all_dat_dict = globals().get('all_dat_dict', {})

# disabled by default, allows the script to populate chd sha1s on subsequent runs
# only enable if CHD destination folder ONLY contains chds created by this script
get_sha_from_existing_chd = False

mapping_stage = { 'source_map' : [],
        'name_serial_auto_map' : [],
 'name_serial_interactive_map' : [],
                 'tosec_remap' : [],
                  'manual_map' : []
                  }

consoles = {    'Amiga CDTV' : 'cdtv',
                'Amiga CD32' : 'cd32',
               'FM Towns CD' : 'fmtowns_cd',
          'IBM PC/AT CD-ROM' : 'ibm5170_cdrom',
       'NEC PC-9801 CD-ROMs' : 'pc98_cd',
 'PC Engine / TurboGrafx CD' : 'pcecd',
              'Philips CD-i' : 'cdi',
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


def sl_update_function(platform):
    '''
    updates the software list xml file with new data

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.
    '''
    from modules.dat import update_rom_source_refs, rewrite_comment_source_group
    # update re-mapped sources from DAT
    update_rom_source_refs(settings['sl_dir']+os.sep+platform+'.xml',softlist_dict[platform],all_dat_dict[platform])
    # update the source group reference for unknown/undocumented sources that have been matched
    rewrite_comment_source_group(settings['sl_dir']+os.sep+platform+'.xml',softlist_dict[platform])


def url_map_function(platform):
    '''
    remaps the softlist based on redump source urls

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.
    '''
    from modules.mapping import redump_url_mapping
    if platform not in softlist_dict:
        print('please run the initial mapping function first')
        return 'map_menu'
    url_remaps = redump_url_mapping(softlist_dict[platform],all_dat_dict[platform],script_dir,platform)
    if url_remaps:
        proceed = inquirer.confirm(menu_msgs['url_commit'], default=False)
        if proceed:
            update_soft_dict(softlist_dict[platform],all_dat_dict[platform],url_remaps)

def list_missing_function(platform):
    '''
    lists the missing ROM files for matched entries

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    answer (str): The key to the menu to return to.
    '''
    from modules.mapping import get_missing_zips
    get_missing_zips(softlist_dict[platform],all_dat_dict[platform])

def first_run(menu_system: "MenuSystem"):
    """
    Configures the softlist, root ROM & DAT directories
    """
    print('Please Configure the MAME Softlist hash directory location.\n')
    slist_dir_function()
    print('\nPlease Confgure the root directory locations for your DAT and ROM files')
    print('This will be used to simplify navigation for DAT and ROM directory selection')
    print('RomVault compatibility can also be enabled here to automate ROM directory configuration\n')
    root_dirs_function()
    print('\nPlease configure DATs for the first Platform (more can be configured later)\n')
    platform_dat_rom_function(menu_system)
    print('\nPlease configure the destination directory for created CHDs - note this directory should not contain CHDs from other sources')
    chd_dir_function()

def dat_build_function(platform):
    '''
    creates a DAT file from the unmatched ROMs

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.
    '''
    from modules.dat import create_dat
    from modules.mapping import get_unmatched_roms
    rom_dict = get_unmatched_roms(softlist_dict[platform])
    create_dat(rom_dict,platform)


def find_dat_matches(platform,sl_platform_dict,dathash_platform_dict):
    '''
    - Finds the matching entries in the DAT files for the given platform.

    - matches softlist source hash fingerprints to the dat fingerprint
    
    - updates the softlist dictionary to point to the dat for that source hash

    Parameters:
    platform (str): The platform for which the mapping is being performed.
    sl_platform_dict (dict): The software list dictionary for the platform.
    dathash_platform_dict (dict): The dat hash dictionary for the platform.

    '''
    from modules.chd import find_rom_zips
    from modules.mapping import get_source_stats, print_source_stats
    matched_titles = []
    for datfile, dathashdict in dathash_platform_dict['hashes'].items():
        dat_group = get_dat_group(datfile)
        for sl_title, sl_data in sl_platform_dict.items():
            dat_name_list = {}
            chds_exist = False
            for disc, disc_data in sl_data['parts'].items():
                if 'source_rom' in disc_data:
                    continue # skip when a source ROM was identified from an earlier DAT
                if 'chd_filename' in disc_data:
                    chd_path = settings['chd']+os.sep+platform+os.sep+sl_title+os.sep+disc_data['chd_filename']+'.chd'
                    if os.path.isfile(chd_path):
                        # add chd path to a list, check for unique files later
                        disc_data.update({'chd_found':True})
                        chds_exist = True
                # get source hash key based on crc or sha
                if 'source_sha' in disc_data:
                    sourcehash = disc_data['source_sha']
                else:
                    continue
                if sourcehash in dathashdict:
                    # add the dat source to the entry
                    disc_data['source_dat'] = datfile
                    # add the dat group to the entry
                    disc_data['source_group'] = dat_group
                    disc_data['source_name'] = dathashdict[sourcehash]['name']
                    disc_data['raw_rom_entry'] = dathashdict[sourcehash]['raw_romlist']
                    dat_name_list.update({dathashdict[sourcehash]['name']:[datfile]})

                    # add the matching entries from the softlist to the dat dict for reference
                    if 'softlist_matches' not in dathashdict[sourcehash]:
                        dathashdict[sourcehash]['softlist_matches'] = []
                    dathashdict[sourcehash]['softlist_matches'].append((sl_title,disc))

                    # set boolean flag at the softlist level to flag a match occurred
                    sl_platform_dict[sl_title].update({'source_found':True})

            # add the matched titles to the matched dict
            matched_titles.append(dat_name_list)
            # check to see if there are valid zips for this softlist entry, creates 'source_rom' key(s) if so
            dat_rom_map = {file: path for sub_dict in settings[platform].values() for file, path in sub_dict.items()}
            zip_name = find_rom_zips(datfile,sl_data,dathashdict,dat_rom_map)
            if zip_name:
                dat_zips = dict(zip(dat_name_list.keys(),zip_name))
                print('\nMatch Found:\n  Softlist: '+sl_data['description'])
                for datname,zipname in dat_zips.items():
                    print('       Dat: '+datname+'\n       Zip: '+zipname)
                    if chds_exist:
                        print('       CHD(s) for this title found')
    # final iteration through the softlist to identify the matched titles add them to the name lookup dict
    for sl_title, sl_data in sl_platform_dict.items():
        for disc, disc_data in sl_data['parts'].items():
            if 'source_dat' in disc_data:
                datfile = disc_data['source_dat']
                source_sha = disc_data['source_sha']
                dat_entry_name = dathash_platform_dict['hashes'][datfile][source_sha]['name']
                if dat_entry_name in dathash_platform_dict['name_lookup'][datfile]:
                    if 'softlist_matches' not in dathash_platform_dict['name_lookup'][datfile][dat_entry_name]:
                        dathash_platform_dict['name_lookup'][datfile][dat_entry_name]['softlist_matches'] = [(sl_title,disc)]
                    else:
                        dathash_platform_dict['name_lookup'][datfile][dat_entry_name]['softlist_matches'].append((sl_title,disc))

    # Count the total number of softlist entries
    total_softlist_entries = len(sl_platform_dict)
    # count the total number of entries with source references
    total_source_ref = sum(1 for softlist_entry in sl_platform_dict.values() for part in softlist_entry['parts'].values() if 'source_sha' in part)
    # Count the number of entries where 'source_found' is True
    total_source_found = sum(1 for softlist_entry in sl_platform_dict.values() if softlist_entry['source_found'])
    # Count the total number of CHDs found
    chd_count = sum(1 for softlist_entry in sl_platform_dict.values() for part in softlist_entry['parts'].values() if 'chd_found' in part and part['chd_found'])
    # Count the total number of 'parts' across all entries
    total_parts = sum(len(softlist_entry['parts']) for softlist_entry in sl_platform_dict.values())
    # Count the number of parts that have a 'source_dat' entry
    total_source_dat = sum(1 for softlist_entry in sl_platform_dict.values() for part in softlist_entry['parts'].values() if 'source_dat' in part)
    # Count the number of parts that have a 'source_rom' entry
    total_source_rom = len(list(part['source_rom'] for softlist_entry in sl_platform_dict.values() for part in softlist_entry['parts'].values() if 'source_rom' in part))

    print(f'found:\n  {total_source_ref} / {total_parts} individual discs contain source references')
    print(f'  {total_source_dat} individual discs can be matched to dat sources')
    print(f'  {total_source_found} / {total_softlist_entries} Software List Entries have DAT matches')
    print(f'  {total_source_rom} valid zip files')
    print(f'  {chd_count} chds already exist in the destination directory\n')
    print('\nDAT Groups:')
    # get the stats on source groups
    source_stats = get_source_stats(sl_platform_dict)
    print_source_stats(source_stats,total_source_ref)
    print('\n\nMatched DAT Entry Titles:')


def get_configured_platforms():
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

def platform_select(menu_system: "MenuSystem" = None, show_all: bool = False):
    """
    Select a console platform with optional filtering.
    
    :param menu_system: MenuSystem instance to update current_platform (optional)
    :param show_all: Whether to include all platforms or only configured ones
    :return: Selected platform name (e.g., "cdtv")
    """
    if show_all:
        # Show ALL consoles
        platforms = []
        #platforms = [(name, plat) for name, plat in consoles.items()]
        for name, platform in consoles.items():
            platforms.append((name,platform))
    else:
        # Filtered list of configured platforms
        platforms = get_configured_platforms()
    
    answer = inquirer.list_input(
        message="Select a platform",
        choices=platforms,
        carousel=True
    )
    menu_system.current_platform = answer
    return answer


def hash_map_function(platform):
    '''
    remaps the softlist based on hash changes

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.

    '''
    from modules.mapping import fuzzy_hash_compare,interactive_title_mapping
    fuzzy_matches = fuzzy_hash_compare(softlist_dict[platform], all_dat_dict[platform])
    confirmed = interactive_title_mapping(fuzzy_matches, softlist_dict[platform], all_dat_dict[platform],platform,script_dir, 'fuzzy')
    if confirmed:
        proceed = inquirer.confirm(menu_msgs['fuzzy_commit'], default=False)
        if proceed:
            update_soft_dict(softlist_dict[platform],all_dat_dict[platform],confirmed)


def tosec_map_function(platform):
    """
    Remap entries with TOSEC sources to Redump sources for a given platform.

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.
    """
    from modules.mapping import build_redump_tosec_tuples,map_tosec_entries
    redump_tuples = {}
    if platform in softlist_dict:
        '''
        iterate through the dats and build a redump hash dict for mapping to TOSEC
        this technique can have variations across consoles and may not work for all platforms
        it takes advantage of the fact that for some types of consoles both group's ripping methods
        produce identical hashes for specific scenarios
        '''
        for dat, group in all_dat_dict[platform]['dat_group'].items():
            if group == 'redump':
                redump_tuples.update(build_redump_tosec_tuples(all_dat_dict[platform]['hashes'][dat],platform))

        if redump_tuples:
            print('have redump tuples to check')
            tosec_matches = map_tosec_entries(softlist_dict[platform],all_dat_dict[platform],redump_tuples)
            if tosec_matches:
                print('\nTOSEC to Redump matches have been found, note the entries listed above are multi-disc entries where there are')
                print('both redump and tosec matches the next step will rewrite the softlist xml to update for redump sources.')
                print('However for these mixed titles the tosec sources references will be deleted. please take note and manually restore these lines.\n')
                proceed = inquirer.confirm(menu_msgs['tosec_commit'], default=False)
                if proceed:
                    # update softlist sources based on tosec/redump matches
                    update_soft_dict(softlist_dict[platform],all_dat_dict[platform],tosec_matches)
                else:
                    print('Not committing changes, return to menu\n')
    else:
        print(f'No {platform} mapping, please run the auto-mapping function first')
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['tosec_remap']:
        mapping_stage['tosec_remap'].append(platform)


def entry_create_function(platform):
    print('new entry placeholder')
    proceed = inquirer.confirm(menu_msgs['new'], default=False)

def setup_platform_dicts(platform):
    '''
    Sets up the dictionaries for the given platform.

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    None: This function does not return any value. It modifies the data in place.
    '''
    from modules.dat import build_dat_dict, remove_dupe_dat_entries, build_sl_dict, convert_xml, shift_sibling_comments
    # process each DAT to build a list of fingerprints
    print('processing '+platform+' DAT Files')
    if platform not in all_dat_dict:
        all_dat_dict.update({platform:{}})
    dat_platform_dict = all_dat_dict[platform]
    for dats in settings[platform].values():
        for dat in dats:
            build_dat_dict(dat,dat_platform_dict)
    # hashes may be identical across DAT groups, prioritise redump hashes and delete dupes in others
    remove_dupe_dat_entries(all_dat_dict[platform])

    # process the software list into a dict, creating hash based fingerprints from comments
    print('processing '+platform+' software list')
    process_comments = True
    softlist_xml = settings['sl_dir']+os.sep+platform+'.xml'
    shift_sibling_comments(softlist_xml)
    raw_sl_dict = convert_xml(softlist_xml,process_comments)
    softdict = dict(raw_sl_dict['softwarelist'])
    if platform not in softlist_dict:
        softlist_dict.update({platform:{}})
    # build the dict object with relevant softlist data for this script, return bool whether crc source keys are needed
    build_sl_dict(softdict['software'], softlist_dict[platform],platform)

def update_file_match_function(platform):
    find_dat_matches(platform,softlist_dict[platform],all_dat_dict[platform])

def automap_function(platform):
    setup_platform_dicts(platform)
    print('\nplatform dicts completed\n')
    debug = inquirer.confirm('Write Debug Data?', default=False)
    # iterate through each fingerprint in the software list and search for matching hashes
    find_dat_matches(platform,softlist_dict[platform],all_dat_dict[platform])
    if debug:
        from modules.utils import write_data
        write_data(softlist_dict,'soft_dict_stage1')
        write_data(all_dat_dict,'dat_dict_stage1')
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['source_map']:
        mapping_stage['source_map'].append(platform)
    print('Subsequent mapping stages will use more heuristics to identify or remap ROM sources for titles')
    print('TOSEC to Redump looks at individual hashes which are consistent across dumping groups for some platforms')
    print('Detecting Redump bad dumps looks for hash changes where only one or two track hashes have been updated')
    print('Changes should be reviewed closely for these stages')
    print('These steps can be skipped')
    map_stage_increment = inquirer.confirm('Begin Next Mapping Stage?', default=False)
    if map_stage_increment:
        return 'map_stage_two' # go to the second mapping stage menu
    else:
        return 'main_menu'

def process_interactive_matches(interactive_matches,platform,match_type):
    from modules.mapping import interactive_title_mapping
    print('Some matches require user review\n')
    confirmed_interactive = interactive_title_mapping(interactive_matches,softlist_dict[platform],all_dat_dict[platform],platform,script_dir,match_type)
    if confirmed_interactive:
        proceed = inquirer.confirm(menu_msgs['tosec_commit'], default=False)
        if proceed:
            update_soft_dict(softlist_dict[platform],all_dat_dict[platform],confirmed_interactive)

def automated_mapping(platform,lookup_type):
    from modules.mapping import name_serial_auto_map
    name_serial_matches, redump_interactive_matches = name_serial_auto_map(platform, softlist_dict[platform],all_dat_dict[platform],script_dir,lookup_type)
    if name_serial_matches:
        print('\nThe above Name / Serial matches have been found, do you want to commit the new hashes the softlist?')
        proceed = inquirer.confirm(menu_msgs['tosec_commit'], default=False)
        if proceed:
            # update softlist sources based on tosec/redump matches
            update_soft_dict(softlist_dict[platform],all_dat_dict[platform],name_serial_matches)

    if redump_interactive_matches:
        match_type = 'redump_serial'
        process_interactive_matches(redump_interactive_matches,platform,match_type)
    else:
        print('No matches to commit, return to menu\n')
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['name_serial_auto_map']:
        mapping_stage['name_serial_auto_map'].append(platform)


def serial_map_function(platform):
    automated_mapping(platform,'serial')

def name_serial_automap_function(platform):
    automated_mapping(platform,'name_serial')

def interactive_map_function(platform):
    from modules.mapping import name_serial_auto_map
    name_serial_matches, interactive_matches = name_serial_auto_map(platform, softlist_dict[platform],all_dat_dict[platform],script_dir,lookup_type='name')
    if interactive_matches:
        match_type = 'redump_name'
        process_interactive_matches(interactive_matches,platform,match_type)
    else:
        print('No matches to commit, return to menu\n')


def chd_builder(platform):
    '''
    checks each soft list entry for a matched source rom and builds chds using those ROM
    sources.  CHD hash is added to the soft-dict.  If a CHD already exists in the build
    directory it's skipped, but there is a flag to enable grabbing hashes for built CDs.
    '''
    from modules.chd import create_chd_from_zip, chdman_info
    from modules.dat import update_softlist_chd_sha1s
    if platform == 'psx':
        from modules.libcrypt import libcrypt_titles
    new_hashes = False
    built_sources = {}
    discontinue = False
    for soft, soft_data in softlist_dict[platform].items():
        if discontinue:
            break
        for disc_data in soft_data['parts'].values():
            if 'chd_found' in disc_data and not get_sha_from_existing_chd:
                if disc_data['chd_found']:
                    continue
            if 'source_rom' in disc_data:
                # create platform directory and softlist title directory
                if not os.path.exists(os.path.join(settings['chd'],platform)):
                    os.mkdir(os.path.join(settings['chd'],platform))
                chd_dir = os.path.join(settings['chd'],platform,soft)
                if not os.path.exists(chd_dir):
                    os.mkdir(chd_dir)
                chd_name = disc_data['chd_filename']+'.chd'
                chd_path = os.path.join(chd_dir,chd_name)
                if not os.path.isfile(chd_path):
                    print('\nbuilding chd for '+soft_data['description']+':')
                    print('            CHD: '+chd_name)
                    print('     Source Zip: '+os.path.basename(disc_data['source_rom']))

                    if disc_data['source_rom'] not in built_sources:
                        '''
                        check the dat group here for any special handling that will be needed
                        known things to handle:
                          - Redump and cdi - need to rewrite the cue file (todo)
                          - Redump & psx - libcrypt support
                          - No-Intro - Cue file data doesn't match filenames (partial support)
                        '''
                        dat_group = get_dat_group(disc_data['source_dat'])
                        special_logic = {'dat_group':dat_group}
                        if dat_group in ['no-intro','other']:
                            game_entry = all_dat_dict[platform]['hashes'][disc_data['source_dat']][disc_data['source_sha']]
                            special_logic.update(game_entry)
                        elif dat_group == 'redump':
                            libcrypt = False
                            if platform == 'psx' and 'serial' in soft_data:
                                for serial in soft_data['serial']:
                                    if serial in libcrypt_titles:
                                        libcrypt = True
                                if libcrypt:
                                    print('This Title uses Libcrypt')
                                    special_logic.update({'redump_url':disc_data['redump_url']})
                                    if sys.platform != 'win32':
                                        print('libcrypt handling requires additional windows binaries, not supported on this platform')
                                        continue
                            elif platform == 'cdi':
                                # placeholder
                                pass
                        else:
                            special_logic = None
                        try:
                            error = create_chd_from_zip(disc_data['source_rom'],chd_path,settings,special_logic)
                            if not error:
                                built_sources.update({disc_data['source_rom']:chd_path})
                            else:
                                print(error)
                                continue
                        except Exception:
                            print('CHD Creation Failed')
                            print(traceback.format_exc())
                            if os.path.isfile(chd_path):
                                try:
                                    os.remove(chd_path)
                                except:
                                    print('Failed to delete partial file:\n'+chd_path)
                                    print('Please ensure this is deleted to avoid corrupted files/hashes')
                            continue_build = inquirer.confirm('Do you want to continue?', default=False)
                            if continue_build:
                                continue
                            else:
                                discontinue = True
                                break
                    # if the exact same chd was built earlier then just symlink to it
                    # these symlinks aren't cross platform, will revisit this
                    elif disc_data['source_rom'] in built_sources:
                        os.symlink(built_sources[disc_data['source_rom']],chd_path)
                        built_sources.update({disc_data['source_rom']:chd_path})
                elif not get_sha_from_existing_chd:
                    continue
                    #print('chd for '+soft_data['description']+' already exists, skipping')
                # if the chd was created as a part of this run or if the flag to trust existing chds is enabled check the sha1 against the softlist
                if os.path.isfile(chd_path):
                    if disc_data['source_rom'] in built_sources or get_sha_from_existing_chd:
                        new_chd_hash = chdman_info(chd_path)
                        if 'chd_sha1' in disc_data:
                            current_chd_hash = disc_data['chd_sha1']
                        else:
                            current_chd_hash = ''
                            disc_data['chd_sha1'] = current_chd_hash
                        if new_chd_hash == current_chd_hash:
                            print('\nHash matches softlist: '+chd_name+'\n')
                        elif new_chd_hash is not None:
                            new_hashes = True
                            print('\nUpdated hash for softlist: '+chd_name+'\n')
                            disc_data.update({'new_sha1':new_chd_hash})
                        else:
                            print('error producing CHD, please try again')
                    else:
                        continue

    if new_hashes:
        write_new_hashes = inquirer.confirm('Update the Software List with new CHD Hashes?', default=False)
        if write_new_hashes:
            update_softlist_chd_sha1s(settings['sl_dir']+os.sep+platform+'.xml',softlist_dict[platform])



def chd_build_function(platform=None):
    from modules.chd import is_greater_than_0_176, chdman_info
    if not is_greater_than_0_176(chdman_info()):
        print('Outdated Chdman, please upgrade to a recent version')
        return None
    if not platform:
        # get configured platforms and map selected from the returned key
        platform = platform_select('chd')['platforms']
    if platform not in softlist_dict:
        print('No mapping has been run for this platform yet, please go back and run a mapping function\n')
        return None
    build = inquirer.confirm('Begin Creating CHDs?', default=False)
    if build:
        chd_builder(platform)

def save_function():
    confirm_message = menu_msgs['save']
    save = inquirer.confirm(confirm_message, default=False)
    if save:
        save_data(user_answers,'answers',script_dir)
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
    '''
    removes DATs from the platform settings

    Parameters:
    platform (str): The platform for which the mapping is being performed.

    Returns:
    str: The key to the menu to return to.
    '''
    if platform not in settings:
        print(f'{platform} not configured')
        return 'settings_menu'
    datlist = []
    for dat in settings[platform].keys():
        print('deleting '+settings['datroot']+'\nfrom '+dat)
        datlist.append(dat.replace(settings['datroot'], ''))
    datlist.append('back')
    answer = list_menu('dat', datlist, menu_msgs['dat_remove'])
    if answer['dat'] == 'back':
        return 'settings_menu'
    else:
        dat_path = settings['datroot']+answer['dat']
        print(dat_path)
        settings[platform].pop(dat_path)

def list_soft_entries(platform,group=None):
    match_type = 'Unmatched'
    if group is not None:
        match_type = group
    print(f'\n\n  {match_type} Sources for this platform:')
    for soft, soft_entry in softlist_dict[platform].items():
        matched_title = False
        for part in soft_entry['parts'].values():
            if 'source_group' in part and part['source_group'] == match_type:
                matched_title = True
            elif 'source_dat' not in part and match_type == 'Unmatched':
                matched_title = True
        if matched_title:
            print(f"    {soft}: {soft_entry['description']}")
    print('\n\n')

def unknown_list_function(platform):
    list_soft_entries(platform)

def tosec_list_function(platform):
    list_soft_entries(platform,'TOSEC')

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
    from modules.dat import get_dat_name
    #print('dat dir is '+dat_directory)
    #rom_dir = settings['romroot']+re.sub(settings['datroot'],'',dat_directory)
    rom_dir = settings['romroot']+dat_directory.replace(settings['datroot'], '')
    #print('rom dir is '+rom_dir)
    if len(dat_files) == 1:
        if os.path.isdir(rom_dir):
            return {dat_directory+os.sep+dat_files[0] : rom_dir}
        else:
            print('Unable to locate '+rom_dir+' directory in ROMroot')
            return {}
    else:
        dat_rom_dict = {}
        for dat in dat_files:
            if not dat.endswith('.xml'):
                dat_path = dat_directory+os.sep+dat
                # rom subfolder is based on dat name, get name
                #print('checking dat '+dat)
                name = get_dat_name(dat_path)
                full_rom_dir = rom_dir+os.sep+name
                if not os.path.isdir(full_rom_dir):
                    print('Unable to locate "'+name+'" directory in platform ROM folder')
                    continue
                dat_rom_dict.update({dat_path:full_rom_dir})
        return dat_rom_dict

def map_dats_to_romdirs(dat_directory):
    dat_files = [f for f in os.listdir(dat_directory) if f.endswith('.dat') or f.endswith('.xml')]
    #print(f"DAT files in {dat_directory}: {dat_files}")
    # if using romvault map the ROM directores for the DATs automatically
    if settings['romvault']:
        datrom_dirmap = romvault_dat_to_romfolder(dat_directory, dat_files)
    else:
        datrom_dirmap = {}
        for dat in dat_files:
            if not dat.endswith('.xml'):
                dat_path = dat_directory+os.sep+dat
                print('Select ROM Directory for DAT:\n'+dat+'\n')
                rom_directory = select_directory('rom',settings['romroot'])
                datrom_dirmap.update({dat_path:rom_directory})
    return datrom_dirmap

def update_dats():
    print('Updating DAT Folders')
    for platform in consoles.values():
        if platform in settings:
            for folder in settings[platform].keys():
                datrom_dirmap = map_dats_to_romdirs(folder)
                settings[platform][folder] = datrom_dirmap

def platform_dat_rom_function(menu_system: "MenuSystem"):
    """
    Configures DAT and ROM directories for a specific platform.
    """
    print("running platform_select in platform_dat_rom_function")
    platform = platform_select(menu_system, show_all=True)
    print(f"selected platform is {platform}")
    # Check if the platform is already configured
    if platform not in settings:
        settings.update({platform : {}})
    # get the dat dir first
    if 'datroot' not in settings:
        single_dir_function('datroot','Root DAT Directory')
    if 'romroot' not in settings:
        single_dir_function('romroot','Root ROM Directory')
    dat_directory = select_directory('dat',settings['datroot'])
    datrom_dirmap = map_dats_to_romdirs(dat_directory)
    settings[platform][dat_directory] = datrom_dirmap

def get_os_dirs(path):
    """
    Returns a list of directories in the given path
    """
    directories = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    directories.sort()
    directories.insert(0,'Parent Directory')
    directories.append('Select the current directory')
    return directories

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
        message = message = "Select a directory - current: ["+current_path+"]"
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

class MainMenu(BaseMenu):
    def __init__(self):
        super().__init__("main_menu")
        self.options = [
            MenuItem(
                text = "a. Mapping Functions",
                target = "map_menu",
                requires_platform = False
            ),
            MenuItem(
                text = "b. Create CHDs from ROMs",
                action_func = chd_build_function,
            ),
            MenuItem(
                text = "c. Settings",
                target = "settings_menu",
                requires_platform = False
            ),
            MenuItem(
                text = "d. Save Settings",
                action_func = save_function,
                requires_platform = False
            ),
            MenuItem(
                text = "e. Exit",
                target="Exit",
                requires_platform = False
            )
        ]


class SelectPlatformMenu(BaseMenu):
    def __init__(self):
        super().__init__("select_platform_menu")
        
        # Helper to create action functions that return the previous menu name
        def make_select_action(platform: str):
            """Sets platform and returns prior menu's name"""
            print("in make_select platform function")
            def select(menu_system: MenuSystem) -> str:
                print(f"Setting platform to: {platform}")
                menu_system.current_platform = platform  # Set platform here
                # Return to the previous menu (stored in stack)
                if menu_system.stack:
                    return menu_system.stack[-1]["menu_name"]  # Prior menu before selection
                else:
                    return "main_menu"  # Default fallback
            
            return select

        # Generate options for each configured platform
        self.options = []
        for name, platform in get_configured_platforms():  # Use your existing logic to filter platforms
            self.options.append(
                MenuItem(
                    text=f"{name} ({platform})",
                    action_func=make_select_action(platform),
                    requires_platform=False,
                    target=None  # No default fallback needed due to return value
                )
            )


class SettingsMenu(BaseMenu):
    def __init__(self):
        super().__init__("settings_menu")
        self.options = [
            MenuItem(
                text="a. MAME Software List XML Directory",
                action_func=slist_dir_function,
                requires_platform = False
            ),
            MenuItem(
                text="b. Configure Root DAT/ROM Directories (ROMvault)",
                action_func=root_dirs_function,
                requires_platform = False
            ),
            MenuItem(
                text="c. Configure DAT/ROM Platform Directories",
                target="dat_menu",
                requires_platform = False
            ),
            MenuItem(
                text="d. Destination folder for CHDs",
                action_func=chd_dir_function,
                requires_platform = False
            ),
            MenuItem(
                text="e. Back",
                target="main_menu",
                requires_platform = False
            )
        ]

class MapMenu(BaseMenu):
    def __init__(self):
        super().__init__("map_menu")
        # Populate options using MenuItem objects
        self.options = [
            MenuItem(
                text="a. Automatically map based on source rom info", 
                action_func = automap_function,
            ),
            MenuItem(
                text="b. List missing matched ROM Files",
                action_func = list_missing_function,
            ),
            MenuItem(
                text="c. List TOSEC sources",
                action_func = tosec_list_function,
            ),
            MenuItem(
                text="d. List unknown sources",
                action_func = unknown_list_function,
            ),
            MenuItem(
                text="e. Update ROM matches",
                action_func = update_file_match_function,
            ),
            MenuItem(
                text = "b. Mapping Stage 2", 
                target = "map_stage_two",
            ),
            MenuItem(
                text = "g. Change Platform",
                action_func = platform_select,
                requires_platform = False
            ),
            MenuItem(
                text="[Back to Main Menu]",
                target="main_menu",
                requires_platform = False
            )
            ]

class MapStageTwo(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_two")
        self.options = [
            MenuItem(
                text="a. Redump URL Based Mapping",
                action_func = url_map_function,
            ),
            MenuItem(
                text="b. Remap TOSEC sources to Redump",
                action_func = tosec_map_function,
            ),
            MenuItem(
                text="c. Automated Redump re-map based on disc serial & name",
                action_func = name_serial_auto_map,
            ),
            MenuItem(
                text="d. List missing matched ROM Files",
                action_func = list_missing_function,
            ),
            MenuItem(
                text="e. List TOSEC sources",
                action_func=tosec_list_function,
            ),
            MenuItem(
                text="f. List unknown sources",
                action_func=unknown_list_function,
            ),
            MenuItem(
                text="g. Update Sofltist XML",
                action_func=sl_update_function,
            ),
            MenuItem(
                text="h. Update ROM matches",
                action_func = update_file_match_function,
            ),
            MenuItem(
                text="i. Interactive Mapping Functions",
                target="map_stage_three",
            ),
            MenuItem(
                text="j. Build CHDs",
                action_func = chd_build_function,
            ),
            MenuItem(
                text="k. Back",
                target="map_menu",
                requires_platform = False
            )
        ]

class MapStageThree(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_three")
        self.options = [
            MenuItem(
                text="a. Fuzzy Matches - Remap bad/alternate Dumps",
                action_func=hash_map_function,
            ),
            MenuItem(
                text="b. Serial Only Mapping",
                action_func=serial_map_function,
            ),
            MenuItem(
                text="c. Interactive Name Based Mapping",
                action_func=interactive_map_function,
            ),
            MenuItem(
                text="d. Update Sofltist XML",
                action_func=sl_update_function,
            ),
            MenuItem(
                text="e. Build CHDs",
                action_func=chd_build_function,
            ),
            MenuItem(
                text="f. Generate Missing DAT",
                action_func=dat_build_function,
            ),
            MenuItem(
                text="g. Back",
                target="map_stage_two",
                requires_platform = False
            )
        ]

class DatMenu(BaseMenu):
    def __init__(self):
        super().__init__("dat_menu")
        self.options = [
            MenuItem(
                text = "a. Add Directories",
                action_func = platform_dat_rom_function,
                requires_platform = False
            ),
            MenuItem(
                text = "b. Remove DATs",
                action_func = del_dats_function,
            ),
            MenuItem(
                text = "c. Back",
                target = "settings_menu",
                requires_platform = False
            )
        ]


if __name__ == '__main__':
    script_dir = get_script_path()

    if len(settings) == 0:
        # walk through all the mandatory settings one by one on the first run
        first_run()
        save_data(settings,'settings',script_dir)
    else:
        update_dats()
        save_data(settings,'settings',script_dir)

    system = MenuSystem()
    
    # Register all menus
    system.register(MainMenu())
    system.register(MapMenu())
    system.register(SettingsMenu())
    system.register(MapStageTwo())
    system.register(MapStageThree())
    system.register(SelectPlatformMenu())
    system.register(DatMenu())

    # Initialize the main menu
    system.navigate_to("main_menu")  # Start at root menu

    while True:
        current_menu = system.current_menu
        if not current_menu:
            print("Invalid menu state! Name:", system.current_menu)
            break

        # Display the current menu
        option_strings = [item.text for item in current_menu.options]
        selected_item = inquirer.list_input(
            current_menu.message,
            choices=option_strings,
            default=0,
            carousel = True
        )
        
        # Find which MenuItem corresponds to this text
        chosen_item = None
        for item in current_menu.options:
            if item.text == selected_item:
                chosen_item = item
                break
        
        if not chosen_item:
            print("Selection invalid")
            continue

        next_target_name = chosen_item.execute(system)

        if next_target_name == "Exit":
            break
        else:
            system.navigate_to(next_target_name)  # Update current menu