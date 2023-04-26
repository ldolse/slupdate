
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
        return sl_dict[soft_title]['disc1source']
    except:
        return None


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


        
def tweak_nointro(soft):
    # sub common characters that aren't supported in the 
    # nointro/redump standard to enable more automatic matches
    soft_nointro = re.sub(r':',' -',soft)
    soft_nointro = re.sub(r'/','-',soft_nointro)
    return soft_nointro

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


def update_title(soft):
    print('Original Title is: '+soft)
    question = [inquirer.Text(soft, message="    New Title")]
    answer = inquirer.prompt(question)
    return answer

 
