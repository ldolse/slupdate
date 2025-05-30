from .logiqx_dat import LogiqxDAT

class Disk:
    def __init__(self, name: str, sha1: str):
        self.name = name
        self.sha1 = sha1.lower()

    def __repr__(self):
        return f"<Disk '{self.name}' (SHA-1: {self.sha1})>"


class MachineEntry:
    def __init__(self, name: str, category: str, description: str, disk=None):
        self.name = name
        self.category = category
        self.description = description
        self.disk = disk  # CHD file

    def __repr__(self):
        if self.disk is None:
            return f"<Machine '{self.name}' (Category: {self.category} | No Disk)>"
        else:
            return f"<Machine '{self.name}' (Category: {self.category} | Disk: {self.disk})>"


class MameDat(LogiqxDAT):
    def __init__(self):
        super().__init__()
        self.machines = []
        
    def _parse_machines(self, root_element):
        """Parse <machine> elements with single <disk>s"""
        machines = []
        for machine_elem in root_element.findall('.//machine'):
            name = machine_elem.get('name', '').strip()
            
            category = machine_elem.findtext('category', default=None)
            description = machine_elem.findtext('description', default=None)
            
            disk_elem = machine_elem.find('disk')
            if disk_elem is not None:
                disk = Disk(
                    name=disk_elem.attrib['name'],
                    sha1=disk_elem.attrib.get('sha1', '')
                )
            else:
                disk = None
                
            machines.append(MachineEntry(name, category, description, disk))
        self.machines = machines
    
    # Override the placeholder method from base class
    def _custom_parse(self, root_element):
        self._parse_games(root_element)
