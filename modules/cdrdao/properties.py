from typing import List, Tuple, Type, Any, Optional
from modules.CD.cd_types import OpticalImageCapabilities, ImageInfo, MediaTagType, SectorTagType, MediaType

class CdrdaoProperties:
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
    def id(self) -> str:
        return "04D7BA12-1BE8-44D4-97A4-1B48A505463E"
    
    @property
    def format(self) -> str:
        return "CDRDAO tocfile"
    
    @property
    def dump_hardware(self) -> List['DumpHardware']:
        return None
    
    @property
    def aaru_metadata(self) -> Optional['Metadata']:
        return None
    
    @property
    def supported_media_tags(self) -> List[MediaTagType]:
        return [MediaTagType.CD_MCN]
    
    @property
    def supported_sector_tags(self) -> List[SectorTagType]:
        return [
            SectorTagType.CdSectorEcc,
            SectorTagType.CdSectorEccP,
            SectorTagType.CdSectorEccQ,
            SectorTagType.CdSectorEdc,
            SectorTagType.CdSectorHeader,
            SectorTagType.CdSectorSubchannel,
            SectorTagType.CdSectorSubHeader,
            SectorTagType.CdSectorSync,
            SectorTagType.CdTrackFlags,
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
            MediaType.Nuon, MediaType.Playdia, MediaType.PCD
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