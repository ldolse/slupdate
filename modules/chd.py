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
import requests
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
    info = None
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
                break
        if info == None:
            delete = inquirer.confirm('CHD is corrupt, delete?' , default=True)
            if delete:
                os.remove(chd)
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

def create_cue(file):
    # Extract the base file name without the extension
    file_name = os.path.splitext(file)[0]
    # Create the cue file name by replacing the extension with ".cue"
    cue_file_name = f"{file_name}.cue"

    # Define the content of the cue file
    cue_content = f'FILE "{file}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00'

    # Write the cue content to the cue file using UTF-8 encoding
    with open(cue_file_name, 'w', encoding='utf-8') as cue_file:
        cue_file.write(cue_content)

    print(f"Cue file '{cue_file_name}' created successfully.")
    return cue_file_name

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

def get_tocname_create_cue(ext,file_list):
    for file in file_list:
        if file.endswith(ext) and ext == '.mdf':
            file_name = os.path.splitext(file)[0]
            toc_file = create_cue(file_name+'.iso')
            break
        elif file.endswith(ext):
            toc_file = create_cue(file)
            break
        else:
            continue
    return toc_file

def create_chd_from_zip(zip_path, chd_path, settings, special_info=None):
    original_path = os.getcwd()
    user_provided_toc = False
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        toc_file = None
        for file_info in zip_file.infolist():
            if file_info.filename.endswith('.gdi') or file_info.filename.endswith('.cue'):
                toc_file = file_info.filename
                break
            elif file_info.filename.endswith('.iso') and sum(1 for file in zip_file.infolist() if file.filename.endswith('.iso')) == 1:
                toc_file = file_info.filename
                break
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
                if special_info['dat_group'] in ['no-intro','other']:
                    manual_fix_check = False
                    fix_message = f'Navigate to {temp_dir} and ensure the filenames and cue contents match.'
                    if toc_file == None:
                        file_list = special_info['file_list']
                        img_count = sum(1 for file in zip_file.infolist() if file.filename.endswith('.img'))
                        ccd_count = sum(1 for file in zip_file.infolist() if file.filename.endswith('.ccd'))
                        bin_count = sum(1 for file in zip_file.infolist() if file.filename.endswith('.bin'))
                        mdf_count = sum(1 for file in zip_file.infolist() if file.filename.endswith('.mdf'))

                        if mdf_count > 0:
                            print('archive contains an MDF file, this isn\'t supported by chdman, it will need to be converted to iso')
                            print('a cue file has been provided please ensure the iso name matches the cue contents')
                            toc_file = get_tocname_create_cue('.mdf',file_list)
                            fix_message = f'Navigate to {temp_dir} to convert the mdf to iso, ensure the cue contents match the new iso.'
                            manual_fix_check = True
                        elif img_count == 1 and ccd_count == 1:
                            toc_file = get_tocname_create_cue('.img',file_list)
                        elif bin_count == 1:
                            toc_file = get_tocname_create_cue('.bin',file_list)
                        else:
                            print('files can\'t be automatically fixed, but a cue has been added for manual resolution')
                            toc_file = get_tocname_create_cue('.bin',['file.bin'])
                            manual_fix_check = True

                    elif toc_file.endswith('.cue'):
                        # no-intro non redump files often use original cues but changed 
                        # the actual filenames without updating the cue, rewrite single file cues
                        cue_file_list = parse_cue_sheet(toc_file)
                        # only handling renaming a single file at this time
                        if len(cue_file_list) == 1:
                            for file in special_info['file_list']:
                                if file.endswith('.gdi') or file.endswith('.cue'):
                                    continue
                                else:
                                    os.rename(file,cue_file_list[0])
                        else:
                            print('DAT & cue file contents don\'t match')
                            manual_fix_check = True
                if manual_fix_check:
                    user_fix = inquirer.confirm('Do you want to manually fix the files?' , default=False)
                    if user_fix:
                        print(fix_message)
                        fixed = inquirer.confirm('Confirm Here when completed' , default=False)
                        if not fixed:
                            return 'no fix, continuing'

            elif toc_file == None:
                user_provided_toc = inquirer.confirm('No TOC or ISO in the zip archive, do you want to provide a CUE?' , default=False)
                if user_provided_toc:
                    user_continue = inquirer.confirm(f'Please add a TOC file to {temp_dir} and confirm when completed, or skip' , default=False)
                    if user_continue:
                        toc_file = inquirer.text(message="Please provide the name of the TOC file provided").strip()
                    else:
                        return 'No gdi, cue or iso file found in the zip archive, skipping this file'
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


def find_rom_zips(dat,soft_entry_data,dathashdict,dat_rom_map):
    zips = []
    zip_matches = False
    for disc, disc_info in soft_entry_data['parts'].items():
        if 'source_sha' in disc_info and disc_info['source_sha'] in dathashdict:
            dat_game_entry = dathashdict[disc_info['source_sha']]
            try:
                # check the entry from the dat against the directory the DAT points to
                goodzip = check_valid_zips(dat_game_entry,dat_rom_map[dat])
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
            for filename, file_data in dat_entry['file_list'].items():
                if not matches:
                    break
                if filename not in zip_file.namelist():
                    matches = False
                    break
                zip_info = zip_file.getinfo(filename)
                if zip_info.CRC != int(file_data['@crc'], 16):
                    matches = False
                    break
            if matches:
                return zip_path
            else:
                return None

def get_imgs_from_bin(cue):
    def get_file_name(line):
        # strip off leading 'FILE '
        pos = line.lower().index('file ')
        line = line[pos + 5:]
        # strip off leading 'FILE '
        pos = line.lower().index(' binary')
        line = line[:pos+1]
        #strip off leading ' '
        while line[0] == ' ':
            line = line[1:]
        #strip off trailing ' '
        while line[-1] == ' ':
            line = line[:-1]
        # remove double quotes
        if line[0] == '"':
            line = line[1:-1]
        # remove single quotes
        if line[0] == '\'':
            line = line[1:-1]
        return line
    
    print('CUE', cue) if verbose else None

    img_files = []
    with open(cue, 'r') as f:
        lines = f.readlines()
        for line in lines:
            # FILE
            if re.search('^\s*FILE', line):
                f = get_file_name(line)
                if f[0] != '/':
                    s = cue.split('/')
                    if len(s) > 1:
                        f = '/'.join(s[:-1]) + '/' + f
                img_files.append(f)
    return img_files


