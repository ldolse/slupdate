#!/usr/bin/env python3

""" slupdate.py: Interactively Update MAME Optical Media based Software Lists
against[Redump](http://redump.org/) & TOSEC dats.

https://github.com/ldolse/slupdate
"""
import os
import sys
import inquirer
from consoles import PlatformManager, Platform
from utils.utils import get_script_path
from menus.menu_system import MenuSystem
from menus import MainMenu, SettingsMenu, DatMenu, MapMenu, MapStageTwo, MapStageThree, CHDBuildMenu, CHDErrorMenu, ExistingCHDMenu
from modules.mapping import get_source_stats
from modules.mapping import print_source_stats

__version__ = '.2'
script_dir = get_script_path()

# Require at least Python 3.7
assert sys.version_info >= (3, 7)

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
            zip_name = None # retired
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


def entry_create_function(platform: Platform) -> None:
    print('new entry placeholder')
    pass



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
        platform_manager.add_dat_function()
    else:
        print("No platform selected. Exiting.")
        sys.exit(0)


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
    system.register(CHDBuildMenu())
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
