import pathlib
import re
import os
import shutil
import subprocess
import tempfile
import zipfile
import logging
import builtins
import inquirer
from distutils.version import LooseVersion

'''
functions for working with chds and ROM/Zip files are defined in this module
'''

# get the script directory for chdman
if hasattr(builtins, "script_dir"):
    script_dir = builtins.script_dir
else:
    script_dir = os.getcwd()


# set environment to include script directory directory in addition to path - for chdman placed with script
env_with_script_dir = {**os.environ, 'PATH': script_dir + ':' + os.environ['PATH']}

def is_greater_than_0_176(version_string):
    return LooseVersion(version_string) > LooseVersion('0.176')

def chdman_info(chd=None):
    '''
    returns the data sha1 if a CHD path is provided
    otherwise returns chdman version
    '''
    if chd:
        command = ['chdman', 'info', '-i', chd]
    else:
        command = 'chdman'
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, env=env_with_script_dir)
    try:
        output = proc.stdout.read().decode('ascii').split('\n')
    except:
        logging.debug(f'chdman not in the system path or installed with slupdate, possibly corrupted CHD\n'+chd)
        pass
    if chd:
        for line in output:
            if re.findall(r'^\s*SHA1', line):
                info = re.sub(r'\s*SHA1:\s*','',line).strip()
                #info = re.sub(r'\s*Data\sSHA1:\s*','',line)
                break
    else:
        info = re.findall(r'\d+\.\d+',output[0])[0] # return version
    return info

# no-intro cuesheets don't match filenames, need to update names before passing to chdman
def parse_cue_sheet(cue_file_path):
    with open(cue_file_path, 'r') as cue_file:
        cue_contents = cue_file.read()
    # Extract FILE entries using regular expressions
    file_entries = re.findall(r'FILE "(.+?)"', cue_contents)
    return file_entries


