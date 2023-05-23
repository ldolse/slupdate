import re, xmltodict, hashlib
import xml.etree.ElementTree as ET
import html
from  lxml import etree, html


'''
Softlist processing functions
'''



def get_sl_descriptions(softlist,dat_type,field):
    '''
    softlist is a list of software list dictionaries
    field is one of the field names in the soft list
    '''
    sl = []
    for item in softlist[dat_type]:
        sl.append(item[field])
    return sl

def sl_romhashes_to_dict(comment):
    xmlheader = '<?xml version="1.0" ?><root>'
    xmlclose = '</root>'
    comment = re.sub(r'&','&amp;',comment)
    fixed_comment = xmlheader+comment+xmlclose
    try:
        commentdict = xmltodict.parse(fixed_comment)
        return commentdict
    except:
        print(comment)
        print('\033[0;31mfailed to parse romhash comment\033[00m')
        return None


def process_sl_rom_sources(softdict):
    '''
    iterates through the rom entires in a Software List dict to build fingerprint hashes.
    cue and gdi files are ignored for hashes and size calculations as they can change over
    time.  multiple discs are listed serially in the same object, so cue/gdi are used as
    separators
    '''
    print('Building Source fingerprints from software list')
    crc_hashlookup = False
    for game_title, game_data in softdict.items():
        hashtype = '@sha1'
        source_type = 'source_sha'
        total_size = 0
        sizes = {}
        concatenated_hashes = {}
        source_fingerprints = {}
        current_disc_number = 0
        current_concatenated_hash = ''
        #print(game_title)
        if 'rom' in game_data:
            if not isinstance(game_data['rom'], list):
                game_data['rom'] = [game_data['rom']]
            # some older soft lists put the cue at the end of the list of roms, handle automatically for single discs
            cue_count = sum(1 for rom in game_data['rom'] if rom['@name'].lower().endswith('.cue') or rom['@name'].endswith('.gdi'))
            if cue_count <= 1:
                current_disc_number = 1
            if cue_count == 0:
                print(game_title+' has no cue or gdi file in source reference, not supported at this time')
            first = True
            for rom in game_data['rom']:
                toc = False
                normal_toc = False
                reverse_toc = False
                if hashtype not in rom:
                    crc_hashlookup = True
                    hashtype = '@crc'
                    source_type = 'source_crc_sha'
                if rom['@name'].lower().endswith(('.cue', '.gdi')) and first:
                    normal_toc = True
                elif first and cue_count > 1:
                    current_disc_number += 1
                if rom['@name'].lower().endswith(('.cue', '.gdi')):
                    toc = True
                try:
                    rom_size = int(rom['@size'])
                except:
                    print('size error for Softlist Entry source ROM: '+game_title)
                    rom_size = 0
                if not rom['@name'].lower().endswith(('.cue', '.gdi')):
                    total_size += rom_size

                if toc and cue_count > 1:
                    current_disc_number += 1
                    current_concatenated_hash = ''
                    total_size = 0
                elif not toc:
                    try:
                        current_concatenated_hash += rom[hashtype]
                    except:
                        print(game_title+' has an error in the commented rom listing') 
                        continue
                if first:
                   first = False
                if current_concatenated_hash:
                    concatenated_hashes.update({current_disc_number : current_concatenated_hash})
                    sizes.update({current_disc_number : total_size})
        
            for disc_number, disc_hash in concatenated_hashes.items():
                sha1 = hashlib.sha1(disc_hash.encode('utf-8')).hexdigest()
                source_fingerprints[f'disc{disc_number}_sha1'] = sha1
                try:
                    game_data['parts'][f'cdrom{disc_number}'][source_type] = sha1
                    game_data['parts'][f'cdrom{disc_number}']['bin_size'] = sizes[disc_number]
                except:
                    print(f'\nkey error for cdrom{disc_number}, in entry \''+game_title+'\'. The softlist entry may not use the correct disc numbering')
                    print('convention.  Single disc sets use \'cdrom\' for the first disc part name, while multi-disk sets use \'cdrom1\'')
                    print('for the first disc part in the set\n')
                    continue
            game_data.update({'discs': source_fingerprints})
    if crc_hashlookup:
        print('some titles did not contain sha1 hashes in sources, crc was also used')
    return crc_hashlookup


