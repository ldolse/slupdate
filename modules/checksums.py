import binascii

class CRC16CCITTContext:
    @staticmethod
    def calculate(buffer: bytes) -> int:
        return binascii.crc_hqx(buffer, 0)

    @classmethod
    def file(cls, filename: str) -> tuple[str, bytes]:
        with open(filename, 'rb') as f:
            data = f.read()
        crc = cls.calculate(data)
        hash_bytes = crc.to_bytes(2, byteorder='big')
        return hash_bytes.hex(), hash_bytes

    @classmethod
    def data(cls, data: bytes) -> tuple[str, bytes]:
        crc = cls.calculate(data)
        hash_bytes = crc.to_bytes(2, byteorder='big')
        return hash_bytes.hex(), hash_bytes
