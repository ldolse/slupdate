import re
import os
import io
import struct
from typing import List, Dict, Optional
from .structs import CdrdaoDisc, CdrdaoTrack, CdrdaoTrackFile
from .constants import *
from .utilities import *
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC
from modules.ifilter import IFilter

from modules.error_number import ErrorNumber
from modules.CD.cd_types import MediaType, TrackType
from .constants import *
from .utilities import process_track_gaps, process_track_indexes, lba_to_msf

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_full_toc(tracks: List[CdrdaoTrack], track_flags: Dict[int, int], create_c0_entry: bool = False) -> bytes:
    toc = CDFullTOC()
    session_ending_track = {}
    toc.first_complete_session = 255
    toc.last_complete_session = 0
    track_descriptors = []
    current_track = 0

    for track in sorted(tracks, key=lambda t: t.sequence):
        if track.sequence < toc.first_complete_session:
            toc.first_complete_session = track.sequence

        if track.sequence <= toc.last_complete_session:
            current_track = track.sequence
            continue

        if toc.last_complete_session > 0:
            session_ending_track[toc.last_complete_session] = current_track

        toc.last_complete_session = track.sequence

    session_ending_track[toc.last_complete_session] = max(t.sequence for t in tracks)

    current_session = 0

    for track in sorted(tracks, key=lambda t: t.sequence):
        track_control = track_flags.get(track.sequence, 0)

        if track_control == 0 and track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
            track_control = 0x04  # Data track flag

        # Lead-Out
        if track.sequence > current_session and current_session != 0:
            leadout_amsf = lba_to_msf(track.start_sector - 150) # subtract 150 for lead-in
            leadout_pmsf = lba_to_msf(max(t.start_sector for t in tracks))

            # Lead-out
            track_descriptors.append(TrackDataDescriptor(
                session_number=current_session,
                point=0xB0,
                adr=5,
                control=0,
                hour=0,
                min=leadout_amsf[0],
                sec=leadout_amsf[1],
                frame=leadout_amsf[2],
                phour=2,
                pmin=leadout_pmsf[0],
                psec=leadout_pmsf[1],
                pframe=leadout_pmsf[2]
            ))

            # This seems to be constant? It should not exist on CD-ROM but CloneCD creates them anyway
            # Format seems like ATIP, but ATIP should not be as 0xC0 in TOC...
            if create_c0_entry:
                track_descriptors.append(TrackDataDescriptor(
                    session_number=current_session,
                    point=0xC0,
                    adr=5,
                    control=0,
                    min=128,
                    pmin=97,
                    psec=25
                ))

        # Lead-in
        if track.sequence > current_session:
            current_session = track.sequence
            ending_track_number = session_ending_track.get(current_session, 0)

            leadin_pmsf = lba_to_msf(next((t.start_sector + t.sectors for t in tracks if t.sequence == ending_track_number), 0))

            # Starting track
            track_descriptors.append(TrackDataDescriptor(
                session_number=current_session,
                point=0xA0,
                adr=1,
                control=track_control,
                pmin=track.sequence
            ))

            # Ending track
            track_descriptors.append(TrackDataDescriptor(
                session_number=current_session,
                point=0xA1,
                adr=1,
                control=track_control,
                pmin=ending_track_number
            ))

            # Lead-out start
            track_descriptors.append(TrackDataDescriptor(
                session_number=current_session,
                point=0xA2,
                adr=1,
                control=track_control,
                phour=0,
                pmin=leadin_pmsf[0],
                psec=leadin_pmsf[1],
                pframe=leadin_pmsf[2]
            ))

        pmsf = lba_to_msf(track.indexes.get(1, track.start_sector))

        # Track
        track_descriptors.append(TrackDataDescriptor(
            session_number=track.sequence,
            point=track.sequence,
            adr=1,
            control=track_control,
            phour=0,
            pmin=pmsf[0],
            psec=pmsf[1],
            pframe=pmsf[2]
        ))

    toc.track_descriptors = track_descriptors

    # Create binary representation
    toc_ms = io.BytesIO()
    toc_ms.write(struct.pack('>H', len(track_descriptors) * 11 + 2))  # DataLength
    toc_ms.write(bytes([toc.first_complete_session, toc.last_complete_session]))

    for descriptor in toc.track_descriptors:
        toc_ms.write(bytes([
            descriptor.session_number,
            (descriptor.adr << 4) | descriptor.control,
            descriptor.tno,
            descriptor.point,
            descriptor.min,
            descriptor.sec,
            descriptor.frame,
            descriptor.zero,
            descriptor.pmin,
            descriptor.psec,
            descriptor.pframe
        ]))

    return toc_ms.getvalue()

