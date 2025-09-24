import re, hashlib, xmltodict
from html import unescape
from lxml import etree
from typing import Optional

class SoftwareList:
    """
    Represents a MAME software list DAT file.
    """
    def __init__(self, path: str, chd_directory: Optional[str] = None):
        self.path = path  # Full path to the XML file (e.g., /MAME/hash/psx.xml)
        self.chd_directory = chd_directory  # Path to CHD directory for this Software List


def convert_xml(file, comments=False):
    '''converts software list xml to a dictionary'''
    try:
        fileptr = open(file, 'r' ,encoding='utf-8')
        xml_content= fileptr.read()
        my_ordered_dict=xmltodict.parse(xml_content, process_comments=comments, force_list=('info','rom',))
        return dict(my_ordered_dict['softwarelist'])
    except FileNotFoundError:
        print(f"Error: The file {file} was not found.")

def get_sl_descriptions(softlist,dat_type,field):
    '''
    returns a list of descriptions from a softlist
    softlist is a list of software list dictionaries
    field is one of the field names in the soft list
    '''
    sl = []
    for item in softlist[dat_type]:
        sl.append(item[field])
    return sl

def comment_xml_to_dict(xml_string):
    '''
    takes dat source xml strings extracted from
    comments and converts them to a dictionary
    '''
    root = etree.fromstring(xml_string)

    file_list = {}
    for rom in root.findall('rom'):
        name = rom.get('name')
        size = rom.get('size')
        md5 = rom.get('md5')
        sha1 = rom.get('sha1')
        crc = rom.get('crc')

        file_dict = {}
        if size:
            file_dict['@size'] = size
        if crc:
            file_dict['@crc'] = crc
        if md5:
            file_dict['@md5'] = md5
        if sha1:
            file_dict['@sha1'] = sha1

        file_list[name] = file_dict

    return {'file_list': file_list}



def sl_romhashes_to_dict(comment):
    '''
    takes a romhash comment and converts it to a dictionary
    '''
    xmlheader = '<?xml version="1.0" ?><root>'
    xmlclose = '</root>'
    comment = re.sub(r'&','&amp;',comment)
    fixed_comment = xmlheader+comment+xmlclose
    try:
        commentdict = comment_xml_to_dict(fixed_comment)
        return commentdict
    except Exception as error:
        print(f'\033[0;31mfailed to parse romhash comment {error} \033[00m')
        print(comment)
        return None

def update_sl_rom_source_ids(concatenated_hashes,soft_title,soft_data,source_type,sizes,known_disc=''):
    '''
    takes concatenated hashes and calculates a sha1 checksum
    source_type defines the type of hash used.
    Both are added to a tuple which is then added to the disc
    known_disc is used for cases where this function is called for a single known disc name
    total binary size is also updated here but not currently added to the tuple
    '''
    source_fingerprints = {}
    for disc_number, disc_hash in concatenated_hashes.items():
        # if the disc reference is submitted during the call use that
        if known_disc:
            disc_ref = known_disc
        # otherwise calculate the disc reference from the number keys in the dict
        else:
            # single disc sets use zero for the first reference, no number added
            if disc_number == 0:
                disc_ref = 'cdrom'
            else:
                # multi-disc sets always start with the disc number appended to cdrom
                disc_ref = f'cdrom{disc_number}'

        sha1 = hashlib.sha1(disc_hash.encode('utf-8')).hexdigest()
        source_fingerprints[f'disc{disc_number}_sha1'] = sha1
        try:
            soft_data['parts'][disc_ref]['source_sha'] = (sha1,source_type)
            soft_data['parts'][disc_ref]['bin_size'] = sizes[disc_number]
            soft_data['source_parsed'] = True
        except:
            print(f'\nkey error for {disc_ref}, in entry \''+soft_title+'\'. The softlist entry may not use the correct disc numbering convention,')
            print('or the source references don\'t use the toc file as a delimiter.  Single disc sets use \'cdrom\' for the first')
            print('disc part name, while multi-disk sets use \'cdrom1\' for the first disc part in the set\n')
            continue

    soft_data.update({'discs': source_fingerprints})


