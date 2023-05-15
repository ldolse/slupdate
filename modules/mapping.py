import re
import requests
#from bs4 import BeautifulSoup
#from requests.adapters import HTTPAdapter
#from requests.packages.urllib3.util.retry import Retry
from modules.utils import save_data, restore_dict
import inquirer


redump_site_dict = restore_dict('redump_site_dict')
redump_site_dict.pop('segacd')

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
                     '3do_m2':'3do'
                    }

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
    
def lkup_redump_url(soft_title):
    try:
        return sl_dict[soft_title]['disc1source']
    except:
        return None


def redump_to_softstyle(redump_name):
    languages = re.compile(r'\s?\(((En|Ja|Fr|De|Es|It|Nl|Pt|Sv|No|Da|Fi|Zh|Ko|Pl),?)+\)')
    discpat = r'\s\([D|d]isc\s\d+\)'
    softtitle  = re.sub(discpat,'',redump_name)
    return re.sub(languages,'',softtitle)

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



def select_from_redump(soft, soft_nointro, san_redumplst):
    matchlist = get_close_matches(soft, san_redumplst,n=5)
    if len(matchlist) > 0:
        closematch = next((s for s in matchlist if soft_nointro.lower() in s.lower()), None)
        if not check_rd_shorthand(soft,matchlist):
            if closematch:
                stripped = redump_to_softstyle(closematch)
                if soft_nointro.lower() == stripped.lower():
                    return {soft:closematch}, True
            print('')
            print('   Mame Title: '+soft_nointro)
            matchlist.append('No Match')
            matchlist.append('Stop')
            answer = list_menu(soft, matchlist, '  Matches')
            return answer, False
        else:
            return {soft:'No Match'}, True
    else:
        return {soft:'No Match'}, True


        
def tweak_nointro_dat(stitle,languages=[],region=''):
    '''
    if only title is supplied, sub common characters that aren't supported in the 
    nointro/redump dat standard to increase likelihood of an auto-match
    if language and region are supplied then it will attempt to create a string
    which matches the redump DAT from the redump db info
    doesn't handle revisions or any of the less frequently used fields
    '''
    lang_sub = {
          'English' : 'En',
         'Japanese' : 'Ja',
           'French' : 'Fr',
           'German' : 'De',
          'Spanish' : 'Es',
          'Italian' : 'It',
            'Dutch' : 'Nl',
       'Portuguese' : 'Pt',
          'Swedish' : 'Sv',
        'Norwegian' : 'No',
           'Danish' : 'Da',
          'Finnish' : 'Fi',
          'Chinese' : 'Zh',
           'Korean' : 'Ko',
           'Polish' : 'Pl',
           'Russian': 'Ru',
           'Arabic' : 'Ar'
         }
    disc_pat = r'\s\(Disc\s\d+\)'
    disc_match = re.findall(disc_pat,stitle)
    if disc_match:
        disc = disc_match[0]
    else:
        disc = ''
    if len(languages) > 1:
        dat_lang = ' ('
        loop = 1
        for language in languages:
            lang = lang_sub[language]
            dat_lang = dat_lang+lang
            if len(languages) - 1 >= loop:
                dat_lang = dat_lang+','
            loop += 1
        dat_lang = dat_lang+')'
    else:
        dat_lang = ''
    if region:
        region = ' ('+region+')'
    # fix for some region shorthand
    stitle = re.sub(r'\(Euro\)','(Europe)',stitle)
    stitle = re.sub(disc_pat,'',stitle)
    stitle = re.sub(r':',' -',stitle)
    stitle = re.sub(r'/','-',stitle)
    return stitle+region+dat_lang+disc

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
    for soft in sllist:
        if soft in answers:
            continue
        else:
            print('checking '+soft)
            process_comments(get_sl_entry(my_soft['software'],soft,'redump'), sl_dict)
            soft_nointro = tweak_nointro_dat(soft)
        if soft in san_redumplst:
            answers.update({soft:soft})
            matches += 1
        elif soft_nointro in san_redumplst and soft_nointro not in answers.values():
            answers.update({soft:soft_nointro})
            autofix += 1
        else:
            rurl = lkup_redump_url(soft)
            if rurl and online:
                rdict = get_redump_title_info(rurl)
                print_redump_info(rdict)
            answer, auto = select_from_redump(soft, soft_nointro, san_redumplst)
            if answer[soft] == 'Stop':
                break
            elif answer[soft] == 'No Match':
                no_match += 1
                answers.update(answer)
            else:
                if answer[soft] in answers.values():
                    print('title has already been selected')
                    answer[soft] = 'No Match'
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


def check_rd_shorthand(soft,matchlist):
    '''
    todo - handle taikenban / demo matching
    '''
    shorthand = ['proto','beta','sample']
    for short in shorthand:
        if short in soft.lower() and (s for s in matchlist if short in s.lower()):
            print('prototype or beta/demo not in redump, skipping')
            return True
    return False


