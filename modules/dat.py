import re, xmltodict, hashlib
import xml.etree.ElementTree as ET


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
    for game_title, game_data in softdict.items():
        total_size = 0
        concatenated_hashes = {}
        source_fingerprints = {}
        current_disc_number = 0
        current_concatenated_hash = None
        if 'rom' in game_data:
            toc_list = []
            for rom in game_data['rom']:
                rom_size = int(rom['@size'])
                if not rom['@name'].endswith(('.cue', '.gdi')):
                    total_size += rom_size

                if rom['@name'].endswith(('.cue', '.gdi')):
                    toc_list.append(rom['@name'])
                    current_disc_number += 1
                    current_concatenated_hash = ''
                else:
                    try:
                        current_concatenated_hash += rom['@sha1']
                    except:
                        print(game_title+' has an error in the commented rom listing') 
                        continue

                concatenated_hashes.update({current_disc_number : current_concatenated_hash})
        
            for disc_number, disc_hash in concatenated_hashes.items():
                sha1 = hashlib.sha1(disc_hash.encode('utf-8')).hexdigest()
                source_fingerprints[f'disc{disc_number}_sha1'] = sha1
                game_data['parts'][f'cdrom{disc_number}']['source_sha'] = sha1
            game_data.update({'discs': source_fingerprints})
            game_data.update({'source_bin_total_size': total_size})


def process_comments(soft, sl_dict):
    redumpurl = r'^http://redump'
    romhash = r'<rom name'
    notedict = {}
    notenum = 1
    if '#comment' in soft:
        comments = soft['#comment']
    else:
        return None
    if isinstance(comments, str):
        comments = [comments]
    for comment in comments:
        if re.match(redumpurl,comment.strip()):
            comment.strip()
            redumplist = re.split(r'(,|\s+)',comment)
            discnum = 1
            sourcedict = {}
            
            for url in redumplist:
                if re.match(redumpurl,url):
                    sourcedict['disc'+str(discnum)+'source'] = url
                    discnum += 1
                elif url == ' ':
                    continue
                else:
                    print('error with '+soft['@name'])
                    print('\033[0;31mother info mixed with redump source comment\033[00m')
            try:
                sl_dict[soft['@name']].update(sourcedict)
            except:
                urls = {soft['@name']:sourcedict}
                sl_dict.update(urls)

        # convert commented DAT entries to a dict
        elif re.match(romhash,comment):
            #print('romhash')
            commentdict = sl_romhashes_to_dict(comment)
            if commentdict: 
                try:
                    sl_dict[soft['@name']].update(commentdict['root'])
                except:
                    itemhashes = {soft['@name']:commentdict['root']}
                    sl_dict.update(itemhashes)
        else:
            notedict['note'+str(notenum)] = comment
            notenum += 1
            try:
                sl_dict[soft['@name']].update(notedict)
            except:
                note = {soft['@name']:notedict}
                sl_dict.update(note)
        
def build_sl_dict(softlist, sl_dict):
    '''
    grabs useful sofltist data and inserts into a simple to manage dict
    '''
    for soft in softlist:
        soft_id = soft['@name']
        soft_description = soft['description']
        print('creating softlist entry for '+soft_description)
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
    process_sl_rom_sources(sl_dict)


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

def update_sl_descriptions(softlist_xml, answerdict):
    '''
    writes updated descriptions to the softlist
    no longer used but can be extended/repurposed later
    '''
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False,strip_cdata=False)
    tree = etree.parse(softlist_xml, parser)

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

    with open(softlist_xml, "w") as f:
        f.write(output)

def add_redump_names_to_slist(softlist_xml, answerdict,redump_name_list):
    '''
    writes redump name tags to slist entry just before the 'part' tag
    no longer used but can be extended/repurposed later
    '''
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False,strip_cdata=False)
    tree = etree.parse(softlist_xml, parser)
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

    with open(softlist_xml, "w") as f:
        f.write(output)




'''
dat processing functions
'''
def build_dat_dict(datfile,raw_dat_dict,dat_dict):
    '''
    grabs data from dat structure puts it into a new dict
    '''
    dat_dict.update({datfile : create_dat_hash_dict(raw_dat_dict)})

def build_dat_dict_xml(datfile,dat_dict):
    '''
    grabs useful data from dat structure puts it into a dict
    '''
    tree = ET.parse(datfile)
    root = tree.getroot()
    dat_dict.update({datfile : create_dat_hash_dict_xml(root)})


def dat_discs_to_titles(disclist):
    '''
    redump entries are for individual discs, SL entries describe 
    boxes/packages this function returns a new list with only titles
    '''
    title_list = []
    discpat = r'\s\([D|d]isc\s\d+\)'
    for disc in disclist:
        softtitle  = re.sub(discpat,'',disc)
        if softtitle not in title_list:
            title_list.append(softtitle)
    return title_list

def create_dat_hash_dict(raw_dat_dict):
    result = {}
    for game in raw_dat_dict['game']:
        file_list = {}
        name = game['@name']
        files = len(game['rom'])
        size = 0
        sha1 = hashlib.sha1()
        for rom in game['rom']:
            file_list.update({rom['@name']:rom['@crc']})
            if not rom['@name'].endswith(('.cue', '.gdi')):
                sha1.update(rom['@sha1'].encode('utf-8'))
                size = size + int(rom['@size'])
        sha1_digest = sha1.hexdigest()
        result[sha1_digest] = {
            'name': name,
            'files': files,
            'size': size,
            'file_list': file_list
        }
    return result


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
            if not rom.get('name').endswith(('.cue', '.gdi')):
                sha1.update(rom.get('sha1').encode('utf-8'))
        sha1_digest = sha1.hexdigest()
        result[sha1_digest] = {
            'name': name,
            'files': files,
            'size': size,
        }
    return result

def get_dat_name(dat_path):
    tree = ET.parse(dat_path)
    root = tree.getroot()
    name = root.find('header/name').text
    return name
    