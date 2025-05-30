# Constants
CDRDAO_TRACK_TYPE_AUDIO = "AUDIO"
CDRDAO_TRACK_TYPE_MODE1 = "MODE1"
CDRDAO_TRACK_TYPE_MODE1_RAW = "MODE1_RAW"
CDRDAO_TRACK_TYPE_MODE2 = "MODE2"
CDRDAO_TRACK_TYPE_MODE2_FORM1 = "MODE2_FORM1"
CDRDAO_TRACK_TYPE_MODE2_FORM2 = "MODE2_FORM2"
CDRDAO_TRACK_TYPE_MODE2_MIX = "MODE2_FORM_MIX"
CDRDAO_TRACK_TYPE_MODE2_RAW = "MODE2_RAW"

# Regular expressions
REGEX_COMMENT = r'^\s*\/\/(?P<comment>.+)$'
REGEX_COPY = r'^\s*(?P<no>NO)?\s*COPY'
REGEX_DISCTYPE = r'^\s*(?P<type>(CD_DA|CD_ROM_XA|CD_ROM|CD_I))'
REGEX_EMPHASIS = r'^\s*(?P<no>NO)?\s*PRE_EMPHASIS'
REGEX_FILE_AUDIO = r'^\s*(AUDIO)?FILE\s*"(?P<filename>.+)"\s*(#(?P<base_offset>\d+))?\s*((?P<start>[\d]+:[\d]+:[\d]+)|(?P<start_num>\d+))\s*(?P<length>[\d]+:[\d]+:[\d]+)?'
REGEX_FILE_DATA = r'^\s*DATAFILE\s*"(?P<filename>.+)"\s*(#(?P<base_offset>\d+))?\s*(?P<length>[\d]+:[\d]+:[\d]+)?'
REGEX_INDEX = r'^\s*INDEX\s*(?P<address>\d+:\d+:\d+)'
REGEX_ISRC = r'^\s*ISRC\s*"(?P<isrc>[A-Z0-9]{5,5}[0-9]{7,7})"'
REGEX_MCN = r'^\s*CATALOG\s*"(?P<catalog>[\x21-\x7F]{13,13})"'
REGEX_PREGAP = r'^\s*START\s*(?P<address>\d+:\d+:\d+)?'
REGEX_STEREO = r'^\s*(?P<num>(TWO|FOUR))_CHANNEL_AUDIO'
REGEX_TRACK = r'^\s*TRACK\s*(?P<type>(AUDIO|MODE1_RAW|MODE1|MODE2_FORM1|MODE2_FORM2|MODE2_FORM_MIX|MODE2_RAW|MODE2))\s*(?P<subchan>(RW_RAW|RW))?'
REGEX_ZERO_AUDIO = r'^\s*SILENCE\s*(?P<length>\d+:\d+:\d+)'
REGEX_ZERO_DATA = r'^\s*ZERO\s*(?P<length>\d+:\d+:\d+)'
REGEX_ZERO_PREGAP = r'^\s*PREGAP\s*(?P<length>\d+:\d+:\d+)'
REGEX_DISC_SCRAMBLED = r'^\s*DataTracksScrambled\s*=\s*(?P<value>\d+)'

# CD-Text related regex
REGEX_ARRANGER = r'^\s*ARRANGER\s*"(?P<arranger>.+)"'
REGEX_COMPOSER = r'^\s*COMPOSER\s*"(?P<composer>.+)"'
REGEX_DISC_ID = r'^\s*DISC_ID\s*"(?P<discid>.+)"'
REGEX_MESSAGE = r'^\s*MESSAGE\s*"(?P<message>.+)"'
REGEX_PERFORMER = r'^\s*PERFORMER\s*"(?P<performer>.+)"'
REGEX_SONGWRITER = r'^\s*SONGWRITER\s*"(?P<songwriter>.+)"'
REGEX_TITLE = r'^\s*TITLE\s*"(?P<title>.+)"'
REGEX_UPC = r'^\s*UPC_EAN\s*"(?P<catalog>[\d]{13,13})"'

# Unused regex
REGEX_CD_TEXT = r'^\s*CD_TEXT\s*\{'
REGEX_CLOSURE = r'^\s*\}'
REGEX_LANGUAGE = r'^\s*LANGUAGE\s*(?P<code>\d+)\s*\{'
REGEX_LANGUAGE_MAP = r'^\s*LANGUAGE_MAP\s*\{'
REGEX_LANGUAGE_MAPPING = r'^\s*(?P<code>\d+)\s?\:\s?(?P<language>\d+|\w+)'