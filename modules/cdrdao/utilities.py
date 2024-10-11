from .structs import CdrdaoTrack
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, 
    Track, MediaType
)
from typing import Tuple, Optional
from .constants import *

@staticmethod
def lba_to_msf(sector: int) -> Tuple[int, int, int]:
    return (sector // 75 // 60, (sector // 75) % 60, sector % 75)

def swap_audio_endianness(buffer: bytearray) -> bytearray:
    swapped = bytearray(len(buffer))
    for i in range(0, len(buffer), 2):
        swapped[i] = buffer[i + 1]
        swapped[i + 1] = buffer[i]
    return swapped

def get_tag_layout(track: CdrdaoTrack, tag: SectorTagType) -> Tuple[int, int, int]:
    sector_offset = 0
    sector_size = 0
    sector_skip = 0

    if track.tracktype == CDRDAO_TRACK_TYPE_MODE1:
        if tag == SectorTagType.CdSectorSync:
            sector_offset, sector_size, sector_skip = 0, 12, 2340
        elif tag == SectorTagType.CdSectorHeader:
            sector_offset, sector_size, sector_skip = 12, 4, 2336
        elif tag == SectorTagType.CdSectorSubHeader:
            raise ValueError("Unsupported tag type for Mode 1")
        elif tag == SectorTagType.CdSectorEcc:
            sector_offset, sector_size, sector_skip = 2076, 276, 0
        elif tag == SectorTagType.CdSectorEccP:
            sector_offset, sector_size, sector_skip = 2076, 172, 104
        elif tag == SectorTagType.CdSectorEccQ:
            sector_offset, sector_size, sector_skip = 2248, 104, 0
        elif tag == SectorTagType.CdSectorEdc:
            sector_offset, sector_size, sector_skip = 2064, 4, 284
        else:
            raise ValueError("Unsupported tag type for Mode 1")
    elif track.tracktype == CDRDAO_TRACK_TYPE_MODE2:
        if tag in [SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader, 
                SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ]:
            raise ValueError("Unsupported tag type for Mode 2 Formless")
        elif tag == SectorTagType.CdSectorSubHeader:
            sector_offset, sector_size, sector_skip = 0, 8, 2328
        elif tag == SectorTagType.CdSectorEdc:
            sector_offset, sector_size, sector_skip = 2332, 4, 0
        else:
            raise ValueError("Unsupported tag type for Mode 2 Formless")
    elif track.tracktype == CDRDAO_TRACK_TYPE_MODE2_FORM1:
        if tag == SectorTagType.CdSectorSync:
            sector_offset, sector_size, sector_skip = 0, 12, 2340
        elif tag == SectorTagType.CdSectorHeader:
            sector_offset, sector_size, sector_skip = 12, 4, 2336
        elif tag == SectorTagType.CdSectorSubHeader:
            sector_offset, sector_size, sector_skip = 16, 8, 2328
        elif tag == SectorTagType.CdSectorEcc:
            sector_offset, sector_size, sector_skip = 2076, 276, 0
        elif tag == SectorTagType.CdSectorEccP:
            sector_offset, sector_size, sector_skip = 2076, 172, 104
        elif tag == SectorTagType.CdSectorEccQ:
            sector_offset, sector_size, sector_skip = 2248, 104, 0
        elif tag == SectorTagType.CdSectorEdc:
            sector_offset, sector_size, sector_skip = 2072, 4, 276
        else:
            raise ValueError("Unsupported tag type for Mode 2 Form 1")
    elif track.tracktype == CDRDAO_TRACK_TYPE_MODE2_FORM2:
        if tag == SectorTagType.CdSectorSync:
            sector_offset, sector_size, sector_skip = 0, 12, 2340
        elif tag == SectorTagType.CdSectorHeader:
            sector_offset, sector_size, sector_skip = 12, 4, 2336
        elif tag == SectorTagType.CdSectorSubHeader:
            sector_offset, sector_size, sector_skip = 16, 8, 2328
        elif tag == SectorTagType.CdSectorEdc:
            sector_offset, sector_size, sector_skip = 2348, 4, 0
        else:
            raise ValueError("Unsupported tag type for Mode 2 Form 2")

    if sector_size == 0:
        raise ValueError(f"Unsupported tag type {tag} for track type {track.tracktype}")

    return sector_offset, sector_size, sector_skip

def cdrdao_track_to_track(cdrdao_track: CdrdaoTrack) -> Track:
    return Track(
        sequence=cdrdao_track.sequence,
        start_sector=cdrdao_track.start_sector,
        end_sector=cdrdao_track.start_sector + cdrdao_track.sectors - 1,
        type=cdrdao_track_type_to_track_type(cdrdao_track.tracktype),
        file=cdrdao_track.trackfile.datafile,
        file_offset=cdrdao_track.trackfile.offset,
        file_type=cdrdao_track.trackfile.filetype,
        filter=cdrdao_track.trackfile.datafilter,
        indexes=cdrdao_track.indexes,
        pregap=cdrdao_track.pregap,
        session=1,  # Assuming single session for now
        bytes_per_sector=cdrdao_track_type_to_cooked_bytes_per_sector(cdrdao_track.tracktype),
        raw_bytes_per_sector=2352,
        subchannel_file=cdrdao_track.trackfile.datafile if cdrdao_track.subchannel else None,
        subchannel_filter=cdrdao_track.trackfile.datafilter if cdrdao_track.subchannel else None,
        subchannel_type=TrackSubchannelType.PackedInterleaved if cdrdao_track.packedsubchannel else TrackSubchannelType.RawInterleaved if cdrdao_track.subchannel else TrackSubchannelType.None_
    )

@staticmethod
def cdrdao_track_type_to_cooked_bytes_per_sector(track_type: str) -> int:
    if track_type in [CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE2_FORM1, CDRDAO_TRACK_TYPE_MODE1_RAW]:
        return 2048
    elif track_type == CDRDAO_TRACK_TYPE_MODE2_FORM2:
        return 2324
    elif track_type in [CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_MIX, CDRDAO_TRACK_TYPE_MODE2_RAW]:
        return 2336
    elif track_type == CDRDAO_TRACK_TYPE_AUDIO:
        return 2352
    else:
        return 0

@staticmethod
def cdrdao_track_type_to_track_type(track_type: str) -> TrackType:
    if track_type in [CDRDAO_TRACK_TYPE_MODE1, CDRDAO_TRACK_TYPE_MODE1_RAW]:
        return TrackType.CdMode1
    elif track_type == CDRDAO_TRACK_TYPE_MODE2_FORM1:
        return TrackType.CdMode2Form1
    elif track_type == CDRDAO_TRACK_TYPE_MODE2_FORM2:
        return TrackType.CdMode2Form2
    elif track_type in [CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_MIX, CDRDAO_TRACK_TYPE_MODE2_RAW]:
        return TrackType.CdMode2Formless
    elif track_type == CDRDAO_TRACK_TYPE_AUDIO:
        return TrackType.Audio
    else:
        return TrackType.Data


def process_track_gaps(current_track: CdrdaoTrack, next_track: Optional[CdrdaoTrack]):
    if current_track.pregap > 0:
        current_track.start_sector -= current_track.pregap
        current_track.sectors += current_track.pregap

    if next_track and next_track.start_sector > current_track.start_sector + current_track.sectors:
        current_track.postgap = next_track.start_sector - (current_track.start_sector + current_track.sectors)
        current_track.sectors += current_track.postgap

def process_track_indexes(track: CdrdaoTrack):
    if track.sequence == 1 and track.pregap > 0:
        track.indexes[0] = -track.pregap
        track.indexes[1] = 0
    else:
        track.indexes[1] = track.start_sector

    # Ensure indexes are properly ordered
    track.indexes = dict(sorted(track.indexes.items()))

@staticmethod
def get_track_mode(track: 'Track') -> str:
    if track.type == TrackType.Audio and track.raw_bytes_per_sector == 2352:
        return CDRDAO_TRACK_TYPE_AUDIO
    elif track.type == TrackType.Data:
        return CDRDAO_TRACK_TYPE_MODE1
    elif track.type == TrackType.CdMode1 and track.raw_bytes_per_sector == 2352:
        return CDRDAO_TRACK_TYPE_MODE1_RAW
    elif track.type == TrackType.CdMode2Formless and track.raw_bytes_per_sector != 2352:
        return CDRDAO_TRACK_TYPE_MODE2
    elif track.type == TrackType.CdMode2Form1 and track.raw_bytes_per_sector != 2352:
        return CDRDAO_TRACK_TYPE_MODE2_FORM1
    elif track.type == TrackType.CdMode2Form2 and track.raw_bytes_per_sector != 2352:
        return CDRDAO_TRACK_TYPE_MODE2_FORM2
    elif track.type in [TrackType.CdMode2Formless, TrackType.CdMode2Form1, TrackType.CdMode2Form2] and track.raw_bytes_per_sector == 2352:
        return CDRDAO_TRACK_TYPE_MODE2_RAW
    else:
        return CDRDAO_TRACK_TYPE_MODE1

def determine_media_type(discimagetracks,sessions):
    data_tracks = sum(1 for track in discimagetracks if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO)
    audio_tracks = len(discimagetracks) - data_tracks
    mode2_tracks = sum(1 for track in discimagetracks if track.tracktype in [
        CDRDAO_TRACK_TYPE_MODE2, CDRDAO_TRACK_TYPE_MODE2_FORM1, 
        CDRDAO_TRACK_TYPE_MODE2_FORM2, CDRDAO_TRACK_TYPE_MODE2_MIX, 
        CDRDAO_TRACK_TYPE_MODE2_RAW
    ])
    
    if data_tracks == 0:
        return MediaType.CDDA
    elif discimagetracks[0].tracktype == CDRDAO_TRACK_TYPE_AUDIO and data_tracks > 0 and len(sessions) > 1 and mode2_tracks > 0:
        return MediaType.CDPLUS
    elif (discimagetracks[0].tracktype != CDRDAO_TRACK_TYPE_AUDIO and audio_tracks > 0) or mode2_tracks > 0:
        return MediaType.CDROMXA
    elif audio_tracks == 0:
        return MediaType.CDROM
    else:
        return MediaType.CD

def calculate_track_flags(track: CdrdaoTrack) -> int:
    flags = 0
    if track.tracktype != CDRDAO_TRACK_TYPE_AUDIO:
        flags |= 0x04  # Data track
    if track.flag_dcp:
        flags |= 0x02  # Digital copy permitted
    if track.flag_4ch:
        flags |= 0x08  # Four channel audio
    if track.flag_pre:
        flags |= 0x01  # Pre-emphasis
    return flags