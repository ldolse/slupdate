#!/usr/bin/env python3

""" slupdate.py: Interactively Update MAME Optical Media based Software Lists
against[Redump](http://redump.org/) & TOSEC dats.

https://github.com/ldolse/slupdate
"""
import os
import sys
import inquirer
import traceback
from consoles import PlatformManager, Platform
from typing import List, Tuple
from utils.utils import select_directory, reconfigure_settings, get_script_path, list_menu
from menus.menus import MenuItem, MenuSystem, BaseMenu
from modules.chd import is_greater_than_0_176, chdman_info, find_rom_zips, create_chd_from_zip, chdman_info
from modules.mapping import build_redump_tosec_tuples, fuzzy_hash_compare, get_missing_zips, get_unmatched_roms, get_source_stats, name_serial_auto_map
from modules.mapping import redump_url_mapping, print_source_stats,interactive_title_mapping,map_tosec_entries, update_soft_dict
from modules.dat import create_dat
from modules.software_list import update_softlist_chd_sha1s

__version__ = '.2'
script_dir = get_script_path()

# Require at least Python 3.7
assert sys.version_info >= (3, 7)

settings = {}

# disabled by default, allows the script to populate chd sha1s on subsequent runs
# only enable if CHD destination folder ONLY contains chds created by this script
get_sha_from_existing_chd = False

mapping_stage = { 'source_map' : [],
        'name_serial_auto_map' : [],
 'name_serial_interactive_map' : [],
                 'tosec_remap' : [],
                  'manual_map' : []
                  }


def softlist_update(platform: Platform) -> None:
    platform.update_softlist()

def url_map_function(platform: Platform) -> None:
    '''
    remaps the Software List based on redump source urls
    '''
    url_remaps = redump_url_mapping(platform, script_dir)
    if url_remaps:
        url_commit_msg = "Updates based on Redump source URLs successful. Proceed to update the Softlist data?"
        proceed = inquirer.confirm(url_commit_msg, default=False)
        if proceed:
            update_soft_dict(platform,url_remaps)

def list_missing_function(platform: Platform) -> None:
    '''
    lists the missing ROM files for matched entries
    '''
    get_missing_zips(platform.software_list_data,platform.dat_hashes)


def dat_build_function(platform: Platform) -> None:
    '''
    creates a DAT file from the unmatched ROMs
    '''
    rom_dict = get_unmatched_roms(platform.software_list_data)
    create_dat(rom_dict,platform.key)


def find_dat_matches(platform: Platform) -> None:
    '''
    - Finds the matching entries in the DAT files for the given platform.

    - matches softlist source hash fingerprints to the dat fingerprint

    - updates the softlist dictionary to point to the dat for that source hash

    Parameters:
    platform (str): The platform for which the mapping is being performed.
    sl_platform_dict (dict): The software list dictionary for the platform.
    dathash_platform_dict (dict): The dat hash dictionary for the platform.

    '''
    sl_platform_dict = platform.software_list_data
    dathash_platform_dict = platform.dat_hashes

    matched_titles = []
    for datfile, dathashdict in dathash_platform_dict['hashes'].items():
        dat_group = platform.dat_hashes['dat_group'][datfile]
        for sl_title, sl_data in sl_platform_dict.items():
            dat_name_list = {}
            chds_exist = False
            for disc, disc_data in sl_data['parts'].items():
                if 'source_rom' in disc_data:
                    continue # skip when a source ROM was identified from an earlier DAT
                if 'chd_filename' in disc_data:
                    chd_path = platform.chd_path+os.sep+sl_title+os.sep+disc_data['chd_filename']+'.chd'
                    #chd_path = os.path.join(platform.chd_path,sl_title,disc_data['chd_filename']+'.chd')
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
            dat_rom_map = platform.dat_rom_dict
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


