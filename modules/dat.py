import hashlib
import xml.etree.ElementTree as ET
from html import unescape
from lxml import etree
import os
from typing import Optional

class DAT:
    def __init__(self, path: str, rom_directory: Optional[str] = None):
        self.path = path  # Full path to the DAT file (e.g., /datroot/psx/redump-psx.dat)
        self.rom_directory = rom_directory  # Path to ROM directory for this DAT
        self._xml_tree = None

    @property
    # lazy load the xml tree
    def xml_tree(self) -> ET.ElementTree:
        if not self._xml_tree:
            try:
                self._xml_tree = ET.parse(self.path)
            except ET.ParseError as e:
                raise ValueError(f"Failed to parse {self.path}: {e}")
        return self._xml_tree

    @property
    def name(self) -> str:
        """Extract <name> from the DAT's XML header."""
        try:
            root = self.xml_tree.getroot()
            return unescape(root.find(".//header/name").text.strip())
        except Exception as e:
            return os.path.basename(self.path)  # Fallback to filename

    @property
    def dat_group(self) -> str:
        """Determine the DAT group based on the URL in the header."""
        try:
            root = self.xml_tree.getroot()
            url = root.find('header/url').text  
            if 'tosec' in url:
                return 'TOSEC'
            elif 'redump' in url:
                return 'redump'
            elif 'no-intro' in url:
                return 'no-intro'
            else:
                return 'other'
        except Exception as e:
            return 'unknown'

    @property
    def dat_author(self) -> str:
        """Extract the author from the DAT's XML header."""
        try:
            root = self.xml_tree.getroot()
            return unescape(root.find('header/author').text.strip())
        except Exception as e:
            return 'unknown'

    def build_hash_dict(self):
        """
        Parses this DAT's XML and returns hash/name lookup tables.
        hash based on concatenating rom sha1s and creating a new sha1
        same is done for crc for old rom sources which don't use sha1
        
        Returns:
            keyresult (Dict[hashes -> metadata])
            nameresult (Dict[name -> list of hashes])
        """
        keyresult = {}
        nameresult = {}
        try:
            root = self.xml_tree.getroot()
        except Exception as e:
            print(f"Error parsing {self.path} XML: {e}")
            return keyresult, nameresult
        for game in root.findall('game'):
            file_list = {}
            raw_romlist = []
            size = 0
            name = game.get('name')
            raw_romlist = get_raw_rom_entry(game)
            files = len(game.findall('rom'))
            sha1 = hashlib.sha1()
            for rom in game.findall('rom'):
                rom_info = {'@size':rom.get('size'),
                            '@crc':rom.get('crc'),
                            '@md5':rom.get('md5'),
                            '@sha1':rom.get('sha1')
                        }
                file_list.update({rom.get('name'):rom_info})
                if not rom.get('name').lower().endswith(('.cue', '.gdi')) and not rom.get('name').lower() == 'ip.bin':
                    sha1.update(rom.get('sha1').encode('utf-8'))
                    size = size + int(rom.get('size'))
            sha1_digest = sha1.hexdigest()
            keyresult[(sha1_digest,'sha1')] = {
                'name': name,
                'files': files,
                'size': size,
                'file_list': file_list,
                'raw_romlist':raw_romlist
            }
            # repeat hash calculation for crc for old rom sources
            crc_sha1 = hashlib.sha1()
            for rom in game.findall('rom'):
                if not rom.get('name').lower().endswith(('.cue', '.gdi')) and not rom.get('name').lower() == 'ip.bin':
                    crc_sha1.update(rom.get('sha1').encode('utf-8'))
            crc_sha1_digest = crc_sha1.hexdigest()
            keyresult[(crc_sha1_digest,'crc')] = {
                'name': name,
                'files': files,
                'size': size,
                'file_list': file_list,
                'raw_romlist':raw_romlist
            }
            nameresult[game.get('name')] = {
                'sha1_digest' : sha1_digest
            }
        return keyresult, nameresult


'''
dat processing functions
'''

def create_dat(rom_dict,platform):
    '''
    creates a dat file from a rom dict
    '''
    # Load the XSD schema
    xsd_file = "datafile/datafile.xsd"
    schema = etree.XMLSchema(file=xsd_file)

    # Create the root element of the XML tree
    root = etree.Element("datafile")

    # Create child elements and set their values
    header = etree.SubElement(root, "header")
    name = etree.SubElement(header, "name")
    name.text = f'MAME {platform} Unmatched'
    # Add other child elements and their values as needed

    for game_name, game_details in rom_dict.items():
        #print(f'writing contents for {game_name}')
        game = etree.SubElement(root, "game")
        game.set("name", game_name)
        # Set other attributes for the game element as needed

        # Create child elements for the ROM details and set their values
        description = etree.SubElement(game, "description")
        description.text = game_details.get("description", "")

        for rom_name, rom_details in game_details.items():
            # Add the ROM file details as sub-elements
            rom = etree.SubElement(game, "rom")
            rom.set("name", rom_name)
            try:
                rom.set("size", rom_details['@size'])
            except:
                print(f'error setting size for rom_name:\n{rom_details}')
            if '@crc' in rom_details:
                rom.set("crc", rom_details['@crc'])
            if '@md5' in rom_details:
                rom.set("md5", rom_details['@md5'])
            if '@sha1' in rom_details:
                rom.set("sha1", rom_details['@sha1'])

    # Create the XML tree
    tree = etree.ElementTree(root)

    # Validate the XML tree against the XSD schema
    is_valid = schema.validate(tree)
    
    dat_file = f'dat/mame {platform} unmatched.dat'
    # write the XML tree if valid
    if not is_valid:
        pass
        #print("The XML tree is not valid according to the XSD schema.")
    xml_string = etree.tostring(tree, xml_declaration=True, pretty_print=True, doctype='<!DOCTYPE datafile PUBLIC "-//Logiqx//DTD ROM Management Datafile//EN" "http://www.logiqx.com/Dats/datafile.dtd">', encoding="UTF-8").decode("UTF-8")
    try:
        with open(dat_file, 'w', encoding='utf-8') as f:
            f.write(xml_string)
    except FileNotFoundError:
        print(f"Error: The file {dat_file} was not found.")



def remove_dupe_dat_entries(platform_dat_dict):
    # dedupe entries in other dats that exist in redump
    dupe_count = 0
    for lookup_dat, lookup_hash_dict in platform_dat_dict['hashes'].items():
        pop_list = []
        # get current dat group
        dat_group = platform_dat_dict['dat_group'][lookup_dat]
        # skip redump 
        if dat_group == 'redump':
            continue
        # look for each source ID for this dat across all the DATs
        for source_id in lookup_hash_dict:
            for dat, hash_dict in platform_dat_dict['hashes'].items():
                # skip cases where the source and dest is same group
                if dat_group == platform_dat_dict['dat_group'][dat]:
                    continue
                if source_id in hash_dict:
                    pop_list.append(source_id)

        for to_delete in pop_list:
            if to_delete in lookup_hash_dict:
                lookup_hash_dict.pop(to_delete)
                dupe_count += 1
    print(f'removed {dupe_count} duplicate DAT entries')
                
def get_raw_rom_entry(dat_entry):
    rom_elements = dat_entry.findall('rom')
    rom_strings = [ET.tostring(rom, encoding='unicode').strip() for rom in rom_elements]
    return rom_strings





    




