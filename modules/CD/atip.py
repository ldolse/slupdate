import logging
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CDATIP:
    data_length: int = 0
    reserved1: int = 0
    reserved2: int = 0
    itwp: int = 0
    ddcd: bool = False
    reference_speed: int = 0
    always_zero: bool = False
    uru: bool = False
    reserved3: int = 0
    always_one: bool = False
    disc_type: bool = False
    disc_sub_type: int = 0
    a1_valid: bool = False
    a2_valid: bool = False
    a3_valid: bool = False
    reserved4: int = 0
    lead_in_start_min: int = 0
    lead_in_start_sec: int = 0
    lead_in_start_frame: int = 0
    reserved5: int = 0
    lead_out_start_min: int = 0
    lead_out_start_sec: int = 0
    lead_out_start_frame: int = 0
    reserved6: int = 0
    a1_values: List[int] = None
    a2_values: List[int] = None
    a3_values: List[int] = None
    reserved7: int = 0
    reserved8: int = 0
    reserved9: int = 0
    s4_values: List[int] = None
    reserved10: int = 0

class ATIP:
    MODULE_NAME = "CD ATIP decoder"

    @staticmethod
    def decode(cd_atip_response: bytes) -> Optional[CDATIP]:
        if not cd_atip_response or len(cd_atip_response) <= 4:
            return None

        decoded = CDATIP()

        if len(cd_atip_response) != 32 and len(cd_atip_response) != 28:
            logger.debug(f"Expected CD ATIP size 32 bytes is not received size {len(cd_atip_response)} bytes, not decoding")
            return None

        decoded.data_length = int.from_bytes(cd_atip_response[0:2], byteorder='big')
        decoded.reserved1 = cd_atip_response[2]
        decoded.reserved2 = cd_atip_response[3]
        decoded.itwp = (cd_atip_response[4] & 0xF0) >> 4
        decoded.ddcd = bool(cd_atip_response[4] & 0x08)
        decoded.reference_speed = cd_atip_response[4] & 0x07
        decoded.always_zero = bool(cd_atip_response[5] & 0x80)
        decoded.uru = bool(cd_atip_response[5] & 0x40)
        decoded.reserved3 = cd_atip_response[5] & 0x3F

        decoded.always_one = bool(cd_atip_response[6] & 0x80)
        decoded.disc_type = bool(cd_atip_response[6] & 0x40)
        decoded.disc_sub_type = (cd_atip_response[6] & 0x38) >> 3
        decoded.a1_valid = bool(cd_atip_response[6] & 0x04)
        decoded.a2_valid = bool(cd_atip_response[6] & 0x02)
        decoded.a3_valid = bool(cd_atip_response[6] & 0x01)

        decoded.reserved4 = cd_atip_response[7]
        decoded.lead_in_start_min = cd_atip_response[8]
        decoded.lead_in_start_sec = cd_atip_response[9]
        decoded.lead_in_start_frame = cd_atip_response[10]
        decoded.reserved5 = cd_atip_response[11]
        decoded.lead_out_start_min = cd_atip_response[12]
        decoded.lead_out_start_sec = cd_atip_response[13]
        decoded.lead_out_start_frame = cd_atip_response[14]
        decoded.reserved6 = cd_atip_response[15]

        decoded.a1_values = list(cd_atip_response[16:19])
        decoded.a2_values = list(cd_atip_response[20:23])
        decoded.a3_values = list(cd_atip_response[24:27])

        decoded.reserved7 = cd_atip_response[19]
        decoded.reserved8 = cd_atip_response[23]
        decoded.reserved9 = cd_atip_response[27]

        if len(cd_atip_response) < 32:
            return decoded if decoded.always_one else None

        decoded.s4_values = list(cd_atip_response[28:31])
        decoded.reserved10 = cd_atip_response[31]

        return decoded if decoded.always_one else None

    @staticmethod
    def prettify(response: Optional[CDATIP]) -> Optional[str]:
        if response is None:
            return None

        output = []

        if response.ddcd:
            output.append(f"Indicative Target Writing Power: {response.itwp}")
            output.append("Disc is DDCD-RW" if response.disc_type else "Disc is DDCD-R")

            if response.reference_speed == 2:
                output.append("Reference speed is 4x")
            elif response.reference_speed == 3:
                output.append("Reference speed is 8x")
            else:
                output.append(f"Reference speed set is unknown: {response.reference_speed}")

            output.append(f"ATIP Start time of Lead-in: {(response.lead_in_start_min << 16) + (response.lead_in_start_sec << 8) + response.lead_in_start_frame}")
            output.append(f"ATIP Last possible start time of Lead-out: {(response.lead_out_start_min << 16) + (response.lead_out_start_sec << 8) + response.lead_out_start_frame}")
            
            if response.s4_values:
                output.append(f"S4 value: {(response.s4_values[0] << 16) + (response.s4_values[1] << 8) + response.s4_values[2]}")
        else:
            output.append(f"Indicative Target Writing Power: {response.itwp & 0x07}")

            if response.disc_type:
                disc_subtypes = [
                    "CD-RW", "High-Speed CD-RW", "Ultra-Speed CD-RW", "Ultra-Speed Plus CD-RW",
                    "Medium type B low beta category CD-RW", "Medium type B high beta category CD-RW",
                    "Medium type C low beta category CD-RW", "Medium type C high beta category CD-RW"
                ]
                if response.disc_sub_type < len(disc_subtypes):
                    output.append(f"Disc is {disc_subtypes[response.disc_sub_type]}")
                else:
                    output.append(f"Unknown CD-RW disc subtype: {response.disc_sub_type}")

                if response.reference_speed == 1:
                    output.append("Reference speed is 2x")
                else:
                    output.append(f"Reference speed set is unknown: {response.reference_speed}")
            else:
                output.append("Disc is CD-R")
                disc_subtypes = [
                    "Normal speed CLV CD-R", "High speed CAV CD-R",
                    "Medium type A low beta category CD-R", "Medium type A high beta category CD-R",
                    "Medium type B low beta category CD-R", "Medium type B high beta category CD-R",
                    "Medium type C low beta category CD-R", "Medium type C high beta category CD-R"
                ]
                if response.disc_sub_type < len(disc_subtypes):
                    output.append(f"Disc is {disc_subtypes[response.disc_sub_type]}")
                else:
                    output.append(f"Unknown CD-R disc subtype: {response.disc_sub_type}")

            output.append("Disc use is unrestricted" if response.uru else "Disc use is restricted")

            output.append(f"ATIP Start time of Lead-in: {response.lead_in_start_min}:{response.lead_in_start_sec}:{response.lead_in_start_frame}")
            output.append(f"ATIP Last possible start time of Lead-out: {response.lead_out_start_min}:{response.lead_out_start_sec}:{response.lead_out_start_frame}")

            if response.a1_valid:
                output.append(f"A1 value: {(response.a1_values[0] << 16) + (response.a1_values[1] << 8) + response.a1_values[2]}")
            if response.a2_valid:
                output.append(f"A2 value: {(response.a2_values[0] << 16) + (response.a2_values[1] << 8) + response.a2_values[2]}")
            if response.a3_valid:
                output.append(f"A3 value: {(response.a3_values[0] << 16) + (response.a3_values[1] << 8) + response.a3_values[2]}")
            if response.s4_values:
                output.append(f"S4 value: {(response.s4_values[0] << 16) + (response.s4_values[1] << 8) + response.s4_values[2]}")

        if response.lead_in_start_min == 97:
            type_ = response.lead_in_start_frame % 10
            frm = response.lead_in_start_frame - type_

            if response.disc_type:
                output.append("Disc uses phase change")
            else:
                output.append("Disc uses long strategy type dye (Cyanine, AZO, etc.)" if type_ < 5 else "Disc uses short strategy type dye (Phthalocyanine, etc.)")

            manufacturer = ATIP.manufacturer_from_atip(response.lead_in_start_sec, frm)
            if manufacturer:
                output.append(f"Disc manufactured by {manufacturer}")

        return "\n".join(output)

    @staticmethod
    def prettify_bytes(cd_atip_response: bytes) -> Optional[str]:
        decoded = ATIP.decode(cd_atip_response)
        return ATIP.prettify(decoded)

    @staticmethod
    def manufacturer_from_atip(sec: int, frm: int) -> str:
        if sec == 10:
            if frm == 0:
                return "Ritek Co."
        elif sec == 15:
            if frm == 0:
                return "TDK Corporation"
            elif frm == 10:
                return "Ritek Co."
            elif frm == 20:
                return "Mitsubishi Chemical Corporation"
            elif frm == 30:
                return "NAN-YA Plastics Corporation"
        elif sec == 16:
            if frm == 20:
                return "Shenzen SG&Gast Digital Optical Discs"
            elif frm == 30:
                return "Grand Advance Technology Ltd."
        elif sec == 17:
            if frm == 0:
                return "Moser Baer India Ltd."
        elif sec == 18:
            if frm == 10:
                return "Wealth Fair Investment Ltd."
            elif frm == 60:
                return "Taroko International Co. Ltd."
        elif sec == 20:
            if frm == 10:
                return "CDA Datenträger Albrechts GmbH"
        elif sec == 21:
            if frm == 10:
                return "Grupo Condor S.L."
            elif frm == 20:
                return "E-TOP Mediatek Inc."
            elif frm == 30:
                return "Bestdisc Technology Corporation"
            elif frm == 40:
                return "Optical Disc Manufacturing Equipment"
            elif frm == 50:
                return "Sound Sound Multi-Media Development Ltd."
        elif sec == 22:
            if frm == 0:
                return "Woongjin Media Corp."
            elif frm == 10:
                return "Seantram Technology Inc."
            elif frm == 20:
                return "Advanced Digital Media"
            elif frm == 30:
                return "EXIMPO"
            elif frm == 40:
                return "CIS Technology Inc."
            elif frm == 50:
                return "Hong Kong Digital Technology Co., Ltd."
            elif frm == 60:
                return "Acer Media Technology, Inc."
        elif sec == 23:
            if frm == 0:
                return "Matsushita Electric Industrial Co., Ltd."
            elif frm == 10:
                return "Doremi Media Co., Ltd."
            elif frm == 20:
                return "Nacar Media s.r.l."
            elif frm == 30:
                return "Audio Distributors Co., Ltd."
            elif frm == 40:
                return "Victor Company of Japan, Ltd."
            elif frm == 50:
                return "Optrom Inc."
            elif frm == 60:
                return "Customer Pressing Oosterhout"
        elif sec == 24:
            if frm == 0:
                return "Taiyo Yuden Company Ltd."
            elif frm == 10:
                return "SONY Corporation"
            elif frm == 20:
                return "Computer Support Italy s.r.l."
            elif frm == 30:
                return "Unitech Japan Inc."
            elif frm == 40:
                return "kdg mediatech AG"
            elif frm == 50:
                return "Guann Yinn Co., Ltd."
            elif frm == 60:
                return "Harmonic Hall Optical Disc Ltd."
        elif sec == 25:
            if frm == 0:
                return "MPO"
            elif frm == 20:
                return "Hitachi Maxell, Ltd."
            elif frm == 30:
                return "Infodisc Technology Co. Ltd."
            elif frm == 40:
                return "Vivastar AG"
            elif frm == 50:
                return "AMS Technology Inc."
            elif frm == 60:
                return "Xcitec Inc."
        elif sec == 26:
            if frm == 0:
                return "Fornet International Pte Ltd."
            elif frm == 10:
                return "POSTECH Corporation"
            elif frm == 20:
                return "SKC Co., Ltd."
            elif frm == 30:
                return "Optical Disc Corporation"
            elif frm == 40:
                return "FUJI Photo Film Co., Ltd."
            elif frm == 50:
                return "Lead Data Inc."
            elif frm == 60:
                return "CMC Magnetics Corporation"
        elif sec == 27:
            if frm == 0:
                return "Digital Storage Technology Co., Ltd."
            elif frm == 10:
                return "Plasmon Data systems Ltd."
            elif frm == 20:
                return "Princo Corporation"
            elif frm == 30:
                return "Pioneer Video Corporation"
            elif frm == 40:
                return "Kodak Japan Ltd."
            elif frm == 50:
                return "Mitsui Chemicals, Inc."
            elif frm == 60:
                return "Ricoh Company Ltd."
        elif sec == 28:
            if frm == 0:
                return "Opti.Me.S. S.p.A."
            elif frm == 10:
                return "Gigastore Corporation"
            elif frm == 20:
                return "Multi Media Masters & Machinary SA"
            elif frm == 30:
                return "Auvistar Industry Co., Ltd."
            elif frm == 40:
                return "King Pro Mediatek Inc."
            elif frm == 50:
                return "Delphi Technology Inc."
            elif frm == 60:
                return "Friendly CD-Tek Co."
        elif sec == 29:
            if frm == 0:
                return "Taeil Media Co., Ltd."
            elif frm == 10:
                return "Vanguard Disc Inc."
            elif frm == 20:
                return "Unidisc Technology Co., Ltd."
            elif frm == 30:
                return "Hile Optical Disc Technology Corp."
            elif frm == 40:
                return "Viva Magnetics Ltd."
            elif frm == 50:
                return "General Magnetics Ltd."
        elif sec == 30:
            if frm == 10:
                return "CDA Datenträger Albrechts GmbH"
        elif sec == 31:
            if frm == 0:
                return "Ritek Co."
            elif frm == 30:
                return "Grand Advance Technology Ltd."
        elif sec == 32:
            if frm == 0:
                return "TDK Corporation"
            elif frm == 10:
                return "Prodisc Technology Inc."
        elif sec == 34:
            if frm in (20, 22):
                return "Mitsubishi Chemical Corporation"
        elif sec == 36:
            if frm == 0:
                return "Gish International Co., Ltd."
        elif sec == 42:
            if frm == 20:
                return "Advanced Digital Media"
        elif sec == 45:
            if frm == 0:
                return "Fornet International Pte Ltd."
            elif frm == 10:
                return "Unitech Japan Inc."
            elif frm == 20:
                return "Acer Media Technology, Inc."
            elif frm == 40:
                return "CIS Technology Inc."
            elif frm == 50:
                return "Guann Yinn Co., Ltd."
            elif frm == 60:
                return "Xcitec Inc."
        elif sec == 46:
            if frm == 0:
                return "Taiyo Yuden Company Ltd."
            elif frm == 10:
                return "Hong Kong Digital Technology Co., Ltd."
            elif frm == 20:
                return "Multi Media Masters & Machinary SA"
            elif frm == 30:
                return "Computer Support Italy s.r.l."
            elif frm == 40:
                return "FUJI Photo Film Co., Ltd."
            elif frm == 50:
                return "Auvistar Industry Co., Ltd."
            elif frm == 60:
                return "CMC Magnetics Corporation"
        elif sec == 47:
            if frm == 10:
                return "Hitachi Maxell, Ltd."
            elif frm == 20:
                return "Princo Corporation"
            elif frm == 40:
                return "POSTECH Corporation"
            elif frm == 50:
                return "Ritek Co."
            elif frm == 60:
                return "Prodisc Technology Inc."
        elif sec == 48:
            if frm == 0:
                return "Ricoh Company Ltd."
            elif frm == 10:
                return "Kodak Japan Ltd."
            elif frm == 20:
                return "Plasmon Data systems Ltd."
            elif frm == 30:
                return "Pioneer Video Corporation"
            elif frm == 40:
                return "Digital Storage Technology Co., Ltd."
            elif frm == 50:
                return "Mitsui Chemicals, Inc."
            elif frm == 60:
                return "Lead Data Inc."
        elif sec == 49:
            if frm == 0:
                return "TDK Corporation"
            elif frm == 10:
                return "Gigastore Corporation"
            elif frm == 20:
                return "King Pro Mediatek Inc."
            elif frm == 30:
                return "Opti.Me.S. S.p.A."
            elif frm == 40:
                return "Victor Company of Japan, Ltd."
            elif frm == 60:
                return "Matsushita Electric Industrial Co., Ltd."
        elif sec == 50:
            if frm == 10:
                return "Vanguard Disc Inc."
            elif frm == 20:
                return "Mitsubishi Chemical Corporation"
            elif frm == 30:
                return "CDA Datenträger Albrechts GmbH"
        elif sec == 51:
            if frm == 10:
                return "Grand Advance Technology Ltd."
            elif frm == 20:
                return "Infodisc Technology Co. Ltd."
            elif frm == 50:
                return "Hile Optical Disc Technology Corp."
        return ""