def hash_map_function(platform: Platform) -> None:
    '''
    remaps the softlist based on hash changes (e.g. redump bad dumps)
    '''
    fuzzy_matches = fuzzy_hash_compare(platform.software_list_data,platform.dat_hashes)
    confirmed = interactive_title_mapping(fuzzy_matches, platform.software_list_data,platform.dat_hashes,platform.key,script_dir, 'fuzzy')
    if confirmed:
        fuzzy_commit_msg = "Do you want to commit the new hashes the softlist?"
        proceed = inquirer.confirm(fuzzy_commit_msg, default=False)
        if proceed:
            update_soft_dict(platform.key,confirmed)


def tosec_map_function(platform: Platform) -> None:
    """
    Remap entries with TOSEC sources to Redump sources for a given platform.
    """
    redump_tuples = {}
    if platform.software_list_data:
        '''
        iterate through the dats and build a redump hash dict for mapping to TOSEC
        this technique can have variations across consoles and may not work for all platforms
        it takes advantage of the fact that for some types of consoles both group's ripping methods
        produce identical hashes for specific scenarios
        '''
        for dat, group in platform.dat_hashes['dat_group'].items():
            if group == 'redump':
                redump_tuples.update(build_redump_tosec_tuples(platform.dat_hashes['hashes'][dat],platform))

        if redump_tuples:
            print('have redump tuples to check')
            tosec_matches = map_tosec_entries(platform.software_list_data,platform.dat_hashes,redump_tuples)
            if tosec_matches:
                print('\nTOSEC to Redump matches have been found, note the entries listed above are multi-disc entries where there are')
                print('both redump and tosec matches the next step will rewrite the softlist xml to update for redump sources.')
                print('However for these mixed titles the tosec sources references will be deleted. please take note and manually restore these lines.\n')
                tosec_commit_msg = "Do you want to write the redump hashes to the softlist, overwriting TOSEC references?"
                proceed = inquirer.confirm(tosec_commit_msg, default=False)
                if proceed:
                    # update softlist sources based on tosec/redump matches
                    update_soft_dict(platform.key,tosec_matches)
                else:
                    print('Not committing changes, return to menu\n')
    else:
        print(f'No {platform} mapping, please run the auto-mapping function first')
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['tosec_remap']:
        mapping_stage['tosec_remap'].append(platform.key)


def entry_create_function(platform: Platform) -> None:
    print('new entry placeholder')
    pass



def update_file_match_function(platform: Platform) -> None:
    find_dat_matches(platform)

def automap_function(platform: Platform) -> None:
    platform.process_data()
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['source_map']:
        mapping_stage['source_map'].append(platform.key)
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

def process_interactive_matches(interactive_matches,platform: Platform,match_type):
    print('Some matches require user review\n')
    confirmed_interactive = interactive_title_mapping(interactive_matches,platform.software_list_data,platform.dat_hashes,platform.key,script_dir,match_type)
    if confirmed_interactive:
        message = "Do you want to commit the new hashes the softlist?"
        proceed = inquirer.confirm(message, default=False)
        if proceed:
            update_soft_dict(platform.key,confirmed_interactive)

def automated_mapping(platform: Platform,lookup_type) -> None:
    name_serial_matches, redump_interactive_matches = name_serial_auto_map(platform.key,platform.software_list_data,platform.dat_hashes,script_dir,lookup_type)
    if name_serial_matches:
        print('\nThe above Name / Serial matches have been found, do you want to commit the new hashes the softlist?')
        message = "Do you want to commit the new hashes the softlist?"
        proceed = inquirer.confirm(message, default=False)
        if proceed:
            # update softlist sources based on tosec/redump matches
            update_soft_dict(platform,name_serial_matches)

    if redump_interactive_matches:
        match_type = 'redump_serial'
        process_interactive_matches(redump_interactive_matches,platform,match_type)
    else:
        print('No matches to commit, return to menu\n')
    # flag that this stage is completed for this platform
    if platform not in mapping_stage['name_serial_auto_map']:
        mapping_stage['name_serial_auto_map'].append(platform.key)


def serial_map_function(platform: Platform) -> None:
    automated_mapping(platform,'serial')

def name_serial_automap_function(platform: Platform) -> None:
    automated_mapping(platform,'name_serial')