def rom_entries_to_source_ids(soft_title,raw_rom_source_data):
    '''
    takes a list of rom entries and builds a concatenated hash
    for each disc in the set.  The concatenated hash is then
    hashed to create a sha1 checksum for the source.  The source
    type is also determined here.  The sizes of the files are
    also summed for each disc
    '''
    hashtype = '@sha1'
    source_type = 'sha1'
    total_size = 0
    sizes = {}
    concatenated_hashes = {}
    current_disc_number = 0
    current_concatenated_hash = ''
    # some older soft lists put the cue at the end of the list of roms, handle automatically for single discs
    cue_count = sum(1 for rom in raw_rom_source_data.keys() if rom.lower().endswith('.cue') or rom.endswith('.gdi'))
    iso_count = sum(1 for rom in raw_rom_source_data.keys() if rom.lower().endswith('.iso'))
    ccd_count = sum(1 for rom in raw_rom_source_data.keys() if rom.lower().endswith('.ccd'))
    if ccd_count >= 2:
        print(f'{soft_title} contains multiple clonecd discs, this is not yet supported')
        return concatenated_hashes, source_type, sizes
    first = True
    for rom,rom_data in raw_rom_source_data.items():
        toc = False
        if rom.lower().endswith(('.cue', '.gdi')) and first:
            # expected case, continue
            pass
        # if the first file wasn't a TOC but this is a multi-disc set, increment disc number
        # multi disc sets always append an integer to 'cdrom'
        elif first and cue_count > 1:
            current_disc_number += 1
        elif first and iso_count > 1 and cue_count != 1:
            current_disc_number += 1

        if rom.lower().endswith(('.cue', '.gdi')):
            toc = True

        try:
            rom_size = int(rom_data['@size'])
        except:
            print('size error for Softlist Entry source ROM: '+soft_title)
            rom_size = 0

        if not toc:
            total_size += rom_size

        if toc and cue_count > 1:
            current_disc_number += 1
            current_concatenated_hash = ''
            total_size = 0
        elif not toc:
            if hashtype not in rom_data:
                hashtype = '@crc'
                source_type = 'crc'
            try:
                current_concatenated_hash += rom_data[hashtype]
            except:
                print(soft_title+' has an error in the commented rom listing')
                continue
        if first:
           first = False
        if current_concatenated_hash:
            concatenated_hashes.update({current_disc_number : current_concatenated_hash})
            sizes.update({current_disc_number : total_size})

    return concatenated_hashes, source_type, sizes


def process_sl_rom_sources(sl_dict):
    '''
    iterates through the rom entires in a Software List dict to build fingerprint hashes.
    cue and gdi files are ignored for hashes and size calculations as they can change over
    time.  multiple discs are listed serially in the same object, so cue/gdi are used as
    separators
    '''
    print('Building Source fingerprints from software list')
    for soft_title, soft_data in sl_dict.items():
        if 'rom' in soft_data:
            concatenated_hashes, source_type, sizes = rom_entries_to_source_ids(soft_title,soft_data['rom'])
            # update the softlist dict with source ids
            if concatenated_hashes:
                update_sl_rom_source_ids(concatenated_hashes,soft_title,soft_data,source_type,sizes)

def split_data_by_discs(commmentlines):
    '''
    takes a comment string and splits it into separate comment groups based on the presence of a TOC file
    '''
    discs = []
    current_disc = ''
    lines = commmentlines.split('\n')
    toc_first = False
    for i, line in enumerate(lines):
        toc = False
        if re.search(r'rom name="[^"]+\.(cue|gdi)"', line):
            toc = True
        if toc and i == 0:
            toc_first = True
            current_disc += line.strip()
            # skip any further logic for this case
            continue
        # if it's a another TOC file append the current to the discs and reset
        if toc_first and toc:
            discs.append(current_disc)
            current_disc = line.strip()
        # in this case add the toc to the current disc and start a new one
        elif not toc_first and toc:
            current_disc += line.strip()
            discs.append(current_disc)
            current_disc = ''
        # keep adding tracks to the current disc otherwise
        else:
            current_disc += line.strip()
    # add the last disc to the disc list
    if current_disc not in discs:
        discs.append(current_disc)
    return discs


def process_commentlines(raw_comment_lines):
    '''
    takes a comment string and separates out dat rom entries from the notes
    '''
    romhash = r'^(\s+)?<rom name'
    redump_url = r'http://redump\.org/disc/\d{2,6}/?'
    note_entry = ''
    rom_entry = ''
    redump_sources = []

    commentlines = raw_comment_lines.split('\n')
    for line in commentlines:
        redump_urls = re.findall(redump_url,line)
        if redump_urls:
            redump_sources += redump_urls
        elif re.match(romhash,line):
            rom_entry = rom_entry+line.strip()+'\n'
        else:
            note_entry = note_entry+line.strip()+'\n'
    return note_entry,rom_entry,redump_sources




