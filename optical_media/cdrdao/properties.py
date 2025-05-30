from typing import List, Tuple, Type, Any, Optional
from enum import Flag, auto
from uuid import UUID
from dataclasses import dataclass, field
from modules.CD.cd_types import (
    OpticalImageCapabilities, ImageInfo, MediaTagType, SectorTagType,
    MediaType, TrackSubchannelType, Track, Session, Partition
)
from modules.error_number import ErrorNumber
from .utilities import cdrdao_track_type_to_track_type, cdrdao_track_to_track, cdrdao_track_type_to_cooked_bytes_per_sector
from .structs import CdrdaoTrack, CdrdaoDisc

class CdrdaoProperties:
    def __init__(self):
        self._discimage: Optional[CdrdaoDisc] = None
        self._image_info: ImageInfo = ImageInfo()
        self._partitions: List[Partition] = []
        self._tracks: List[Track] = []
        self._is_writing: bool = False
        self._error_message: Optional[str] = None

    @property
    def optical_capabilities(self) -> OpticalImageCapabilities:
        return (OpticalImageCapabilities.CanStoreAudioTracks |
                OpticalImageCapabilities.CanStoreDataTracks |
                OpticalImageCapabilities.CanStorePregaps |
                OpticalImageCapabilities.CanStoreSubchannelRw |
                OpticalImageCapabilities.CanStoreIsrc |
                OpticalImageCapabilities.CanStoreCdText |
                OpticalImageCapabilities.CanStoreMcn |
                OpticalImageCapabilities.CanStoreRawData |
                OpticalImageCapabilities.CanStoreCookedData |
                OpticalImageCapabilities.CanStoreMultipleTracks |
                OpticalImageCapabilities.CanStoreIndexes)
    
    @property
    def info(self) -> ImageInfo:
        return self._image_info
    
    @property
    def name(self) -> str:
        return "CDRDAO"
    
    @property
    def id(self) -> UUID:
        return UUID("04D7BA12-1BE8-44D4-97A4-1B48A505463E")

    @property
    def format(self) -> str:
        return "CDRDAO tocfile"

    @property
    def partitions(self) -> List[Partition]:
        return self._partitions

    @partitions.setter
    def partitions(self, value: List[Partition]):
        self._partitions = value

    @property
    def sessions(self) -> List[Session]:
        if not self._discimage or not self._discimage.tracks:
            return []
        first_track = min(self._discimage.tracks, key=lambda t: t.sequence)
        last_track = max(self._discimage.tracks, key=lambda t: t.sequence)
        return [Session(
            sequence=1,
            start_sector=first_track.start_sector,
            end_sector=last_track.start_sector + last_track.sectors - 1,
            start_track=first_track.sequence,
            end_track=last_track.sequence
        )]

    @sessions.setter
    def sessions(self, value: List[Session]):
        self._sessions = value

@property
def tracks(self) -> List[Track]:
    if not self._discimage:
        return []
    tracks = []
    for cdr_track in self._discimage.tracks:
        aaru_track = Track(
            description=cdr_track.title,
            start_sector=cdr_track.start_sector,
            pregap=cdr_track.pregap,
            session=1,
            sequence=cdr_track.sequence,
            type=cdrdao_track_type_to_track_type(cdr_track.tracktype),
            filter=cdr_track.trackfile.datafilter,
            file=cdr_track.trackfile.datafilter.filename,
            file_offset=cdr_track.trackfile.offset,
            file_type=cdr_track.trackfile.filetype,
            raw_bytes_per_sector=cdr_track.bps,
            bytes_per_sector=cdrdao_track_type_to_cooked_bytes_per_sector(cdr_track.tracktype)
        )
        aaru_track.end_sector = aaru_track.start_sector + cdr_track.sectors - 1
        aaru_track.start_sector = cdr_track.indexes.get(0, cdr_track.indexes.get(1, aaru_track.start_sector))

        if cdr_track.subchannel:
            aaru_track.subchannel_type = (TrackSubchannelType.PackedInterleaved
                                          if cdr_track.packedsubchannel
                                          else TrackSubchannelType.RawInterleaved)
            aaru_track.subchannel_filter = cdr_track.trackfile.datafilter
            aaru_track.subchannel_file = cdr_track.trackfile.datafile
            aaru_track.subchannel_offset = cdr_track.trackfile.offset
        else:
            aaru_track.subchannel_type = TrackSubchannelType.None_

        if aaru_track.sequence == 1:
            aaru_track.pregap = 150
            if not cdr_track.indexes:
                aaru_track.indexes[0] = -150
                aaru_track.indexes[1] = 0
            elif 0 not in cdr_track.indexes:
                aaru_track.indexes[0] = -150
                for idx, value in sorted(cdr_track.indexes.items()):
                    aaru_track.indexes[idx] = int(value)
        else:
            for idx, value in sorted(cdr_track.indexes.items()):
                aaru_track.indexes[idx] = int(value)

        tracks.append(aaru_track)
    return tracks

    @tracks.setter
    def tracks(self, value: List[Track]):
        self._tracks = value

    @property
    def dump_hardware(self) -> Optional[List]:
        return None
    
    @property
    def aaru_metadata(self) -> Optional[Any]:
        return None
    
    @property
    def supported_media_tags(self) -> List[MediaTagType]:
        return [MediaTagType.CD_MCN]
    
    @property
    def supported_sector_tags(self) -> List[SectorTagType]:
        return [
            SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ,
            SectorTagType.CdSectorEdc, SectorTagType.CdSectorHeader, SectorTagType.CdSectorSubchannel,
            SectorTagType.CdSectorSubHeader, SectorTagType.CdSectorSync, SectorTagType.CdTrackFlags,
            SectorTagType.CdTrackIsrc
        ]
    
    @property
    def supported_media_types(self) -> List[MediaType]:
        return [
            MediaType.CD, MediaType.CDDA, MediaType.CDEG, MediaType.CDG, MediaType.CDI,
            MediaType.CDMIDI, MediaType.CDMRW, MediaType.CDPLUS, MediaType.CDR,
            MediaType.CDROM, MediaType.CDROMXA, MediaType.CDRW, MediaType.CDV,
            MediaType.DDCD, MediaType.DDCDR, MediaType.DDCDRW, MediaType.MEGACD,
            MediaType.PS1CD, MediaType.PS2CD, MediaType.SuperCDROM2, MediaType.SVCD,
            MediaType.SATURNCD, MediaType.ThreeDO, MediaType.VCD, MediaType.VCDHD,
            MediaType.NeoGeoCD, MediaType.PCFX, MediaType.CDTV, MediaType.CD32,
            MediaType.Nuon, MediaType.Playdia, MediaType.Pippin, MediaType.FMTOWNS,
            MediaType.MilCD, MediaType.VideoNow, MediaType.VideoNowColor,
            MediaType.VideoNowXp, MediaType.CVD, MediaType.PCD
        ]
    
    @property
    def supported_options(self) -> List[Tuple[str, Type, str, Any]]:
        return [
            ("separate", bool, "Write each track to a separate file", False)
        ]
    
    @property
    def known_extensions(self) -> List[str]:
        return [".toc"]
    
    @property
    def is_writing(self) -> bool:
        return self._is_writing
    
    @property
    def error_message(self) -> Optional[str]:
        return self._error_message