def interactive_map_function(platform: Platform) -> None:
    name_serial_matches, interactive_matches = name_serial_auto_map(platform,script_dir,lookup_type='name')
    if interactive_matches:
        match_type = 'redump_name'
        process_interactive_matches(interactive_matches,platform,match_type)
    else:
        print('No matches to commit, return to menu\n')


def chd_builder(platform: Platform) -> None:
    '''
    checks each soft list entry for a matched source rom and builds chds using those ROM
    sources.  CHD hash is added to the soft-dict.  If a CHD already exists in the build
    directory it's skipped, but there is a flag to enable grabbing hashes for built CDs.
    '''
    if platform == 'psx':
        from consoles.psx.libcrypt import libcrypt_titles
    new_hashes = False
    built_sources = {}
    discontinue = False
    for soft, soft_data in platform.software_list_data.items():
        if discontinue:
            break
        for disc_data in soft_data['parts'].values():
            if 'chd_found' in disc_data and not get_sha_from_existing_chd:
                if disc_data['chd_found']:
                    continue
            if 'source_rom' in disc_data:
                # create platform directory and softlist title directory
                if not os.path.exists(platform.chd_path):
                    os.mkdir(os.path.join(platform.chd_path))
                chd_dir = os.path.join(platform.chd_path,soft)
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
                        dat_group = platform.dat_hashes['dat_group'][disc_data['source_dat']]
                        special_logic = {'dat_group':dat_group}
                        if dat_group in ['no-intro','other']:
                            game_entry = platform.dat_hashes['hashes'][disc_data['source_dat']][disc_data['source_sha']]
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
            update_softlist_chd_sha1s(platform.softlist_xml_path,platform.software_list_data)



def chd_build_function(platform: Platform) -> None:
    if not is_greater_than_0_176(chdman_info()):
        print('Outdated Chdman, please upgrade to a recent version')
        return None
    if not platform.software_list_data:
        print('No mapping has been run for this platform yet, please go back and run a mapping function\n')
        return None
    build = inquirer.confirm('Begin Creating CHDs?', default=False)
    if build:
        chd_builder(platform)


def del_datpath_function(platform: Platform) -> None:
    '''
    removes DATs from the platform settings
    '''
    datlist = list(platform.dat_directories.keys())
    datlist.append('back')
    message = 'Select a DAT to remove from the list'
    answer = list_menu('dat', datlist, message)
    if answer['dat'] == 'back':
        return 'settings_menu'
    else:
        platform.dat_directories.pop(answer['dat'])

def list_soft_entries(platform: Platform, group=None):
    match_type = 'Unmatched'
    if group is not None:
        match_type = group
    print(f'\n\n  {match_type} Sources for this platform:')
    for soft, soft_entry in platform.software_list_data.items():
        matched_title = False
        for part in soft_entry['parts'].values():
            if 'source_group' in part and part['source_group'] == match_type:
                matched_title = True
            elif 'source_dat' not in part and match_type == 'Unmatched':
                matched_title = True
        if matched_title:
            print(f"    {soft}: {soft_entry['description']}")
    print('\n\n')

def unknown_list_function(platform: Platform) -> None:
    list_soft_entries(platform)

def tosec_list_function(platform: Platform) -> None:
    list_soft_entries(platform,'TOSEC')

def platform_add_dat_function(platform: Platform, platform_manager: PlatformManager):
    """Select and Configure DAT and ROM directories for a platform."""
    dat_directory_path = select_directory("DAT", start_dir=platform_manager.datroot)

    # Process DAT files in directory
    platform_manager.add_platform_dat_directory(
        platform.key,
        dat_directory_path
    )

def reset_platform(platform: Platform) -> None:
    """Reset the current platform to its default state."""
    platform.reset()
    print(f"Platform {platform.key} has been reset to its default state.")

def load_or_create_platform_manager():
    pm, loaded = PlatformManager.load()

    if not loaded:
        print("Initializing new settings...")
        pm.initialize_settings()  # Configures datroot/romroot etc.
        configure_initial_platform(pm)

    return pm

def configure_initial_platform(platform_manager: PlatformManager):
    """Ensure at least one platform has a DAT directory and ROM folder."""
    print("\nConfiguring initial platform with DAT/ROM directories.")

    selected_platform = platform_manager.select_platform(show_all=True)
    if selected_platform:
        platform_add_dat_function(selected_platform, platform_manager)