def process_comments(soft_entry, sl_dict):
    '''
    takes a softlist entry and processes the comments into a dictionary
    '''
    def comment_to_sl_dict(soft,raw_comment_dict,sl_dict):
        '''
        takes a comment dictionary and adds the parsed data to the softlist dictionary
        '''
        s_name = soft['@name']
        split_sources = False
        toc = r'(\.(cue|gdi))'
        trurip = '(Trurip|trurip)'
        redump_sources = []
        rom_sources = {}
        notenum = 1
        mismatch = False
        disc_count = len(sl_dict[s_name]['parts'])
        # get number of TOC files in the comment
        total_toc = sum(len(re.findall(toc, comment)) for comments in raw_comment_dict.values() for comment in comments)
        if disc_count != total_toc and total_toc > 0:
            print(f' * mismatched toc/disc count for {s_name} {total_toc} toc / {disc_count} disc(s)\n   - Please ensure the source references are attached to the correct disc')
            mismatch = True
        if disc_count > 1:
            split_sources = True
        for comment_location, comments in raw_comment_dict.items():
            notedict = {}
            rom_entry = ''
            notes = ''
            for comment in comments:
                if split_sources and len(re.findall(toc, comment)) > 1:
                    # add lines which aren't rom entries to a new comment until we hit a rom line
                    commentlines = comment.split('\n')
                    romhash = r'^(\s+)?<rom name'
                    info_comments = ''
                    rom_comments = ''
                    for line in commentlines:
                        if re.match(romhash,line.strip()):
                            rom_comments += line.strip()+'\n'
                        else:
                            line = line.strip()
                            if line:
                                info_comments += line.strip()+'\n'
                    #print(f'rom_comments are\n{rom_comments}')
                    comments_by_disc = split_data_by_discs(rom_comments)
                    #print(f'have {len(comments_by_disc)} rom comments in {s_name}')
                    # separate out the individual comment lines to the different types of comments
                    note_entry,rom_entry,redump_source_info = process_commentlines(info_comments)
                    notes += note_entry.strip()
                    redump_sources += redump_source_info
                    disc = 1
                    for disc_comm in comments_by_disc:
                        note_entry,rom_entry,redump_source_info = process_commentlines(disc_comm)
                        notes += note_entry.strip()
                        redump_sources += redump_source_info
                        if rom_entry:
                            # convert commented DAT entries to a dict list
                            rom_sources['cdrom'+str(disc)] = sl_romhashes_to_dict(rom_entry)
                            disc +=1
                else:
                    note_entry,rom_entry,redump_source_info = process_commentlines(comment)
                    notes += note_entry
                    redump_sources += redump_source_info
                    # convert commented DAT entries to a dict
                    if rom_entry:
                        # keep the comment associated with the assigned disc
                        if comment_location.startswith('cdrom'):
                            rom_sources[comment_location] = sl_romhashes_to_dict(rom_entry)
                        # if discs/sources mismatch for a single disc, assign to the first disc
                        elif mismatch:
                            rom_sources['cdrom1'] = sl_romhashes_to_dict(rom_entry)
                        else:
                            rom_sources['cdrom'] = sl_romhashes_to_dict(rom_entry)

            # set the proper destinations based on whether the comment came from the root of
            # the softlist or if it came from a disc part
            if comment_location == 'main_entry':
                comment_dest = sl_dict[s_name]
                except_dest_outer = sl_dict
                except_dest_inner = s_name
            elif comment_location.startswith('cdrom'):
                comment_dest = sl_dict[s_name]['parts'][comment_location]
                except_dest_outer = sl_dict[s_name]['parts'][comment_location]
                except_dest_inner = comment_location
            if rom_sources:
                # concatenate the hashes from the rom dict if it was directly associated with a disc
                #if rom_dict and comment_location.startswith('cdrom'):
                for location, rom_data in rom_sources.items():
                    if location.startswith('cdrom'):
                        try:
                            comment_dest = sl_dict[s_name]['parts'][location]
                        except:
                            print(f'Error writing hashes for {s_name}, {location}, check the softlist entry')
                    else:
                        location = 'cdrom'
                    concatenated_hashes, source_type, sizes = rom_entries_to_source_ids(s_name,rom_data['file_list'])
                    update_sl_rom_source_ids(concatenated_hashes,s_name,sl_dict[s_name],source_type,sizes,location)
                    # store the raw source info for troubleshooting or dat creation
                    try:
                        comment_dest.update(rom_data)
                    except Exception as error:
                        print(f'got an error trying to update this note {error}, {rom_sources}')
                        except_dest_outer.update({comment_location:rom_sources})
            # handle notes
            if notes:
                notedict['note'+str(notenum)] = notes
                notenum += 1
                try:
                    comment_dest.update(notedict)
                except Exception as error:
                    print(f'got an error trying to update this note {error}, {notedict}')
                    except_dest_outer.update({except_dest_inner:notedict})

            if redump_sources:
                if len(redump_sources) == 1 and comment_location == 'main_entry':
                    if 'cdrom' in sl_dict[s_name]['parts']:
                        sl_dict[s_name]['parts']['cdrom'].update({'redump_url':redump_sources[0].strip()})
                    else:
                        print(f'could not find the cdrom disc to insert redump url for {soft["@name"]}')
                elif len(redump_sources) == 1 and comment_location.startswith('cdrom'):
                    if comment_location in sl_dict[s_name]['parts']:
                        sl_dict[s_name]['parts'][comment_location].update({'redump_url':redump_sources[0].strip()})
                    else:
                        print(f'could not find the {comment_location} disc to insert redump url for {soft["@name"]}')
                else:
                    discnum = 1
                    for url in redump_sources:
                        disc = 'cdrom'+str(discnum)
                        if disc in sl_dict[s_name]['parts']:
                            sl_dict[s_name]['parts'][disc].update({'redump_url':url.strip()})
                        else:
                            print(f'could not find the {disc} to insert redump url for {soft["@name"]}')
                        discnum += 1

    raw_comment_dict = {}
    if '#comment' in soft_entry:
        if not isinstance(soft_entry['#comment'], list):
            soft_entry['#comment'] = [soft_entry['#comment']]
        raw_comment_dict.update({'main_entry':soft_entry['#comment']})
    for disc in soft_entry['part']:
        if '#comment' in disc:
            if not isinstance(disc['#comment'], list):
                disc['#comment'] = [disc['#comment']]
            raw_comment_dict.update({disc['@name']:disc['#comment']})
    if len(raw_comment_dict) == 0:
        return None
    else:
        comment_to_sl_dict(soft_entry,raw_comment_dict,sl_dict)

