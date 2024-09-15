import logging
from modules.checksums import CRC16CCITTContext

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Subchannel:
    _isrc_table = [
        # 0x00
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "", "", "", "", "", "",
        # 0x10
        "", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
        # 0x20
        "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "", "", "", "", "",
        # 0x30
        "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    ]

    @staticmethod
    def binary_to_bcd_q(q: bytearray) -> None:
        if (q[0] & 0xF) == 1 or (q[0] & 0xF) == 5:
            for i in range(1, 9):
                if q[i] > 255:
                    logging.warning(f"Invalid value {q[i]} at index {i} in Q subchannel")
                    q[i] = 0  # or some other appropriate default value
                else:
                    q[i] = ((q[i] // 10) << 4) + (q[i] % 10)
        if q[9] > 255:
            logging.warning(f"Invalid value {q[9]} at index 9 in Q subchannel")
            q[9] = 0  # or some other appropriate default value
        else:
            q[9] = ((q[9] // 10) << 4) + (q[9] % 10)

    @staticmethod
    def bcd_to_binary_q(q: bytearray) -> None:
        if (q[0] & 0xF) == 1 or (q[0] & 0xF) == 5:
            for i in range(1, 9):
                q[i] = (q[i] // 16) * 10 + (q[i] & 0x0F)
        q[9] = (q[9] // 16) * 10 + (q[9] & 0x0F)

    @staticmethod
    def convert_q_to_raw(subchannel: bytes) -> bytes:
        pos = 0
        sub_buf = bytearray(len(subchannel) * 6)

        for i in range(0, len(subchannel), 16):
            # P
            if (subchannel[i + 15] & 0x80) <= 0:
                pos += 12
            else:
                sub_buf[pos:pos+12] = b'\xFF' * 12
                pos += 12

            # Q
            sub_buf[pos:pos+12] = subchannel[i:i+12]
            pos += 12

            # R to W
            pos += 72

        return Subchannel.interleave(sub_buf)

    @staticmethod
    def interleave(subchannel: bytes) -> bytes:
        sub_buf = bytearray(len(subchannel))
        out_pos = 0

        for in_pos in range(0, len(subchannel), 96):
            for i in range(12):
                # P
                sub_buf[out_pos + 0] += subchannel[in_pos + i + 0] & 0x80
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 0] & 0x40) << 1
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 0] & 0x20) << 2
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 0] & 0x10) << 3
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 0] & 0x08) << 4
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 0] & 0x04) << 5
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 0] & 0x02) << 6
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 0] & 0x01) << 7

                # Q
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 12] & 0x80) >> 1
                sub_buf[out_pos + 1] += subchannel[in_pos + i + 12] & 0x40
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 12] & 0x20) << 1
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 12] & 0x10) << 2
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 12] & 0x08) << 3
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 12] & 0x04) << 4
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 12] & 0x02) << 5
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 12] & 0x01) << 6

                # R
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 24] & 0x80) >> 2
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 24] & 0x40) >> 1
                sub_buf[out_pos + 2] += subchannel[in_pos + i + 24] & 0x20
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 24] & 0x10) << 1
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 24] & 0x08) << 2
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 24] & 0x04) << 3
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 24] & 0x02) << 4
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 24] & 0x01) << 5

                # S
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 36] & 0x80) >> 3
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 36] & 0x40) >> 2
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 36] & 0x20) >> 1
                sub_buf[out_pos + 3] += subchannel[in_pos + i + 36] & 0x10
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 36] & 0x08) << 1
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 36] & 0x04) << 2
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 36] & 0x02) << 3
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 36] & 0x01) << 4

                # T
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 48] & 0x80) >> 4
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 48] & 0x40) >> 3
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 48] & 0x20) >> 2
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 48] & 0x10) >> 1
                sub_buf[out_pos + 4] += subchannel[in_pos + i + 48] & 0x08
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 48] & 0x04) << 1
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 48] & 0x02) << 2
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 48] & 0x01) << 3

                # U
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 60] & 0x80) >> 5
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 60] & 0x40) >> 4
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 60] & 0x20) >> 3
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 60] & 0x10) >> 2
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 60] & 0x08) >> 1
                sub_buf[out_pos + 5] += subchannel[in_pos + i + 60] & 0x04
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 60] & 0x02) << 1
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 60] & 0x01) << 2

                # V
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 72] & 0x80) >> 6
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 72] & 0x40) >> 5
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 72] & 0x20) >> 4
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 72] & 0x10) >> 3
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 72] & 0x08) >> 2
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 72] & 0x04) >> 1
                sub_buf[out_pos + 6] += subchannel[in_pos + i + 72] & 0x02
                sub_buf[out_pos + 7] += (subchannel[in_pos + i + 72] & 0x01) << 1

                # W
                sub_buf[out_pos + 0] += (subchannel[in_pos + i + 84] & 0x80) >> 7
                sub_buf[out_pos + 1] += (subchannel[in_pos + i + 84] & 0x40) >> 6
                sub_buf[out_pos + 2] += (subchannel[in_pos + i + 84] & 0x20) >> 5
                sub_buf[out_pos + 3] += (subchannel[in_pos + i + 84] & 0x10) >> 4
                sub_buf[out_pos + 4] += (subchannel[in_pos + i + 84] & 0x08) >> 3
                sub_buf[out_pos + 5] += (subchannel[in_pos + i + 84] & 0x04) >> 2
                sub_buf[out_pos + 6] += (subchannel[in_pos + i + 84] & 0x02) >> 1
                sub_buf[out_pos + 7] += subchannel[in_pos + i + 84] & 0x01
                out_pos += 8

        return bytes(sub_buf)

    @staticmethod
    def deinterleave(subchannel: bytes) -> bytes:
        sub_buf = bytearray(len(subchannel))
        in_pos = 0

        for out_pos in range(0, len(subchannel), 96):
            for i in range(12):
                # P
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 0] & 0x80) >> 0
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 1] & 0x80) >> 1
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 2] & 0x80) >> 2
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 3] & 0x80) >> 3
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 4] & 0x80) >> 4
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 5] & 0x80) >> 5
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 6] & 0x80) >> 6
                sub_buf[out_pos + i + 0] += (subchannel[in_pos + 7] & 0x80) >> 7

                # Q
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 0] & 0x40) << 1
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 1] & 0x40) >> 0
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 2] & 0x40) >> 1
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 3] & 0x40) >> 2
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 4] & 0x40) >> 3
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 5] & 0x40) >> 4
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 6] & 0x40) >> 5
                sub_buf[out_pos + i + 12] += (subchannel[in_pos + 7] & 0x40) >> 6

                # R
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 0] & 0x20) << 2
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 1] & 0x20) << 1
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 2] & 0x20) >> 0
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 3] & 0x20) >> 1
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 4] & 0x20) >> 2
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 5] & 0x20) >> 3
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 6] & 0x20) >> 4
                sub_buf[out_pos + i + 24] += (subchannel[in_pos + 7] & 0x20) >> 5

                # S
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 0] & 0x10) << 3
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 1] & 0x10) << 2
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 2] & 0x10) << 1
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 3] & 0x10) >> 0
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 4] & 0x10) >> 1
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 5] & 0x10) >> 2
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 6] & 0x10) >> 3
                sub_buf[out_pos + i + 36] += (subchannel[in_pos + 7] & 0x10) >> 4

                # T
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 0] & 0x8) << 4
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 1] & 0x8) << 3
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 2] & 0x8) << 2
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 3] & 0x8) << 1
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 4] & 0x8) >> 0
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 5] & 0x8) >> 1
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 6] & 0x8) >> 2
                sub_buf[out_pos + i + 48] += (subchannel[in_pos + 7] & 0x8) >> 3

                # U
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 0] & 0x4) << 5
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 1] & 0x4) << 4
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 2] & 0x4) << 3
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 3] & 0x4) << 2
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 4] & 0x4) << 1
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 5] & 0x4) >> 0
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 6] & 0x4) >> 1
                sub_buf[out_pos + i + 60] += (subchannel[in_pos + 7] & 0x4) >> 2

                # V
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 0] & 0x2) << 6
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 1] & 0x2) << 5
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 2] & 0x2) << 4
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 3] & 0x2) << 3
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 4] & 0x2) << 2
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 5] & 0x2) << 1
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 6] & 0x2) >> 0
                sub_buf[out_pos + i + 72] += (subchannel[in_pos + 7] & 0x2) >> 1

                # W
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 0] & 0x1) << 7
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 1] & 0x1) << 6
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 2] & 0x1) << 5
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 3] & 0x1) << 4
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 4] & 0x1) << 3
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 5] & 0x1) << 2
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 6] & 0x1) << 1
                sub_buf[out_pos + i + 84] += (subchannel[in_pos + 7] & 0x1) >> 0

                in_pos += 8

        return bytes(sub_buf)

    @staticmethod
    def prettify_q(sub_buf: bytes, bcd: bool, lba: int, corrupted_pause: bool, pause: bool, rw_empty: bool) -> str:
        try:
            crc = CRC16CCITTContext.calculate_static(sub_buf[:10])
            crc_ok = crc.to_bytes(2, 'big') == sub_buf[10:12]

            minute = (lba + 150) // 4500
            second = ((lba + 150) % 4500) // 75
            frame = (lba + 150) % 75

            area = "Lead-In" if lba < 0 else ("Lead-out" if sub_buf[1] == 0xAA else "Program")
            control = (sub_buf[0] & 0xF0) // 16
            adr = sub_buf[0] & 0x0F

            control_info = {
                0: "Stereo audio without pre-emphasis",
                1: "Stereo audio with pre-emphasis",
                4: "Data track, recorded uninterrupted",
                5: "Data track, recorded incrementally",
                8: "Quadraphonic audio without pre-emphasis",
                9: "Quadraphonic audio with pre-emphasis"
            }.get(control & 0x0D, f"Reserved control value: {control & 0x01}")

            copy = "Copy permitted" if (control & 0x02) else "Copy prohibited"

            if bcd:
                Subchannel.bcd_to_binary_q(bytearray(sub_buf))

            q_pos = sub_buf[3] * 60 * 75 + sub_buf[4] * 75 + sub_buf[5] - 150
            pmin, psec = sub_buf[7], sub_buf[8]

            q_start = sub_buf[7] * 60 * 75 + sub_buf[8] * 75 + sub_buf[9] - 150
            next_pos = sub_buf[3] * 60 * 75 + sub_buf[4] * 75 + sub_buf[5] - 150
            zero = sub_buf[6]
            max_out = sub_buf[7] * 60 * 75 + sub_buf[8] * 75 + sub_buf[9] - 150
            final = sub_buf[3] == 0xFF and sub_buf[4] == 0xFF and sub_buf[5] == 0xFF

            Subchannel.binary_to_bcd_q(bytearray(sub_buf))

            result = []
            result.append(f"{minute:02d}:{second:02d}:{frame:02d} (LBA: {lba})")
            result.append(f"Area: {area}")
            result.append("Corrupted pause" if corrupted_pause else ("Pause" if pause else "Not pause"))
            result.append(control_info)
            result.append(copy)

            if lba < 0:
                if adr in [1, 4]:
                    if sub_buf[2] < 0xA0:
                        result.append(f"Q mode {adr}")
                        result.append(f"Position: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {q_pos})")
                        result.append(f"Track {sub_buf[2]} starts at {sub_buf[7]:02X}:{sub_buf[8]:02X}:{sub_buf[9]:02X} (LBA: {q_start})")
                    elif sub_buf[2] == 0xA0:
                        result.append(f"Q mode {adr}")
                        result.append(f"Position: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {q_pos})")
                        result.append(f"Track {sub_buf[2]} is first program area track")
                        disc_type = {
                            0x00: "CD-DA or CD-ROM",
                            0x10: "CD-I",
                            0x20: "CD-ROM XA"
                        }.get(sub_buf[8], f"Unknown: {sub_buf[8]:02X}")
                        result.append(f"Disc type: {disc_type}")
                    elif sub_buf[2] == 0xA1:
                        result.append(f"Q mode {adr}")
                        result.append(f"Position: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {q_pos})")
                        result.append(f"Track {sub_buf[2]} is last program area track")
                    elif sub_buf[2] == 0xA2:
                        result.append(f"Q mode {adr}")
                        result.append(f"Position: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {q_pos})")
                        result.append(f"Lead-out starts at {sub_buf[7]:02X}:{sub_buf[8]:02X}:{sub_buf[9]:02X} (LBA: {q_start})")
                elif adr == 2:
                    result.append(f"Q mode {adr}")
                    result.append(f"MCN: {Subchannel.decode_mcn(sub_buf)}")
                    result.append(f"Frame: {sub_buf[9]:02X}")
                elif adr == 5:
                    if sub_buf[2] == 0xB0:
                        if final:
                            result.append(f"Q mode {adr}")
                            result.append(f"Next possible program area can start at {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {next_pos})")
                            result.append(f"Last session {zero} mode 5 pointers")
                        else:
                            result.append(f"Q mode {adr}")
                            result.append(f"Next possible program area can start at {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {next_pos})")
                            result.append(f"Maximum Lead-out at {sub_buf[7]:02X}:{sub_buf[8]:02X}:{sub_buf[9]:02X} (LBA: {max_out})")
                            result.append(f"{zero} mode 5 pointers")
                    elif sub_buf[2] == 0xB1:
                        result.append(f"Q mode {adr}")
                        result.append(f"{pmin} skip interval pointers")
                        result.append(f"{psec} skip track assignments")
                    elif sub_buf[2] == 0xB2 or sub_buf[2] == 0xB3 or sub_buf[2] == 0xB4:
                        skip_tracks = ", ".join([f"{x:02X}" for x in [sub_buf[3], sub_buf[4], sub_buf[5], sub_buf[7], sub_buf[8], sub_buf[9]] if x > 0])
                        result.append(f"Q mode {adr}")
                        result.append(f"Tracks {skip_tracks} to be skipped")
                    elif sub_buf[2] == 0xC0:
                        result.append(f"Q mode {adr}")
                        result.append(f"ATIP values: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X}")
                        result.append(f"First disc Lead-in starts at {sub_buf[7]:02X}:{sub_buf[8]:02X}:{sub_buf[9]:02X} (LBA: {q_start})")
                    else:
                        result.append(f"Unknown Q sub-channel data: {sub_buf.hex().upper()}")
                else:
                    result.append(f"Unknown Q sub-channel data: {sub_buf.hex().upper()}")
            else:
                if adr == 1:
                    result.append(f"Q mode {adr}")
                    result.append(f"Track {sub_buf[1]}, Index {sub_buf[2]}")
                    result.append(f"Relative position: {sub_buf[3]:02X}:{sub_buf[4]:02X}:{sub_buf[5]:02X} (LBA: {q_pos + 150})")
                    result.append(f"Absolute position: {sub_buf[7]:02X}:{sub_buf[8]:02X}:{sub_buf[9]:02X} (LBA: {q_start})")
                elif adr == 2:
                    result.append(f"Q mode {adr}")
                    result.append(f"MCN: {Subchannel.decode_mcn(sub_buf)}")
                    result.append(f"Frame: {sub_buf[9]:02X}")
                elif adr == 3:
                    result.append(f"Q mode {adr}")
                    result.append(f"ISRC: {Subchannel.decode_isrc(sub_buf)}")
                    result.append(f"Frame: {sub_buf[9]:02X}")
                else:
                    result.append(f"Unknown Q sub-channel data: {sub_buf.hex().upper()}")

            result.append(f"Q CRC: {sub_buf[10]:02X}{sub_buf[11]:02X} ({'OK' if crc_ok else 'BAD'})")
            result.append("R-W empty" if rw_empty else "R-W not empty")

            return "\n".join(result)
        except Exception as e:
            logging.error(f"Error in prettify_q: {str(e)}")
            return f"Error processing Q subchannel: {str(e)}"

    @staticmethod
    def decode_isrc(q: bytes) -> str:
        return ''.join([
            Subchannel._isrc_table[q[1] // 4],
            Subchannel._isrc_table[(q[1] & 3) * 16 + q[2] // 16],
            Subchannel._isrc_table[(q[2] & 0xF) * 4 + q[3] // 64],
            Subchannel._isrc_table[q[3] & 0x3F],
            Subchannel._isrc_table[q[4] // 4],
            f"{q[5]:02X}{q[6]:02X}{q[7]:02X}{q[8] // 16:X}"
        ])

    @staticmethod
    def decode_mcn(q: bytes) -> str:
        return f"{q[1]:02X}{q[2]:02X}{q[3]:02X}{q[4]:02X}{q[5]:02X}{q[6]:02X}{q[7] >> 4:X}"

    @staticmethod
    def get_isrc_code(c: str) -> int:
        isrc_codes = {
            '0': 0x00, '1': 0x01, '2': 0x02, '3': 0x03, '4': 0x04, '5': 0x05, '6': 0x06, '7': 0x07,
            '8': 0x08, '9': 0x09, 'A': 0x11, 'B': 0x12, 'C': 0x13, 'D': 0x14, 'E': 0x15, 'F': 0x16,
            'G': 0x17, 'H': 0x18, 'I': 0x19, 'J': 0x1A, 'K': 0x1B, 'L': 0x1C, 'M': 0x1D, 'N': 0x1E,
            'O': 0x1F, 'P': 0x20, 'Q': 0x21, 'R': 0x22, 'S': 0x23, 'T': 0x24, 'U': 0x25, 'V': 0x26,
            'W': 0x27, 'X': 0x28, 'Y': 0x29, 'Z': 0x2A
        }
        return isrc_codes.get(c, 0x00)

    @staticmethod
    def generate(sector: int, track_sequence: int, pregap: int, track_start: int, flags: int, index: int) -> bytes:
        is_pregap = sector < 0 or sector <= track_start + pregap

        if index == 0:
            index = 0 if is_pregap else 1

        sub = bytearray(96)

        # P
        if is_pregap:
            sub[:12] = b'\xFF' * 12

        # Q
        q = bytearray(12)

        q[0] = (flags << 4) + 1
        q[1] = track_sequence
        q[2] = index

        if is_pregap:
            relative = pregap + track_start - sector
        else:
            relative = sector - track_start

        sector += 150

        min, sec = divmod(relative, 60*75)
        sec, frame = divmod(sec, 75)

        amin, asec = divmod(sector, 60*75)
        asec, aframe = divmod(asec, 75)

        q[3], q[4], q[5] = min, sec, frame
        q[7], q[8], q[9] = amin, asec, aframe

        for i in range(1, 10):
            q[i] = ((q[i] // 10) << 4) + (q[i] % 10)

        crc = CRC16CCITTContext.calculate(q[:10])
        q[10:12] = crc.to_bytes(2, byteorder='big')

        sub[12:24] = q

        return Subchannel.interleave(sub)
