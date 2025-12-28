from menus.menu_system import BaseMenu, MenuItem
from consoles import Platform
import inquirer
import os
from modules.dat import create_dat
from modules.mapping import (
    get_unmatched_roms,
    name_serial_auto_map,
    interactive_title_mapping,
    map_tosec_entries,
    get_missing_zips,
    redump_url_mapping,
    build_redump_tosec_tuples,
    update_soft_dict,
    fuzzy_hash_compare,
)

from rom_management.processing.models import PendingInputPayload, Action
from typing import Optional, Tuple

script_dir = os.path.dirname(os.path.abspath(__file__))

def process_interactive_matches(interactive_matches,platform: Platform,match_type):
    print('Some matches require user review\n')
    confirmed_interactive = interactive_title_mapping(interactive_matches,platform.software_list_data,platform.dat_hashes,platform.key,script_dir,match_type)
    if confirmed_interactive:
        message = "Do you want to commit the new hashes the softlist?"
        proceed = inquirer.confirm(message, default=False)
        if proceed:
            update_soft_dict(platform.key,confirmed_interactive)

def softlist_update(platform: Platform) -> None:
    platform.update_softlist()

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

class MapMenu(BaseMenu):
    def __init__(self):
        super().__init__("map_menu")
        self.message = "Process software lists and dat files, mapping source file references"
        self.options = [
            MenuItem(
                text = "a. Automatically map based on source rom info",
                action_func = self._automap_function
            ),
            MenuItem(
                text = "b. List missing matched ROM Files",
                action_func = self._list_missing_function
            ),
            MenuItem(
                text = "c. List TOSEC sources",
                action_func = self._tosec_list_function
            ),
            MenuItem(
                text = "d. List unknown sources",
                action_func = self._unknown_list_function
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

    @staticmethod
    def _automap_function(platform: Platform) -> None:
        platform.process_data()

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
    @staticmethod
    def _list_missing_function(platform: Platform) -> None:
        '''
        lists the missing ROM files for matched entries
        '''
        get_missing_zips(platform.software_list_data,platform.dat_hashes)

    def _tosec_list_function(self, platform: Platform) -> None:
        self._list_soft_entries(platform,'TOSEC')

    @staticmethod
    def _list_soft_entries(platform: Platform, group=None):
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

    def _unknown_list_function(self, platform: Platform) -> None:
        self._list_soft_entries(platform)

    def display_and_get_input(
        self, payload: PendingInputPayload
    ) -> Tuple[Action, Optional[dict]]:
        """MapMenu does not require user input - should not be called"""
        raise NotImplementedError("MapMenu does not support process-based user input")


class MapStageTwo(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_two")
        self.message = "Use other reference datapoints to remap the software list & DAT files"
        self.options = [
            MenuItem(
                text = "a. Redump URL Based Mapping",
                action_func = self._url_map_function,
                requires_platform = True
            ),
            MenuItem(
                text = "b. Remap TOSEC sources to Redump",
                action_func = self._tosec_map_function,
            ),
            MenuItem(
                text = "c. Automated Redump re-map based on disc serial & name",
                action_func = self._name_serial_automap_function,
            ),
            MenuItem(
                text = "g. Update Software list XML",
                action_func = softlist_update
            ),
            MenuItem(
                text = "i. Interactive Mapping Functions",
                target = "map_stage_three",
            ),
            MenuItem(
                text = "j. Build CHDs",
                target = "chd_build_menu",
            ),
            MenuItem(
                text = "Back",
                is_back = True,
                requires_platform = False
            )
        ]

    @staticmethod
    def _url_map_function(platform: Platform) -> None:
        '''
        remaps the Software List based on redump source urls
        '''
        url_remaps = redump_url_mapping(platform, script_dir)
        if url_remaps:
            url_commit_msg = "Updates based on Redump source URLs successful. Proceed to update the Softlist data?"
            proceed = inquirer.confirm(url_commit_msg, default=False)
            if proceed:
                update_soft_dict(platform,url_remaps)

    @staticmethod
    def _tosec_map_function(platform: Platform) -> None:
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

    def _name_serial_automap_function(self, platform: Platform) -> None:
        self.automated_mapping(platform,'name_serial')

    def display_and_get_input(
        self, payload: PendingInputPayload
    ) -> Tuple[Action, Optional[dict]]:
        """MapMenu does not require user input - should not be called"""
        raise NotImplementedError("MapMenu does not support process-based user input")



class MapStageThree(BaseMenu):
    def __init__(self):
        super().__init__("map_stage_three")
        self.message = "Assisted Mapping Functions"
        self.options = [
            MenuItem(
                text="a. Fuzzy Matches - Remap bad/alternate Dumps",
                action_func=self._hash_map_function,
            ),
            MenuItem(
                text="b. Serial Only Mapping",
                action_func=self._serial_map_function,
            ),
            MenuItem(
                text="c. Interactive Name Based Mapping",
                action_func=self._interactive_map_function,
            ),
            MenuItem(
                text="d. Update Sofltist XML",
                action_func=softlist_update
            ),
            MenuItem(
                text="e. Build CHDs",
                target = "chd_build_menu",
            ),
            MenuItem(
                text="f. Generate Missing DAT",
                action_func=self._dat_build_function,
            ),
            MenuItem(
                text="g. Back",
                is_back=True,
                requires_platform = False
            )
        ]
    @staticmethod
    def _interactive_map_function(platform: Platform) -> None:
        name_serial_matches, interactive_matches = name_serial_auto_map(platform,script_dir,lookup_type='name')
        if interactive_matches:
            match_type = 'redump_name'
            process_interactive_matches(interactive_matches,platform,match_type)
        else:
            print('No matches to commit, return to menu\n')

    @staticmethod
    def _dat_build_function(platform: Platform) -> None:
        '''
        creates a DAT file from the unmatched ROMs
        '''
        rom_dict = get_unmatched_roms(platform.software_list_data)
        create_dat(rom_dict,platform.key)

    def _serial_map_function(self, platform: Platform) -> None:
        self.automated_mapping(platform,'serial')

    @staticmethod
    def _hash_map_function(platform: Platform) -> None:
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

    def display_and_get_input(
        self, payload: PendingInputPayload
    ) -> Tuple[Action, Optional[dict]]:
        """MapMenu does not require user input - should not be called"""
        raise NotImplementedError("MapMenu does not support process-based user input")

