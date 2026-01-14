from menus.menu_system import BaseMenu, MenuItem, MenuSystem
from menus.menu_system.adapters import DeclarativeMenuAdapter
import os, sys, traceback
import inquirer
from consoles import Platform
from rom_management import CHD
from modules.software_list import update_softlist_chd_sha1s
from modules.chd import (
    create_chd_from_zip,
    chdman_info,
)
from rom_management.processing.archive_validation import ArchiveValidationProcess
from rom_management.processing.chd_build_process import ChdBuildProcess
from rom_management.processing.chd_hash_validation import CHDHashValidationProcess
from rom_management.processing.models import ResultObject, PendingInputPayload, Action


def old_chd_builder(platform: Platform) -> None:
    """
    This version is only for refactoring reference, the actual chd builder will be a
    process called by ProcessRunner and CHDBuildProcess.

    checks each soft list entry for a matched source rom and builds chds using those ROM
    sources.  CHD hash is added to the soft-dict.  If a CHD already exists in the build
    directory it's skipped, but there is a flag to enable grabbing hashes for built CDs.
    """
    get_sha_from_existing_chd = False
    settings = {}
    if platform == "psx":
        from rom_management.handlers.libcrypt_handler import libcrypt_titles
    new_hashes = False
    built_sources = {}  # replaced by platform.validated_chds
    discontinue = False  # Need to replicate this logic from the menu system, there is exception handling there but it's not fully implemented
    for soft, soft_data in platform.software_list_data.items():
        if discontinue:
            break
        for disc_data in soft_data["parts"].values():
            if "chd_found" in disc_data and not get_sha_from_existing_chd:
                if disc_data["chd_found"]:
                    continue
            if "source_rom" in disc_data:
                # create platform directory and softlist title directory
                if not os.path.exists(platform.chd_path):
                    os.mkdir(os.path.join(platform.chd_path))
                chd_dir = os.path.join(platform.chd_path, soft)
                if not os.path.exists(chd_dir):
                    os.mkdir(chd_dir)
                chd_name = disc_data["chd_filename"] + ".chd"
                chd_path = os.path.join(chd_dir, chd_name)
                if not os.path.isfile(chd_path):  # printing here not duplicated
                    print("\nbuilding chd for " + soft_data["description"] + ":")
                    print("            CHD: " + chd_name)
                    print(
                        "     Source Zip: " + os.path.basename(disc_data["source_rom"])
                    )

                    if disc_data["source_rom"] not in built_sources:
                        """
                        check the dat group here for any special handling that will be needed
                        known things to handle:
                          - Todo: Redump and Philips cdi - need a simple rewrite to the cue file to change the mode
                          - Redump & psx - libcrypt support
                          - No-Intro - Cue file data doesn't match filenames (partial support)
                          - others, CCD to bin/cue conversion, ISO handling, etc
                        """
                        dat_group = platform.dat_hashes["dat_group"][
                            disc_data["source_dat"]
                        ]
                        special_logic = {
                            "dat_group": dat_group
                        }  # all of this special logic needs to be replicated somewhere
                        if dat_group in ["no-intro", "other"]:
                            # no-intro and other dat groups often play fast and loose with filenames, formats and toc requirements
                            game_entry = platform.dat_hashes["hashes"][
                                disc_data["source_dat"]
                            ][disc_data["source_sha"]]
                            special_logic.update(game_entry)
                        elif dat_group == "redump":
                            libcrypt = False
                            if platform == "psx" and "serial" in soft_data:
                                """
                                in refactor, psx is a subclass of consoles.platform to move this logic to
                                psx class needs to look at the serial number, which is in the
                                SoftwareList.Software object (but not guaranteed in all cases) and redump
                                db entry object, which is guaranteed -
                                note we can only apply libcrypt logic to Redump dumps
                                """
                                for serial in soft_data["serial"]:
                                    if serial in libcrypt_titles:
                                        libcrypt = True
                                if libcrypt:
                                    """
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
                                    """
                                    print("This Title uses Libcrypt")
                                    special_logic.update(
                                        {"redump_url": disc_data["redump_url"]}
                                    )
                                    if sys.platform != "win32":
                                        # OS check can go away when this is implemented
                                        print(
                                            "libcrypt handling requires additional windows binaries, not supported on this platform"
                                        )
                                        continue
                            elif platform == "cdi":
                                # placeholder CDI requires a simple manipulation of the existing cue file provided by Redump
                                pass
                        else:
                            special_logic = None
                        try:
                            error = create_chd_from_zip(
                                disc_data["source_rom"],
                                chd_path,
                                settings,
                                special_logic,
                            )
                            if not error:
                                built_sources.update(
                                    {disc_data["source_rom"]: chd_path}
                                )
                            else:
                                print(error)
                                continue
                        except Exception:
                            print("CHD Creation Failed")
                            print(traceback.format_exc())
                            if os.path.isfile(chd_path):
                                try:
                                    os.remove(chd_path)
                                except:
                                    print("Failed to delete partial file:\n" + chd_path)
                                    print(
                                        "Please ensure this is deleted to avoid corrupted files/hashes"
                                    )
                            continue_build = inquirer.confirm(
                                "Do you want to continue?", default=False
                            )
                            if continue_build:
                                continue
                            else:
                                discontinue = True
                                break
                    # if the exact same chd was built earlier then just symlink to it
                    # these symlinks aren't cross platform, will revisit this
                    elif disc_data["source_rom"] in built_sources:
                        os.symlink(built_sources[disc_data["source_rom"]], chd_path)
                        built_sources.update({disc_data["source_rom"]: chd_path})
                elif not get_sha_from_existing_chd:
                    continue
                    # print('chd for '+soft_data['description']+' already exists, skipping')
                # if the chd was created as a part of this run or if the flag to trust existing chds is enabled check the sha1 against the softlist
                if os.path.isfile(chd_path):
                    if (
                        disc_data["source_rom"] in built_sources
                        or get_sha_from_existing_chd
                    ):
                        new_chd_hash = chdman_info(chd_path)
                        if "chd_sha1" in disc_data:
                            current_chd_hash = disc_data["chd_sha1"]
                        else:
                            current_chd_hash = ""
                            disc_data["chd_sha1"] = current_chd_hash
                        if new_chd_hash == current_chd_hash:
                            print("\nHash matches softlist: " + chd_name + "\n")
                        elif new_chd_hash is not None:
                            new_hashes = True
                            print("\nUpdated hash for softlist: " + chd_name + "\n")
                            disc_data.update({"new_sha1": new_chd_hash})
                        else:
                            print("error producing CHD, please try again")
                    else:
                        continue

    if new_hashes:
        write_new_hashes = inquirer.confirm(
            "Update the Software List with new CHD Hashes?", default=False
        )
        if write_new_hashes:
            update_softlist_chd_sha1s(
                platform.softlist_xml_path, platform.software_list_data
            )