def expand_serial_range(serial_range):
    '''
    expands a serial range into a list of serial numbers
    '''
    start, end = serial_range.split('~')
    prefix = re.match(r"([A-Za-z-]+)", start).group(1)
    start_num = re.search(r"\d+", start).group()
    end_num = re.search(r"\d+", end).group()

    serial_numbers = [prefix + str(num).zfill(len(start_num)) for num in range(int(start_num), int(end_num) + 1)]
    return serial_numbers

def sanitize_serials(raw_serial,platform):
    '''
    takes a raw serial string and returns a list of serials
    '''
    # some platforms use bracket comments
    bracket_c = ['dc','psx']
    serials = []
    if platform in bracket_c: # delete bracketed in serial comments
        raw_serial = re.sub(r'\([^\)]+\)','',raw_serial)
    if platform == 'psx':  # add back hyphen for cases where space is used
        raw_serial = re.sub(r'([A-Z]{4})\s(\d{5})', r'\1-\2', raw_serial)
    for serial in raw_serial.replace(' ',',').split(','):
        if platform == 'psx':
            if re.findall(r'(\d+)~([A-Z]+)',serial):
                try:
                    serials += expand_serial_range(serial.strip())
                    continue
                except:
                    print(f'error expanding serial string {serial}')
        if serial.strip():
            serials.append(serial.strip())
    return list(filter(None,serials))

def build_sl_dict(softlist, sl_dict,platform):
    '''
    softlist: raw softlist data from xmltodict
    sl_dict: dictionary to build
    platform: platform key
    grabs useful sofltist data and inserts into a simpler dict object
    '''
    for soft in softlist:
        soft_id = soft['@name']
        soft_description = soft['description']
        soft_entry = {
            'description' : soft_description,
            'source_found' : False,
            'source_parsed': False
        }
        # process info tags
        if 'info' in soft:
            for tag in soft['info']:
                if tag['@name'] == 'serial':
                    soft_entry.update({'rawserial':tag['@value']})
                    soft_entry['serial'] = sanitize_serials(soft_entry['rawserial'],platform)
                if tag['@name'] == 'release':
                    soft_entry.update({'release':tag['@value']})
        sl_dict.update({soft_id:soft_entry})
        if not isinstance(soft['part'], list):
            soft['part'] = [soft['part']]
        sl_dict[soft['@name']].update({'parts':{}})
        for disc in soft['part']:
            # skip data area references used for non optical media types
            if 'dataarea' in disc:
                continue
            disk_entry = {disc['@name']:{'chd_filename': disc['diskarea']['disk']['@name']}}
            if '@sha1' in disc['diskarea']['disk']:
                disk_entry[disc['@name']].update({'chd_sha1' : disc['diskarea']['disk']['@sha1']})
            disk_entry[disc['@name']].update({'chd_found' : False})
            sl_dict[soft['@name']]['parts'].update(disk_entry)
        # converts comments to dict
        process_comments(soft, sl_dict)
    # build source hashes based on parsed comments
    process_sl_rom_sources(sl_dict)

