#!/usr/bin/env python

""" slupdate.py: Interactively Update Optical Media based Software Lists 
against[Redump](http://redump.org/) dats.

https://github.com/ldolse/slupdate
"""


import os
import re
import sys
import glob
import pickle
import traceback
import xmltodict
import pykakasi
import pprint
import pathlib
import subprocess
import tempfile
import logging
import inquirer
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from  lxml import etree
from difflib import get_close_matches
from bs4 import BeautifulSoup

# Require at least Python 3.8
assert sys.version_info >= (3, 8)

__version__ = '.1'

datpaths = {
    'sl' : '../mame/hash/',
    'redump' : '../'
}

def pickling(dataset):
    with open('dataset.cache', 'wb') as f:
        pickle.dump(dataset, f)

def unpickling():
    try:
        with open('dataset.cache', 'rb') as f:
            return pickle.load(f)
    except:
        return None

def requests_retry_session(
    retries=10,
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

sl_dat_mapping = {
    "dc" : {
    "mame" : "dc.xml",
    "redump" : "Sega - Dreamcast*.dat"
    },
    "psx" : {
    "mame" : "psx.xml",
    "redump" : "Sony - Dreamcast*.dat"
    },
    "saturn" : {
    "mame" : "saturn.xml",
    "redump" : "Sega - Saturn*.dat"
    },
    "megacd" : {
    "mame" : "megacd.xml",
    "redump" : "Sega - megacd*.dat"
    }   
   }



try:
    infodict
except:
    infodict = {}
    # example of adding an item to this dict
    # infodict['software title']['example'] = 2

def get_dat_paths(platform, datpaths, sl_dat_map):
    slpath = datpaths['sl']+sl_dat_map[platform]['mame']
    redump_pattern = datpaths['redump']+sl_dat_map[platform]['redump']
    files = glob.glob(redump_pattern)
    redump_path = files[0]
    return [slpath, redump_path]


def chdman_ver():
    try:
        proc = subprocess.Popen('chdman', stdout=subprocess.PIPE)
        output = proc.stdout.read()
        version = re.findall(r'\d+\.\d+',output.decode('ascii'))
    except:
        logging.debug(f'chdman not in the system path or installed with slupdate')
    return version[0]


def slupdate_version():
    return __version__


def get_sl_titles(soup):
    softwares = soup.find_all('software')
    titles = []
    for soft in softwares:
        titles.append(soft.description.text)
    return titles.sort()
    
def input_to_soup(input):
    with open(input, 'r') as f:
        file = f.read()
    soup = BeautifulSoup(file, 'xml')
    return soup
    
def print_mame_names(softlist):
    for item in my_soft['software']:
        pprint.pprint(item['@name'])
        

def get_sl_descriptions(softlist,dat_type,field):
    '''
    softlist is a list of software list dictionaries
    field is one of the field names in the soft list
    '''
    sl = []
    for item in softlist[dat_type]:
        sl.append(item[field])
    return sl

def redump_source(found):
    if found: print("found a redump url")
    else: print("no redump")

def romhashes_to_dict(comment):
    xmlheader = '<?xml version="1.0" ?><root>'
    xmlclose = '</root>'
    fixed_comment = xmlheader+comment+xmlclose
    try:
        commentdict = xmltodict.parse(fixed_comment)
        return commentdict
    except:
        print('failed to parse comment')
        return None
    

def process_comments(soft, infodict):
    redumpurl = r'^http://redump'
    romhash = r'^<rom name'

    for comment in soft['#comment']:
        if re.match(redumpurl,comment):
            redumplist = re.split(r'(,|\s+)',comment)
            discnum = 1
            sourcedict = {}
            for url in redumplist:
                if re.match(redumpurl,url):
                    sourcedict['disc'+str(discnum)+'source'] = url
                    discnum += 1
                else:
                    print('other info mixed with redump source comment')
            try:
                infodict[soft['description']].update(sourcedict)
            except:
                urls = {soft['description']:sourcedict}
                infodict.update(urls)
            
        elif re.match(romhash,comment):
            #print('romhash')
            commentdict = romhashes_to_dict(comment)
            if commentdict: 
                try:
                    infodict[soft['description']].update(commentdict['root'])
                except:
                    itemhashes = {soft['description']:commentdict['root']}
                    infodict.update(itemhashes)


def build_infodict(softlist, infodict):
    '''
    grabs useful data and inserts into a simple to manage dict
    '''
    for item in softlist:
        process_comments(item, infodict)


def print_discs(softlist):
    for item in my_soft['software']:
        pprint.pprint(item['part'])

def print_sha1s(softlist):
    for item in my_soft['software']:
        print('mame name is '+item['@name']+' and descrption is '+item['description'])
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

def convert__bincue_to_chd(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path, show_command_output: bool):
    # Use another temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)

        logging.debug(f'Converting "{chd_file_path.name}" to .bin/.cue format')
        chdman_result = subprocess.run(["chdman", "createcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], stdout=None if show_command_output else subprocess.DEVNULL)
        if chdman_result.returncode != 0:
            # chdman provides useful progress output on stderr so we don't want to capture stderr when running it. That means we can't provide actual error output to the exception, but I can't find a way around that.
            raise ConversionException("Failed to convert .chd using chdman", chd_file_path, None)

def convert_xml(file, comments=False):
    #read xml content from the file
    fileptr = open(file,"r")
    xml_content= fileptr.read()
    #print("XML content is:")
    #print(xml_content)
    my_ordered_dict=xmltodict.parse(xml_content, process_comments=comments)
    return my_ordered_dict

def discs_to_titles(disclist):
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

def opt_menu(key, options, prompt):
    selection = options
    optconfirm = [
        inquirer.List(key,
                      message = prompt,
                      choices = options,
                      carousel = True),
                    ]
    answer = inquirer.prompt(optconfirm)
    return answer

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
        
def select_from_redump(soft, soft_nointro, san_redumplst):
    languages = re.compile(r'\s?\(((En|Ja|Fr|De|Es|It|Nl|Pt|Sv|No|Da|Fi|Zh|Ko|Pl),?)+\)')
    matchlist = get_close_matches(soft, san_redumplst,n=5)
    if len(matchlist) > 0:
        closematch = next((s for s in matchlist if soft_nointro.lower() in s.lower()), None)
        if not check_rd_shorthand(soft,matchlist):
            if closematch:
                stripped = re.sub(languages,'',closematch)
                if soft_nointro.lower() == stripped.lower():
                    return {soft:closematch}, True
            print('')
            print('   Mame Title: '+soft_nointro)
            matchlist.append('No Match')
            matchlist.append('Stop')
            answer = opt_menu(soft, matchlist, '  Matches')
            return answer, False
        else:
            return {soft:'No Match'}, True
    else:
        return {soft:'No Match'}, True

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
    


def rtable_to_dict(bs_table):
    gameinfo = {}
    alt = re.compile(r'(Region|Languages)')
    for bsr in bs_table:
        if bsr.find('th') and not re.search(alt,bsr.find('th').text):
            gameinfo.update({bsr.find('th').text:bsr.find('td').text})
        elif bsr.find('th'):
            gameinfo.update({bsr.find('th').text:bsr.find('img').get('title')})
    return gameinfo
    

def get_redump_info(redumpurl):
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
        return infodict[soft_title]['disc1source']
    except:
        return None
        
def tweak_nointro(soft):
    # sub common characters that aren't supported in the 
    # nointro/redump standard to enable more automatic matches
    soft_nointro = re.sub(r':',' -',soft)
    soft_nointro = re.sub(r'/','-',soft_nointro)
    return soft_nointro

def compare_sl_with_redump(sllist,san_redumplst,answers={}):
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
            process_comments(get_sl_entry(my_soft['software'],soft,'redump'), infodict)
            soft_nointro = tweak_nointro(soft)
        if soft in san_redumplst:
            answers.update({soft:soft})
            matches += 1
        elif soft_nointro in san_redumplst and soft_nointro not in answers.values():
            answers.update({soft:soft_nointro})
            autofix += 1
        else:
            rurl = lkup_redump_url(soft)
            if rurl and online:
                rdict = get_redump_info(rurl)
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
    
def update_title(soft):
    print('Original Title is: '+soft)
    question = [inquirer.Text(soft, message="    New Title")]
    answer = inquirer.prompt(question)
    return answer

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
            process_comments(get_sl_entry(my_soft['software'],soft,'redump'), infodict)
            inredump = inquirer.prompt(confirmq)
            if inredump['inredump']:
                rurl = lkup_redump_url(soft)
                if rurl and online:
                    rdict = get_redump_info(rurl)
                    print_redump_info(rdict)
                softnointro = tweak_nointro(soft)
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
                            infodict.update({soft:redumpurl})        
            else:
                try:
                    answer = update_title(soft)
                    answers.update(answer)
                except:
                    continue
    return answers

def zip_slredump_infodict(sl_re_map,infodict):
   for soft, redump in sl_re_map.items():
        try:
            infodict[soft].update({'redumpmap':redump})
        except:
            infodict.update({soft:{'redumpmap':redump}})

def save_session():
    dataset = {}
    save = inquirer.prompt(
                [inquirer.Confirm('save',message='Save Session?',default=True)
                ])
    if save:
        dataset.update({'sl_redump_titlemap':myanswers})
        dataset.update({'infodict':infodict})
        pickling(dataset)

def restore_session():
    dataset = unpickling()
    infodict = dataset['infodict']
    myanswers = dataset['sl_redump_titlemap']
    return myanswers

def history(search=None):
    import readline
    for i in range(readline.get_current_history_length()):
        if search:
            if re.search(search,readline.get_history_item(i + 1)):
                print (readline.get_history_item(i + 1))
        else:
            print (readline.get_history_item(i + 1))

def main_menu():
    options = [
        'Update SL Titles to match Redump Names',
        'Edit non-matching SL Titles',
        'Session Settings',
        'Save Session',
        'Load Previous Session'
        ]

def compare_redump_to_sl(sllist,san_redumplst,answers):
    for title in san_redumplst:
        if title in answers.values():
            continue
        else:
            print(title)
            
def update_sl_descriptions(xml_file, answerdict):
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(xml_file, parser)

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

    with open(xml_file, "w") as f:
        f.write(output)


def add_redump_names_to_slist(xml_file, answerdict):
    # Parse the XML file using lxml
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(xml_file, parser)
    root = tree.getroot()

    for soft_desc, redump_name in answerdict.items():
        if redump_name == 'No Match':
            continue
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

    with open(xml_file, "w") as f:
        f.write(output)


chdman_version = chdman_ver()
online = False

files = get_dat_paths('dc', datpaths, sl_dat_mapping)

# strip the root comment from the softwarelist so xmltodict can parse it
fileptr = open(files[0],"r")
xml = fileptr.read()
sltree = etree.fromstring(bytes(xml, encoding='utf-8'))

raw_sl_dict = convert_xml(files[0],True)
raw_redump_dict = convert_xml(files[1])

#change xml format to ordered dict

#print("Ordered Dictionary is:")
#pprint.pprint(my_ordered_slist)
#print("Softlist description is:")
#pprint.pprint(my_ordered_slist['softwarelist']['software'])

xml_output = xmltodict.unparse(raw_sl_dict, pretty=True)
#print("XML format data is:")
#print(xml_output)
 
#Use contents of ordered dict to make python dictionary
my_soft = dict(raw_sl_dict['softwarelist'])
redumps = dict(raw_redump_dict['datafile'])

#print(raw_sl_dict['softwarelist']['software'][0]['@name'])

sl_description_list = get_sl_descriptions(my_soft,'software','description')
redump_name_list = get_sl_descriptions(redumps,'game','@name')

redump_titles = discs_to_titles(redump_name_list)



def main(gui_input=''): 
    return


#if __name__ == '__main__':
#    try:
#        main()
#    except Exception:
#        print(f'{Font.error_bold}\n\n* Unexpected error:\n\n{Font.end}')
#        traceback.print_exc()
#        input(f'{Font.error_bold}\n\nPress any key to quit slupdate{Font.end}')