class MainMenu(BaseMenu):
    def __init__(self):
        super().__init__("main_menu")
        self.message = "Main Menu"
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
                action_func = platform_manager.save,
                requires_platform = False
            ),
            MenuItem(
                text = "e. Exit",
                target="Exit",
                requires_platform = False
            )
        ]


class SettingsMenu(BaseMenu):
    def __init__(self):
        super().__init__("settings_menu")
        self.message = "Settings Menu"
        self.options = [
            MenuItem(
                text="a. Configure DAT/ROM Platform Directories",
                target="dat_menu",
                requires_platform = True
            ),
            MenuItem(
                text = "b. Change Platform",
                action_func = self._platform_select,
                requires_platform = False
            ),
            MenuItem(
                text="c. Reconfigure Global Directories",
                action_func=self._handle_reconfigure_settings,
                requires_platform = False
            ),
            MenuItem(
                text="d. Destination folder for CHDs",
                #action_func=chd_dir_function,
                requires_platform = False
            ),
            MenuItem(
                text="e. Reset Current Platform",
                action_func=reset_platform,
            ),
            MenuItem(
                text="[Back to Main Menu]",
                is_back=True,
                requires_platform = False
            )
        ]


    def _get_settings_list(self) -> List[Tuple[str, str, str]]:
        """Define the list of configurable settings for this menu with input type."""
        return [
            ('datroot', 'DAT Root Directory', 'directory'),
            ('romroot', 'ROM Root Directory', 'directory'),
            ('mame_hash_dir', 'MAME Software List (hash) Directory', 'directory'),
            ('romvault', 'Enable RomVault', 'boolean')  # Add boolean flag
        ]

    def _handle_reconfigure_settings(self, platform_manager: "PlatformManager"):
        """Handler for re-configuring global settings in this menu."""
        settings_list = self._get_settings_list()
        reconfigure_settings(instance=platform_manager, settings_list=settings_list)

    def _platform_select(self, platform_manager: PlatformManager) -> None:
        """Select a platform from the list of available platforms."""
        selected_platform = platform_manager.select_platform(show_all=True)
        if selected_platform:
            print(f"Selected platform: {selected_platform.name}")
        else:
            print("No platform selected.")

class MapMenu(BaseMenu):
    def __init__(self):
        super().__init__("map_menu")
        self.message = "Process software lists and dat files, mapping source file references"
        self.options = [
            MenuItem(
                text = "a. Automatically map based on source rom info",
                action_func = automap_function
            ),
            MenuItem(
                text = "b. List missing matched ROM Files",
                action_func = list_missing_function
            ),
            MenuItem(
                text = "c. List TOSEC sources",
                action_func = tosec_list_function
            ),
            MenuItem(
                text = "d. List unknown sources",
                action_func = unknown_list_function
            ),
            MenuItem(
                text = "e. Update ROM matches",
                action_func = update_file_match_function
            ),
            MenuItem(
                text = "f. Mapping Stage 2",
                target = "map_stage_two"
            ),
            MenuItem(
                text = "[Back to Main Menu]",
                is_back = True,
                requires_platform = False
            )
            ]

class MapStageTwo(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_two")
        self.message = "Use other reference datapoints to remap the software list & DAT files"
        self.options = [
            MenuItem(
                text = "a. Redump URL Based Mapping",
                action_func = url_map_function,
            ),
            MenuItem(
                text = "b. Remap TOSEC sources to Redump",
                action_func = tosec_map_function,
            ),
            MenuItem(
                text = "c. Automated Redump re-map based on disc serial & name",
                action_func = name_serial_automap_function,
            ),
            MenuItem(
                text = "d. List missing matched ROM Files",
                action_func = list_missing_function,
            ),
            MenuItem(
                text = "e. List TOSEC sources",
                action_func = tosec_list_function,
            ),
            MenuItem(
                text = "f. List unknown sources",
                action_func = unknown_list_function,
            ),
            MenuItem(
                text = "g. Update Software list XML",
                action_func = softlist_update
            ),
            MenuItem(
                text = "h. Update ROM matches",
                action_func = update_file_match_function,
            ),
            MenuItem(
                text = "i. Interactive Mapping Functions",
                target = "map_stage_three",
            ),
            MenuItem(
                text = "j. Build CHDs",
                action_func = chd_build_function,
            ),
            MenuItem(
                text = "Back",
                is_back = True,
                requires_platform = False
            )
        ]


class MapStageThree(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_three")
        self.message = "Assisted Mapping Functions"
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
                action_func=softlist_update
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
                is_back=True,
                requires_platform = False
            )
        ]