def print_sha1s(softlist):
    for item in softlist['software']:
        print('mame name is '+item['@name']+' and description is '+item['description'])
        if isinstance(item['part'], list):
            discnum = 1
            for disc in item['part']:
                try:
                    print('      disc '+str(discnum)+' sha1  is '+disc['diskarea']['disk']['@sha1'])
                except:
                    print('      disc '+str(discnum)+' has no sha1')
                discnum += 1
        else:
            print('     sha1  is '+item['part']['diskarea']['disk']['@sha1'])

def get_lxml_replacements(softlist_xml_file):
    '''
    this finds a few cases that lxml changes and keeps track of the original string
    to restore it after processing by lxml:
     - trailing whitespace from self closed tags - there are a lot of these so retain
       to keep changes to a minimum
    - double quote entities are converted to quotes by lxml, convert back to entity later

    function builds a dictionary of each case to find the impacted strings so they can
    be changed back after lxml has updated the xml
    '''
    entity_list = re.compile(r'>[^<]+?(&quot;)[^<]+?<')
    try:
        with open(softlist_xml_file, 'r', encoding='utf-8') as f:
            xml_string = f.read()
    except FileNotFoundError:
        print(f'Error reading {softlist_xml_file}')
        return None
    tag_regex = re.compile(r'<[^>]+? />')
    lxml_changes = {}
    for match in tag_regex.finditer(xml_string):
        # get the matched tag as a string
        tag_str = match.group(0)
        # replace " />" with "/>" to create the new key
        new_key = tag_str.replace(" />", "/>")
        # add the new key and the matched tag as the value to the dictionary
        lxml_changes[new_key] = tag_str
    for match in entity_list.finditer(xml_string):
        # get the matched tag as a string
        entity_str = match.group(0)
        # unescape the entities to create the new key
        new_key = unescape(entity_str)
        # add the new key and the matched tag as the value to the dictionary
        lxml_changes[new_key] = entity_str
    return lxml_changes


def write_softlist_output(tree,softlist_xml_file,tags_with_whitespace):
    '''
    writes the updated softlist xml to disk, restoring the whitespace that lxml deletes,
    preserving the original entity strings and retaining original comments
    '''
    output = etree.tostring(
        tree,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
        doctype='<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">'
    ).decode("UTF-8")
    # put back the whitespace lxml deleted
    for old_string, new_string in tags_with_whitespace.items():
        output = output.replace(old_string, new_string)
    try:
        with open(softlist_xml_file, 'w', encoding='utf-8') as f:
            f.write(output)
    except FileNotFoundError:
        print(f'Error writing {softlist_xml_file}')

def get_lxml_tree_strings(softlist_xml_file):
    '''
    returns the lxml tree and a dictionary of strings that lxml will change
    '''
    # build a dictionary for whitespace in tags that lxml will delete
    tags_with_whitespace = get_lxml_replacements(softlist_xml_file)
    parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
    tree = etree.parse(softlist_xml_file, parser)
    return tree, tags_with_whitespace

def update_softlist_chd_sha1s(softlist_xml_file, sl_dict):
    '''
    updates the chd sha1s in the softlist xml file
    '''
    tree, tags_with_whitespace = get_lxml_tree_strings(softlist_xml_file)
    root = tree.getroot()
    for software in root.findall('software'):
        soft_entry_parts = {}
        try:
            soft_entry_parts = sl_dict[software.get('name')]['parts']
        except:
            # print an error as this is unexpected:
            print('Unexpected mismatch in for game title '+software.get('name')+'\nSoftlist: '+softlist_xml_file)
            continue
        for part, part_data in soft_entry_parts.items():
            if 'new_sha1' in part_data:
                for part in software.findall('part'):
                    if 'source_group' in soft_entry_parts[part.get('name')]:
                        source_group = soft_entry_parts[part.get('name')]['source_group']
                        if source_group in ['redump', 'TOSEC']: # 'no-intro' - leave out for now
                            good_source = True
                        else:
                            good_source = False
                    if 'new_sha1' in soft_entry_parts[part.get('name')]:
                        diskarea = part.find('diskarea')
                        disk = diskarea.find('disk')
                        if disk is not None:
                            status = disk.get('status')
                            if status == 'nodump':
                                del disk.attrib['status']
                            if status == 'baddump' and good_source:
                                del disk.attrib['status']
                            disk.set('sha1', soft_entry_parts[part.get('name')]['new_sha1'])
        else:
            continue
    write_softlist_output(tree,softlist_xml_file,tags_with_whitespace)



def get_sl_entry(search_list, title, type):
    '''
    dc example: get_sl_entry(mysoft['softwarelist']['software'],'4wt','mame')
    '''
    res = ''
    if type == 'mame':
        res = next((sub for sub in search_list if sub['@name'] == title), None)
    elif type == 'redump':
        res = next((sub for sub in search_list if sub['description'] == title), None)
    else:
        print('unsupported title type')
    return res


