import struct
from math import floor
from cd_utils import crc16

# creates an empty subchannel file

# Sub function
def sub(filename, strsectors):
    sectors = int(strsectors)
    if sectors == 0 or sectors == -1:
        print("Wrong size!")
        return

    with open(filename, "w+b") as subchannel:
        buffer = bytearray([0x41, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        for sector in range(sectors):
            mindbl = sector / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector - (minutes * 60 * 75) - (sec * 75)
            buffer[3] = int(minutes)
            buffer[4] = int(sec)
            buffer[5] = int(frame)

            mindbl = sector / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector - (minutes * 60 * 75) - (sec * 75)
            buffer[7] = int(minutes)
            buffer[8] = int(sec)
            buffer[9] = int(frame)

            crc = crc16(buffer, 10)

            for i in range(12):
                subchannel.write(b"\x00")
            subchannel.write(buffer)
            subchannel.write(struct.pack("B", crc[1]))
            subchannel.write(struct.pack("B", crc))
            for i in range(72):
                subchannel.write(b"\x00")

            print("Creating: %02u%%" % ((100 * sector) / sectors))
    subchannel.seek(0, 0)
    for i in range(12):
        subchannel.write(b"\xFF")
    print("Creating: 100%%")
    subchannel.close()
    print("Done!")
    return

def sub_new(filename, strsectors):
    with open(filename, 'wb') as subchannel:
        sectors = int(strsectors)
        sector2s = [150 + i for i in range(sectors)]
        if sectors == 0 or sectors == -1:
            print('Wrong size!')
            return

        buffer = bytearray(10)
        buffer[0] = 0x41
        buffer[1] = 0x01
        buffer[2] = 0x01
        buffer[6] = 0x00

        for sector, sector2 in zip(range(sectors), sector2s):
            mindbl = sector / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector - (minutes * 60 * 75) - (sec * 75)
            buffer[3] = int(minutes)
            buffer[4] = int(sec)
            buffer[5] = int(frame)

            mindbl = sector2 / 60 / 75
            minutes = int(floor(mindbl))
            secdbl = (sector2 - (minutes * 60 * 75)) / 75
            sec = int(floor(secdbl))
            frame = sector2 - (minutes * 60 * 75) - (sec * 75)
            buffer[7] = int(minutes)
            buffer[8] = int(sec)
            buffer[9] = int(frame)

            crc = crc16(buffer, 10)
            # Write the checksum into the subchannel
            for i in range(12):
                subchannel.write(bytes([0x00]))
            subchannel.write(buffer)
            subchannel.write(bytes([(crc >> 8) & 0xff, (crc >> 0) & 0xff]))
            for i in range(72):
                subchannel.write(bytes([0x00]))

            print("Creating: %02u%%" % ((100 * sector) / sectors))
        subchannel.seek(0, 0)
        for i in range(12):
            subchannel.write(b"\xFF")
        print("Creating: 100%%")
        subchannel.close()
    print('Done!')