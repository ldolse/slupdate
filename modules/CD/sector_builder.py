import logging
from typing import Tuple
from modules.CD.cd_types import TrackType


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SectorBuilder:
    def __init__(self):
        self._ecc_f_table = bytearray(256)
        self._ecc_b_table = bytearray(256)
        self._edc_table = [0] * 256

        for i in range(256):
            edc = i
            j = (i << 1) ^ (0x11D if (i & 0x80) == 0x80 else 0)
            self._ecc_f_table[i] = j & 0xFF
            self._ecc_b_table[i ^ j] = i & 0xFF

            for _ in range(8):
                edc = edc >> 1 ^ (0xD8018001 if (edc & 1) > 0 else 0)

            self._edc_table[i] = edc

    @staticmethod
    def lba_to_msf(pos: int) -> Tuple[int, int, int]:
        pos += 150
        return (pos // 75 // 60, (pos // 75) % 60, pos % 75)

    def reconstruct_prefix(self, sector: bytearray, track_type: TrackType, lba: int) -> None:
        # Sync
        sector[0x000:0x00C] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00'

        minute, second, frame = self.lba_to_msf(lba)
        sector[0x00C] = (minute // 10 << 4) + minute % 10
        sector[0x00D] = (second // 10 << 4) + second % 10
        sector[0x00E] = (frame // 10 << 4) + frame % 10

        if track_type == TrackType.CdMode1:
            # Mode
            sector[0x00F] = 0x01
        elif track_type in [TrackType.CdMode2Form1, TrackType.CdMode2Form2, TrackType.CdMode2Formless]:
            # Mode
            sector[0x00F] = 0x02

            # Flags
            sector[0x010:0x014] = sector[0x014:0x018]
        else:
            return

    def compute_edc(self, edc: int, src: bytes, size: int, src_offset: int = 0) -> int:
        for i in range(size):
            edc = ((edc >> 8) ^ self._edc_table[(edc ^ src[src_offset + i]) & 0xFF]) & 0xFFFFFFFF
        return edc

    def reconstruct_ecc(self, sector: bytearray, track_type: TrackType) -> None:
        if track_type == TrackType.CdMode1:
            computed_edc = self.compute_edc(0, sector, 0x810)
            sector[0x810:0x814] = computed_edc.to_bytes(4, byteorder='little')
        elif track_type == TrackType.CdMode2Form1:
            computed_edc = self.compute_edc(0, sector[0x10:], 0x808)
            sector[0x818:0x81C] = computed_edc.to_bytes(4, byteorder='little')
        elif track_type == TrackType.CdMode2Form2:
            computed_edc = self.compute_edc(0, sector[0x10:], 0x91C)
            sector[0x92C:0x930] = computed_edc.to_bytes(4, byteorder='little')
        else:
            return

        zero_address = bytearray(4)

        if track_type == TrackType.CdMode1:
            # Reserved
            sector[0x814:0x81C] = b'\x00' * 8
            self.ecc_write_sector(sector, sector, 0xC, 0x10, 0x81C)
        elif track_type == TrackType.CdMode2Form1:
            self.ecc_write_sector(zero_address, sector, 0, 0x10, 0x81C)
        else:
            return

    def ecc_write_sector(self, address: bytearray, data: bytearray, address_offset: int, data_offset: int, ecc_offset: int) -> None:
        self.write_ecc(address, data, 86, 24, 2, 86, address_offset, data_offset, ecc_offset)        # P
        self.write_ecc(address, data, 52, 43, 86, 88, address_offset, data_offset, ecc_offset + 0xAC)  # Q

    def write_ecc(self, address: bytearray, data: bytearray, major_count: int, minor_count: int, major_mult: int, minor_inc: int,
                  address_offset: int, data_offset: int, ecc_offset: int) -> None:
        size = major_count * minor_count

        for major in range(major_count):
            idx = (major >> 1) * major_mult + (major & 1)
            ecc_a = 0
            ecc_b = 0

            for _ in range(minor_count):
                temp = address[idx + address_offset] if idx < 4 else data[idx + data_offset - 4]
                idx += minor_inc
                if idx >= size:
                    idx -= size

                ecc_a ^= temp
                ecc_b ^= temp
                ecc_a = self._ecc_f_table[ecc_a]

            ecc_a = self._ecc_b_table[self._ecc_f_table[ecc_a] ^ ecc_b]
            data[major + ecc_offset] = ecc_a
            data[major + major_count + ecc_offset] = ecc_a ^ ecc_b