def update_sl_descriptions(softlist_xml_file, answerdict):
    '''
    writes updated descriptions to the softlist
    no longer used but can be extended/repurposed later
    '''
    tree, tags_with_whitespace = get_lxml_tree_strings(softlist_xml_file)

    for original_desc, new_desc in answerdict.items():
        if new_desc == 'No Match':
            continue
        else:
            print('rewriting '+original_desc)
            try:
                # Find the software element with the original description
                software = tree.xpath(f"//software[description=$subs]",subs=original_desc)[0]
                # Update the description element with the new description
                description = software.xpath("description")[0]
                description.text = new_desc
            except Exception as e:
                print('new description: '+new_desc+' failed')
                print(e)
                continue
    write_softlist_output(tree,softlist_xml_file,tags_with_whitespace)


def add_redump_names_to_slist(softlist_xml_file, answerdict,redump_name_list):
    '''
    writes redump name tags to slist entry just before the 'part' tag
    no longer used but can be extended/repurposed later
    '''
    tree, tags_with_whitespace = get_lxml_tree_strings(softlist_xml_file)
    root = tree.getroot()

    for soft_desc, redump_name in answerdict.items():
        if redump_name == 'No Match':
            continue
        # don't add a redump name if the description as
        elif redump_name not in redump_name_list:
            continue
        else:
            print('inserting tag in '+soft_desc)
        for software in root.findall('.//software'):
            description = software.find('description').text
            if description == soft_desc:

                # Create the redump_name tag and insert it before the part tag
                new_tag = etree.Element('info', {'name': 'redump_name', 'value': redump_name})
                new_tag.tail = '\n\t\t'
                # Find the index of the part tag
                part_index = software.index(software.xpath('part')[0])
                software.insert(part_index, new_tag)
    write_softlist_output(tree,softlist_xml_file,tags_with_whitespace)

def rewrite_comment_source_group(softlist_xml_file,sl_dict):
    '''
    updates comments in a softlist xml file to reflect the source group and updated hashes
    standardizes the source group names and location of the notes with disc parts
    '''
    old_string = None
    tree, tags_with_whitespace = get_lxml_tree_strings(softlist_xml_file)
    root = tree.getroot()
    replace_strings = ['unknown source']
    for soft,soft_data in sl_dict.items():
        for disc, part_data in soft_data['parts'].items():
            if 'note1' not in part_data:
                # no comment to update
                continue
            else:
                # commment to note handled naively atm, need to update
                for string in replace_strings:
                    print(f'checking {string} for {soft}')
                    if string.lower() in part_data['note1'].lower():
                        old_string = string

                if 'source_group' in part_data and old_string is not None:
                    source_group = part_data['source_group']
                    if 'redump_url' in part_data:
                        new_string =  part_data['redump_url']
                    elif source_group == 'redump':
                        new_string = 'original images (Redump)'
                    elif source_group == 'TOSEC':
                        new_string = 'original images (TOSEC)'
                    elif source_group == 'no-intro':
                        new_string = 'original images (No-Intro non-Redump)'
                    else:
                        continue
                    print(f'updating {soft} {disc} comment - new_string is {new_string}')
                    update_comment_strings(root, soft, old_string, new_string, disc)
                else:
                    continue
    write_softlist_output(tree,softlist_xml_file,tags_with_whitespace)

def update_comment_strings(xml_root, software_name, old_string, new_string, disc):
    '''
    updates the comment strings in a softlist xml entry
    '''
    software_nodes = xml_root.xpath(f'//software[@name="{software_name}"]')
    for software_node in software_nodes:
            replace_comment_string(software_node, old_string, new_string, disc)
            if disc != 'cdrom':
                part_nodes = software_node.xpath(f'part[@name="{disc}"]')
                for part_node in part_nodes:
                    replace_comment_string(part_node, old_string, new_string, disc)
    return xml_root

def replace_comment_string(node, old_string, new_string, disc):
    '''
    replaces a string in a comment node
    '''
    comment_nodes = node.xpath('comment()')
    if disc == 'cdrom':
        c_tail = '\n\t\t'
    else:
        c_tail = '\n\t\t\t'
    unwritten = True
    if comment_nodes:
        for comment_node in comment_nodes:
            comment_head = re.match(r'^\s+',comment_node.text)[0]+new_string+c_tail
            comment_text = comment_node.text.strip()  # Extract comment content as a string

            if old_string in comment_text.lower():
                comment_text = '\n'.join(line for line in comment_text.splitlines() if old_string.lower() not in line.strip().lower())
                # put the new source at the start of the comment
                print('writing the rewritten comment')
                rewritten_comment = etree.Comment(comment_head + comment_text.strip() + c_tail)
                rewritten_comment.tail = c_tail
                node.replace(comment_node, rewritten_comment)
            else:
                continue


