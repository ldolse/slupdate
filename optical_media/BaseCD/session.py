import logging
from typing import Optional, List
from enum import IntEnum
import struct

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Session:
    MODULE_NAME = "CD Session Info decoder"

    class CDSessionInfo:
        def __init__(self):
            self.data_length: int = 0
            self.first_complete_session: int = 0
            self.last_complete_session: int = 0
            self.track_descriptors: List['Session.TrackDataDescriptor'] = []

    class TrackDataDescriptor:
        def __init__(self):
            self.reserved1: int = 0
            self.adr: int = 0
            self.control: int = 0
            self.track_number: int = 0
            self.reserved2: int = 0
            self.track_start_address: int = 0

    class TocAdr(IntEnum):
        NoInformation = 0x00
        CurrentPosition = 0x01
        ISRC = 0x03
        MediaCatalogNumber = 0x02

    class TocControl(IntEnum):
        TwoChanNoPreEmph = 0x00
        TwoChanPreEmph = 0x01
        CopyPermissionMask = 0x02
        DataTrack = 0x04
        DataTrackIncremental = 0x05
        FourChanNoPreEmph = 0x08
        FourChanPreEmph = 0x09
        ReservedMask = 0x0C

    @staticmethod
    def Decode(cd_session_info_response: bytes) -> Optional[CDSessionInfo]:
        if not cd_session_info_response or len(cd_session_info_response) <= 4:
            return None

        decoded = Session.CDSessionInfo()
        decoded.data_length = struct.unpack('>H', cd_session_info_response[0:2])[0]
        decoded.first_complete_session = cd_session_info_response[2]
        decoded.last_complete_session = cd_session_info_response[3]

        decoded.track_descriptors = []

        if decoded.data_length + 2 != len(cd_session_info_response):
            logger.debug(
                f"Expected CDSessionInfo size {decoded.data_length + 2} bytes is not received size {len(cd_session_info_response)} bytes, not decoding"
            )
            return None

        for i in range((decoded.data_length - 2) // 8):
            descriptor = Session.TrackDataDescriptor()
            offset = i * 8 + 4
            descriptor.reserved1 = cd_session_info_response[offset]
            descriptor.adr = (cd_session_info_response[offset + 1] & 0xF0) >> 4
            descriptor.control = cd_session_info_response[offset + 1] & 0x0F
            descriptor.track_number = cd_session_info_response[offset + 2]
            descriptor.reserved2 = cd_session_info_response[offset + 3]
            descriptor.track_start_address = struct.unpack('>I', cd_session_info_response[offset + 4:offset + 8])[0]
            decoded.track_descriptors.append(descriptor)

        return decoded

    @staticmethod
    def Prettify(cd_session_info_response: Optional[CDSessionInfo]) -> Optional[str]:
        if cd_session_info_response is None:
            return None

        response = cd_session_info_response
        output = []

        output.append(f"First complete session number: {response.first_complete_session}")
        output.append(f"Last complete session number: {response.last_complete_session}")

        for descriptor in response.track_descriptors:
            output.append(f"First track number in last complete session: {descriptor.track_number}")
            output.append(f"Track starts at LBA: {descriptor.track_start_address} or MSF: {(descriptor.track_start_address & 0x0000FF00) >> 8}:{(descriptor.track_start_address & 0x00FF0000) >> 16}:{(descriptor.track_start_address & 0xFF000000) >> 24}")

            adr = Session.TocAdr(descriptor.adr)
            if adr == Session.TocAdr.NoInformation:
                output.append("Q subchannel mode not given")
            elif adr == Session.TocAdr.CurrentPosition:
                output.append("Q subchannel stores current position")
            elif adr == Session.TocAdr.ISRC:
                output.append("Q subchannel stores ISRC")
            elif adr == Session.TocAdr.MediaCatalogNumber:
                output.append("Q subchannel stores media catalog number")

            control = Session.TocControl(descriptor.control)
            if descriptor.control & Session.TocControl.ReservedMask == Session.TocControl.ReservedMask:
                output.append(f"Reserved flags {descriptor.control} set")
            else:
                if control == Session.TocControl.TwoChanNoPreEmph:
                    output.append("Stereo audio track with no pre-emphasis")
                elif control == Session.TocControl.TwoChanPreEmph:
                    output.append("Stereo audio track with 50/15 us pre-emphasis")
                elif control == Session.TocControl.FourChanNoPreEmph:
                    output.append("Quadraphonic audio track with no pre-emphasis")
                elif control == Session.TocControl.FourChanPreEmph:
                    output.append("Stereo audio track with 50/15 us pre-emphasis")
                elif control == Session.TocControl.DataTrack:
                    output.append("Data track recorded uninterrupted")
                elif control == Session.TocControl.DataTrackIncremental:
                    output.append("Data track recorded incrementally")

                if descriptor.control & Session.TocControl.CopyPermissionMask:
                    output.append("Digital copy of track is permitted")
                else:
                    output.append("Digital copy of track is prohibited")

            output.append("")

        return "\n".join(output)

    @staticmethod
    def Prettify_bytes(cd_session_info_response: bytes) -> str:
        decoded = Session.Decode(cd_session_info_response)
        return Session.Prettify(decoded)