class DatMenu(BaseMenu):
    def __init__(self):
        super().__init__("dat_menu")
        self.options = [
            MenuItem(
                text = "a. Add Directories",
                action_func = platform_add_dat_function,
                requires_platform = False
            ),
            MenuItem(
                text = "b. Remove DAT Directory",
                action_func = del_datpath_function,
            ),
            MenuItem(
                text = "c. Back",
                is_back=True,
                requires_platform = False
            )
        ]

class CHDErrorMenu(BaseMenu):
    def __init__(self, chd_path: str, error_message: str):
        super().__init__("chd_error_menu")
        self.message = f"Error processing {chd_path}: {error_message}"
        self.options = [
            MenuItem(text="Skip this CHD and continue", action_func=self.skip),
            MenuItem(text="Stop processing all CHDs", action_func=self.stop),
            MenuItem(text="Retry this CHD", action_func=self.retry)
        ]

    def skip(self, menu_system: "MenuSystem") -> str:
        return "continue_chd_processing"

    def stop(self, menu_system: "MenuSystem") -> str:
        return "main_menu"

    def retry(self, menu_system: "MenuSystem") -> str:
        return "retry_current_chd"

class ExistingCHDMenu(BaseMenu):
    def __init__(self, chd_path: str, existing_version: str, current_version: str):
        super().__init__("existing_chd_menu")
        self.message = f"CHD already exists at {chd_path}\nExisting version: {existing_version}, Current version: {current_version}"
        self.options = [
            MenuItem(text="Overwrite this CHD", action_func=self.overwrite),
            MenuItem(text="Skip this CHD", action_func=self.skip),
            MenuItem(text="Always overwrite older CHDs for this session", action_func=self.set_overwrite_preference),
            MenuItem(text="Always skip existing CHDs for this session", action_func=self.set_skip_preference)
        ]

    def overwrite(self, menu_system: "MenuSystem") -> str:
        return "overwrite_current_chd"

    def skip(self, menu_system: "MenuSystem") -> str:
        return "continue_chd_processing"

    def set_overwrite_preference(self, menu_system: "MenuSystem") -> str:
        menu_system.current_platform.set_chd_preference("overwrite")
        return "continue_chd_processing"  # Continue with overwrite

    def set_skip_preference(self, menu_system: "MenuSystem") -> str:
        menu_system.current_platform.set_chd_preference("skip")
        return "continue_chd_processing"  # Continue with skip

if __name__ == '__main__':
    platform_manager = load_or_create_platform_manager()

    system = MenuSystem()
    system.platform_manager = platform_manager
    if not platform_manager.current_platform:
        print("No platform selected. Please select a platform to continue.")
        selected_platform = platform_manager.select_platform(show_all=True)
        if selected_platform:
            print(f"Selected platform: {selected_platform.name}")
        else:
            print("No platform selected. Exiting.")
            sys.exit(0)

    # Register all menus
    system.register(MainMenu())
    system.register(MapMenu())
    system.register(SettingsMenu())
    system.register(MapStageTwo())
    system.register(MapStageThree())
    system.register(DatMenu())
    #system.register(CHDErrorMenu())
    #system.register(ExistingCHDMenu())

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
        if next_target_name == None: # Handled by 'is_back' logic in execute()
            pass
        elif next_target_name == "Exit":
            platform_manager.save()
            print("Exiting...")
            break
        else:
            system.navigate_to(next_target_name)  # Update current menu
