from .base import SpecialHandler
from .registry import HandlerRegistry


# register handlers in init to avoid circular imports
def register_all_handlers():
    """Register all handlers with the global registry"""
    # Format handlers
    from .bincue_handler import BinCueHandler
    from .ccd_handler import CloneCdHandler
    from .mdf_handler import MdFHandler

    registry.register_format_handler("bin_cue", BinCueHandler)
    registry.register_format_handler("ccd", CloneCdHandler)
    registry.register_format_handler("mdf", MdFHandler)

    # DAT group handlers
    from .datgroup_handlers import RedumpHandler, NoIntroHandler

    registry.register_dat_group_handler("redump", RedumpHandler)
    registry.register_dat_group_handler("no-intro", NoIntroHandler)

    # Platform handlers
    from .libcrypt_handler.libcrypt_handler import LibCryptHandler

    registry.register_platform_handler("psx", LibCryptHandler)

    # Special handlers (checked separately by processes)
    from .md5_handler import MD5ScanHandler

    registry.register_special_handler("md5_scan", MD5ScanHandler)

    from .chd_existence_handler import CHDExistenceHandler

    registry.register_special_handler("chd_existence", CHDExistenceHandler)


registry = HandlerRegistry()
register_all_handlers()

__all__ = ["SpecialHandler", "HandlerRegistry", "registry"]
