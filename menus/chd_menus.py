from menus.menu_system import BaseMenu, MenuItem, MenuSystem
import os, sys, traceback
import inquirer
from consoles import Platform
from rom_management import CHD
from rom_management.exceptions import HandlerException, UserActionRequiredException, CHDAlreadyExistsException
from modules.software_list import update_softlist_chd_sha1s
from modules.chd import (
    create_chd_from_zip,
    chdman_info,
)

# disabled by default, allows the script to populate chd sha1s on subsequent runs
# only enable if CHD destination folder ONLY contains chds created by this script
get_sha_from_existing_chd = False
settings = {}

def chd_builder(platform: Platform) -> None:
    '''
    checks each soft list entry for a matched source rom and builds chds using those ROM
    sources.  CHD hash is added to the soft-dict.  If a CHD already exists in the build
    directory it's skipped, but there is a flag to enable grabbing hashes for built CDs.
    '''
    if platform == 'psx':
        from rom_management.handlers.libcrypt_handler import libcrypt_titles
    new_hashes = False
    built_sources = {} # replaced by platform.validated_chds
    discontinue = False # Need to replicate this logic from the menu system, there is exception handling there but it's not fully implemented
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
                if not os.path.isfile(chd_path): # printing here not duplicated
                    print('\nbuilding chd for '+soft_data['description']+':')
                    print('            CHD: '+chd_name)
                    print('     Source Zip: '+os.path.basename(disc_data['source_rom']))

                    if disc_data['source_rom'] not in built_sources:
                        '''
                        check the dat group here for any special handling that will be needed
                        known things to handle:
                          - Todo: Redump and Philips cdi - need a simple rewrite to the cue file to change the mode
                          - Redump & psx - libcrypt support
                          - No-Intro - Cue file data doesn't match filenames (partial support)
                          - others, CCD to bin/cue conversion, ISO handling, etc
                        '''
                        dat_group = platform.dat_hashes['dat_group'][disc_data['source_dat']]
                        special_logic = {'dat_group':dat_group} # all of this special logic needs to be replicated somewhere
                        if dat_group in ['no-intro','other']:
                            # no-intro and other dat groups often play fast and loose with filenames, formats and toc requirements
                            game_entry = platform.dat_hashes['hashes'][disc_data['source_dat']][disc_data['source_sha']]
                            special_logic.update(game_entry)
                        elif dat_group == 'redump':
                            libcrypt = False
                            if platform == 'psx' and 'serial' in soft_data:
                                '''
                                in refactor, psx is a subclass of consoles.platform to move this logic to
                                psx class needs to look at the serial number, which is in the
                                SoftwareList.Software object (but not guaranteed in all cases) and redump
                                db entry object, which is guaranteed -
                                note we can only apply libcrypt logic to Redump dumps
                                '''
                                for serial in soft_data['serial']:
                                    if serial in libcrypt_titles:
                                        libcrypt = True
                                if libcrypt:
                                    '''
                                    in refactored code we wil be doing the following with libcrypt:
                                     1. convert the bin/cue to cloneCD format to support adding a subchannel
                                     2. Create an empty subchannel file - this is working code, also not hooked
                                     3. Download the lsd file from the redump website which contains the DRM data
                                     4. Patch the empty subchannel file with the LSD data
                                     5. Convert the CloneCD + Subchannel to CDRDAO, as CHDMAN doesn't support CloneCD
                                     6. Convert CDRDAO to CHD

                                     Note Steps 1-4 are already in the codebase 100% working but not hooked up
                                     Step 5 has code translated from C# to python from the Aaru project but is not yet working.
                                     Step 6 really just involves recognizing a CDRDAO file in the TOC identification function,
                                     which likely already works.
                                    '''
                                    print('This Title uses Libcrypt')
                                    special_logic.update({'redump_url':disc_data['redump_url']})
                                    if sys.platform != 'win32':
                                        # OS check can go away when this is implemented
                                        print('libcrypt handling requires additional windows binaries, not supported on this platform')
                                        continue
                            elif platform == 'cdi':
                                # placeholder CDI requires a simple manipulation of the existing cue file provided by Redump
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