def process_comments(soft, sl_dict):
    redumpurl = r'http://redump\.org'
    redump_url = r'http://redump\.org/disc/\d{4,6}/?'
    romhash = r'^(\s+)?<rom name'
    trurip = '(Trurip|trurip)'
    notedict = {}
    notenum = 1
    if '#comment' in soft:
        comments = soft['#comment']
        discnum = 1
    else:
        return None
    if isinstance(comments, str):
        comments = [comments]
    for comment in comments:
        note_entry = ''
        rom_entry = ''
        sourcedict = {}
        commentlines = comment.split('\n')
        for line in commentlines:
            redump_sources = re.findall(redump_url,line)
            if redump_sources:
                for url in redump_sources:
                    sourcedict['disc'+str(discnum)+'source'] = url
                    discnum += 1
            elif re.match(romhash,line):
                rom_entry = rom_entry+line.strip()+'\n'
            else:
                note_entry = note_entry+line.strip()+'\n'
        if sourcedict:
            try:
                sl_dict[soft['@name']].update(sourcedict)
            except:
                sl_dict.update({soft['@name']:sourcedict})
        if rom_entry:
            # convert commented DAT entries to a dict list
            commentdict = sl_romhashes_to_dict(rom_entry)
            if commentdict: 
                try:
                    sl_dict[soft['@name']].update(commentdict['root'])
                except:
                    sl_dict.update({soft['@name']:commentdict['root']})
        if note_entry:
            notedict['note'+str(notenum)] = note_entry
            notenum += 1
            try:
                sl_dict[soft['@name']].update(notedict)
            except:
                sl_dict.update({soft['@name']:notedict})
        
def build_sl_dict(softlist, sl_dict):
    '''
    grabs useful sofltist data and inserts into a simple to manage dict
    '''
    for soft in softlist:
        soft_id = soft['@name']
        soft_description = soft['description']
        soft_entry = {
            'description' : soft_description,
        }
        # process info tags
        if 'info' in soft:
            for tag in soft['info']:
                if tag['@name'] == 'serial':
                    soft_entry.update({'serial':tag['@value']})
                if tag['@name'] == 'release':
                    soft_entry.update({'release':tag['@value']})
        sl_dict.update({soft_id:soft_entry})
        # converts comments to dict
        process_comments(soft, sl_dict)
        if not isinstance(soft['part'], list):
            if soft['part']['@name'] == 'cdrom':
                # rename single cd name to match 1st of multiple
                soft['part']['@name'] = 'cdrom1'
            soft['part'] = [soft['part']]
        sl_dict[soft['@name']].update({'parts':{}})
        for disc in soft['part']:
            disk_entry = {disc['@name']:{'chd_filename': disc['diskarea']['disk']['@name']}}
            if '@sha1' in disc['diskarea']['disk']:
                disk_entry[disc['@name']].update({'chd_sha1' : disc['diskarea']['disk']['@sha1']})
            sl_dict[soft['@name']]['parts'].update(disk_entry)
    # build source hashes based on parsed comments
    crc_hashlookup = process_sl_rom_sources(sl_dict)
    return crc_hashlookup


def print_discs(softlist):
    for item in my_soft['software']:
        pprint.pprint(item['part'])


def print_sha1s(softlist):
    for item in my_soft['software']:
        print('mame name is '+item['@name']+' and description is '+item['description'])
        if isinstance(item['part'], list):
            discnum = 1
            for disc in item['part']:
                #pprint.pprint(disc)
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
    with open(softlist_xml_file, 'r', encoding='utf-8') as f:
        xml_string = f.read()
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
        new_key = html.unescape(entity_str)
        # add the new key and the matched tag as the value to the dictionary
        lxml_changes[new_key] = entity_str
    return lxml_changes

