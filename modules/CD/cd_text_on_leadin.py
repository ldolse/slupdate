import logging
from typing import Optional, List
import struct
from enum import IntEnum

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CDTextOnLeadIn:
    MODULE_NAME = "CD-TEXT decoder"

    class PackTypeIndicator(IntEnum):
        Title = 0x80
        Performer = 0x81
        Songwriter = 0x82
        Composer = 0x83
        Arranger = 0x84
        Message = 0x85
        DiscIdentification = 0x86
        GenreIdentification = 0x87
        TOCInformation = 0x88
        SecondTOCInformation = 0x89
        Reserved1 = 0x8A
        Reserved2 = 0x8B
        Reserved3 = 0x8C
        ReservedForContentProvider = 0x8D
        UPCorISRC = 0x8E
        BlockSizeInformation = 0x8F

    class CDText:
        def __init__(self):
            self.data_length: int = 0
            self.reserved1: int = 0
            self.reserved2: int = 0
            self.data_packs: List['CDTextOnLeadIn.CDTextPack'] = []

    class CDTextPack:
        def __init__(self):
            self.header_id1: int = 0
            self.header_id2: int = 0
            self.header_id3: int = 0
            self.dbcc: bool = False
            self.block_number: int = 0
            self.character_position: int = 0
            self.text_data_field: bytes = b''
            self.crc: int = 0

    @staticmethod
    def Decode(cd_text_response: bytes) -> Optional[CDText]:
        if not cd_text_response or len(cd_text_response) <= 4:
            return None

        decoded = CDTextOnLeadIn.CDText()
        decoded.data_length = struct.unpack('>H', cd_text_response[0:2])[0]
        decoded.reserved1 = cd_text_response[2]
        decoded.reserved2 = cd_text_response[3]

        if decoded.data_length == 2:
            return None

        if decoded.data_length + 2 != len(cd_text_response):
            logger.debug(
                f"Expected CD-TEXT size {decoded.data_length + 2} bytes is not received size {len(cd_text_response)} bytes, not decoding"
            )
            return None

        for i in range((decoded.data_length - 2) // 18):
            pack = CDTextOnLeadIn.CDTextPack()
            offset = i * 18 + 4
            pack.header_id1 = cd_text_response[offset]
            pack.header_id2 = cd_text_response[offset + 1]
            pack.header_id3 = cd_text_response[offset + 2]
            pack.dbcc = bool(cd_text_response[offset + 3] & 0x80)
            pack.block_number = (cd_text_response[offset + 3] & 0x70) >> 4
            pack.character_position = cd_text_response[offset + 3] & 0x0F
            pack.text_data_field = cd_text_response[offset + 4:offset + 16]
            pack.crc = struct.unpack('>H', cd_text_response[offset + 16:offset + 18])[0]
            decoded.data_packs.append(pack)

        return decoded

    @staticmethod
    def Prettify(cd_text_response: Optional[CDText]) -> Optional[str]:
        if cd_text_response is None:
            return None

        response = cd_text_response
        output = []

        for descriptor in response.data_packs:
            if (descriptor.header_id1 & 0x80) != 0x80:
                if (descriptor.header_id1 & 0x80) != 0:
                    output.append(f"Incorrect CD-Text pack type {descriptor.header_id1}, not decoding")
                continue

            pack_type = CDTextOnLeadIn.PackTypeIndicator(descriptor.header_id1)
            if pack_type == CDTextOnLeadIn.PackTypeIndicator.Title:
                if descriptor.header_id2 == 0x00:
                    output.append("CD-Text pack contains title for album")
                else:
                    output.append(f"CD-Text pack contains title for track {descriptor.header_id2}")
            elif pack_type == CDTextOnLeadIn.PackTypeIndicator.Performer:
                if descriptor.header_id2 == 0x00:
                    output.append("CD-Text pack contains performer for album")
                else:
                    output.append(f"CD-Text pack contains performer for track {descriptor.header_id2}")
            # ... (similar conditions for other pack types)
            elif pack_type == CDTextOnLeadIn.PackTypeIndicator.BlockSizeInformation:
                output.append("CD-Text pack contains size block information")

            if pack_type in [CDTextOnLeadIn.PackTypeIndicator.Title, 
                             CDTextOnLeadIn.PackTypeIndicator.Performer, 
                             CDTextOnLeadIn.PackTypeIndicator.Songwriter,
                             CDTextOnLeadIn.PackTypeIndicator.Composer,
                             CDTextOnLeadIn.PackTypeIndicator.Arranger,
                             CDTextOnLeadIn.PackTypeIndicator.Message,
                             CDTextOnLeadIn.PackTypeIndicator.DiscIdentification,
                             CDTextOnLeadIn.PackTypeIndicator.GenreIdentification,
                             CDTextOnLeadIn.PackTypeIndicator.UPCorISRC]:
                if descriptor.dbcc:
                    output.append("Double Byte Character Code is used")
                output.append(f"Block number: {descriptor.block_number}")
                output.append(f"Character position: {descriptor.character_position}")
                output.append(f"Text field: {descriptor.text_data_field.decode('iso-8859-1')}")
            else:
                output.append(f"Binary contents: {descriptor.text_data_field.hex()}")

            output.append(f"CRC: 0x{descriptor.crc:X4}")
            output.append("")

        return "\n".join(output)

    @staticmethod
    def Prettify_bytes(cd_text_response: bytes) -> Optional[str]:
        decoded = CDTextOnLeadIn.Decode(cd_text_response)
        return CDTextOnLeadIn.Prettify(decoded)