def extract_zip_to_tempdir(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        temp_file = tempfile.SpooledTemporaryFile(max_size=2*1024*1024*1024) # 2GB max size
        temp_dir = tempfile.mkdtemp()

        # extract all files to temp directory
        for file_info in zip_file.infolist():
            file_path = os.path.join(temp_dir, file_info.filename)
            with open(file_path, 'wb') as f:
                f.write(zip_file.read(file_info.filename))

        # seek to beginning of file to read its name
        temp_file.seek(0)
        return temp_file, temp_dir


def create_chd_from_zip(zip_path, chd_path, settings, special_info=None):
    original_path = os.getcwd()
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        toc_file = None
        for file_info in zip_file.infolist():
            if file_info.filename.endswith('.gdi') or file_info.filename.endswith('.cue') or file_info.filename.endswith('.iso'):
                toc_file = file_info.filename
                break
        if not toc_file:
            return 'No gdi, cue or iso file found in the zip archive'
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            temp_dir = tempfile.mkdtemp(dir=settings['zip_temp'])

            # extract all files to temp directory
            for file_info in zip_file.infolist():
                # handle manually zipped garbage added by osx
                if not file_info.filename.startswith('__MACOSX/'):
                    file_path = os.path.join(temp_dir, file_info.filename)
                    with open(file_path, 'wb') as f:
                        f.write(zip_file.read(file_info.filename))

            os.chdir(temp_dir)
            
            # if the final argument is populated then take action
            if special_info:
                # dat group will always be here
                if special_info['dat_group'] == 'no-intro':
                    manual_fix_check = False
                    while not manual_fix_check:
                        if toc_file.endswith('.cue'):
                            # no-intro non redump files use original cues but changed the actual filenames
                            cue_file_list = parse_cue_sheet(toc_file)
                            # only handling renaming a single file at this time
                            if len(cue_file_list) == 1:
                                for file in special_info['file_list']:
                                    if file.endswith('.gdi') or file.endswith('.cue'):
                                        continue
                                    else:
                                        os.rename(file,cue_file_list[0])
                                manual_fix_check = True
                            else:
                                print('DAT & cue file contents don\'t match')
                                user_fix = inquirer.confirm('Do you want to manually fix the files?' , default=False)
                                if user_fix:
                                    print('Navigate to the temp directory configured for this script and ensure the filenames and cue contents match')
                                    fixed = inquirer.confirm('Confirm Here when completed' , default=False)
                                    if not fixed:
                                        return 'no fix, continuing'
                                    else:
                                        manual_fix_check = True
                                else:
                                    return 'no fix, continuing'
                        else:
                            manual_fix_check = True

            command = ['chdman', 'createcd', '-i', toc_file, '-o', chd_path]
            subprocess.run(command, check=True, env=env_with_script_dir)
    finally:
        os.chdir(original_path)
        shutil.rmtree(temp_dir)

def convert__bincue_to_chd(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path, show_command_output: bool):
    # Use temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)

        logging.debug(f'Converting "{chd_file_path.name}" to .bin/.cue format')
        chdman_result = subprocess.run(["chdman", "createcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], stdout=None if show_command_output else subprocess.DEVNULL, env=env_with_script_dir)
        if chdman_result.returncode != 0:
            # chdman provides useful progress output on stderr so we don't want to capture stderr when running it. That means we can't provide actual error output to the exception, but I can't find a way around that.
            raise ConversionException("Failed to convert .chd using chdman", chd_file_path, None)


def find_rom_zips(dat,soft_entry_data,dathashdict,platform_settings):
    zips = []
    zip_matches = False
    for disc, disc_info in soft_entry_data['parts'].items():
        if 'source_sha' in disc_info and disc_info['source_sha'] in dathashdict:
            dat_game_entry = dathashdict[disc_info['source_sha']]
            try:
                # check the entry from the dat against the directory the DAT points to
                goodzip = check_valid_zips(dat_game_entry,platform_settings[dat])
            except:
                print('key error for '+disc+', dat: '+dat)
                continue
            if goodzip:
                dat_game_entry.update({'source_rom':goodzip})
                disc_info.update({'source_rom':goodzip})
                zips.append(os.path.basename(goodzip))
                zip_matches = True
            else:
                zips.append('No Valid Zip')
    if zip_matches:
        return zips
    else:
        return None


def find_softlist_zips(soft_list, platform_dats,dat_rom_map):
    '''
    iterates through the soft_list to check source DAT and fingerprint
    checks the platform_dats for the description to calculate the name
    gets the ROM folder from the dat_rom_map to find a matching ZIP
    Checks the ZIP contents, returns the list of valid matches
    deprecated in favor of doing the check rom by rom from another function
    '''
    print('checking all source zip files')
    valid_zips = {}
    for soft, softdata in soft_list.items():
        if 'sourcedat' in softdata:
            dat = softdata['sourcedat']
            for disc, disc_info in softdata['parts'].items():
                if 'source_sha' in disc_info and disc_info['source_sha'] in platform_dats[dat]:
                    game_entry = platform_dats[dat][disc_info['source_sha']]
                    goodzip = check_valid_zips(game_entry,dat_rom_map[dat])
                    if goodzip:
                        disc_info.update({'source_rom':goodzip})
                        valid_zips.update({sha:goodzip})
        else:
            continue
    print('found '+str(len(valid_zips))+' valid rom sources which can be coverted to CHD')


def check_valid_zips(dat_entry,rom_folder):
    '''
    Checks the ZIP contents to ensure it's a valid dat match, returns valid matches
    TODO - add 7zip support
    '''
    name_with_zip = dat_entry['name'] + '.zip'
    #print('checking '+name_with_zip+' in folder '+rom_folder)
    zip_path = os.path.join(rom_folder, name_with_zip)
    if os.path.isfile(zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            matches = True
            for filename, crc in dat_entry['file_list'].items():
                if not matches:
                    break
                if filename not in zip_file.namelist():
                    matches = False
                    break
                zip_info = zip_file.getinfo(filename)
                if zip_info.CRC != int(crc, 16):
                    matches = False
                    break
            if matches:
                return zip_path
            else:
                return None
