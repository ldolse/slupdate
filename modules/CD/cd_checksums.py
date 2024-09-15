# cd_checksums.py

import struct
from typing import List, Optional, Tuple
from modules.checksums import CRC16CCITTContext

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CdChecksums:
    MODULE_NAME = "CD checksums"
    _ecc_f_table: List[int] = []
    _ecc_b_table: List[int] = []
    _edc_table: List[int] = []

    @staticmethod
    def check_cd_sector(buffer: bytes) -> Optional[bool]:
        return CdChecksums.check_cd_sector_with_details(buffer)[0]

    @staticmethod
    def check_cd_sector_with_details(buffer: bytes) -> Tuple[Optional[bool], Optional[bool], Optional[bool], Optional[bool]]:
        correct_ecc_p = None
        correct_ecc_q = None
        correct_edc = None

        if len(buffer) == 2448:
            subchannel = buffer[2352:]
            channel = buffer[:2352]
            channel_status, correct_ecc_p, correct_ecc_q, correct_edc = CdChecksums.check_cd_sector_channel(channel)
            subchannel_status = CdChecksums.check_cd_sector_subchannel(subchannel)
            status = None

            if channel_status is False or subchannel_status is False:
                status = False

            if channel_status is None and subchannel_status is True:
                status = True
            elif channel_status is True and subchannel_status is None:
                status = True

            return status, correct_ecc_p, correct_ecc_q, correct_edc

        elif len(buffer) == 2352:
            return CdChecksums.check_cd_sector_channel(buffer)

        return None, None, None, None

    @staticmethod
    def ecc_init():
        CdChecksums._ecc_f_table = [0] * 256
        CdChecksums._ecc_b_table = [0] * 256
        CdChecksums._edc_table = [0] * 256

        for i in range(256):
            edc = i
            j = (i << 1) ^ (0x11D if (i & 0x80) else 0)
            CdChecksums._ecc_f_table[i] = j & 0xFF
            CdChecksums._ecc_b_table[i ^ j] = i & 0xFF

            for _ in range(8):
                edc = (edc >> 1) ^ (0xD8018001 if (edc & 1) else 0)

            CdChecksums._edc_table[i] = edc

    @staticmethod
    def check_ecc(address: bytes, data: bytes, major_count: int, minor_count: int, major_mult: int, minor_inc: int, ecc: bytes) -> bool:
        size = major_count * minor_count

        for major in range(major_count):
            index = (major >> 1) * major_mult + (major & 1)
            ecc_a = 0
            ecc_b = 0

            for _ in range(minor_count):
                temp = address[index] if index < 4 else data[index - 4]
                index += minor_inc

                if index >= size:
                    index -= size

                ecc_a ^= temp
                ecc_b ^= temp
                ecc_a = CdChecksums._ecc_f_table[ecc_a]

            ecc_a = CdChecksums._ecc_b_table[CdChecksums._ecc_f_table[ecc_a] ^ ecc_b]

            if ecc[major] != ecc_a or ecc[major + major_count] != (ecc_a ^ ecc_b):
                return False

        return True

    @staticmethod
    def check_cd_sector_channel(channel: bytes) -> Tuple[Optional[bool], Optional[bool], Optional[bool], Optional[bool]]:
        CdChecksums.ecc_init()

        correct_ecc_p = None
        correct_ecc_q = None
        correct_edc = None

        if channel[:12] != b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00':
            return None, None, None, None

        mode = channel[0x00F] & 0x03

        if mode == 0x00:
            return all(b == 0 for b in channel[0x010:0x930]), None, None, None

        elif mode == 0x01:
            if any(channel[0x814:0x81C]):
                return False, None, None, None

            address = channel[0x0C:0x10]
            data = channel[0x10:0x810]
            data2 = channel[0x10:0x818]
            ecc_p = channel[0x81C:0x8C8]
            ecc_q = channel[0x8C8:0x930]

            failed_ecc_p = not CdChecksums.check_ecc(address, data, 86, 24, 2, 86, ecc_p)
            failed_ecc_q = not CdChecksums.check_ecc(address, data2, 52, 43, 86, 88, ecc_q)

            correct_ecc_p = not failed_ecc_p
            correct_ecc_q = not failed_ecc_q

            stored_edc = struct.unpack("<I", channel[0x810:0x814])[0]
            calculated_edc = CdChecksums.compute_edc(0, channel[:0x810])

            correct_edc = calculated_edc == stored_edc

            return not (failed_ecc_p or failed_ecc_q or not correct_edc), correct_ecc_p, correct_ecc_q, correct_edc

        elif mode == 0x02:
            mode2_sector = channel[0x10:]

            if channel[0x012] & 0x20:  # mode 2 form 2
                if channel[0x010:0x014] != channel[0x014:0x018]:
                    print(f"Subheader copies differ in mode 2 form 2 sector at address: {channel[0x00C]:02X}:{channel[0x00D]:02X}:{channel[0x00E]:02X}")

                stored_edc = struct.unpack("<I", mode2_sector[0x91C:0x920])[0]

                if stored_edc == 0x00000000:
                    return True, None, None, None

                calculated_edc = CdChecksums.compute_edc(0, mode2_sector[:0x91C])
                correct_edc = calculated_edc == stored_edc

                return correct_edc, None, None, correct_edc

            else:  # mode 2 form 1
                if channel[0x010:0x014] != channel[0x014:0x018]:
                    print(f"Subheader copies differ in mode 2 form 1 sector at address: {channel[0x00C]:02X}:{channel[0x00D]:02X}:{channel[0x00E]:02X}")

                address = b'\x00\x00\x00\x00'
                ecc_p = mode2_sector[0x80C:0x8B8]
                ecc_q = mode2_sector[0x8B8:0x920]

                failed_ecc_p = not CdChecksums.check_ecc(address, mode2_sector, 86, 24, 2, 86, ecc_p)
                failed_ecc_q = not CdChecksums.check_ecc(address, mode2_sector, 52, 43, 86, 88, ecc_q)

                correct_ecc_p = not failed_ecc_p
                correct_ecc_q = not failed_ecc_q

                stored_edc = struct.unpack("<I", mode2_sector[0x808:0x80C])[0]
                calculated_edc = CdChecksums.compute_edc(0, mode2_sector[:0x808])

                correct_edc = calculated_edc == stored_edc

                return not (failed_ecc_p or failed_ecc_q or not correct_edc), correct_ecc_p, correct_ecc_q, correct_edc

        else:
            print(f"Unknown mode {mode} sector at address: {channel[0x00C]:02X}:{channel[0x00D]:02X}:{channel[0x00E]:02X}")
            return None, None, None, None

    @staticmethod
    def compute_edc(edc: int, src: bytes) -> int:
        for b in src:
            edc = (edc >> 8) ^ CdChecksums._edc_table[(edc ^ b) & 0xFF]
        return edc

    @staticmethod
    def check_cd_sector_subchannel(subchannel: bytes) -> Optional[bool]:
        status = True
        q_sub_channel = bytearray(12)
        cd_text_pack1 = bytearray(18)
        cd_text_pack2 = bytearray(18)
        cd_text_pack3 = bytearray(18)
        cd_text_pack4 = bytearray(18)
        cd_sub_rw_pack1 = bytearray(24)
        cd_sub_rw_pack2 = bytearray(24)
        cd_sub_rw_pack3 = bytearray(24)
        cd_sub_rw_pack4 = bytearray(24)

        i = 0

        # Deinterleave Q subchannel
        for j in range(12):
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) << 1)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | (subchannel[i] & 0x40)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 1)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 2)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 3)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 4)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 5)) & 0xFF
            i += 1
            q_sub_channel[j] = (q_sub_channel[j] | ((subchannel[i] & 0x40) >> 6)) & 0xFF
            i += 1

        i = 0

        # Deinterleave CD-Text packs
        for pack in (cd_text_pack1, cd_text_pack2, cd_text_pack3, cd_text_pack4):
            for j in range(18):
                pack[j] = (pack[j] | ((subchannel[i] & 0x3F) << 2)) & 0xFF
                i += 1
                if j < 17:
                    pack[j] = (pack[j] | ((subchannel[i] & 0xC0) >> 4)) & 0xFF
                pack[j] = (pack[j] | ((subchannel[i] & 0x0F) << 4)) & 0xFF
                i += 1
                if j < 17:
                    pack[j] = (pack[j] | ((subchannel[i] & 0x3C) >> 2)) & 0xFF
                pack[j] = (pack[j] | ((subchannel[i] & 0x03) << 6)) & 0xFF
                i += 1
                pack[j] = (pack[j] | (subchannel[i] & 0x3F)) & 0xFF
                i += 1

        i = 0

        # Deinterleave CD Sub RW packs
        for pack in (cd_sub_rw_pack1, cd_sub_rw_pack2, cd_sub_rw_pack3, cd_sub_rw_pack4):
            for j in range(24):
                pack[j] = subchannel[i] & 0x3F
                i += 1

        # Check pack type
        pack_type = cd_sub_rw_pack1[0]
        if pack_type == 0x00:
            logger.debug("Detected Zero Pack in subchannel")
        elif pack_type == 0x08:
            logger.debug("Detected Line Graphics Pack in subchannel")
        elif pack_type == 0x09:
            logger.debug("Detected CD+G Pack in subchannel")
        elif pack_type == 0x0A:
            logger.debug("Detected CD+EG Pack in subchannel")
        elif pack_type == 0x14:
            logger.debug("Detected CD-TEXT Pack in subchannel")
        elif pack_type == 0x18:
            logger.debug("Detected CD-MIDI Pack in subchannel")
        elif pack_type == 0x38:
            logger.debug("Detected User Pack in subchannel")
        else:
            logger.debug(f"Detected unknown Pack type in subchannel: mode {pack_type & 0x38:02b}, item {pack_type & 0x07:02b}")

        # Check Q subchannel CRC
        q_subchannel_crc = (q_sub_channel[10] << 8) | q_sub_channel[11]
        q_subchannel_for_crc = q_sub_channel[:10]
        calculated_qcrc = CRC16CCITTContext.calculate(q_subchannel_for_crc)

        if q_subchannel_crc != calculated_qcrc:
            logger.debug(f"Q subchannel CRC {calculated_qcrc:04X}, expected {q_subchannel_crc:04X}")
            status = False

        # Check CD-Text pack CRCs
        for i, pack in enumerate([cd_text_pack1, cd_text_pack2, cd_text_pack3, cd_text_pack4], 1):
            if pack[0] & 0x80:
                cd_text_pack_crc = (pack[16] << 8) | pack[17]
                cd_text_pack_for_crc = pack[:16]
                calculated_cdtp_crc = CRC16CCITTContext.calculate(cd_text_pack_for_crc)

                logger.debug(f"Cyclic CDTP{i} {cd_text_pack_crc:04X} Calc CDTP{i} {calculated_cdtp_crc:04X}")

                if cd_text_pack_crc != calculated_cdtp_crc and cd_text_pack_crc != 0:
                    logger.debug(f"CD-Text Pack {i} CRC {cd_text_pack_crc:04X}, expected {calculated_cdtp_crc:04X}")
                    status = False

        return status