def parse_toc_file(image_filter: IFilter) -> Tuple[ErrorNumber, Optional[CdrdaoDisc]]:
    try:
        with image_filter.get_data_fork_stream() as toc_stream:
            toc_content = toc_stream.read().decode('utf-8')

        lines = toc_content.split('\n')
        discimage = CdrdaoDisc(tracks=[], comment="")
        current_track = None
        current_track_number = 0
        current_sector = 0
        in_track = False
        next_index = 2  # Initialize next_index before the loop
        comment_builder = []
        last_end_sector = 0

        # Initialize all RegExs
        regex_comment = re.compile(REGEX_COMMENT)
        regex_disk_type = re.compile(REGEX_DISCTYPE)
        regex_mcn = re.compile(REGEX_MCN)
        regex_track = re.compile(REGEX_TRACK)
        regex_copy = re.compile(REGEX_COPY)
        regex_emphasis = re.compile(REGEX_EMPHASIS)
        regex_stereo = re.compile(REGEX_STEREO)
        regex_isrc = re.compile(REGEX_ISRC)
        regex_index = re.compile(REGEX_INDEX)
        regex_pregap = re.compile(REGEX_PREGAP)
        regex_zero_pregap = re.compile(REGEX_ZERO_PREGAP)
        regex_zero_data = re.compile(REGEX_ZERO_DATA)
        regex_zero_audio = re.compile(REGEX_ZERO_AUDIO)
        regex_audio_file = re.compile(REGEX_FILE_AUDIO)
        regex_file = re.compile(REGEX_FILE_DATA)
        regex_title = re.compile(REGEX_TITLE)
        regex_performer = re.compile(REGEX_PERFORMER)
        regex_songwriter = re.compile(REGEX_SONGWRITER)
        regex_composer = re.compile(REGEX_COMPOSER)
        regex_arranger = re.compile(REGEX_ARRANGER)
        regex_message = re.compile(REGEX_MESSAGE)
        regex_disc_id = re.compile(REGEX_DISC_ID)
        regex_upc = re.compile(REGEX_UPC)
        regex_disc_scrambled = re.compile(REGEX_DISC_SCRAMBLED)

        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            
            match_comment = regex_comment.match(line)
            match_disk_type = regex_disk_type.match(line)
            match_mcn = regex_mcn.match(line)
            match_track = regex_track.match(line)
            match_copy = regex_copy.match(line)
            match_emphasis = regex_emphasis.match(line)
            match_stereo = regex_stereo.match(line)
            match_isrc = regex_isrc.match(line)
            match_index = regex_index.match(line)
            match_pregap = regex_pregap.match(line)
            match_zero_pregap = regex_zero_pregap.match(line)
            match_zero_data = regex_zero_data.match(line)
            match_zero_audio = regex_zero_audio.match(line)
            match_audio_file = regex_audio_file.match(line)
            match_file = regex_file.match(line)
            match_disc_scrambled = regex_disc_scrambled.match(line)

            # cd text matches
            match_title = regex_title.match(line)
            match_performer = regex_performer.match(line)
            match_songwriter = regex_songwriter.match(line)
            match_composer = regex_composer.match(line)
            match_arranger = regex_arranger.match(line)
            match_message = regex_message.match(line)
            match_disc_id = regex_disc_id.match(line)
            match_upc = regex_upc.match(line)

            if match_comment:
                if not match_comment.group("comment").startswith(" Track "):
                    logger.debug(f" Found comment '{match_comment.group('comment').strip()}' at line {line_number}")
                    comment_builder.append(match_comment.group("comment").strip())
            elif match_disk_type:
                logger.debug(f" Found {match_disk_type.group('type')} at line {line_number}")
                discimage.disktypestr = match_disk_type.group("type")
                discimage.disktype = {
                    "CD_DA": MediaType.CDDA,
                    "CD_ROM": MediaType.CDROM,
                    "CD_ROM_XA": MediaType.CDROMXA,
                    "CD_I": MediaType.CDI
                }.get(match_disk_type.group("type"), MediaType.CD)
            elif match_mcn:
                logger.debug(f" Found CATALOG '{match_mcn.group('catalog')}' at line {line_number}")
                discimage.mcn = match_mcn.group("catalog")
            elif match_track := regex_track.match(line):
                if current_track:
                    discimage.tracks.append(current_track)

                current_track_number += 1
                track_type = match_track.group("type")
                current_track = CdrdaoTrack(
                    sequence=current_track_number,
                    start_sector=current_sector,
                    tracktype=track_type,
                    bps=cdrdao_track_type_to_cooked_bytes_per_sector(track_type),
                    subchannel=bool(match_track.group("subchan")),
                    packedsubchannel=match_track.group("subchan") == "RW",
                    indexes={},
                    pregap=0  # We'll calculate this later
                )
                in_track = True
                subchan = match_track.group("subchan")
                logger.debug(f' Found TRACK type "{match_track.group('type')}" {'with no subchannel' if not subchan else f'subchannel {subchan}'} at line {line_number}')

                current_track.sequence = current_track_number
                current_track.start_sector = current_sector
                current_track.tracktype = match_track.group("type")
                
                # Adjust bps bytes per sector based on track type
                if current_track.tracktype in ["AUDIO", "MODE1_RAW", "MODE2_RAW"]:
                    current_track.bps = 2352
                elif current_track.tracktype in ["MODE1", "MODE2_FORM1"]:
                    current_track.bps = 2048
                elif current_track.tracktype == "MODE2_FORM2":
                    current_track.bps = 2324
                elif current_track.tracktype in ["MODE2", "MODE2_FORM_MIX"]:
                    current_track.bps = 2336
                else:
                    logger.warning(f"Unknown track mode: {current_track.tracktype}, defaulting to 2352 bytes per sector")

                if subchan:
                    if subchan == "RW":
                        current_track.packedsubchannel = True
                    current_track.subchannel = True
            elif match_copy and current_track:
                logger.debug(f" Found {'NO ' if match_copy.group('no') else ''}COPY at line {line_number}")
                current_track.flag_dcp = not bool(match_copy.group("no"))
            elif match_emphasis and current_track:
                logger.debug(f" Found {'NO ' if match_emphasis.group('no') else ''}PRE_EMPHASIS at line {line_number}")
                current_track.flag_pre = not bool(match_emphasis.group("no"))
            elif match_stereo and current_track:
                logger.debug(f" Found {match_stereo.group('num')}_CHANNEL_AUDIO at line {line_number}")
                current_track.flag_4ch = match_stereo.group("num") == "FOUR"
            elif match_isrc and current_track:
                logger.debug(f" Found ISRC '{match_isrc.group('isrc')}' at line {line_number}")
                current_track.isrc = match_isrc.group("isrc")
            elif match_index and current_track:
                logger.debug(f" Found INDEX {match_index.group('address')} at line {line_number}")
                minutes, seconds, frames = map(int, match_index.group("address").split(":"))
                index_sector = minutes * 60 * 75 + seconds * 75 + frames
                current_track.indexes[next_index] = index_sector + current_track.pregap + current_track.start_sector
                next_index += 1
            elif match_pregap and current_track:
                logger.debug(f" Found START {match_pregap.group('address') or ''} at line {line_number}")
                current_track.indexes[0] = current_track.start_sector
                if match_pregap.group("address"):
                    minutes, seconds, frames = map(int, match_pregap.group("address").split(":"))
                    current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
                else:
                    current_track.pregap = current_track.sectors
            elif match_zero_pregap and current_track:
                logger.debug(f" Found PREGAP {match_zero_pregap.group('length')} at line {line_number}")
                current_track.indexes[0] = current_track.start_sector
                minutes, seconds, frames = map(int, match_zero_pregap.group("length").split(":"))
                current_track.pregap = minutes * 60 * 75 + seconds * 75 + frames
            elif match_zero_data:
                logger.debug(f" Found ZERO {match_zero_data.group('length')} at line {line_number}")
            elif match_zero_audio:
                logger.debug(f" Found SILENCE {match_zero_audio.group('length')} at line {line_number}")
            elif (match_audio_file or match_file) and current_track:
                match = match_audio_file or match_file
                logger.debug(f" Found {'AUDIO' if match_audio_file else 'DATA'}FILE '{match.group('filename')}' at line {line_number}")
                current_track.trackfile = CdrdaoTrackFile(
                    datafilter=image_filter.get_filter(os.path.join(image_filter.parent_folder, match.group("filename"))),
                    datafile=match.group("filename"),
                    offset=int(match.group("base_offset") or 0),
                    filetype="BINARY",
                    sequence=current_track_number
                )
                if match.groupdict().get("length"):
                    minutes, seconds, frames = map(int, match.group("length").split(":"))
                    current_track.sectors = minutes * 60 * 75 + seconds * 75 + frames
                else:
                    current_track.sectors = (current_track.trackfile.datafilter.data_fork_length - current_track.trackfile.offset) // current_track.bps

                # Handle pregap for the first track
                if current_track.sequence == 1:
                    current_track.pregap = 150  # Assume 150-sector pregap for the first track
                    current_track.start_sector = 0
                else:
                    current_track.start_sector = last_end_sector  # Set start_sector to the end of the previous track

                last_end_sector = current_track.start_sector + current_track.sectors  # Update last_end_sector for the next track

                logger.debug(f" Calculated track {current_track.sequence}: start_sector={current_track.start_sector}, sectors={current_track.sectors}, end_sector={last_end_sector - 1}, pregap={current_track.pregap}")
            elif match_audio_file or match_file:
                if not in_track:
                    return ErrorNumber.InvalidData  # File declaration outside of track
                else:
                    logger.debug(f' Found DATAFILE {match.group(filename)} at line {line_number}')
            elif match_disc_scrambled:
                logger.debug(f" Found DataTracksScrambled {match_disc_scrambled.group('value')} at line {line_number}")
                discimage.scrambled = match_disc_scrambled.group('value') == "1"
            # Handle CD-Text related matches
            elif match_title:
                logger.debug(f" Found TITLE '{match_title.group('title')}' at line {line_number}")
                if in_track:
                    current_track.title = match_title.group("title")
                else:
                    discimage.title = match_title.group("title")
            elif match_performer:
                logger.debug(f" Found PERFORMER '{match_performer.group('performer')}' at line {line_number}")
                if in_track:
                    current_track.performer = match_performer.group("performer")
                else:
                    discimage.performer = match_performer.group("performer")
            elif match_songwriter:
                logger.debug(f" Found SONGWRITER '{match_songwriter.group('songwriter')}' at line {line_number}")
                if in_track:
                    current_track.songwriter = match_songwriter.group("songwriter")
                else:
                    discimage.songwriter = match_songwriter.group("songwriter")
            elif match_composer:
                logger.debug(f" Found COMPOSER '{match_composer.group('composer')}' at line {line_number}")
                if in_track:
                    current_track.composer = match_composer.group("composer")
                else:
                    discimage.composer = match_composer.group("composer")
            elif match_arranger:
                logger.debug(f" Found ARRANGER '{match_arranger.group('arranger')}' at line {line_number}")
                if in_track:
                    current_track.arranger = match_arranger.group("arranger")
                else:
                    discimage.arranger = match_arranger.group("arranger")
            elif match_message:
                logger.debug(f" Found MESSAGE '{match_message.group('message')}' at line {line_number}")
                if in_track:
                    current_track.message = match_message.group("message")
                else:
                    discimage.message = match_message.group("message")
            elif match_disc_id:
                logger.debug(f" Found DISC_ID '{match_disc_id.group('discid')}' at line {line_number}")
                if not in_track:
                    discimage.disk_id = match_disc_id.group("discid")
            elif match_upc:
                logger.debug(f" Found UPC_EAN '{match_upc.group('catalog')}' at line {line_number}")
                if not in_track:
                    discimage.barcode = match_upc.group("catalog")
            elif line == "":
                pass  # Ignore empty lines
            else:
                logger.warning(f"Unknown line at {line_number}: {line}")

        # Add the last track if we were processing one
        if in_track:
            process_track_gaps(current_track, None)
            process_track_indexes(current_track)
            discimage.tracks.append(current_track)

        discimage.comment = "\n".join(comment_builder)

        for track in discimage.tracks:
            process_track_indexes(track)

        return ErrorNumber.NoError, discimage
    except Exception as ex:
        print(f"Exception trying to parse TOC file: {str(ex)}")
        return ErrorNumber.UnexpectedException, None



