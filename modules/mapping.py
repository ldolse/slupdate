import re
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urlparse
from modules.utils import save_data, restore_dict,list_menu
import inquirer
import hashlib
from difflib import get_close_matches


redump_site_dict = restore_dict('redump_site_dict')

redump__platform_paths = { 'jaguar':'ajcd',
                       'cdtv':'cdtv',
                       'cd32':'cd32',
                 'fmtowns_cd':'fmt',
              'ibm5170_cdrom':'pc',
                      'pcecd':'pce',
                        'cdi':'cdi',
                     'pippin':'pippin',
                       'pcfx':'pc-fx',
                     'segacd':'mcd',
                     'megacd':'mcd',
                    'megacdj':'mcd',
                     'saturn':'ss',
                         'dc':'dc',
                      'neocd':'ngcd',
                        'psx':'psx',
                     '3do_m2':'3do',
               'psx_libcrypt':'psx/libcrypt/2'
                    }

def get_source_stats(sl_dict):
    '''
    builds a dict with the total number of dumps which can be attributed to each source group
    '''
    from collections import defaultdict
    group_counts = defaultdict(int)

    for soft_entry in sl_dict.values():
        for part in soft_entry['parts'].values():
            if 'source_group' in part:
                group_counts[part['source_group']] += 1

    return dict(group_counts)

def print_source_stats(source_stats,total_source_ref):
    '''
    prints the dict returned by get_source_stats as percentages
    '''
    known_sum = 0
    for group, group_count in source_stats.items():
        known_sum += group_count
        percentage = (group_count / total_source_ref) * 100
        print(f"  {group}: {percentage:.1f}%")
    if total_source_ref >= 1:
        other_percent = ((total_source_ref - known_sum) / total_source_ref) * 100
        print(f"  Unknown: {other_percent:.1f}%")

def build_redump_tosec_tuples(dat_hash_dict,platform):
    supported_platforms = ['dc']
    redump_tosec_tuples = {}
    if platform not in supported_platforms:
        return redump_tosec_tuples
    else:
        for source_id, source_info in dat_hash_dict.items():
            debug = False
            if source_id[1] == 'crc':
                if debug:
                    print(f'skipping debug {source_info["name"]}')
                continue
            entry_tuple = get_tosec_tuples(source_info['file_list'],debug)
            if entry_tuple:
                redump_tosec_tuples[entry_tuple] = source_id
        return redump_tosec_tuples

def get_tosec_tuples(rom_entry,debug=False):
    '''
    dreamcast - track 1 and track 3 share the same hashes for both groups
    '''
    track_hashes = []
    for filename, data in rom_entry.items():
        match_info = filename.lower()
        if debug:
            print(match_info)
        if match_info.endswith('(track 1).bin') or match_info.endswith('track01.bin') or match_info.endswith('track 01).bin'):
            track_hashes.append(data['@crc'])
        elif match_info.endswith('(track 3).bin') or match_info.endswith('track03.bin') or match_info.endswith('track 03).bin'):
            track_hashes.append(data['@crc'])
    if debug:
        print(f'Track hashes: {track_hashes}')
    if len(track_hashes) == 2:
        return tuple(track_hashes)
    else:
        return None

def update_soft_dict(sl_dict,dat_dict,new_sources_map):
    '''
    new_sources_map is a dict with the following structure:
    (soft_title, part) = {  'raw_romlist':dat_dict['hashes'][dat][source_sha]['raw_romlist'],
                            'orig_title':'orig_title',
                            'source_name':'source_name',
                            'source_sha':'source_sha',
                            'source_dat':'dat',
                            'source_group':'redump',
                            'redump_url':'redump_url',
                            'soft_description':'soft_description'}
    '''
    for disc_key, replace_data in new_sources_map.items():
        soft_name = disc_key[0]
        soft_part = sl_dict[soft_name]['parts'][disc_key[1]]
        new_dat = replace_data['source_dat']
        new_sha = replace_data['source_sha']
        orig_data = {}
        new_data = { 'source_dat':new_dat,
                     'source_sha':new_sha,
                     'source_name':replace_data['source_name'],
                     'source_group':replace_data['source_group'],
                     'redump_url':replace_data['redump_url'],
                     'raw_rom_entry':replace_data['raw_romlist']
                   }
        # get original source info if it exists and update the orig dat entry
        if 'source_sha' in soft_part:
            orig_sha = soft_part.pop('source_sha')
            orig_data = { 'source_sha':orig_sha,
                          'file_list':soft_part.pop('file_list')
                        }
            if 'source_dat' in soft_part:
                orig_dat = soft_part.pop('source_dat')
                orig_data.update({ 'source_dat':orig_dat,
                                   'source_group':soft_part.pop('source_group'),
                                   'source_name':soft_part.pop('source_name')
                                })
                # get the indices of this softlist entry in the dat match list and remove them
                dat_matches = dat_dict['hashes'][orig_dat][orig_sha]['softlist_matches']
                match_index = [i for i, soft in enumerate(dat_matches) if soft == soft_name]
                for i in match_index:
                    dat_matches.pop(i)
        if 'redump_url' in soft_part:
            if replace_data['redump_url'] != soft_part['redump_url']:
                print(f'changed URL for {soft_name} {disc_key[1]}:\n   was{soft_part["redump_url"]}\n   now:{replace_data["redump_url"]}')
                orig_href = soft_part.pop('redump_url')
                orig_data.update({'redump_url':orig_href})

        soft_part.update(new_data)
        # store the old match data in a new dict
        if orig_data:
            soft_part.update({'original_matches':orig_data})
        # add the soflist entry to the new dat entry
        new_dat_entry = dat_dict['hashes'][new_dat][new_sha]
        if 'softlist_matches' not in new_dat_entry:
            new_dat_entry['softlist_matches'] = [soft_name]
        elif soft_name not in new_dat_entry['softlist_matches']:
            new_dat_entry['softlist_matches'].append(soft_name)
        # get rid of any previously matched source rom reference
        if 'source_rom' in soft_part:
            soft_part.pop('source_rom')
        # flag update for later functions to leverage
        sl_dict[soft_name]['update_required'] = True

def libcrypt_report(psx_dict):
    from modules.gamedb import libcrypt
    for soft, soft_data in psx_dict.items():
        if 'serial' in soft_data:
            for string in soft_data['serial']:
                check = string.replace('-','')
                check = check.replace(' ','')
                if check in libcrypt:
                    print(f'{soft}: {soft_data["description"]} uses libcrypt')