def update_rom_source_refs(softlist_xml_file,sl_dict):
    '''
    updates the source references in a softlist xml file to match the dat file
    '''
    tree, tags_with_whitespace = get_lxml_tree_strings(softlist_xml_file)
    root = tree.getroot()
    for soft,soft_data in sl_dict.items():
        if 'update_required' not in soft_data:
            continue
        elif soft_data['update_required']:
            for disc, part_data in soft_data['parts'].items():
                orig_title = 'Unknown/Unmatched'
                if 'raw_rom_entry' in part_data:
                    source_group = part_data['source_group']
                    new_comment_lines = part_data['raw_rom_entry'].copy()
                    if 'redump_url' in part_data:
                        new_comment_lines.insert(0,part_data['redump_url'])
                    elif source_group == 'redump':
                        new_comment_lines.insert(0,'original images (Redump)')
                    elif source_group == 'TOSEC':
                        new_comment_lines.insert(0,'original images (TOSEC)')
                    elif source_group == 'no-intro':
                        new_comment_lines.insert(0,'original images (No-Intro Non-Redump)')
                    if 'original_matches' in part_data:
                        if 'source_name' in part_data['original_matches']:
                            orig_title = part_data['original_matches']['source_name']
                        elif 'file_list' in part_data['original_matches']:
                            source_files = part_data['original_matches']['file_list']
                            orig_title = next(iter(source_files))

                    print(f'\nupdating {soft}, {soft_data["description"]} {disc}')
                    print(f'  Original Source Title: {orig_title}')
                    print(f'     {source_group} Replacement: {part_data["source_name"]}')
                    modify_rom_source_refs(root,soft,new_comment_lines,disc)
    write_softlist_output(tree,softlist_xml_file,tags_with_whitespace)


def modify_rom_source_refs(xml_root, software_name, rom_strings, disc):
    '''
    updates the source reference comments in a softlist xml entry
    '''
    software_nodes = xml_root.xpath(f'//software[@name="{software_name}"]')

    for software_node in software_nodes:
        if disc == 'cdrom':
            handle_comment_nodes(software_node, rom_strings,disc)
        else:
            if rom_strings and rom_strings[0].startswith('http://redump.org'):
                handle_comment_nodes(software_node, [],disc,delete_string=rom_strings[0])
            else:
                handle_comment_nodes(software_node, [],disc)
            part_nodes = software_node.xpath(f'part[@name="{disc}"]')
            for part_node in part_nodes:
                handle_comment_nodes(part_node, rom_strings,disc)
    return xml_root

def handle_comment_nodes(node, rom_strings, disc, delete_string=None):
    '''
    updates the source reference comments in a softlist xml entry
    '''
    delete_strings = ['unknown source','original images (redump)']
    if delete_string is not None:
        delete_strings.append(delete_string)
    if rom_strings and rom_strings[0].startswith('http://redump.org'):
        delete_strings.append(rom_strings[0])
    if rom_strings and not rom_strings[0].startswith('<rom'):
        source_info = True
    else:
        source_info = False
    comment_nodes = node.xpath('comment()')
    if disc == 'cdrom':
        c_head = '\t\t'
        c_tail = '\n\t\t'
    else:
        c_head = '\t\t\t'
        c_tail = '\n\t\t\t'
    unwritten = True
    if comment_nodes:
        counter = 0
        for comment_node in comment_nodes:
            comment_updated = False
            counter +=1
            comment_head = re.match(r'^\s+',comment_node.text)[0]
            comment_text = comment_node.text.strip()  # Extract comment content as a string
            if comment_text.strip() == '':
                # Delete empty comments
                node.remove(comment_node)
                continue

            print(f'comment_text is {comment_text}\ndisc is {disc} loop count is {counter}')
            if rom_strings:
                print(f'rom 1 is:\n{rom_strings[0]}')
            else:
                print('no rom_strings')

            for string in delete_strings:
                comment_text = '\n'.join(line for line in comment_text.splitlines() if string not in line.strip().lower())

            # delete the comment if it's now empty
            if comment_text.strip() == '':
                node.remove(comment_node)

            if any(line.strip().startswith('<rom') for line in comment_text.splitlines()):
                print('removing <rom lines')
                # Remove rom entries from the rewritten comment
                rewritten_comment = ''
                for line in comment_text.splitlines():
                    if line.strip().startswith('<rom'):
                        continue
                    rewritten_comment += c_head + line + '\n'

                # Add the new rom entries to the rewritten comment
                if unwritten:
                    print('writing the new lines to this comment as still unwritten')
                    for rom_string in rom_strings:
                        rewritten_comment += c_head + rom_string + '\n'
                    if source_info:
                        comment_head = ' '

                    unwritten = False

                if rewritten_comment.strip() == '':
                    print('comment empty after modifications')
                    node.remove(comment_node)
                    continue
                else:
                    print('writing the rewritten comment')
                    rewritten_comment = etree.Comment(comment_head + rewritten_comment.strip() + c_tail)
                    rewritten_comment.tail = c_tail
                    node.replace(comment_node, rewritten_comment)
                    continue

            elif counter < len(comment_nodes):
                continue # keep going as there might be better comments to insert into

            elif rom_strings and unwritten:
                print('creating a new comment because no existing comments matched modify rules')
                create_new_comment(node,rom_strings,c_head,c_tail)
                unwritten = False

    elif unwritten and rom_strings:
        print(f'creating a new comment because no comments exist in this {disc} node')
        create_new_comment(node,rom_strings,c_head,c_tail)
        unwritten = False

