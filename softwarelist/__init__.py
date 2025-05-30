from softwarelist.softwarelist import SoftwareList
from softwarelist.software import Software
from softwarelist.comment import Comment
from softwarelist.part import Part
import importlib
import sys


__all__ = ["SoftwareList","Software","Part","Comment"]

__version__ = "0.1.0"

def reload_all():
    import softwarelist.comment
    import softwarelist.part
    import softwarelist.software
    import softwarelist
    """Force-reload all submodules for development and testing."""
    module_names = [
        "softwarelist.comment",
        "softwarelist.part",
        "softwarelist.software",
        "softwarelist",
    ]

    for name in module_names:
        if name in sys.modules:
            print(f"Reloading {name}...")
            importlib.reload(sys.modules[name])


