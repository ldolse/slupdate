import pathlib
import re
import os
import shutil
import subprocess
import tempfile
import zipfile
from io import BytesIO
import logging

def chdman_info(chd=None):
    '''
    returns the data sha1 if a CHD path is provided
    otherwise returns chdman version
    '''
    if chd:
        command = ['chdman', 'info', '-i', chd]
    else:
        command = 'chdman'
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        output = proc.stdout.read().decode('ascii').split('\n')
    except:
        logging.debug(f'chdman not in the system path or installed with slupdate, possibly corrupted CHD\n'+chd)
        pass
    if chd:
        for line in output:
            if re.findall(r'^\s*SHA1', line):
                info = re.sub(r'\s*SHA1:\s*','',line)
                #info = re.sub(r'\s*Data\sSHA1:\s*','',line)
                break
    else:
        info = re.findall(r'\d+\.\d+',output[0])[0] # return version
    return info


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


def create_chd_from_zip(zip_path, chd_path):
    origin_path = os.getcwd()
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        toc_file = None
        for file_info in zip_file.infolist():
            if file_info.filename.endswith('.gdi') or file_info.filename.endswith('.cue'):
                toc_file = file_info.filename
                break
        if not toc_file:
            raise ValueError('No .gdi or .cue file found in the zip archive')
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            temp_dir = tempfile.mkdtemp()

            # extract all files to temp directory
            for file_info in zip_file.infolist():
                file_path = os.path.join(temp_dir, file_info.filename)
                with open(file_path, 'wb') as f:
                    f.write(zip_file.read(file_info.filename))

            os.chdir(temp_dir)

            command = ['chdman', 'createcd', '-i', toc_file, '-o', chd_path]
            subprocess.run(command, check=True)
    finally:
        os.chdir(origin_path)
        shutil.rmtree(temp_dir)




def convert__bincue_to_chd(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path, show_command_output: bool):
    # Use another temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)

        logging.debug(f'Converting "{chd_file_path.name}" to .bin/.cue format')
        chdman_result = subprocess.run(["chdman", "createcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], stdout=None if show_command_output else subprocess.DEVNULL)
        if chdman_result.returncode != 0:
            # chdman provides useful progress output on stderr so we don't want to capture stderr when running it. That means we can't provide actual error output to the exception, but I can't find a way around that.
            raise ConversionException("Failed to convert .chd using chdman", chd_file_path, None)
            

def find_rom_zips(soft_list, platform_dats,dat_rom_map):
    '''
    iterates through the soft_list to check source DAT and fingerprint
    checks the platform_dats for the description to calculate the name
    gets the ROM folder from the dat_rom_map to find a matching ZIP
    Checks the ZIP contents, returns the list of valid matches
    TODO - add 7zip support
    '''
    valid_zips = {}
    for soft, softdata in soft_list.items():
        if 'sourcedat' in softdata:
            dat = softdata['sourcedat']
            for disc, disc_info in softdata['parts'].items():
                if 'source_sha' in disc_info and disc_info['source_sha'] in platform_dats[dat]:
                    sha = disc_info['source_sha']
                    game_entry = platform_dats[dat][sha]
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