def update_nonmatch(answers, san_redumplst):
    '''
    requires a populated answer list from the first pass and
    the sanitised title list from a redump dat (disc# stripped)
    '''
    for soft, redump in answers.items():
        confirmq = [
            inquirer.Confirm("inredump", message="Check "+soft+" against Redump titles?"),
        ]
        if redump == 'No Match':
            process_comments(get_sl_entry(my_soft['software'],soft,'redump'), sl_dict)
            inredump = inquirer.prompt(confirmq)
            if inredump['inredump']:
                rurl = lkup_redump_url(soft)
                if rurl and online:
                    rdict = get_redump_title_info(rurl)
                    print_redump_info(rdict)
                softnointro = tweak_nointro_dat(soft)
                answer, auto = select_from_redump(soft, softnointro, san_redumplst)
                if answer[soft] == 'Stop':
                    break
                elif answer[soft] in answers.values():
                    if answer[soft] != 'No Match':
                        print('title has already been selected')
                    try:
                        answer = update_title(soft)
                        if answer[soft] not in answers.values():
                            answers.update(answer)
                        else:
                            print('title has already been selected')
                    except:
                        continue
                elif answer[soft] == 'No Match':
                    try:
                        answer = update_title(soft)
                        if answer[soft] not in answers.values():
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
                            #iteminfo = {soft:redumpurl}
                            sl_dict.update({soft:redumpurl})        
            else:
                try:
                    answer = update_title(soft)
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

def name_serial_map(platform, softlst_platform,dat_platform):
    print('doing serial and name mapping')
    if platform not in redump_site_dict:
        build_redump_site_dict(platform)
    redump_platform = redump_site_dict[platform]
    for soft_title, soft in softlst_platform.items():
        # skip titles where a source is identified
        redump_info = {}
        if 'sourcedat' in soft:
            pass
        elif 'serial' in soft:
            try:
                redump_info = redump_platform[soft['serial']]
            except:
                # serial not in redump table - note some softlist titles have multiple
                # serials, not handled at this point
                pass
            if len(redump_info) > 1:
                print('multiple associated with this serial: '+str(len(redump_info))+' discs')
            for rtitle,info in redump_info.items():
                if soft_redump_match(rtitle, soft['description']):
                    for dat in dat_platform['redump_unmatched'].keys():
                        if rtitle in dat_platform['redump_unmatched'][dat]:
                            print('Got a DAT match for '+soft['description']+' and '+rtitle)
                            
            
def soft_redump_match(redump_title,softlist_title):
    # convert the description to comply with nointro/redump
    nointrofix = tweak_nointro_dat(softlist_title)
    # convert the redump title to better match softlist standards
    redump_soft = redump_to_softstyle(redump_title)
    if nointrofix.lower() == redump_soft.lower():
        return True
    else:
        print('No match: '+nointrofix+', '+redump_soft)
        return False
      

def build_redump_site_dict(platform):
    import time
    games_dict = {}
    redump_url = 'http://redump.org/discs/system/'+redump__platform_paths[platform]+'/'
    html = requests_retry_session().request("GET", redump_url, timeout=3)
    soup = BeautifulSoup(html.text, 'xml')
    max_page = get_largest_page_number(soup)
    games_dict = {}
    games_dict.update(parse_games_table(games_dict,soup))
    for page in range(2,max_page+1):
        time.sleep(3)
        url = redump_url+'?page='+str(page)
        html = requests_retry_session().request("GET", url, timeout=3)
        soup = BeautifulSoup(html.text, 'xml')
        games_dict.update(parse_games_table(games_dict,soup))
    redump_site_dict[platform] = games_dict
    save_data(redump_site_dict,'redump_site_dict')
    

def get_largest_page_number(soup):
    pages_div = soup.find('div', {'class': 'pages'})
    page_numbers = [int(page.text) for page in pages_div.find_all('a') if page.text.isdigit()]
    largest_page_number = max(page_numbers)
    return largest_page_number

def parse_games_table(games_dict, soup):
    table = soup.find('table', class_='games')
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
        rawserial = cols[6].text.strip()
        if ',' in rawserial:
            serials = rawserial.split(',')
        else:
            serials = [rawserial]
        status = cols[7].find('img')['alt']

        dat_title = tweak_nointro_dat(rtitle,languages,region)
        game_entry = {
            'db_title' : rtitle,
            'dat_style' : dat_title, # needs more work
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
        for serial in serials:
            serial = serial.strip()
            if serial not in games_dict:
                games_dict[serial] = {}
            if dat_title in games_dict[serial]:
                # handle different revisions with the same serial number
                if version:
                    revtitle = dat_title+'('+version+')'
                else:
                    revtitle = dat_title+'('+re.sub(r'/disc/(\d+)/',r'\1',disc_href)+')'
                rev_list.update({serial:revtitle})
                if revtitle in games_dict[serial]:
                    print('duplicate title for serial '+serial+':\n'+revtitle)
                    print('This error isn\'t handled')        
                games_dict[serial][revtitle] = game_entry
            else:
                games_dict[serial][dat_title] = game_entry
    return games_dict



def update_title(soft):
    print('Original Title is: '+soft)
    question = [inquirer.Text(soft, message="    New Title")]
    answer = inquirer.prompt(question)
    return answer

 
