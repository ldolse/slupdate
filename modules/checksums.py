import binascii
from typing import Tuple

class CRC16CCITTContext:
    CRC16_CCITT_POLY = 0x8408
    CRC16_CCITT_SEED = 0x0000

    @staticmethod
    def calculate(buffer: bytes) -> int:
        return binascii.crc_hqx(buffer, CRC16CCITTContext.CRC16_CCITT_SEED)

    @classmethod
    def file(cls, filename: str) -> Tuple[str, bytes]:
        with open(filename, 'rb') as f:
            data = f.read()
        crc = cls.calculate(data)
        hash_bytes = crc.to_bytes(2, byteorder='big')
        return hash_bytes.hex(), hash_bytes

    @classmethod
    def data(cls, data: bytes, length: int = None) -> Tuple[str, bytes]:
        if length is None:
            length = len(data)
        crc = cls.calculate(data[:length])
        hash_bytes = crc.to_bytes(2, byteorder='big')
        return hash_bytes.hex(), hash_bytes

    @staticmethod
    def calculate_static(buffer: bytes) -> int:
        return CRC16CCITTContext.calculate(buffer)

    @property
    def name(self) -> str:
        return "CRC-16 CCITT"