#  Read.py toc handling
'''
            if match_track:
                if in_track:
                    process_track_gaps(current_track, None)  # Process gaps for the previous track
                    process_track_indexes(current_track, current_sector)
                    current_sector += current_track.sectors
                    discimage.tracks.append(current_track)

                current_track_number += 1
                current_track = CdrdaoTrack(
                    sequence=current_track_number,
                    start_sector=current_sector,
                    tracktype=match_track.group("type"),
                    bps=2352 if match_track.group("type") == "AUDIO" else 2048,
                    subchannel=bool(match_track.group("subchan")),
                    packedsubchannel=match_track.group("subchan") == "RW",
                    indexes={},
                    pregap=0
                )
                in_track = True              
                subchan = match_track.group("subchan")
                logger.debug(f"Found TRACK type '{match_track.group('type')}' {'with no subchannel' if not subchan else f'subchannel {subchan}'} at line {line_number}")

                current_track.sequence = current_track_number
                current_track.start_sector = current_sector
                current_track.tracktype = match_track.group("type")
                
                if match_track.group("type") == "AUDIO":
                    current_track.bps = 2352
                elif match_track.group("type") in ["MODE1", "MODE2_FORM1"]:
                    current_track.bps = 2048
                elif match_track.group("type") == "MODE2_FORM2":
                    current_track.bps = 2324
                elif match_track.group("type") in ["MODE2", "MODE2_FORM_MIX"]:
                    current_track.bps = 2336
                else:
                    logger.error(f"Unsupported track mode: {match_track.group('type')}")
                    return ErrorNumber.NotSupported

                if subchan:
                    if subchan == "RW":
                        current_track.packedsubchannel = True
                    current_track.subchannel = True
'''