def map_tosec_entries(sl_dict,dat_dict,redump_tuples):
    '''
    for some platforms redump and tosec are identical for some or all tracks
    cdi - all tracks are identical in most cases
    '''
    tosec_matches = {}
    partial_matches = []
    for soft, soft_data in sl_dict.items():
        match_tuples = []
        if soft_data['source_found']:
            tosec = False
            for part, part_data in soft_data['parts'].items():
                if 'source_group' in part_data and part_data['source_group'] == 'TOSEC':
                    tosec = True
                    # build the tuple
                    tosec_tuple = get_tosec_tuples(dat_dict['hashes'][part_data['source_dat']][part_data['source_sha']]['file_list'])
                    print(f'{soft} {part} TOSEC Tuple: {tosec_tuple}')
                    orig_title = dat_dict['hashes'][part_data['source_dat']][part_data['source_sha']]['name']
                    # if there is a match then get the redump hashes
                    if tosec_tuple in redump_tuples:
                        print('found tosec tuple in redump tuples')
                        source_sha = redump_tuples[tosec_tuple]
                        for dat, group in dat_dict['dat_group'].items():
                            if group == 'redump':
                                if source_sha in dat_dict['hashes'][dat]:
                                    print(f'{soft} redump lookup: {source_sha}')
                                    # match key is a tuple using the soft name and part number
                                    match_key = (soft,part)
                                    match_tuples.append(match_key)
                                    redump_title = dat_dict['hashes'][dat][source_sha]['name']

                                    # add the hashes to the matches dict
                                    tosec_matches.update(create_update_entry(match_key,sl_dict,dat_dict,dat,redump_title,source_sha))

        if match_tuples and len(match_tuples) != len(soft_data['parts'].items()):
            #print(f'match tuples:{len(match_tuples)}  Soft data parts: {len(soft_data["parts"].items())}')
            partial_matches.append(soft_data['description'])
    if partial_matches:
        print('\n\n The number of discs with new hashes does not equal the number of discs in these software list')
        print(' items. Source hashes may be deleted from the original comment, if so the missing hashes will need to')
        print(' be manually added back')
        print('\n Titles:')
        for description in partial_matches:
            print(f'    {description}')
        print('\n\n')
    return tosec_matches

