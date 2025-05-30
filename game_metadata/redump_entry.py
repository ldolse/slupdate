import re
import hashlib
from urllib.parse import urlparse
from utils import requests_retry_session
from typing import Optional


class RedumpEntry:
    def __init__(self, db, rtitle: str, href: str, region: str, system: str,
                 version: str, edition: str, languages: list[str],
                 serials: list[str], status: str,
                 localized_title: Optional[str] = None):
        self.db = db
        self.db_title = rtitle.strip()
        self.href = href
        self.region = region.strip() if region else ''
        self.system = system.strip()
        self.version = version.strip()
        self.edition = edition.strip()
        self.languages = [lang.strip() for lang in languages] if isinstance(languages, list) else []
        self.serials = serials or []
        self.status = status.strip()
        self.localized_title = localized_title.strip() if localized_title else None

        # Lazy-load data
        self._dat_name: str | None = None
        self._rom_list: list[dict] | None = None
        self._site_hash: tuple[str, str] | None = None

    @property
    def rom_list(self) -> list | None:
        if not self._rom_list:
            url = f"{self.href}sha1/"
            self._fetch_redump_data(url)
        return self._rom_list if self._rom_list else None

    @property
    def site_hash(self) -> Optional[tuple[str, str]]:
        if self._site_hash is not None:
            return self._site_hash
        
        # Fetch data only once
        if self._rom_list is None and self.rom_list is None:
            return None  # Fallback after failure

        self._site_hash = self._calculate_combined_hash()
        return self._site_hash

    @property
    def dat_name(self) -> str | None:
        """Lazy-load and cache the dat name from the rom_list file."""
        if not self._dat_name:
            url = f"{self.href}sha1/"
            self._fetch_redump_data(url)
        return self._dat_name if self._dat_name else None

    @property
    def imputed_dat_name(self):
        """Returns a title compatible with Redump DAT format."""
        lang_sub = {
            'English': 'En','Japanese': 'Ja', 'French': 'Fr', 'German': 'De',
            'Spanish': 'Es', 'Italian': 'It', 'Dutch': 'Nl', 'Portuguese': 'Pt',
            'Swedish': 'Sv', 'Norwegian': 'No', 'Danish': 'Da', 'Finnish': 'Fi',
            'Chinese': 'Zh','Korean': 'Ko', 'Polish': 'Pl', 'Russian': 'Ru', 
            'Arabic': 'Ar', 'Czech': 'Cs', 'Catalan': 'Ca', 'Slovak': 'Sk'
        }
        
        disc_pat = r'\s\(Disc\s\d+\)'
        disc_match = re.findall(disc_pat, self.db_title)
        disc_str = f' {disc_match[0]}' if disc_match else ''
        title_base = re.sub(disc_pat, '', self.db_title).strip()
        title_base = re.sub(r'\(Euro\)', '(Europe)', title_base)
        title_base = re.sub(r'[/:]', '-', title_base)

        lang_str = ""
        if len(self.languages) > 1:
            ordered_languages = sorted(
                (lang for lang in self.languages if lang in lang_sub),
                key=lambda l: list(lang_sub.values()).index(lang_sub[l])
            )
            lang_str = f' ({",".join([lang_sub[l] for l in ordered_languages])})'

        region_str = f" ({self.region})" if self.region else ""
        
        return f"{title_base}{region_str}{lang_str}{disc_str}"

    def __getstate__(self):
        state = self.__dict__.copy()
        if 'db' in state:  # Don't serialize parent DB
            del state['db']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.db = None  # Reset to avoid stale reference on load

    def _fetch_redump_data(self, file_url: str):
        """Fetch and parse the .sha1 file from redump.org."""
        # Check if network failure threshold has been reached
        if self.db and hasattr(self.db, 'network_failure') and self.db.network_failure:
            return  # Skip further attempts

        try:
            request_url = 'http://redump.org'+file_url
            response = requests_retry_session().get(request_url)
            if not response.ok:
                print(f"[Error] HTTP {response.status_code}: {request_url}")
                return None
        except Exception as e:
            print(f"[Error] Downloading {request_url}: {e}")
            if self.db and hasattr(self.db, 'report_fetch_failure'):
                self.db.report_fetch_failure()
            return None

        content = response.text.strip()
        header = response.headers.get('Content-Disposition')
        if header and 'filename=' in header:
            raw_filename = header.split("filename=")[1].strip('"\'')
            match = re.search(r'.*\.sha1', urlparse(raw_filename).path)
            self._dat_name = match.group(0) if match else None

        rom_list = []
        for line in content.splitlines():
            parts = re.search(r'([a-fA-F0-9]{40}) \*(.+)', line.strip())
            if not parts:
                continue
            sha1, name = parts.groups()
            rom_list.append({'@sha1': sha1.strip(), '@name': name.strip()})

        self._rom_list = rom_list

    def _calculate_combined_hash(self) -> Optional[tuple[str, str]]:
        """Calculate a combined hash from ROMs, excluding CUE/GDI."""
        if not self._rom_list:
            return None

        concatenated = ''.join(
            rom['@sha1'] for rom in self._rom_list
            if not (rom['@name'].endswith('.cue') or rom['@name'].endswith('.gdi'))
        )
        if not concatenated:
            return None

        sha1_hash = hashlib.sha1(concatenated.encode('utf-8')).hexdigest()
        return (sha1_hash, 'SHA1')