def update_softlist_chd_sha1s(softlist_xml_file, soft_dict):
    # build a dictionary for whitespace in tags that lxml will delete
    tags_with_whitespace = get_lxml_replacements(softlist_xml_file)
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
    tree = etree.parse(softlist_xml_file, parser)
    root = tree.getroot()
    for software in root.findall('software'):
        soft_entry_parts = {}
        needs_update = False
        try:
            soft_entry_parts = soft_dict[software.get('name')]['parts']
        except:
            # print an error as this is unexpected:
            print('Unexpected mismatch in for game title '+software.get('name')+'\nSoftlist: '+softlist_xml_file)
            continue
        for part, part_data in soft_entry_parts.items():
            if 'new_sha1' in part_data:
                needs_update = True
        if needs_update:
            # map single disk back correctly (was rewritten for source matching)
            if len(soft_entry_parts) == 1 and 'cdrom1' in soft_entry_parts:
                soft_entry_parts['cdrom'] = soft_entry_parts.pop('cdrom1')
            for part in software.findall('part'):
                if 'new_sha1' in soft_entry_parts[part.get('name')]:
                    diskarea = part.find('diskarea')
                    disk = diskarea.find('disk')
                    disk.set('sha1', soft_entry_parts[part.get('name')]['new_sha1'])
        else:
            continue
    # Write the updated XML to disk while preserving the original comments
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
    with open(softlist_xml_file, "w",encoding='utf-8') as f:
        f.write(output)


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
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False,strip_cdata=False)
    tree = etree.parse(softlist_xml_file, parser)

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

    # Write the updated XML to disk while preserving the original comments
    output = etree.tostring(
        tree,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
        doctype='<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">'
    ).decode("UTF-8")

    with open(softlist_xml_file, "w",encoding='utf-8') as f:
        f.write(output)

def add_redump_names_to_slist(softlist_xml_file, answerdict,redump_name_list):
    '''
    writes redump name tags to slist entry just before the 'part' tag
    no longer used but can be extended/repurposed later
    '''
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False,strip_cdata=False)
    tree = etree.parse(softlist_xml_file, parser)
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

    # Write the updated XML to disk while preserving the original comments
    output = etree.tostring(
        tree,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
        doctype='<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">'
    ).decode("UTF-8")

    with open(softlist_xml_file, "w",encoding='utf-8') as f:
        f.write(output)




'''
dat processing functions
'''
def build_dat_dict(datfile,raw_dat_dict,dat_dict,crc_hashlookup):
    '''
    grabs data from dat structure puts it into a new dict
    '''
    if 'dat_group' not in dat_dict:
        dat_dict.update({'dat_group':{}})
    if 'redump_unmatched' not in dat_dict:
        dat_dict.update({'redump_unmatched':{}})
    if 'hashes' not in dat_dict:
        dat_dict.update({'hashes':{}})
    keyresult, nameresult = create_dat_hash_dict(raw_dat_dict,crc_hashlookup)
    dat_dict['hashes'].update({datfile : keyresult})
    dat_dict['redump_unmatched'].update({datfile : nameresult})
    group = get_dat_header_info(datfile,'url').lower()    
    if 'tosec' in group:
        dat_dict['dat_group'].update({datfile : 'TOSEC'})
    elif 'redump' in group:
        dat_dict['dat_group'].update({datfile : 'redump'})
    else:
        dat_dict['dat_group'].update({datfile : 'other'})


def build_dat_dict_xml(datfile,dat_dict):
    '''
    grabs useful data from dat structure puts it into a dict
    '''
    tree = ET.parse(datfile)
    root = tree.getroot()
    dat_dict.update({datfile : create_dat_hash_dict_xml(root)})



