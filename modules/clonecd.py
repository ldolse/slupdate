import io
import re
import os
import struct
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field

from modules.CD.atip import ATIP
from modules.CD.fulltoc import FullTOC, TrackDataDescriptor, CDFullTOC
from modules.CD.sector import Sector
from modules.CD.subchannel import Subchannel
from modules.CD.cd_types import (
    TrackType, TrackSubchannelType, SectorTagType, MediaType, 
    MediaTagType, MetadataMediaType, TocControl, OpticalImageCapabilities,
    Track, Session, Partition, ImageInfo
)
from modules.error_number import ErrorNumber
from modules.ifilter import IFilter

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CloneCD:
    MODULE_NAME = "CloneCD plugin"

    # Constants
    CCD_IDENTIFIER = r'^\s*\[CloneCD\]'
    DISC_IDENTIFIER = r'^\s*\[Disc\]'
    SESSION_IDENTIFIER = r'^\s*\[Session\s*(?P<number>\d+)\]'
    ENTRY_IDENTIFIER = r'^\s*\[Entry\s*(?P<number>\d+)\]'
    TRACK_IDENTIFIER = r'^\s*\[TRACK\s*(?P<number>\d+)\]'
    CDTEXT_IDENTIFIER = r'^\s*\[CDText\]'
    CCD_VERSION = r'^\s*Version\s*=\s*(?P<value>\d+)'
    DISC_ENTRIES = r'^\s*TocEntries\s*=\s*(?P<value>\d+)'
    DISC_SESSIONS = r'^\s*Sessions\s*=\s*(?P<value>\d+)'
    DISC_SCRAMBLED = r'^\s*DataTracksScrambled\s*=\s*(?P<value>\d+)'
    CDTEXT_LENGTH = r'^\s*CDTextLength\s*=\s*(?P<value>\d+)'
    DISC_CATALOG = r'^\s*CATALOG\s*=\s*(?P<value>[\x21-\x7F]{13})'
    SESSION_PREGAP = r'^\s*PreGapMode\s*=\s*(?P<value>\d+)'
    SESSION_SUBCHANNEL = r'^\s*PreGapSubC\s*=\s*(?P<value>\d+)'
    ENTRY_SESSION = r'^\s*Session\s*=\s*(?P<value>\d+)'
    ENTRY_POINT = r'^\s*Point\s*=\s*(?P<value>[\w+]+)'
    ENTRY_ADR = r'^\s*ADR\s*=\s*(?P<value>\w+)'
    ENTRY_CONTROL = r'^\s*Control\s*=\s*(?P<value>\w+)'
    ENTRY_TRACKNO = r'^\s*TrackNo\s*=\s*(?P<value>\d+)'
    ENTRY_AMIN = r'^\s*AMin\s*=\s*(?P<value>\d+)'
    ENTRY_ASEC = r'^\s*ASec\s*=\s*(?P<value>\d+)'
    ENTRY_AFRAME = r'^\s*AFrame\s*=\s*(?P<value>\d+)'
    ENTRY_ALBA = r'^\s*ALBA\s*=\s*(?P<value>-?\d+)'
    ENTRY_ZERO = r'^\s*Zero\s*=\s*(?P<value>\d+)'
    ENTRY_PMIN = r'^\s*PMin\s*=\s*(?P<value>\d+)'
    ENTRY_PSEC = r'^\s*PSec\s*=\s*(?P<value>\d+)'
    ENTRY_PFRAME = r'^\s*PFrame\s*=\s*(?P<value>\d+)'
    ENTRY_PLBA = r'^\s*PLBA\s*=\s*(?P<value>\d+)'
    CDTEXT_ENTRIES = r'^\s*Entries\s*=\s*(?P<value>\d+)'
    CDTEXT_ENTRY = r'^\s*Entry\s*(?P<number>\d+)\s*=\s*(?P<value>([0-9a-fA-F]+\s*)+)'
    TRACK_MODE = r'^\s*MODE\s*=\s*(?P<value>\d+)'
    TRACK_INDEX = r'^\s*INDEX\s*(?P<index>\d+)\s*=\s*(?P<lba>\d+)'

    def __init__(self):
        self._catalog: Optional[str] = None
        self._ccd_filter: Optional[IFilter] = None
        self._cdtext: Optional[bytes] = None
        self._cue_stream = None  # We'll define this later when we know what type it should be
        self._data_filter: Optional[IFilter] = None
        self._data_stream = None  # We'll define this later when we know what type it should be
        self._descriptor_stream = None  # We'll define this later when we know what type it should be
        self._full_toc: Optional[bytes] = None
        self._image_info = ImageInfo(
            readable_sector_tags=[],
            readable_media_tags=[],
            has_partitions=True,
            has_sessions=True,
            version=None,
            application_version=None,
            media_title=None,
            creator=None,
            media_manufacturer=None,
            media_model=None,
            media_part_number=None,
            media_sequence=0,
            last_media_sequence=0,
            drive_manufacturer=None,
            drive_model=None,
            drive_serial_number=None,
            drive_firmware_revision=None
        )
        self._offset_map: Dict[int, int] = {}
        self._scrambled: bool = False
        self._sub_filter: Optional[IFilter] = None
        self._sub_stream = None  # We'll define this later when we know what type it should be
        self._track_flags: Dict[int, int] = {}
        self._writing_base_name: Optional[str] = None

        self.partitions: List[Partition] = []
        self.tracks: List[Track] = []
        self.sessions: List[Session] = []
        self._is_writing: bool = False
        self._error_message: Optional[str] = None

        self.ccd_identifier_regex = re.compile(self.CCD_IDENTIFIER)
        self.disc_identifier_regex = re.compile(self.DISC_IDENTIFIER)
        self.session_identifier_regex = re.compile(self.SESSION_IDENTIFIER)
        self.entry_identifier_regex = re.compile(self.ENTRY_IDENTIFIER)
        self.track_identifier_regex = re.compile(self.TRACK_IDENTIFIER)
        self.cdtext_identifier_regex = re.compile(self.CDTEXT_IDENTIFIER)
        self.ccd_version_regex = re.compile(self.CCD_VERSION)
        self.disc_entries_regex = re.compile(self.DISC_ENTRIES)
        self.disc_sessions_regex = re.compile(self.DISC_SESSIONS)
        self.disc_scrambled_regex = re.compile(self.DISC_SCRAMBLED)
        self.cdtext_length_regex = re.compile(self.CDTEXT_LENGTH)
        self.disc_catalog_regex = re.compile(self.DISC_CATALOG)
        self.session_pregap_regex = re.compile(self.SESSION_PREGAP)
        self.session_subchannel_regex = re.compile(self.SESSION_SUBCHANNEL)
        self.entry_session_regex = re.compile(self.ENTRY_SESSION)
        self.entry_point_regex = re.compile(self.ENTRY_POINT)
        self.entry_adr_regex = re.compile(self.ENTRY_ADR)
        self.entry_control_regex = re.compile(self.ENTRY_CONTROL)
        self.entry_trackno_regex = re.compile(self.ENTRY_TRACKNO)
        self.entry_amin_regex = re.compile(self.ENTRY_AMIN)
        self.entry_asec_regex = re.compile(self.ENTRY_ASEC)
        self.entry_aframe_regex = re.compile(self.ENTRY_AFRAME)
        self.entry_alba_regex = re.compile(self.ENTRY_ALBA)
        self.entry_zero_regex = re.compile(self.ENTRY_ZERO)
        self.entry_pmin_regex = re.compile(self.ENTRY_PMIN)
        self.entry_psec_regex = re.compile(self.ENTRY_PSEC)
        self.entry_pframe_regex = re.compile(self.ENTRY_PFRAME)
        self.entry_plba_regex = re.compile(self.ENTRY_PLBA)
        self.cdtext_entries_regex = re.compile(self.CDTEXT_ENTRIES)
        self.cdtext_entry_regex = re.compile(self.CDTEXT_ENTRY)
        self.track_mode_regex = re.compile(self.TRACK_MODE)
        self.track_index_regex = re.compile(self.TRACK_INDEX)

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
                OpticalImageCapabilities.CanStoreMultipleTracks)

    @property
    def info(self) -> ImageInfo:
        return self._image_info

    @property
    def name(self) -> str:
        return "CloneCD"

    @property
    def id(self) -> str:
        return "EE9C2975-2E79-427A-8EE9-F86F19165784"

    @property
    def format(self) -> str:
        return "CloneCD"

    @property
    def dump_hardware(self) -> List['DumpHardware']:
        return None

    @property
    def aaru_metadata(self) -> Optional['Metadata']:
        return None

    @property
    def supported_media_tags(self) -> List[MediaTagType]:
        return [MediaTagType.CD_MCN, MediaTagType.CD_FullTOC]

    @property
    def supported_sector_tags(self) -> List[SectorTagType]:
        return [
            SectorTagType.CdSectorEcc,
            SectorTagType.CdSectorEccP,
            SectorTagType.CdSectorEccQ,
            SectorTagType.CdSectorEdc,
            SectorTagType.CdSectorHeader,
            SectorTagType.CdSectorSubHeader,
            SectorTagType.CdSectorSync,
            SectorTagType.CdTrackFlags,
            SectorTagType.CdSectorSubchannel
        ]

    @property
    def supported_media_types(self) -> List[MediaType]:
        return [
            MediaType.CD, MediaType.CDDA, MediaType.CDEG, MediaType.CDG, MediaType.CDI,
            MediaType.CDMIDI, MediaType.CDMRW, MediaType.CDPLUS, MediaType.CDR,
            MediaType.CDROM, MediaType.CDROMXA, MediaType.CDRW, MediaType.CDV,
            MediaType.DTSCD, MediaType.JaguarCD, MediaType.MEGACD, MediaType.PS1CD,
            MediaType.PS2CD, MediaType.SuperCDROM2, MediaType.SVCD, MediaType.SATURNCD,
            MediaType.ThreeDO, MediaType.VCD, MediaType.VCDHD, MediaType.NeoGeoCD,
            MediaType.PCFX, MediaType.CDTV, MediaType.CD32, MediaType.Nuon,
            MediaType.Playdia, MediaType.PCD
        ]

    @property
    def supported_options(self) -> List[tuple]:
        return []

    @property
    def known_extensions(self) -> List[str]:
        return [".ccd"]

    @property
    def is_writing(self) -> bool:
        return self._is_writing

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def image_info(self) -> ImageInfo:
        return self._image_info

    @staticmethod
    def get_lba(minute: int, second: int, frame: int) -> int:
        return (minute * 60 * 75 + second * 75 + frame - 150)

    @staticmethod
    def msf_to_lba(msf: tuple) -> int:
        minute, second, frame = msf
        return minute * 60 * 75 + second * 75 + frame - 150

    def identify(self, image_filter: IFilter) -> bool:
        self._ccd_filter = image_filter
    
        try:
            with image_filter.get_data_fork_stream() as stream:
                stream.seek(0)
                test_array = bytearray(512)
                stream.readinto(test_array)
                stream.seek(0)
    
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
    
                self._cue_stream = io.TextIOWrapper(stream, encoding='utf-8')
                line = self._cue_stream.readline()
    
                return self.ccd_identifier_regex.match(line) is not None
    
        except Exception as ex:
            logger.error(f"Exception trying to identify image file: {image_filter.filename}")
            logger.exception(ex)
            return False

    def open(self, image_filter: IFilter) -> ErrorNumber:
        if image_filter is None:
            return ErrorNumber.NoSuchFile

        self._ccd_filter = image_filter

        try:
            ccd_stream = self._ccd_filter.get_ccd_stream()
            self._cue_stream = io.TextIOWrapper(ccd_stream, encoding='utf-8')
            line_number = 0

            in_ccd = False
            in_disk = False
            in_session = False
            in_entry = False
            in_track = False
            in_cdtext = False
            cdt_ms = io.BytesIO()
            min_session = float('inf')
            max_session = float('-inf')
            current_entry = TrackDataDescriptor()
            current_track_entry = 0
            track_modes: Dict[int, int] = {}
            track_indexes: Dict[int, Dict[int, int]] = {}
            entries: List[TrackDataDescriptor] = []
            self._scrambled = False
            self._catalog = None

            while True:
                line = self._cue_stream.readline()
                if not line:
                    break
                line_number += 1

                ccd_id_match = self.ccd_identifier_regex.match(line)
                disc_id_match = self.disc_identifier_regex.match(line)
                sess_id_match = self.session_identifier_regex.match(line)
                entry_id_match = self.entry_identifier_regex.match(line)
                track_id_match = self.track_identifier_regex.match(line)
                cdt_id_match = self.cdtext_identifier_regex.match(line)

                if ccd_id_match:
                    if in_disk or in_session or in_entry or in_track or in_cdtext:
                        logger.error(f"Found [CloneCD] out of order in line {line_number}")
                        return ErrorNumber.InvalidArgument
                    in_ccd, in_disk, in_session, in_entry, in_track, in_cdtext = True, False, False, False, False, False
                elif disc_id_match or sess_id_match or entry_id_match or track_id_match or cdt_id_match:
                    if in_entry:
                        entries.append(current_entry)
                        current_entry = TrackDataDescriptor()
                    in_ccd = False
                    in_disk = disc_id_match is not None
                    in_session = sess_id_match is not None
                    in_entry = entry_id_match is not None
                    in_track = track_id_match is not None
                    in_cdtext = cdt_id_match is not None
                    if in_track:
                        current_track_entry = int(track_id_match.group('number'))
                else:
                    if in_ccd:
                        ccd_ver_match = self.ccd_version_regex.match(line)
                        if ccd_ver_match:
                            logger.debug(f"Found Version at line {line_number}")
                            self._image_info.version = ccd_ver_match.group('value')
                            if self._image_info.version not in ["2", "3"]:
                                logger.warning(f"Unknown CCD image version {self._image_info.version}, may not work")
                    elif in_disk:
                        disc_ent_match = self.disc_entries_regex.match(line)
                        disc_sess_match = self.disc_sessions_regex.match(line)
                        disc_scr_match = self.disc_scrambled_regex.match(line)
                        cdt_len_match = self.cdtext_length_regex.match(line)
                        disc_cat_match = self.disc_catalog_regex.match(line)

                        if disc_ent_match:
                            logger.debug(f"Found TocEntries at line {line_number}")
                        elif disc_sess_match:
                            logger.debug(f"Found Sessions at line {line_number}")
                        elif disc_scr_match:
                            logger.debug(f"Found DataTracksScrambled at line {line_number}")
                            self._scrambled |= disc_scr_match.group('value') == "1"
                        elif cdt_len_match:
                            logger.debug(f"Found CDTextLength at line {line_number}")
                        elif disc_cat_match:
                            logger.debug(f"Found Catalog at line {line_number}")
                            self._catalog = disc_cat_match.group('value')
                    elif in_cdtext:
                        cdt_ents_match = self.cdtext_entries_regex.match(line)
                        cdt_ent_match = self.cdtext_entry_regex.match(line)

                        if cdt_ents_match:
                            logger.debug(f"Found CD-Text Entries at line {line_number}")
                        elif cdt_ent_match:
                            logger.debug(f"Found CD-Text Entry at line {line_number}")
                            bytes_str = cdt_ent_match.group('value').split()
                            cdt_ms.write(bytes(int(b, 16) for b in bytes_str))
                        self._cdtext = cdt_ms.getvalue()
                        if self._cdtext:
                            self._image_info.readable_media_tags.append(MediaTagType.CD_TEXT)

                    elif in_session:
                        sess_preg_match = self.session_pregap_regex.match(line)
                        sess_subc_match = self.session_subchannel_regex.match(line)

                        if sess_preg_match:
                            logger.debug(f"Found PreGapMode at line {line_number}")
                        elif sess_subc_match:
                            logger.debug(f"Found PreGapSubC at line {line_number}")
                    elif in_entry:
                        ent_sess_match = self.entry_session_regex.match(line)
                        ent_point_match = self.entry_point_regex.match(line)
                        ent_adr_match = self.entry_adr_regex.match(line)
                        ent_ctrl_match = self.entry_control_regex.match(line)
                        ent_tno_match = self.entry_trackno_regex.match(line)
                        ent_amin_match = self.entry_amin_regex.match(line)
                        ent_asec_match = self.entry_asec_regex.match(line)
                        ent_aframe_match = self.entry_aframe_regex.match(line)
                        ent_alba_match = self.entry_alba_regex.match(line)
                        ent_zero_match = self.entry_zero_regex.match(line)
                        ent_pmin_match = self.entry_pmin_regex.match(line)
                        ent_psec_match = self.entry_psec_regex.match(line)
                        ent_pframe_match = self.entry_pframe_regex.match(line)
                        ent_plba_match = self.entry_plba_regex.match(line)

                        if ent_sess_match:
                            logger.debug(f"Found Session at line {line_number}")
                            current_entry.session_number = int(ent_sess_match.group('value'))
                            min_session = min(min_session, current_entry.session_number)
                            max_session = max(max_session, current_entry.session_number)
                        elif ent_point_match:
                            logger.debug(f"Found Point at line {line_number}")
                            current_entry.point = int(ent_point_match.group('value'), 16)
                        elif ent_adr_match:
                            logger.debug(f"Found ADR at line {line_number}")
                            current_entry.adr = int(ent_adr_match.group('value'), 16)
                        elif ent_ctrl_match:
                            logger.debug(f"Found Control at line {line_number}")
                            current_entry.control = int(ent_ctrl_match.group('value'), 16)
                        elif ent_tno_match:
                            logger.debug(f"Found TrackNo at line {line_number}")
                            current_entry.tno = int(ent_tno_match.group('value'))
                        elif ent_amin_match:
                            logger.debug(f"Found AMin at line {line_number}")
                            current_entry.min = int(ent_amin_match.group('value'))
                        elif ent_asec_match:
                            logger.debug(f"Found ASec at line {line_number}")
                            current_entry.sec = int(ent_asec_match.group('value'))
                        elif ent_aframe_match:
                            logger.debug(f"Found AFrame at line {line_number}")
                            current_entry.frame = int(ent_aframe_match.group('value'))
                        elif ent_alba_match:
                            logger.debug(f"Found ALBA at line {line_number}")
                        elif ent_zero_match:
                            logger.debug(f"Found Zero at line {line_number}")
                            current_entry.zero = int(ent_zero_match.group('value'))
                            current_entry.hour = (current_entry.zero & 0xF0) >> 4
                            current_entry.phour = current_entry.zero & 0x0F
                        elif ent_pmin_match:
                            logger.debug(f"Found PMin at line {line_number}")
                            current_entry.pmin = int(ent_pmin_match.group('value'))
                        elif ent_psec_match:
                            logger.debug(f"Found PSec at line {line_number}")
                            current_entry.psec = int(ent_psec_match.group('value'))
                        elif ent_pframe_match:
                            logger.debug(f"Found PFrame at line {line_number}")
                            current_entry.pframe = int(ent_pframe_match.group('value'))
                        elif ent_plba_match:
                            logger.debug(f"Found PLBA at line {line_number}")
                    elif in_track:
                        trk_mode_match = self.track_mode_regex.match(line)
                        trk_index_match = self.track_index_regex.match(line)

                        if trk_mode_match and current_track_entry > 0:
                            track_modes[current_track_entry] = int(trk_mode_match.group('value'))
                        elif trk_index_match and current_track_entry > 0:
                            index_no = int(trk_index_match.group('index'))
                            index_lba = int(trk_index_match.group('lba'))
                            if current_track_entry not in track_indexes:
                                track_indexes[current_track_entry] = {}
                            track_indexes[current_track_entry][index_no] = index_lba

            if in_entry:
                entries.append(current_entry)

            if not entries:
                logger.error("Did not find any track")
                return ErrorNumber.InvalidArgument

            # Create and populate FullTOC.CDFullTOC
            toc = CDFullTOC()
            toc.first_complete_session = min_session
            toc.last_complete_session = max_session
            toc.track_descriptors = entries
    
            # Create binary representation of TOC
            toc_ms = io.BytesIO()
            toc_ms.write(struct.pack('>H', len(entries) * 11 + 2))  # DataLength
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
    
            self._full_toc = toc_ms.getvalue()
            logger.debug(f"Read TOC data: {len(self._full_toc)} bytes")
            self._image_info.readable_media_tags.append(MediaTagType.CD_FullTOC)

            self._data_filter = image_filter
            self._sub_filter = image_filter

            self._data_stream = self._data_filter.get_img_stream()
            if self._sub_filter:
                self._sub_stream = self._sub_filter.get_sub_stream()
            else:
                self._sub_stream = None

            cur_session_no = 0
            current_track = Track()
            first_track_in_session = True
            self.tracks = []
            lead_out_start = 0

            self._data_stream = self._data_filter.get_data_fork_stream()

            self._track_flags = {}

            for descriptor in entries:
                if descriptor.session_number > cur_session_no:
                    cur_session_no = descriptor.session_number

                    if not first_track_in_session:
                        current_track.end_sector = lead_out_start - 1
                        self.tracks.append(current_track)

                    first_track_in_session = True

                if descriptor.adr in [1, 4]:
                    if descriptor.point == 0xA0:
                        disc_type = descriptor.psec
                        logger.debug(f"Disc Type: {disc_type}")
                    elif descriptor.point == 0xA2:
                        lead_out_start = self.get_lba(descriptor.pmin, descriptor.psec, descriptor.pframe)
                    elif 0x01 <= descriptor.point <= 0x63:
                        if not first_track_in_session:
                            current_track.end_sector = self.get_lba(descriptor.pmin, descriptor.psec, descriptor.pframe) - 1
                            self.tracks.append(current_track)

                        current_track = Track(
                            bytes_per_sector=2352,
                            file=self._data_filter.filename,
                            file_type="SCRAMBLED" if self._scrambled else "BINARY",
                            filter=self._data_filter,
                            raw_bytes_per_sector=2352,
                            sequence=descriptor.point,
                            start_sector=self.get_lba(descriptor.pmin, descriptor.psec, descriptor.pframe),
                            session=descriptor.session_number
                        )

                        if descriptor.point == 1:
                            current_track.pregap = current_track.start_sector + 150
                            current_track.indexes[0] = -150
                            current_track.indexes[1] = int(current_track.start_sector)
                            current_track.start_sector = 0
                        else:
                            if first_track_in_session:
                                current_track.pregap = 150
                                if current_track.start_sector > 0:
                                    current_track.indexes[0] = int(current_track.start_sector) - 150
                                    if current_track.indexes[0] < 0:
                                        current_track.indexes[0] = 0
                                current_track.indexes[1] = int(current_track.start_sector)
                                current_track.start_sector -= 150
                            else:
                                current_track.indexes[1] = int(current_track.start_sector)

                        first_track_in_session = False

                        if (descriptor.control & 0x0D) in [TocControl.DataTrack, TocControl.DataTrackIncremental]:
                            current_track.type = TrackType.Data
                        else:
                            current_track.type = TrackType.Audio

                        self._track_flags[descriptor.point] = descriptor.control

                        if self._sub_filter:
                            current_track.subchannel_file = self._sub_filter.filename
                            current_track.subchannel_filter = self._sub_filter
                            current_track.subchannel_type = TrackSubchannelType.Raw
                        else:
                            current_track.subchannel_type = TrackSubchannelType.None_

                elif descriptor.adr == 5:
                    if descriptor.point == 0xC0:
                        if descriptor.pmin == 97:
                            type_ = descriptor.pframe % 10
                            frm = descriptor.pframe - type_
                            self._image_info.media_manufacturer = ATIP.manufacturer_from_atip(descriptor.psec, frm)
                            if self._image_info.media_manufacturer:
                                logger.debug(f"Disc manufactured by {self._image_info.media_manufacturer}")

                elif descriptor.adr == 6:
                    id_ = (descriptor.min << 16) + (descriptor.sec << 8) + descriptor.frame
                    logger.debug(f"Disc ID: {id_ & 0x00FFFFFF:06X}")
                    self._image_info.media_serial_number = f"{id_ & 0x00FFFFFF:06X}"

            if not first_track_in_session:
                current_track.end_sector = lead_out_start - 1
                self.tracks.append(current_track)

            self.tracks.sort(key=lambda t: t.sequence)

            current_data_offset = 0
            current_subchannel_offset = 0

            for track in self.tracks:
                track.file_offset = current_data_offset
                current_data_offset += 2352 * (track.end_sector - track.indexes[1] + 1)

                if self._sub_filter:
                    track.subchannel_offset = current_subchannel_offset
                    current_subchannel_offset += 96 * (track.end_sector - track.indexes[1] + 1)

                if 0 in track.indexes:
                    if track.indexes[0] < 0:
                        track.file_offset = 0
                        track.subchannel_offset = 0
                    else:
                        index_difference = track.indexes[1] - track.indexes[0]
                        track.file_offset -= 2352 * index_difference
                        if self._sub_filter:
                            track.subchannel_offset -= 96 * index_difference

                if track.sequence in track_modes:
                    track.type = {
                        0: TrackType.Audio,
                        1: TrackType.CdMode1,
                        2: TrackType.CdMode2Formless
                    }.get(track_modes[track.sequence], TrackType.Data)

                if track.sequence in track_indexes:
                    for index, value in sorted(track_indexes[track.sequence].items()):
                        if index > 1:
                            track.indexes[index] = value

                if track.type == TrackType.Data:
                    self.detect_track_type(track)

                if self._image_info.sector_size < track.bytes_per_sector:
                    self._image_info.sector_size = track.bytes_per_sector

            if self._sub_filter and SectorTagType.CdSectorSubchannel not in self._image_info.readable_sector_tags:
                self._image_info.readable_sector_tags.append(SectorTagType.CdSectorSubchannel)

            self._image_info.readable_sector_tags.append(SectorTagType.CdTrackFlags)

            self.sessions = []
            current_session = Session(
                sequence=1,
                start_track=float('inf'),
                end_track=float('-inf'),
                start_sector=0,
                end_sector=0
            )

            self.partitions = []
            self._offset_map = {}

            for track in self.tracks:
                if track.end_sector + 1 > self._image_info.sectors:
                    self._image_info.sectors = track.end_sector + 1

                if track.session == current_session.sequence:
                    if track.sequence > current_session.end_track:
                        current_session.end_sector = track.end_sector
                        current_session.end_track = track.sequence
                    if track.sequence < current_session.start_track:
                        current_session.start_sector = track.start_sector
                        current_session.start_track = track.sequence
                else:
                    self.sessions.append(current_session)
                    current_session = Session(
                        sequence=track.session,
                        start_track=track.sequence,
                        end_track=track.sequence,
                        start_sector=track.start_sector,
                        end_sector=track.end_sector
                    )
                partition = Partition(
                    description=track.description,
                    size=(track.end_sector - track.indexes[1] + 1) * track.raw_bytes_per_sector,
                    length=track.end_sector - track.indexes[1] + 1,
                    sequence=track.sequence,
                    offset=track.file_offset,
                    start=track.indexes[1],
                    type=str(track.type)
                )
                self.partitions.append(partition)
                self._offset_map[track.sequence] = track.start_sector

            self.sessions.append(current_session)

            self.determine_media_type()

            self._image_info.application = "CloneCD"
            self._image_info.image_size = image_filter.length
            self._image_info.creation_time = datetime.fromtimestamp(os.path.getctime(image_filter.base_path))
            self._image_info.last_modification_time = datetime.fromtimestamp(os.path.getmtime(image_filter.base_path))
            self._image_info.metadata_media_type = MetadataMediaType.OpticalDisc

            return ErrorNumber.NoError
    
        except Exception as ex:
            logger.error(f"Exception trying to open image file: {image_filter.filename}")
            logger.exception(ex)
            return ErrorNumber.UnexpectedException

    def detect_track_type(self, track: Track):
        for s in range(225, min(750, int(track.end_sector - track.start_sector))):
            sync_test = bytearray(12)
            sect_test = bytearray(2352)
    
            pos = track.file_offset + s * 2352
    
            if pos >= self._data_stream.seek(0, io.SEEK_END) + 2352:
                break
    
            self._data_stream.seek(pos)
            self._data_stream.readinto(sect_test)
            sync_test[:] = sect_test[:12]
    
            if sync_test != Sector.SYNC_MARK:
                continue
    
            if self._scrambled:
                sect_test = Sector.scramble(sect_test)
    
            if sect_test[15] == 1:
                track.bytes_per_sector = 2048
                track.type = TrackType.CdMode1
                self.update_readable_sector_tags([
                    SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                    SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP,
                    SectorTagType.CdSectorEccQ, SectorTagType.CdSectorEdc
                ])
                break
            elif sect_test[15] == 2:
                sub_hdr1 = sect_test[16:20]
                sub_hdr2 = sect_test[20:24]
                emp_hdr = bytes(4)
    
                if sub_hdr1 == sub_hdr2 and sub_hdr1 != emp_hdr:
                    if sub_hdr1[2] & 0x20:
                        track.bytes_per_sector = 2324
                        track.type = TrackType.CdMode2Form2
                        self.update_readable_sector_tags([
                            SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                            SectorTagType.CdSectorSubHeader, SectorTagType.CdSectorEdc
                        ])
                    else:
                        track.bytes_per_sector = 2048
                        track.type = TrackType.CdMode2Form1
                        self.update_readable_sector_tags([
                            SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                            SectorTagType.CdSectorSubHeader, SectorTagType.CdSectorEcc,
                            SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ,
                            SectorTagType.CdSectorEdc
                        ])
                    break
                else:
                    track.bytes_per_sector = 2336
                    track.type = TrackType.CdMode2Formless
                    self.update_readable_sector_tags([
                        SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader
                    ])
                    break
    
    def update_readable_sector_tags(self, tags):
        for tag in tags:
            if tag not in self._image_info.readable_sector_tags:
                self._image_info.readable_sector_tags.append(tag)

    
    def determine_media_type(self):
        data = False
        mode2 = False
        first_audio = False
        first_data = False
        audio = False
    
        for i, track in enumerate(self.tracks):
            first_audio |= i == 0 and track.type == TrackType.Audio
            first_data |= i == 0 and track.type != TrackType.Audio
            data |= i != 0 and track.type != TrackType.Audio
            audio |= i != 0 and track.type == TrackType.Audio
            mode2 |= track.type in [TrackType.CdMode2Form1, TrackType.CdMode2Form2, TrackType.CdMode2Formless]
    
        if not data and not first_data:
            self._image_info.media_type = MediaType.CDDA
        elif first_audio and data and len(self.sessions) > 1 and mode2:
            self._image_info.media_type = MediaType.CDPLUS
        elif (first_data and audio) or mode2:
            self._image_info.media_type = MediaType.CDROMXA
        elif not audio:
            self._image_info.media_type = MediaType.CDROM
        else:
            self._image_info.media_type = MediaType.CD

    def read_media_tag(self, tag: MediaTagType) -> tuple[ErrorNumber, Optional[bytes]]:
        if tag == MediaTagType.CD_FullTOC:
            return ErrorNumber.NoError, self._full_toc.copy() if self._full_toc else None
        elif tag == MediaTagType.CD_TEXT:
            return ErrorNumber.NoError, self._cdtext.copy() if self._cdtext else None
        else:
            return ErrorNumber.NotSupported, None

    def read_sector(self, sector_address: int, track: Optional[int] = None) -> tuple[ErrorNumber, Optional[bytes]]:
        return self.read_sectors(sector_address, 1, track)

    def read_sector_tag(self, sector_address: int, tag: SectorTagType, track: Optional[int] = None) -> tuple[ErrorNumber, Optional[bytes]]:
        if tag == SectorTagType.CdTrackFlags:
            track = sector_address
    
        aaruTrack = next((t for t in self.tracks if t.sequence == track), None)
        if aaruTrack is None:
            return ErrorNumber.SectorNotFound, None

        if sector_address > aaruTrack.end_sector:
            return ErrorNumber.OutOfRange, None
    
        if aaruTrack.type == TrackType.Audio:
            return ErrorNumber.NotSupported, None
    
        if tag == SectorTagType.CdSectorSubchannel:
            if self._sub_stream is None:
                return ErrorNumber.NotSupported, None
            
            buffer = bytearray(96)
            self._sub_stream.seek(aaruTrack.subchannel_offset + sector_address * 96)
            bytes_read = self._sub_stream.readinto(buffer)
            
            if bytes_read != 96:
                return ErrorNumber.ReadError, None
            
            # Interleave the subchannel data
            interleaved = Subchannel.interleave(buffer)
            return ErrorNumber.NoError, bytes(interleaved)

        if tag == SectorTagType.CdTrackFlags:
            if track not in self._track_flags:
                return ErrorNumber.NoData, None
            return ErrorNumber.NoError, bytes([self._track_flags[track]])

        return ErrorNumber.NotSupported, None
    

    def read_sectors_tag(self, sector_address: int, length: int, tag: SectorTagType, track: Optional[int] = None) -> tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.end_sector - track.start_sector + 1:
                        return self.read_sectors_tag(sector_address - start_sector, length, tag, track_sequence)
            return ErrorNumber.SectorNotFound, None
    
        if tag == SectorTagType.CdTrackFlags:
            track = sector_address
    
        aaruTrack = next((t for t in self.tracks if t.sequence == track), None)
        if aaruTrack is None:
            return ErrorNumber.SectorNotFound, None
    
        if length + sector_address - 1 > aaruTrack.end_sector:
            return ErrorNumber.OutOfRange, None
    
        if aaruTrack.type == TrackType.Audio:
            return ErrorNumber.NotSupported, None

        if tag in [SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ,
                   SectorTagType.CdSectorEdc, SectorTagType.CdSectorHeader, SectorTagType.CdSectorSubHeader,
                   SectorTagType.CdSectorSync]:
            pass
        elif tag == SectorTagType.CdTrackFlags:
            if track not in self._track_flags:
                return ErrorNumber.NoData, None
            return ErrorNumber.NoError, bytes([self._track_flags[track]])
        elif tag == SectorTagType.CdSectorSubchannel:
            buffer = bytearray(96 * length)
            self._sub_stream.seek(aaruTrack.subchannel_offset + sector_address * 96)
            self._sub_stream.readinto(buffer)
            return ErrorNumber.NoError, bytes(Subchannel.interleave(buffer))
        else:
            return ErrorNumber.NotSupported, None

        sector_offset = 0
        sector_size = 0
        sector_skip = 0

        if aaruTrack.type == TrackType.CdMode1:
            if tag == SectorTagType.CdSectorSync:
                sector_offset, sector_size, sector_skip = 0, 12, 2340
            elif tag == SectorTagType.CdSectorHeader:
                sector_offset, sector_size, sector_skip = 12, 4, 2336
            elif tag == SectorTagType.CdSectorSubHeader:
                return ErrorNumber.NotSupported, None
            elif tag == SectorTagType.CdSectorEcc:
                sector_offset, sector_size, sector_skip = 2076, 276, 0
            elif tag == SectorTagType.CdSectorEccP:
                sector_offset, sector_size, sector_skip = 2076, 172, 104
            elif tag == SectorTagType.CdSectorEccQ:
                sector_offset, sector_size, sector_skip = 2248, 104, 0
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2064, 4, 284
        elif aaruTrack.type == TrackType.CdMode2Formless:
            if tag in [SectorTagType.CdSectorSync, SectorTagType.CdSectorHeader,
                       SectorTagType.CdSectorEcc, SectorTagType.CdSectorEccP, SectorTagType.CdSectorEccQ]:
                return ErrorNumber.NotSupported, None
            elif tag == SectorTagType.CdSectorSubHeader:
                sector_offset, sector_size, sector_skip = 0, 8, 2328
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2332, 4, 0
        elif aaruTrack.type == TrackType.CdMode2Form1:
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
        elif aaruTrack.type == TrackType.CdMode2Form2:
            if tag == SectorTagType.CdSectorSync:
                sector_offset, sector_size, sector_skip = 0, 12, 2340
            elif tag == SectorTagType.CdSectorHeader:
                sector_offset, sector_size, sector_skip = 12, 4, 2336
            elif tag == SectorTagType.CdSectorSubHeader:
                sector_offset, sector_size, sector_skip = 16, 8, 2328
            elif tag == SectorTagType.CdSectorEdc:
                sector_offset, sector_size, sector_skip = 2348, 4, 0
            else:
                return ErrorNumber.NotSupported, None
        else:
            return ErrorNumber.NotSupported, None

        buffer = bytearray(sector_size * length)
        self._data_stream.seek(aaruTrack.file_offset + sector_address * 2352)
        self._sub_stream = self._sub_filter.get_sub_stream()

        if sector_offset == 0 and sector_skip == 0:
            self._data_stream.readinto(buffer)
        else:
            for i in range(length):
                sector = bytearray(sector_size)
                self._data_stream.seek(sector_offset, io.SEEK_CUR)
                self._data_stream.readinto(sector)
                self._data_stream.seek(sector_skip, io.SEEK_CUR)
                buffer[i*sector_size:(i+1)*sector_size] = sector

        return ErrorNumber.NoError, bytes(buffer)

    def read_sectors(self, sector_address: int, length: int, track: Optional[int] = None) -> tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            # Existing implementation for reading sectors without track specification
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.end_sector - track.start_sector + 1:
                        return self.read_sectors(sector_address - start_sector, length, track_sequence)
            return ErrorNumber.SectorNotFound, None
        else:
            aaruTrack = next((t for t in self.tracks if t.sequence == track), None)
            if aaruTrack is None:
                return ErrorNumber.SectorNotFound, None
            
            if length + sector_address - 1 > aaruTrack.end_sector:
                return ErrorNumber.OutOfRange, None
            
            sector_offset = 0
            sector_size = 0
            sector_skip = 0
            mode2 = False
            
            if aaruTrack.type == TrackType.Audio:
                sector_offset = 0
                sector_size = 2352
                sector_skip = 0
            elif aaruTrack.type == TrackType.CdMode1:
                sector_offset = 16
                sector_size = 2048
                sector_skip = 288
            elif aaruTrack.type in [TrackType.CdMode2Formless, TrackType.CdMode2Form1, TrackType.CdMode2Form2]:
                mode2 = True
                sector_offset = 0
                sector_size = 2352
                sector_skip = 0
            else:
                return ErrorNumber.NotSupported, None
            
            buffer = bytearray(sector_size * length)
            self._data_stream.seek(aaruTrack.file_offset + sector_address * 2352)
            
            if mode2:
                mode2_ms = io.BytesIO()
                self._data_stream.readinto(buffer)
                for i in range(length):
                    sector = buffer[sector_size*i:sector_size*(i+1)]
                    sector = Sector.get_user_data_from_mode2(sector)
                    mode2_ms.write(sector)
                buffer = mode2_ms.getvalue()
            elif sector_offset == 0 and sector_skip == 0:
                self._data_stream.readinto(buffer)
            else:
                for i in range(length):
                    sector = bytearray(sector_size)
                    self._data_stream.seek(sector_offset, io.SEEK_CUR)
                    self._data_stream.readinto(sector)
                    self._data_stream.seek(sector_skip, io.SEEK_CUR)
                    buffer[i*sector_size:(i+1)*sector_size] = sector
            
            return ErrorNumber.NoError, bytes(buffer)

    def read_sectors_long(self, sector_address: int, length: int, track: Optional[int] = None) -> tuple[ErrorNumber, Optional[bytes]]:
        if track is None:
            # Existing implementation for reading long sectors without track specification
            for track_sequence, start_sector in self._offset_map.items():
                if sector_address >= start_sector:
                    track = next((t for t in self.tracks if t.sequence == track_sequence), None)
                    if track and sector_address - start_sector < track.end_sector - track.start_sector + 1:
                        return self.read_sectors_long(sector_address - start_sector, length, track_sequence)
            return ErrorNumber.SectorNotFound, None
        else:
            aaruTrack = next((t for t in self.tracks if t.sequence == track), None)
            if aaruTrack is None:
                return ErrorNumber.SectorNotFound, None

            if length + sector_address - 1 > aaruTrack.end_sector:
                return ErrorNumber.OutOfMemory, None

            buffer = bytearray(2352 * length)
            self._data_stream.seek(aaruTrack.file_offset + sector_address * 2352)
            self._data_stream.readinto(buffer)

            return ErrorNumber.NoError, bytes(buffer)

    def read_sectors_long(self, sector_address: int, length: int) -> tuple[ErrorNumber, Optional[bytes]]:
        for track_sequence, start_sector in self._offset_map.items():
            if sector_address >= start_sector:
                track = next((t for t in self.tracks if t.sequence == track_sequence), None)
                if track and sector_address - start_sector < track.end_sector - track.start_sector + 1:
                    return self.read_sectors_long_with_track(sector_address - start_sector, length, track_sequence)
        return ErrorNumber.SectorNotFound, None

    def get_session_tracks(self, session: Union[Session, int]) -> List[Track]:
        if isinstance(session, Session):
            return self.get_session_tracks(session.sequence)
        return [track for track in self.tracks if track.session == session]

    def close(self):
        if self._cue_stream:
            self._cue_stream.close()
        if self._data_stream:
            self._data_stream.close()
        if self._sub_stream:
            self._sub_stream.close()
        if self._ccd_filter:
            self._ccd_filter.close()