class CHDBuildMenu(DeclarativeMenuAdapter, BaseMenu):
    def __init__(self):
        super().__init__("chd_build_menu")
        self.message = "Create CHDs from ROMs"
        self.options = [
            MenuItem(
                text="a. Validate source ROMs",
                action_func=self._validate_roms,
            ),
            MenuItem(
                text="b. Build CHDs from ROMs",
                action_func=self._chd_builder,
                requires_platform=True,
            ),
            MenuItem(
                text="c. Validate CHD hashes against softwarelist",
                action_func=self._validate_chd_hashes,
                requires_platform=True,
            ),
            MenuItem(
                text="d. Back to Main Menu", target="main_menu", requires_platform=False
            ),
        ]

    def _validate_roms(
        self, platform: Platform, menu_system: "MenuSystem"
    ) -> ResultObject:
        """Run validation process via MenuSystem"""

        # Run the validation process
        result = menu_system.run_process(
            ArchiveValidationProcess, destination_menu="chd_build_menu"
        )

        # If None, process is waiting for user input - return success
        # Control will be resumed after user interaction
        if result is None:
            return ResultObject.success(message="Waiting for user input...")

        # Process completed or errored
        return result

    def _chd_builder(
        self, platform: Platform, menu_system: "MenuSystem"
    ) -> ResultObject:
        """Build CHDs from validated ROMs"""

        # Check chdman version
        check = CHD(check_chdman=True)
        if not check.chdman_uptodate:
            print("Outdated Chdman, please upgrade to a recent version")
            return ResultObject.complete(
                total_processed=0, destination_menu="chd_build_menu"
            )

        if len(platform.matched_buildable_media) == 0:
            print(
                "No valid media found, please check source ROMs and DAT files, and ensure mapping is complete."
            )
            return ResultObject.complete(
                total_processed=0, destination_menu="chd_build_menu"
            )

        # Confirm with user
        build = inquirer.confirm("Begin Creating CHDs?", default=False)
        if not build:
            return ResultObject.complete(
                total_processed=0, destination_menu="chd_build_menu"
            )

        try:
            # Run CHD build process via ProcessRunner
            result = menu_system.run_process(
                ChdBuildProcess, destination_menu="chd_build_menu"
            )

            # If None, process is waiting for user input - return success
            # Control will be resumed after user interaction via resume_process()
            if result is None:
                return ResultObject.success(message="Waiting for user input...")

            # Auto-run validation after successful CHD build
            if result.is_complete():
                return self._validate_chd_hashes(platform, menu_system)

            # Process completed or errored
            return result

        except Exception as e:
            # Return error result with handler_error_menu as destination
            return ResultObject.error(
                error_type="HandlerException",
                message=str(e),
                exception=e,
                destination_menu="chd_build_menu",
            )

    def _validate_chd_hashes(
        self, platform: Platform, menu_system: "MenuSystem"
    ) -> ResultObject:
        """Validate CHD hashes and filenames against softwarelist entries"""

        if not platform.validated_chds:
            print("No validated CHDs found to check")
            return ResultObject.complete(
                total_processed=0,
                destination_menu="chd_build_menu",
            )

        try:
            result = menu_system.run_process(
                CHDHashValidationProcess, destination_menu="chd_build_menu"
            )

            # If None, process is waiting for user input - return success
            # Control will be resumed after user interaction via resume_process()
            if result is None:
                return ResultObject.success(message="Waiting for user input...")

            # Process completed or errored
            return result

        except Exception as e:
            # Return error result with handler_error_menu as destination
            return ResultObject.error(
                error_type="HandlerException",
                message=str(e),
                exception=e,
                destination_menu="handler_error_menu",
            )
