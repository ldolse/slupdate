from typing import Dict, Type
from modules.ifilter import IFilter

class PluginRegister:
    _instance = None

    def __init__(self):
        self.media_images: Dict[str, Type[IFilter]] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_media_image(self, name: str, filter_class: Type[IFilter]):
        self.media_images[name.lower()] = filter_class

    def get_filter(self, path: str) -> IFilter:
        for filter_class in self.media_images.values():
            filter_instance = filter_class(path)
            if filter_instance.identify(path):
                return filter_instance
        return None