class CHDBuildMenu(BaseMenu):
    def __init__(self):
        super().__init__("chd_build_menu")
        self.message = "Create CHDs from ROMs"
        self.options = [
            MenuItem(
                text = "a. Validate source ROMs",
                action_func = self._validate_roms,
            ),
            MenuItem(
                text = "a. Validate source ROMs (old method)",
                action_func = self._validate_roms_old,
            ),
            MenuItem(
                text = "b. Build CHDs from ROMs",
                action_func = self._chd_builder,
                requires_platform = True
            ),
            MenuItem(
                text = "c. Back to Main Menu",
                target = "main_menu",
                requires_platform = False
            )
        ]

    @staticmethod
    def _validate_roms(platform: Platform) -> None:
        return platform.start_validation_process()
    
    @staticmethod
    def _validate_roms_old(platform: Platform) -> None:
        return platform.validate_matched_entries()

    @staticmethod
    def _chd_builder(platform: Platform) -> dict:
        # check chdman version
        check = CHD(check_chdman=True)
        if not check.chdman_uptodate:
            print('Outdated Chdman, please upgrade to a recent version')
            return {"menu": "chd_build_menu", "payload": None}
        if len(platform.matched_buildable_media) == 0:
            print('No valid media found, please check source ROMs and DAT files, and ensure mapping is complete.')
            return {"menu": "chd_build_menu", "payload": None}
        build = inquirer.confirm('Begin Creating CHDs?', default=False)
        if build:
            try:
                return platform.start_chd_build_process()

            except HandlerException as e:
                # Let the menu system handle this by returning navigation info
                return {"menu": "handler_error_menu", "payload": e}
        else:
            return {"menu": "chd_build_menu", "payload": None}

class HandlerErrorMenu(BaseMenu):
    def __init__(self, name: str = "handler_error_menu"):
        super().__init__(name)
        self.message = f"Handler Error"
        self.options = [
            MenuItem(text="Retry", action_func=self.retry),
            MenuItem(text="Skip this item", action_func=self.skip),
            MenuItem(text="Stop processing", action_func=self.stop)
        ]

    def set_payload(self, payload):
        """Set the exception payload and update message"""
        self.payload = payload
        if payload:
            self.message = f"Handler Error: {payload}"

    @staticmethod
    def retry() -> str:
        return "retry_current_item"

    @staticmethod
    def skip() -> str:
        return "skip_current_item"

    @staticmethod
    def stop() -> str:
        return "stop_processing"


class CHDErrorMenu(BaseMenu):
    def __init__(self, name: str = "chd_error_menu"):
        super().__init__(name)
        self.message = f"Error processing CHD"
        self.options = [
            MenuItem(text="Skip this CHD and continue", action_func=self.skip),
            MenuItem(text="Stop processing all CHDs", action_func=self.stop),
            MenuItem(text="Retry this CHD", action_func=self.retry)
        ]

    def set_payload(self, payload):
        """Set the error payload and update message"""
        self.payload = payload
        if payload:
            self.message = f"Error processing {payload.chd_path}: {payload.error_message}"

    @staticmethod
    def skip() -> str:
        return "continue_chd_processing"

    @staticmethod
    def stop() -> str:
        return "main_menu"

    @staticmethod
    def retry() -> str:
        return "retry_current_chd"


class ExistingCHDMenu(BaseMenu):
    def __init__(self, name: str = "existing_chd_menu"):
        super().__init__(name)
        self.message = f"CHD already exists"
        self.options = [
            MenuItem(text="Overwrite this CHD", action_func=self.overwrite),
            MenuItem(text="Skip this CHD", action_func=self.skip),
            MenuItem(text="Always overwrite older CHDs for this session", action_func=self.set_overwrite_preference),
            MenuItem(text="Always skip existing CHDs for this session", action_func=self.set_skip_preference)
        ]

    def set_payload(self, payload):
        """Set the exception payload and update message"""
        self.payload = payload
        if payload:
            existing_version = payload.existing_version or "Unknown"
            self.message = f"CHD already exists at {payload.chd_path}\nExisting version: {existing_version}"

    @staticmethod
    def overwrite(platform: Platform) -> str:
        return "overwrite_current_chd"

    @staticmethod
    def skip(platform: Platform) -> str:
        return "continue_chd_processing"

    @staticmethod
    def set_overwrite_preference(platform: Platform) -> str:
        platform.set_chd_preference("overwrite")
        return "continue_chd_processing"  # Continue with overwrite

    @staticmethod
    def set_skip_preference(platform: Platform) -> str:
        platform.set_chd_preference("skip")
        return "continue_chd_processing"  # Continue with skip