def requests_retry_session(
    retries=4,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def rtable_to_dict(bs_table):
    gameinfo = {}
    alt = re.compile(r'(Region|Languages)')
    for bsr in bs_table:
        if bsr.find('th') and not re.search(alt,bsr.find('th').text):
            gameinfo.update({bsr.find('th').text:bsr.find('td').text})
        elif bsr.find('th'):
            gameinfo.update({bsr.find('th').text:bsr.find('img').get('title')})
    return gameinfo
    

def get_redump_title_info(redumpurl):
    rdict = {}
    data = requests_retry_session().request("GET", redumpurl, timeout=3)
    rsoup = BeautifulSoup(data.text, 'xml')
    rdict.update({'Redump Title':rsoup.find('h1').text})
    rdict.update({'Full Title':rsoup.find('h2').text})
    rtable = rsoup.find( "table", {"class":"gameinfo"} )
    rows=list()
    for row in rtable.findAll("tr"):
        rows.append(row)
    rdict.update(rtable_to_dict(rows))
    return rdict


def redump_to_softlist_fmt(redump_name,keep_disc=False):
    languages = re.compile(r'\s?\(((En|Ja|Fr|De|Es|It|Nl|Pt|Sv|No|Da|Fi|Zh|Ko|Pl),?)+\)')
    discpat = r'\s\([D|d]isc\s\d+\)'
    softlist_fmt = re.sub(languages,'',redump_name)
    if keep_disc:
        return softlist_fmt
    else:
        return re.sub(discpat,'',softlist_fmt)

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

def select_close_redump(sl_dict,dat_dict,redump_tuple_list):
    redump_possible = {}
    for dat, group in dat_dict.items():
        if group == 'redump':
            redump_possible.update(dat_dict['name_lookup'][dat])
    for soft_key, matches in redump_tuple_list.items():
        matchlist = get_close_matches(sl_dict[soft_key[0]], redump_possible.keys(),n=5)


def select_from_redump_site(search_title, match_list,soft_nointro_fmt=''):
    matchlist = get_close_matches(search_title, match_list,n=5)
    if len(matchlist) > 0:
        # append other menu choices to the match list
        matchlist.append('No Match')
        matchlist.append('Stop')
        # ask the user to choose from the choices
        answer = list_menu(search_title, matchlist, '  Matches')
        return answer, False
    else:
        print(f'No Matches found for {search_title}')
        return {search_title:'No Match'}, True



def select_from_redump_dat(search_title, match_list,soft_nointro_fmt=''):
    matchlist = get_close_matches(search_title, match_list,n=5)
    proto_beta = proto_beta_check(search_title,matchlist)
    if len(matchlist) > 0:
        if soft_nointro_fmt and proto_beta:
            # most of these are not in DATs, skip
            return {search_title:'No Match'}, True            
        elif soft_nointro_fmt:
            # softlist sources titles need extra checks and can sometimes be automatically matched
            closematch = next((s for s in matchlist if soft_nointro_fmt.lower() in s.lower()), None)
            if closematch:
                # try to bring the two formats together and see if there is a match
                softlist_fmt = redump_to_softlist_fmt(closematch)
                if soft_nointro_fmt.lower() == softlist_fmt.lower():
                    return {search_title:closematch}, True

        # append other menu choices to the match list
        matchlist.append('No Match')
        matchlist.append('Stop')
        # ask the user to choose from the choices
        answer = list_menu(search_title, matchlist, '  Matches')
        return answer, False
    else:
        print(f'No Matches found for {search_title}')
        return {search_title:'No Match'}, True

        
def tweak_nointro_dat(stitle, languages=[], region=''):
    '''
    if only title is supplied, sub common characters that aren't supported in the 
    nointro/redump dat standard to increase likelihood of an auto-match
    if language and region are supplied then it will attempt to create a string
    which matches the redump DAT from the redump db info
    doesn't handle revisions or any of the less frequently used fields
    '''
    lang_sub = {
         'English': 'En',
        'Japanese': 'Ja',
          'French': 'Fr',
          'German': 'De',
         'Spanish': 'Es',
         'Italian': 'It',
           'Dutch': 'Nl',
      'Portuguese': 'Pt',
         'Swedish': 'Sv',
       'Norwegian': 'No',
          'Danish': 'Da',
         'Finnish': 'Fi',
         'Chinese': 'Zh',
          'Korean': 'Ko',
          'Polish': 'Pl',
         'Russian': 'Ru',
          'Arabic': 'Ar',
           'Czech': 'Cs',
         'Catalan': 'Ca',
         'Slovak' : 'Sk',
                '':''
    }
    disc_pat = r'\s\(Disc\s\d+\)'
    disc_match = re.findall(disc_pat, stitle)
    if disc_match:
        disc = disc_match[0]
    else:
        disc = ''

    if len(languages) > 1:
        ordered_languages = sorted(languages, key=lambda lang: list(lang_sub.values()).index(lang_sub.get(lang, '')))
        dat_lang = ' ('
        for i, language in enumerate(ordered_languages):
            if language in lang_sub:
                lang = lang_sub[language]
            else:
                print(f'{language} not configured in nointro list.  Title:{stitle}')
                
            dat_lang += lang
            if i < len(ordered_languages) - 1:
                dat_lang += ','
        dat_lang += ')'
    else:
        dat_lang = ''

    if region:
        region = ' (' + region + ')'

    stitle = re.sub(r'\(Euro\)', '(Europe)', stitle)
    stitle = re.sub(disc_pat, '', stitle)
    stitle = re.sub(r':', ' -', stitle)
    stitle = re.sub(r'/', '-', stitle)

    return stitle + region + dat_lang + disc

def compare_sl_with_redump(sllist,san_redumplst,sl_dict,answers={}):
    '''
    Expects:
    - A list of SL descriptions
    - A list of Redump descriptions sanitized to remove disc numbers
    - optionally an answer dict to continue a previous session
    
    returns a dict of sl to redump title matches
    todo - load redump url from SL entry, for title comparison, serial, etc
    '''
    matches = 0
    close_matches = 0
    no_match = 0
    autofix = 0
    sllist.sort()
    for soft_description in sllist:
        if soft_description in answers:
            continue
        else:
            print('checking '+soft_description)
            process_comments(get_sl_entry(my_soft['software'],soft_description,'redump'), sl_dict)
            soft_nointro_fmt = tweak_nointro_dat(soft_description)
        if soft_description in san_redumplst:
            answers.update({soft_description:soft_description})
            matches += 1
        elif soft_nointro_fmt in san_redumplst and soft_nointro_fmt not in answers.values():
            answers.update({soft_description:soft_nointro_fmt})
            autofix += 1
        else:
            #rurl = lkup_redump_url(soft_description)
            #if rurl and online:
            #    rdict = get_redump_title_info(rurl)
            #    print_redump_info(rdict)
            print('\n   Mame Title: '+soft_description)
            answer, auto = select_from_redump_dat(soft_description, san_redumplst, soft_nointro_fmt)
            if answer[soft_description] == 'Stop':
                break
            elif answer[soft_description] == 'No Match':
                no_match += 1
                answers.update(answer)
            else:
                if answer[soft_description] in answers.values():
                    print('title has already been selected')
                    answer[soft_description] = 'No Match'
                    no_match += 1
                else:
                    if auto:
                        autofix += 1
                    else:
                        close_matches += 1
                answers.update(answer)
                

    print(str(matches)+' titles had exact matches')
    print(str(autofix)+' titles were automatically matched')
    print(str(close_matches)+' titles had user selected matches')
    print(str(no_match)+' titles had no match')
    return answers


def proto_beta_check(soft_description,matchlist):
    '''
    possible todo - handle taikenban / demo matching
    '''
    shorthand = ['proto','beta','sample']
    for short in shorthand:
        if short in soft_description.lower() and (s for s in matchlist if short in s.lower()):
            print('prototype or beta/demo not in redump, skipping')
            return True
    return False


def update_nonmatch(answers, san_redumplst):
    '''
    requires a populated answer list from the first pass and
    the sanitised title list from a redump dat (disc# stripped)
    '''
    for soft_description, redump in answers.items():
        confirmq = [
            inquirer.Confirm("inredump", message="Check "+soft_description+" against Redump titles?"),
        ]
        if redump == 'No Match':
            process_comments(get_sl_entry(my_soft['software'],soft_description,'redump'), sl_dict)
            inredump = inquirer.prompt(confirmq)
            if inredump['inredump']:
                #rurl = lkup_redump_url(soft_description)
                #if rurl and online:
                #    rdict = get_redump_title_info(rurl)
                #    print_redump_info(rdict)
                soft_nointro_fmt = tweak_nointro_dat(soft_description)
                answer, auto = select_from_redump_dat(soft_description, san_redumplst, soft_nointro_fmt)
                if answer[soft_description] == 'Stop':
                    break
                elif answer[soft_description] in answers.values():
                    if answer[soft_description] != 'No Match':
                        print('title has already been selected')
                    try:
                        answer = update_description(soft_description)
                        if answer[soft_description] not in answers.values():
                            answers.update(answer)
                        else:
                            print('title has already been selected')
                    except:
                        continue
                elif answer[soft_description] == 'No Match':
                    try:
                        answer = update_description(soft_description)
                        if answer[soft_description] not in answers.values():
                            answers.update(answer)
                        else:
                            print('title has already been selected')
                    except:
                        continue
                else:
                    answers.update(answer)
                    if not rurl:
                        # if user provided a confirmation here then they likely have the 
                        # redump URL for the title, ask and store it here
                        addurl = inquirer.prompt(
                                 [inquirer.Confirm('redumpurl',message='Add redump URL?',default=True)
                                  ])
                        if addurl['redumpurl']:
                            redumpquery = [inquirer.Text('disc1source', message="Redump URL")]
                            redumpurl = inquirer.prompt(redumpquery)
                            #iteminfo = {soft_description:redumpurl}
                            sl_dict.update({soft_description:redumpurl})        
            else:
                try:
                    answer = update_description(soft_description)
                    answers.update(answer)
                except:
                    continue
    return answers


def print_redump_info(redump_dict):
    limited = re.compile(r'(Genteiban|Limited Edition|Shokai Genteiban)')
    print('')
    print('Redump.org Website details for this title:')
    print('Redump Title: '+redump_dict['Redump Title'])
    print('  Full Title: '+redump_dict['Full Title'])
    if redump_dict['Region'] == 'Japan':
        print('      Romaji: ', end='')
        kks = pykakasi.kakasi()
        jresult = kks.convert(redump_dict['Full Title'])
        for item in jresult:
            print('{} '.format(item['hepburn'].capitalize()), end='')
        print('')
    print('      Region: '+redump_dict['Region'])
    print('   Languages: '+redump_dict['Languages'])
    if redump_dict['Region'] == 'Japan' and re.match(limited,redump_dict['Edition']):
        print('     Edition: '+redump_dict['Edition']+'  (Shokai Genteiban/Genteiban/Limited Edition)')        
    else:
        print('     Edition: '+redump_dict['Edition'])
    print('')



def dat_key_lookup_dict(sl_dict):
    source_sha_dict = {}

    for soft_key, soft in sl_dict.items():
        for part_key, part in soft['parts'].items():
            if 'source_sha' in part:
                source_sha = part['source_sha']
                if source_sha not in source_sha_dict:
                    source_sha_dict[source_sha] = [(soft_key, part_key)]
                else:
                    source_sha_dict[source_sha].append((soft_key, part_key))
    return source_sha_dict

def dup_report(sl_dict):
    dupe_list = []
    source_sha_dict = dat_key_lookup_dict(sl_dict)
    for titles in source_sha_dict.values():
        if len(titles) > 1:
            dupe_list.append(titles)
    if len(dupe_list) > 0:
        print('Duplicates Found:')
        for dupe_items in dupe_list:
            for dupe in dupe_items:
                print(f'{dupe[0]}: {sl_dict[dupe[0]]["description"]} {get_user_disc(dupe[1])}')
            print('')

def href_sl_lookup_dict(sl_dict):
    lookup_dict = {}
    lookup_key = None
    for soft, data in sl_dict.items():
        description = data['description']

        for part, part_data in data['parts'].items():
            if 'redump_url' in part_data:
                lookup_key = part_data['redump_url'].replace('http://redump.org','')
                second_level_key = (soft, part)
                # Update lookup_dict
                if lookup_key not in lookup_dict:
                    lookup_dict[lookup_key] = []
                lookup_dict[lookup_key].append({second_level_key:part_data})

    return lookup_dict

def nameserial_lookup_dict(redump_dict,platform,lookup_type):
    lookup_dict = {}

    for data in redump_dict.values():
        serials = data['serial']
        dat_style = data['dat_style']
        keep_disc = True
        softlist_fmt = redump_to_softlist_fmt(data['dat_style'],keep_disc)
        edition = data['edition']
        version = data['version']
        href = data['href']
    
        for serial in serials:
            if platform == 'psx':  # add back hyphen for cases where space is used
                serial = re.sub(r'([A-Z]{4})\s(\d{5})', r'\1-\2', serial)
            if lookup_type == 'name':
                lookup_key = softlist_fmt
            elif lookup_type == 'serial':
                lookup_key = serial
            else:
                lookup_key = (softlist_fmt, serial)

            second_level_key = (dat_style, serial, edition, version, href)
        
            # Update lookup_dict
            if lookup_key not in lookup_dict:
                lookup_dict[lookup_key] = []
            lookup_dict[lookup_key].append(second_level_key)

    return lookup_dict


  
def preprocess_redump_sha_txt(file_url,redump_entry):
    response = requests.get(file_url)
    if response.status_code == 200:
        filename = content_header_to_filename(response)
        content = response.text
        lines = content.split('\n')
        rom_list = []

        for line in lines:
            if line.strip() != '':
                sha1, filename = line.split(' *')
                rom = {
                    '@name': filename,
                    '@sha1': sha1
                }
                rom_list.append(rom)
        if rom_list:
            redump_entry['site_rom_list'] = rom_list
        if filename:
            redump_entry['site_filename'] = filename

        return rom_list

    else:
        print(f"Failed to download the file. Status code: {response.status_code}")
        return None

def calculate_hash(rom_list):
    concatenated_hash = ''
    for rom in rom_list:
        if '.cue' in rom['@name'] or '.gdi' in rom['@name']:
            pass
        else:
            concatenated_hash += rom['@sha1']
    sha1 = hashlib.sha1(concatenated_hash.encode('utf-8')).hexdigest()
    return (sha1,'sha1')


def compare_dictionaries(dict1, dict2):
    # Ignore .cue or .gdi files
    ignored_extensions = ['.cue', '.gdi']

    # Filter out ignored files
    filtered_dict1 = {k: v for k, v in dict1.items() if not any(ext in k.lower() for ext in ignored_extensions)}
    filtered_dict2 = {k: v for k, v in dict2.items() if not any(ext in k.lower() for ext in ignored_extensions)}

    # Compare the total number of files
    if len(filtered_dict1) != len(filtered_dict2):
        return (0,0)

    # Get the keys in the same order
    keys1 = list(filtered_dict1.keys())
    keys2 = list(filtered_dict2.keys())

    # Compare individual '@sha1' hashes at the same index
    matching_hashes = sum(1 for i, k in enumerate(keys1) if filtered_dict1[k]['@sha1'] == filtered_dict2[keys2[i]]['@sha1'])
    #print(f"Match: {matching_hashes} out of {len(filtered_dict1)}")
    return (matching_hashes,len(filtered_dict1))
    #return f"Match: {matching_hashes} out of {len(filtered_dict1)}"

def find_similar_dat(source_dict,dat_dict,hash_min=1,list_limit=10):
    results = []
    for dat,hashdict in dat_dict['hashes'].items():
        dat_group = dat_dict['dat_group'][dat]
        for key, data in hashdict.items():
            if 'softlist_matches' in data:
                continue
            elif key[1] == 'crc':
                continue
            else:
                compare_dict = data['file_list']
                result = compare_dictionaries(source_dict,compare_dict)
                # append to list if at least one hash matches
                if result[0] > hash_min:
                    results.append((data['name'],result[0],result[1],dat_group,dat,key))
    # discard long lists of results
    if len(results) > list_limit:
        results = []
    return results

def fuzzy_hash_compare(sl_dict,dat_dict,skip_prototype=True):
    replacements = {}
    for soft, data in sl_dict.items():
        if 'prototype' in data['description'].lower() and skip_prototype:
            continue
        for cd, part in data['parts'].items():
            if 'source_dat' in part:
                continue
            elif 'file_list' in part:
                source_dict = part['file_list']
            elif len(data['parts']) == 1 and 'file_list' in data:
                source_dict = data['file_list']
            else:
                continue
            results = find_similar_dat(source_dict,dat_dict)
            if results:
                kv_result = {(soft,cd):results}
                replacements.update(kv_result)
            for result in results:
                print(f"Match for {soft}: {result[1]} out of {result[2]}, dat name: {result[0]}")
    return replacements

def get_unmatched_roms(sl_dict):
    unmatched = {}
    for soft,soft_data in sl_dict.items():
        for disc,part_data in soft_data['parts'].items():
            if 'source_dat' not in part_data and 'file_list' in part_data:
                user_disc = get_user_disc(disc)
                if user_disc:
                    user_disc = ' '+user_disc
                dat_title = f'{part_data["chd_filename"]}{user_disc}'
                if dat_title in unmatched:
                    dat_title = soft+' - '+dat_title
                unmatched.update({dat_title:part_data['file_list']})
    return unmatched
    
def get_name_dat_match(dat_title, dat_dict, redump=True):
    source_sha = None
    matched_dat = None
    for match_dat in dat_dict['name_lookup'].keys():
        # skip non redump dats
        if dat_dict['dat_group'][match_dat] != 'redump' and redump:
            continue
        elif dat_title in dat_dict['name_lookup'][match_dat].keys():
            source_sha = (dat_dict['name_lookup'][match_dat][dat_title]['sha1_digest'],'sha1')
            matched_dat = match_dat
            break
    return source_sha, matched_dat

def get_sha_dat_match(sha_lookup, dat_dict, redump=True):
    matched_dat = None
    returned_title = None
    for match_dat in dat_dict['name_lookup'].keys():
        # skip non redump dats
        if dat_dict['dat_group'][match_dat] != 'redump' and redump:
            continue
        elif sha_lookup in dat_dict['hashes'][match_dat].keys():
            returned_title = dat_dict['hashes'][match_dat][sha_lookup]['name']
            matched_dat = match_dat
            break
    return matched_dat, returned_title

                
def redump_url_mapping(sl_dict,dat_dict,script_dir,platform):
    url_mappings = {}
    if platform not in redump_site_dict:
        build_redump_site_dict(platform,script_dir)
    redump_dict = redump_site_dict[platform]
    lookup_dict = nameserial_lookup_dict(redump_dict,platform,lookup_type='name')
    for soft,soft_data in sl_dict.items():
        for disc,part_data in soft_data['parts'].items():
            retrieve_name = False
            dat_title = None
            source_sha = None
            matched_dat = None
            match_key = None
            if 'source_group' in part_data and part_data['source_group'] == 'redump':
                continue

            if 'redump_url' in part_data:
                redump_url = part_data['redump_url']
                redump_lookup = re.match(r'http://redump.org(/disc/\d+/)',redump_url)[1]
                if redump_lookup in redump_dict:
                    print(f'found redump disc match for {soft}: {redump_lookup}')
                    # check if this URL has already been updated in the dict   
                    if 'site_hash' in redump_dict[redump_lookup]:
                        print('site_hash in redump_dict')
                        source_sha = redump_dict[redump_lookup]['site_hash']
                        dat_title = redump_dict[redump_lookup]['site_filename']
                    elif 'site_filename' in redump_dict[redump_lookup]:
                        print(f'{soft} title already in the redump site dict')
                        dat_title = redump_dict[redump_lookup]['site_filename']
                    else:
                        print(f'Found a redump URL match for {soft} {disc}:{soft_data["description"]}')
                        # get the simplified DAT style name from the redump dict
                        dat_style = redump_dict[redump_lookup]['dat_style']
                        print(f'          searching for redump titles matching {dat_style}')
                        # check for the simple name in the lookup dict and see how many possible version of this title exist
                        if dat_style in lookup_dict:
                            print(f'          {lookup_dict[dat_style]}')
                            if len(lookup_dict[dat_style]) == 1:
                                lookup_title = lookup_dict[dat_style][0][0]
                                print(f'          lookup_key is {dat_title}')
                                source_sha, matched_dat = get_name_dat_match(lookup_title, dat_dict, redump=True)
                                if source_sha is None:
                                    print('          was unable to find this name in the DAT, will retrieve from redump website')
                                    retrieve_name = True
                                else:
                                    dat_title = lookup_title   
                            else: # multiple possible dat entries, get precise name from redump
                                print('          multiple hits, will retrieve correct name from redump website')
                                retrieve_name = True
                        else: # can't find the name at all, check the redump site
                            retrieve_name = True
                    if retrieve_name: # get the dat name from the redump sha URL
                        print('          getting name from redump website')
                        filename = get_filename_from_url(redump_url+'sha1/',redump_dict[redump_lookup])
                        if filename:
                            dat_title = filename
                else: # no url match
                    print(f'{redump_url} doesn\'t appear valid for {soft} {disc}')

                if dat_title is not None:
                    match_key = (soft,disc)
                    source_sha, matched_dat = get_name_dat_match(dat_title, dat_dict, redump=True)
                    if source_sha:
                        print(f'          mapped dat name is {dat_title}, creating record')
                        # add the hashes to the matches dict
                        url_mappings.update(create_update_entry(match_key,sl_dict,dat_dict,matched_dat,dat_title,source_sha,redump_url))
                    else: # check hashes for cases where redump title and user dat don't match
                        print(f'          no title match for {dat_title}, getting full hash from redump')
                        source_sha = get_redump_site_file_data(redump_url+'sha1/',redump_dict[redump_lookup])
                        if source_sha:
                            print(f'          got a hash for {dat_title}, {source_sha}')
                            matched_dat, dat_title = get_sha_dat_match(source_sha, dat_dict, redump=True)
                            if dat_title:
                                url_mappings.update(create_update_entry(match_key,sl_dict,dat_dict,matched_dat,dat_title,source_sha,redump_url))
                elif source_sha is not None:
                    match_key = (soft,disc)
                    print(f'          using stored hash for {dat_title}, {source_sha}')
                    matched_dat, dat_title = get_sha_dat_match(source_sha, dat_dict, redump=True)
                    if dat_title:
                        url_mappings.update(create_update_entry(match_key,sl_dict,dat_dict,matched_dat,dat_title,source_sha,redump_url))
                    else:
                        print(f'          No Sha or Title match to redump site, DAT may be out of date?')
                else:
                    print(f'          unable to find a match for {soft} {disc}')
            else:
                continue
    save_data(redump_site_dict,'redump_site_dict',script_dir)
    return url_mappings

def get_redump_site_file_data(redump_sha_href,redump_entry):
    redump_hash_key = None
    if 'site_hash' in redump_entry:
        return redump_entry['site_hash']
    rom_list = preprocess_redump_sha_txt(redump_sha_href,redump_entry)
    if rom_list:
        redump_hash_key = calculate_hash(rom_list)
        redump_entry['site_hash'] = redump_hash_key
    return redump_hash_key

def content_header_to_filename(response):
    header = response.headers.get('Content-Disposition')
    if header:
        raw_filename = header.split('filename=')[1].strip('"\'')

        # In case the filename is quoted, remove the surrounding quotes
        parsed_filename = urlparse(raw_filename)
        if parsed_filename:
            filename = re.match(f'(.*)\.sha1',parsed_filename.path)[1]
            return filename
        else:
            return None
    else:
        return None

def get_filename_from_url(url,redump_entry):
    response = requests.head(url)
    filename = content_header_to_filename(response)
    if filename is not None:
        redump_entry['site_filename'] = filename
    return filename
                    
                        

def interactive_title_mapping(interactive_matches,sl_dict,dat_dict,platform,script_dir,match_type='redump_serial'):
    '''
    interactive_matches examples:
    From redump site dict:
      {('flntstns', 'cdrom'): [('The Flintstones - Viva Rock Vegas (Europe) (En,Fr,De,Es,It)', '952-0174-50', 'Sample', '1.002', '/disc/77555/')],
       ('incomingj', 'cdrom'): [('Incoming - Jinrui Saishuu Kessen (Japan)', 'T-15001M', 'Original', '2.000', '/disc/40973/')]}
    From fuzzy matches:
      {('kaod', 'cdrom'): [('Kao the Kangaroo (Europe) (Demo)', 2, 7, 'redump', '<datpath>', ('0851401e42ff4899b7008fa8f4c015040ec7c984', 'sha1'))]}
    '''
    def print_preface(soft_key,soft_entry,match_type):
        file_list = None
        if 'redump' in match_type:
            print('Select from possible Redump Matches (Review of Softlist comments and Redump URL may be needed)')
        elif 'fuzzy' in match_type:
            print('Select from possible DAT matches based individual track hashes (Review of Softlist Comments and Redump URL may be needed)')
        print(f'\n                MAME Software List Details:\n                        ROM Name: {soft_key[0]}')
        print(f'                     Description: {soft_entry["description"]}')
        print(f'                            Disc: {get_user_disc(soft_key[1])}')
        if 'rawserial' in sl_dict[soft_key[0]]:
            print(f'                          Serial: {soft_entry["rawserial"]}')
        if 'source_group' in soft_entry['parts'][soft_key[1]]:
            print(f'\nSource Matched\n   Source Group: {soft_entry["parts"][soft_key[1]]["source_group"]}')
            print(f'    Source Name: {soft_entry["parts"][soft_key[1]]["source_name"]}')
        elif 'file_list' in soft_entry:
            source_files = soft_entry['file_list']
            fname = next(iter(source_files))
            print(f'Source Info:\n   No Source match but source is documented.\n   Source Filename (first entry): {fname}')
        elif 'file_list' in soft_entry["parts"][soft_key[1]]:
            source_files = soft_entry["parts"][soft_key[1]]['file_list']
            fname = next(iter(source_files))
            print(f'Source Info:\n   No Source match but source is documented.\n   Source Filename (first entry): {fname}')

    def match_redump_db_to_dat(redump_sha_href,dat_title_name,redump_dict_entry):
        source_info = None
        source_dat = None
        source_name = None
        print(f'redump_sha_href is {redump_sha_href}')
        print(f'downloading hashes for {dat_title_name} from the redump website')
        redump_hash_key = get_redump_site_file_data(redump_sha_href,redump_dict_entry)
        #redump_hash_key = calculate_hash(preprocess_redump_sha_txt(redump_sha_href))
        print(f'redump_hash_key is {redump_hash_key}')
        if redump_hash_key is not None:
            for dat, hashdict in dat_dict['hashes'].items():
                if dat_dict['dat_group'][dat] != 'redump':
                    continue
                if redump_hash_key in hashdict.keys():
                    source_sha = redump_hash_key
                    source_dat = dat
                    source_name = hashdict[redump_hash_key]['name']
                    break
            if source_sha is not None:
                print('found a match')
            else:
                print('unable to find a dat match for the selected redump source based on the redump site hashes')
        else:
            print('unable to download the redump hash file, you can manually select on of the unmatched redump entries')
            selected_source = select_from_redump_dat(dat_title_name, possible_matches)
            source_sha, source_dat, source_name = get_name_dat_match(selected_source, dat_dict, redump=True)

        return source_sha, source_dat, source_name

    def build_select_list(match_list,match_type):
        select_list = []
        match_list = sorted(match_list)
        print(f'match_list is {match_list}')
        if 'redump' in match_type:
            for redump_entry in match_list:
                # build a set of strings to add to the select list
                select_list.append((f'{redump_entry[0]} - Serial:{redump_entry[1]}, ({redump_entry[2]}) ({redump_entry[3]}) http://redump.org{redump_entry[4]}',(redump_entry[0],redump_entry[4])))
        elif match_type == 'fuzzy':
            for fz_mtch in match_list:
                select_list.append((f'{fz_mtch[0]} - {fz_mtch[1]}/{fz_mtch[2]} hash matches in {fz_mtch[3]}',fz_mtch))

        select_list.append(('No Match',None))
        select_list.append(('Stop','exit'))
        print(f'select_list is\n{select_list}')
        return select_list

    review_matches = inquirer.confirm(f'There are {len(interactive_matches)} matches to review, continue?', default=False)
    if not review_matches:
        return
    else:
        # build the list of possible titles from unmatched titles
        possible_matches = []
        confirmed_matches = {}
        for match_dat in dat_dict['name_lookup'].keys():
            # skip non redump dats except for fuzzy matches based on individual hashes
            if dat_dict['dat_group'][match_dat] == 'redump' or match_type == 'fuzzy':
                possible_matches = possible_matches+[*dat_dict['name_lookup'][match_dat]]
            else:
                continue
        for soft_key, match_list in interactive_matches.items():
            match_list = list(set(match_list)) # get rid of dupes
            print(f'soft key is {soft_key}, match_list is {match_list}')

            # if there is only a single match see if it can be automatically matched against the hash on the redump website
            if len(match_list) == 1 and len(get_close_matches(match_list[0][0],possible_matches)) > 0 and match_type == 'redump_serial':
                print('single match logic, will automatically choose a dat match based on Redump website hash')
                print_preface(soft_key,sl_dict[soft_key[0]],match_type)
                redump_url = 'http://redump.org'+match_list[0][4]
                redump_sha_href = redump_url+'sha1'
                redump_dict_entry = redump_site_dict[platform][match_list[0][4]]
                dat_title_name = match_list[0][0]
                source_sha, source_dat, source_title = match_redump_db_to_dat(redump_sha_href,dat_title_name,redump_dict_entry)
                if source_sha is not None:
                    print(f'{soft_key[0]}, {soft_key[1]} was able to be automatically matched to {match_list[0][0]}')
                    confirmed_matches.update(create_update_entry(soft_key,sl_dict,dat_dict,source_dat,dat_title_name,source_sha,redump_url))

            else:
                print('more than one match, user select.')
                possible_interactive = build_select_list(match_list,match_type)
                
                print_preface(soft_key,sl_dict[soft_key[0]],match_type)
                user_choice = list_menu('u_match',possible_interactive,'       Select Matching Entry')
                print(f'user_choice is\n{user_choice}')
                if user_choice['u_match'] == 'exit':
                    return confirmed_matches
                if 'redump' in match_type and user_choice['u_match'] is not None:
                    redump_url = 'http://redump.org'+user_choice['u_match'][1]
                    redump_sha_href = redump_url+'sha1'
                    redump_dict_entry = redump_site_dict[platform][user_choice['u_match'][1]]
                    dat_title_name = user_choice['u_match'][0]
                    source_sha, source_dat, source_title = match_redump_db_to_dat(redump_sha_href,dat_title_name,redump_dict_entry)
                    if source_sha is not None:
                        confirmed_matches.update(create_update_entry(soft_key,sl_dict,dat_dict,source_dat,dat_title_name,source_sha,redump_url))
                elif match_type == 'fuzzy' and user_choice['u_match'] is not None:
                    source_dat = user_choice['u_match'][4]
                    dat_title_name = user_choice['u_match'][0]
                    source_sha = user_choice['u_match'][5]
                    confirmed_matches.update(create_update_entry(soft_key,sl_dict,dat_dict,source_dat,dat_title_name,source_sha))
        save_data(redump_site_dict,'redump_site_dict',script_dir)
        return confirmed_matches

  
def create_update_entry(soft_key,sl_dict,dat_dict,dat,source_name,new_source_sha,redump_url=None):
    if 'source_dat' in sl_dict[soft_key[0]]['parts'][soft_key[1]]:
        # need to check if there are orig before populating these
        orig_dat = sl_dict[soft_key[0]]['parts'][soft_key[1]]['source_dat']
        orig_sha = sl_dict[soft_key[0]]['parts'][soft_key[1]]['source_sha']
        orig_title = dat_dict['hashes'][orig_dat][orig_sha]['name']
    else:
        orig_title = 'Unconfirmed - New Match'
    raw_romlist = dat_dict['hashes'][dat][new_source_sha]['raw_romlist']
    soft_description = sl_dict[soft_key[0]]['description']
    return {soft_key : { 'raw_romlist':raw_romlist,
                        'orig_title':orig_title,
                        'source_name':source_name,
                        'source_sha':new_source_sha,
                        'source_dat':dat,
                        'source_group':'redump',
                        'redump_url':redump_url,
                        'soft_description':soft_description
                        }}

def get_user_disc(mame_part):
    if mame_part == 'cdrom':
        return ''
    else:
    # set a string for the disc number to use later
        num = re.sub(r'cdrom(\d+)$',r'\1',mame_part)
        return f' (Disc {num})'


def name_serial_auto_map(platform, sl_dict,dat_dict,script_dir,lookup_type='name_serial',skip_proto=True):
    '''
    two-stage function - first stage compares redump site titles to sanitized soflist descriptions
    second stage uses the redump title to match against unmatched dat entries
    redump site titles don't necessarily have exact matches to the dat based on version, package, etc
    entries which have only a single possible match are auto-mapped
    entries with multiple possible matches are returned by the function for the next stage 
    '''
    redump_single_matches = {}
    redump_interactive_matches = {}
    redump_softlist_matches = {}
    debug_list = []

    print('Starting serial and name mapping')
    if platform not in redump_site_dict:
        build_redump_site_dict(platform,script_dir)

    redump_dict = redump_site_dict[platform]
    lookup_dict = nameserial_lookup_dict(redump_dict,platform,lookup_type)
    sl_href_lookups = href_sl_lookup_dict(sl_dict)

    def update_match_lists(search_item,part_matches,lookup_dict):
        # Perform a case-insensitive lookup
        if type(search_item) is tuple:
            print(f'{search_item} is a tuple')
            matching_keys = [key for key in lookup_dict if key[0].lower() == search_item[0].lower() and key[1] == search_item[1]]
        else:
            matching_keys = [key for key in lookup_dict if key.lower() == search_item.lower() and key == search_item]
        if matching_keys:
            # Retrieve the corresponding values from second level key
            matches = [lookup_dict[key] for key in matching_keys]
            print(f'found a match for {(soft_title,part)} {matching_keys[0]}')
            print('Matching values:', matches)
            if len(matches[0]) == 1:
                if matches[0][0][4] in sl_href_lookups:
                    # check if the redump url is already tagged to another entry
                    print(f'{matches[0][0][0]} matched {soft_title} {disc} but this redump URL (http://redump.org{matches[0][0][4]}) is linked to another title, it will not be auto-matched')
                    if (soft_title,part) in redump_interactive_matches:
                        print(f'          {(soft_title,part)} in redump_interactive_matches length one, has redump URL - merge')
                        redump_interactive_matches[(soft_title,part)] += matches[0]
                        print(f'          Latest:{redump_interactive_matches}')
                    else:
                        print(f'          {(soft_title,part)} in part_matches length one, no redump URL - update dict')
                        redump_interactive_matches.update({(soft_title,part):matches[0]})
                        print(f'          Latest:{redump_interactive_matches}')
                elif (soft_title,part) in part_matches:
                    print(f'         {(soft_title,part)} in part_matches - single length - merging')
                    part_matches[(soft_title,part)] += (matches[0])
                    print(f'          Latest:{part_matches}')
                else:
                    print(f'         {(soft_title,part)} not in part_matches - single length, updating the dict')
                    part_matches.update({(soft_title,part):matches[0]})
                    print(f'          Latest:{part_matches}')
            elif (soft_title,part) in part_matches:
                print(f'          {(soft_title,part)} in part_matches - multi length - merging')
                part_matches[(soft_title,part)] += (matches[0])
                print(f'          Latest:{part_matches}')
            else:
                print(f'          {(soft_title,part)} not in part_matches - multi length')
                part_matches.update({(soft_title,part):matches[0]})
                print(f'          Latest:{part_matches}')
        return part_matches

    ignore_groups = ['no-intro','redump']

    for soft_title, soft in sl_dict.items():
        if 'prototype' in soft['description'].lower() and skip_proto:
            continue # skip unmatched prototypes by default
        for part,part_data in soft['parts'].items():
            part_matches = {}
            # skip titles where a redump source is identified
            if 'source_group' in part_data and any(group in part_data['source_group'].lower() for group in ignore_groups):
                continue
            # set a string for the disc number to use later
            disc = get_user_disc(part)

            # sanitize the description to better match no-intro standard
            nointrofix = tweak_nointro_dat(soft['description'].strip())
            if disc:
                nointrofix = nointrofix + disc
            if 'serial' in soft and lookup_type == 'name_serial':
                for ser in soft['serial']:
                    redump_tuple = (nointrofix,ser)
                    print(f'redump tuple is {redump_tuple}')
                    #print(f'redump_tuple is {redump_tuple}')
                    part_matches = update_match_lists(redump_tuple,part_matches,lookup_dict)
                    print(f'{soft_title} {disc} part_matches is {part_matches}')

            elif lookup_type == 'name': # generate a lookup list based on name close matches
                print(f'\ngen matching keys for {soft_title}, {disc}')
                matching_keys = get_close_matches(nointrofix, lookup_dict.keys(),n=5)
                if matching_keys:
                    print(f'key match for {soft_title}, {disc}: {matching_keys}')
                    # Retrieve the corresponding values for the detailed options
                    matches = []
                    for key in matching_keys:
                        matches += lookup_dict[key]
                    print(f'L2 matches are: {matches}')
                    redump_interactive_matches.update({(soft_title,part):matches})
            elif 'serial' in soft and lookup_type == 'serial': # look for exact serial matches
                print('in name_serial_auto_map exact serial mapping function')
                if len(soft['serial']) < len(soft['parts']):
                    print('fewer serial numbers than disc parts, this title can\'t be automatically mapped')
                    continue
                for ser in soft['serial']:
                    part_matches = update_match_lists(ser, part_matches,lookup_dict)
                    
            if part_matches:
                if len(part_matches[(soft_title,part)][0]) == 1:
                    print(f'{soft_title} {disc} part_matches is {part_matches}, updating single match dict')
                    redump_single_matches.update(part_matches)
                else:
                    print(f'{soft_title} {disc} part_matches is {part_matches}, updating interactive dict')
                    redump_interactive_matches.update(part_matches)

    if len(redump_single_matches) >= 1:
        # iterate through the matches to see if there are unmatched redump dat entries which match these names
        print(f'\n\n Found {len(redump_single_matches)} discs which should support automatic re-mapping, but results should be closely reviewed')
        auto_match_confirm = inquirer.confirm(f'Continue', default=False)
        if auto_match_confirm:
            for soft_key, match_tuple in redump_single_matches.items():
                dat_match = False
                dat = ''
                redump_title = match_tuple[0][0]
                redump_url = match_tuple[0][4]
                for match_dat in dat_dict['name_lookup'].keys():

                    # skip non redump dats
                    if dat_dict['dat_group'][match_dat] != 'redump':
                        continue

                    if redump_title in dat_dict['name_lookup'][match_dat]:
                        dat_match = True
                        dat = match_dat
                        print(f'Got a DAT match:\n   Softlist: {sl_dict[soft_key[0]]["description"]}\n     Redump: {redump_title}\n')
                        
                if not dat_match:
                        redump_interactive_matches.update({soft_key:match_tuple})

                elif dat_match:
                    # pass the required info to a function which creates a key to append to a list of matches
                    new_source_sha = (dat_dict['name_lookup'][dat][redump_title]['sha1_digest'], 'sha1')
                    redump_softlist_matches.update(create_update_entry(soft_key,sl_dict,dat_dict,dat,redump_title,new_source_sha,redump_url))
                    

    #from modules.utils import write_data
    #debug_list.append({'redump_single_matches':redump_single_matches})
    #debug_list.append({'redump_interactive_matches':redump_interactive_matches})
    #debug_list.append({'lookup_dict':lookup_dict})
    #write_data(debug_list)
    return redump_softlist_matches, redump_interactive_matches

       

def soft_redump_match(redump_title,softlist_title):
    # convert the description to comply with nointro/redump
    nointrofix = tweak_nointro_dat(softlist_title)
    # convert the redump title to better match softlist standards
    redump_soft = redump_to_softlist_fmt(redump_title)
    if nointrofix.lower() == redump_soft.lower():
        return True
    else:
        print('No match: '+nointrofix+', '+redump_soft)
        return False
      

def build_redump_site_dict(platform,script_dir):

    def get_largest_page_number(soup):
        pages_div = soup.find('div', {'class': 'pages'})
        if pages_div is not None:
            page_numbers = [int(page.text) for page in pages_div.find_all('a') if page.text.isdigit()]
            largest_page_number = max(page_numbers)
        else:
            largest_page_number = 1
        return largest_page_number

    import time
    games_dict = {}
    redump_url = 'http://redump.org/discs/system/'+redump__platform_paths[platform]+'/'
    html = requests_retry_session().request("GET", redump_url, timeout=3)
    soup = BeautifulSoup(html.text, 'lxml')
    max_page = get_largest_page_number(soup)
    games_dict = {}
    games_dict.update(parse_games_table(games_dict,soup))
    for page in range(2,max_page+1):
        time.sleep(3)
        url = redump_url+'?page='+str(page)
        html = requests_retry_session().request("GET", url, timeout=3)
        soup = BeautifulSoup(html.text, 'lxml')
        games_dict.update(parse_games_table(games_dict,soup))
    redump_site_dict[platform] = games_dict
    save_data(redump_site_dict,'redump_site_dict',script_dir)
    

def parse_games_table(games_dict, soup):
    table = soup.find('table', class_='games')
    print(f'table is \n{table.text}')
    rows = table.find_all('tr')[1:]
    rev_list = {}
    for row in rows:
        cols = row.find_all('td')
        region = cols[0].find('img')['alt']
        # Get the game title and disc href
        title_cell = cols[1]
        title_link = title_cell.find('a')
        #title = title_link.text.strip().split('\n')[0]
        disc_href = title_link.get('href')

        # Handle titles that span two lines
        localized_title = None
        br_tag = title_cell.find('br')
        if br_tag:
            #localized = title_link.text.strip().split('\n')[1]
            title_lines = br_tag.previous_sibling.strip().split('\n')
            localized_title = br_tag.find_next_siblings()[0].text
        else:
            title_lines = title_cell.text.strip().split('\n')
        rtitle = title_lines[0]         
        system = cols[2].text.strip()
        version = cols[3].text.strip()
        edition = cols[4].text.strip()
        languages = cols[5].find_all('img')
        languages = [lang['alt'] for lang in languages]
        if 'title' in cols[6].attrs:
            rawserial = cols[6]['title'].strip()
        else:
            rawserial = cols[6].text.strip()
        if ',' in rawserial:
            serials = []
            rawserials = rawserial.split(',')
            for serial in rawserials:
                serials.append(serial.strip())     
        else:
            serials = [rawserial.strip()]
        raw_status = cols[7].find('img')['alt']
        if raw_status == 'Dumped from original media':
            status = 'single'
        elif raw_status == '2 and more dumps from original media [!]':
            status = 'verified'
        else:
            status = raw_status
        dat_style_title = tweak_nointro_dat(rtitle,languages,region)
        game_entry = {
            'db_title' : rtitle,
            'dat_style' : dat_style_title, # needs more work
            'href': disc_href,
            'region': region,
            'system': system,
            'version': version,
            'edition': edition,
            'languages': languages,
            'serial': serials,
            'status': status
        }
        if localized_title:
            game_entry['localized'] = localized_title
        if disc_href not in games_dict:
            games_dict[disc_href] = {}
        if dat_style_title in games_dict[disc_href]:
            # handle different revisions with the same url
            if version:
                revtitle = dat_style_title+'('+version+')'
            else:
                revtitle = dat_style_title+'('+re.sub(r'/disc/(\d+)/',r'\1',disc_href)+')'
            rev_list.update({serial:revtitle})
            if revtitle in games_dict[disc_href]:
                print('duplicate title for serial '+serial+':\n'+revtitle)
                print('This error isn\'t handled')        
            games_dict[disc_href][revtitle] = game_entry
        else:
            games_dict[disc_href] = game_entry
    return games_dict

def build_libcrypt_dict(script_dir):
    build_redump_site_dict('psx_libcrypt',script_dir)
    


def get_missing_zips(sl_dict,dat_dict):
    missing = {}
    for soft, soft_data in sl_dict.items():
        if 'source_found' in soft_data and soft_data['source_found']:
            for disc, disc_data in soft_data['parts'].items():
                if 'source_rom' not in disc_data:
                    if 'source_group' in disc_data:
                        source_group = disc_data['source_group']
                        if source_group not in missing:
                            missing.update({source_group:[]})
                    else:
                        continue
                    if 'source_sha' and 'source_dat' in disc_data:
                        try:
                            dat_title = dat_dict['hashes'][disc_data['source_dat']][disc_data['source_sha']]['name']
                            missing[source_group].append(dat_title)
                        except:
                            print('    key error')
                            print('    Title '+soft+': '+soft_data['description'])
                            print('    source_sha: '+str(disc_data['source_sha']))
                else:
                    continue
    if missing:
        for group, titles in missing.items():
            print(f'\nDAT Group {group}:')
            for rom in sorted(list(set(titles))):
                print(rom)


def update_description(soft):
    print('Original Title is: '+soft)
    question = [inquirer.Text(soft, message="    New Title")]
    answer = inquirer.prompt(question)
    return answer