def create_dat_hash_dict(raw_dat_dict,crc_hashlookup):
    keyresult = {}
    nameresult = {}
    for game in raw_dat_dict['game']:
        file_list = {}
        name = game['@name']
        files = len(game['rom'])
        size = 0
        sha1 = hashlib.sha1()
        for rom in game['rom']:
            file_list.update({rom['@name']:rom['@crc']})
            if not rom['@name'].lower().endswith(('.cue', '.gdi')):
                sha1.update(rom['@sha1'].encode('utf-8'))
                size = size + int(rom['@size'])
        sha1_digest = sha1.hexdigest()
        if sha1_digest in keyresult:
            print('duplicate dat entry for '+name)
        keyresult[sha1_digest] = {
            'name': name,
            'files': files,
            'size': size,
            'file_list': file_list
        }
        # enabled if sources in softlist didn't always use sha1 hashes
        if crc_hashlookup:
            crc_sha1 = hashlib.sha1()
            for rom in game['rom']:
                if not rom['@name'].lower().endswith(('.cue', '.gdi')):
                    crc_sha1.update(rom['@crc'].encode('utf-8'))
            crc_sha1_digest = crc_sha1.hexdigest()
            if crc_sha1_digest in keyresult:
                print('duplicate dat entry for '+name)
                print('overwriting '+keyresult[crc_sha1_digest]['name'])
            keyresult[crc_sha1_digest] = {
                'name': name,
                'files': files,
                'size': size,
                'file_list': file_list
            }
        # enables name to hash lookups based on softlist descriptions/redump serials
        nameresult[name] = {
            'sha1_digest' : sha1_digest
        }
    return keyresult, nameresult


def create_dat_hash_dict_xml(datroot):
    '''
    same as create_dat_hash_dict but uses xml the whole time
    '''
    result = {}
    for game in datroot.findall('game'):
        name = game.get('name')
        files = len(game.findall('rom'))
        size = sum(int(rom.get('size')) for rom in game.findall('rom'))
        sha1 = hashlib.sha1()
        for rom in game.findall('rom'):
            if not rom.get('name').lower().endswith(('.cue', '.gdi')):
                sha1.update(rom.get('sha1').encode('utf-8'))
        sha1_digest = sha1.hexdigest()
        result[sha1_digest] = {
            'name': name,
            'files': files,
            'size': size,
        }
    return result
    
def shift_sibling_comments(xml_file):
    import lxml.etree, lxml.html
    parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
    tree = etree.parse(xml_file, parser)
    root = tree.getroot()

    for child in root.iterchildren():
        # if the child is software tag
        if len(child) > 1 and child.tag == "software":
            firstsibling = True
            for sibling in child.itersiblings(preceding=True):
                if not firstsibling:
                    break
                if isinstance(sibling, lxml.etree._Comment):
                    comment_string = etree.tostring(sibling)
                    #comment_bytes = str(lxml.html.tostring(sibling))
                    #comment_string = comment_bytes.decode('UTF-8')
                    if comment_string.endswith(b'-->\n\t'):
                        print('shifting comment\n',lxml.html.tostring(sibling))
                        sibling.tail = '\n\t\t'
                        child.insert(0,sibling)
                firstsibling = False

            # iterate through the child's siblings to find any comments outside the set of tags
#            if isinstance(child[-1], lxml.etree._Comment):
#                print('sibling minus one is:\n',lxml.html.tostring(child[-1]))
#            previous_child = child[-1]
#            for sibling in previous_child.itersiblings(preceding=True):

#                if isinstance(sibling, lxml.etree._Comment): # check if sibling is a comment
#                    print('found a comment')
#                    # move the comment inside the last tag of the set
#                    child[-1].insert(-1, sibling)

        # save the modified XML document
    output = etree.tostring(
        tree,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
        doctype='<!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">'
    ).decode("UTF-8")

    with open(xml_file, "w") as f:
        f.write(output)



def get_dat_header_info(dat_path,field):
    tree = ET.parse(dat_path)
    root = tree.getroot()
    try:
        tag_data = root.find('header/'+field).text
        return tag_data
    except:
        return ''

def get_dat_author(dat_path):
    tree = ET.parse(dat_path)
    root = tree.getroot()
    author = root.find('header/author').text
    return author


def get_dat_name(dat_path):
    tree = ET.parse(dat_path)
    root = tree.getroot()
    name = root.find('header/name').text
    name = html.unescape(name)
    return name
    