def create_new_comment(node,rom_strings,c_head,c_tail):
    '''
    creates a new comment node with the rom entries
    '''
    if not rom_strings[0].startswith('<rom'):
        comment_head = ' '
    else:
        comment_head = '\n'
    new_comment_string = ''
    new_comment = etree.Comment(comment_head)
    for rom_string in rom_strings:
        new_comment_string += c_head + rom_string + '\n'
    new_comment = etree.Comment(comment_head + new_comment_string.strip() + c_tail)
    new_comment.tail = c_tail
    node.insert(0, new_comment)


def modify_rom_source_refs_old(xml_root, software_name, rom_strings, disc):
    '''
    updates the source reference information in a softlist xml entry comment
    '''
    software_nodes = xml_root.xpath(f'//software[@name="{software_name}"]')

    for software_node in software_nodes:
        comment_nodes = software_node.xpath('comment()')

        if comment_nodes:
            if len(comment_nodes) > 1:
                import pprint
                pprint.pprint(comment_nodes)
            comment_node = comment_nodes[0]
            comment_text = comment_node.text.strip()  # Extract comment content as a string
            rewritten_comment = ''
        else:
            comment_node = None
            comment_text = ''
            rewritten_comment = '\t\t'

        new_part_comment = ''

        # remove rom entries from the rewritten comment
        for line in comment_text.splitlines():
            if line.strip().startswith('<rom'):
                continue
            rewritten_comment += '\t\t' + line + '\n'

        # if the disc is cdrom then add the new rom entries to the rewritten comment
        if disc == 'cdrom':
            for rom_string in rom_strings:
                rewritten_comment += '\t\t' + rom_string.strip() + '\n'

        elif disc != 'cdrom':
            # write the entries to a new comment to go to the disc part
            for rom_string in rom_strings:
                new_part_comment += '\t\t\t' + rom_string.strip() + '\n'

            # Find the part node with the matching 'name' attribute
            part_node = software_node.xpath(f'part[@name="{disc}"]')[0]
            # Create a new comment with the rom entries
            new_comment = etree.Comment('\n\t\t\t' + new_part_comment.strip() + '\n\t\t\t')
            new_comment.tail = '\n\t\t\t'  # Add newline and indentation to the tail
            part_node.insert(0, new_comment)

        if rewritten_comment.strip():
            rewritten_comment = etree.Comment('\n\t\t' + rewritten_comment.strip() + '\n\t\t')
            rewritten_comment.tail = '\n\t\t'
        else:
            rewritten_comment = None

        if comment_node is not None and rewritten_comment is not None:
            software_node.replace(comment_node, rewritten_comment)
        elif rewritten_comment is not None:
            software_node.insert(0, rewritten_comment)
        elif comment_node is not None and rewritten_comment is None:
            software_node.remove(comment_node)

def shift_sibling_comments(xml_file):
    tree, tags_with_whitespace = get_lxml_tree_strings(xml_file)
    root = tree.getroot()

    for child in root.iterchildren():
        # if the child is software tag
        if len(child) > 1 and child.tag == "software":
            firstsibling = True
            for sibling in child.itersiblings(preceding=True):
                if not firstsibling:
                    break
                if isinstance(sibling, etree._Comment):
                    comment_string = etree.tostring(sibling)
                    #comment_bytes = str(lxml.html.tostring(sibling))
                    #comment_string = comment_bytes.decode('UTF-8')
                    # shift only redump source references
                    if b'http://redump.org' in comment_string and comment_string.endswith(b'-->\n\t'):
                        #print('shifting comment\n',lxml.html.tostring(sibling))
                        sibling.tail = '\n\t\t'
                        child.insert(0,sibling)
                firstsibling = False

    # write the modified XML tree back to the file
    write_softlist_output(tree,xml_file,tags_with_whitespace)