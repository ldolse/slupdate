import re
import io
from .constants import *
from modules.ifilter import IFilter
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def identify(self, image_filter: IFilter) -> bool:
    try:
        image_filter.get_data_fork_stream().seek(0)
        test_array = bytearray(512)
        image_filter.get_data_fork_stream().readinto(test_array)
        image_filter.get_data_fork_stream().seek(0)

        # Check for unexpected control characters
        two_consecutive_nulls = False

        for i, byte in enumerate(test_array):
            if i >= image_filter.length:
                break

            if byte == 0:
                if two_consecutive_nulls:
                    return False
                two_consecutive_nulls = True
            else:
                two_consecutive_nulls = False

            if byte < 0x20 and byte not in (0x0A, 0x0D, 0x00):
                return False

        self._cue_stream = io.TextIOWrapper(image_filter.get_data_fork_stream(), encoding='utf-8')
        
        cr = re.compile(self.REGEX_COMMENT)
        dr = re.compile(self.REGEX_DISCTYPE)

        while self._cue_stream.peek() >= 0:
            line = self._cue_stream.readline()

            dm = dr.match(line or "")
            cm = cr.match(line or "")

            # Skip comments at start of file
            if cm:
                continue

            return bool(dm)

        return False

    except Exception as ex:
        logger.error(f"Exception trying to identify image file: {image_filter.filename}")
        logger.exception(ex)
        return False
