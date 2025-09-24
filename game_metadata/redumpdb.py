
import time
from bs4 import BeautifulSoup
from game_metadata.redump_entry import RedumpEntry
from datetime import datetime, timedelta
from utils import requests_retry_session
from collections import defaultdict
from typing import Optional, Any



redump__platform_paths = {
    'jaguar': 'ajcd',
    'cdtv': 'cdtv',
    'cd32': 'cd32',
    'fmtowns_cd': 'fmt',
    'ibm5170_cdrom': 'pc',
    'pcecd': 'pce',
    'cdi': 'cdi',
    'pippin': 'pippin',
    'pcfx': 'pc-fx',
    'segacd': 'mcd',
    'megacd': 'mcd',
    'megacdj': 'mcd',
    'saturn': 'ss',
    'dc': 'dc',
    'neocd': 'ngcd',
    'psx': 'psx',
    '3do_m2': '3do',
    'psx_libcrypt': 'psx/libcrypt/2'
}

class RedumpDB:
    MAX_FAILURE_THRESHOLD = 3
    def __init__(self, platform):
        self.platform = platform.lower()
        self.failure_count = 0
        self.base_url = "http://redump.org/discs/system/"
        self.last_fetched: datetime | None = None
        self.entries_by_url: dict[str, RedumpEntry] = {}

        # lazy load these lookup tables
        self._entries_by_serial: defaultdict[str, list[RedumpEntry]] = defaultdict(list)
        self._entries_by_name: defaultdict[str, list[RedumpEntry]] = defaultdict(list)
        self._entries_by_region: defaultdict[str, list[RedumpEntry]] = defaultdict(list)
        self._entries_by_language: defaultdict[str, list[RedumpEntry]] = defaultdict(list)

    @property
    def is_stale(self, days=30) -> bool:
        """Check if the database should be re-fetched."""
        return not self.last_fetched or (datetime.now() - self.last_fetched) > timedelta(days=days)

    @property
    def entries_by_serial(self) -> defaultdict[str,list[RedumpEntry]]:
        if not self._entries_by_serial:
            for entry in self.entries_by_url.values():
                for serial in entry.serials:
                    self._entries_by_serial[serial].append(entry)
        return self._entries_by_serial

    @property
    def entries_by_name(self) -> defaultdict[str,list[RedumpEntry]]:
        if not self._entries_by_name:
            for entry in self.entries_by_url.values():
                self._entries_by_name[entry.db_title].append(entry)
        return self._entries_by_name

    @property
    def entries_by_region(self) -> defaultdict[str,list[RedumpEntry]]:
        if not self._entries_by_region:
            for entry in self.entries_by_url.values():
                region = entry.region
                if isinstance(region, str):
                    self._entries_by_region[region].append(entry)
        return self._entries_by_region

    @property
    def entries_by_language(self) -> defaultdict[str,list[RedumpEntry]]:
        if not self._entries_by_language:
            for entry in self.entries_by_url.values():
                for lang in entry.languages:
                    if isinstance(lang, str):
                        self._entries_by_language[lang].append(entry)
        return self._entries_by_language

    @property
    def network_failure(self) -> bool:
        """Indicates whether the global failure threshold has been exceeded."""
        return self.failure_count >= self.MAX_FAILURE_THRESHOLD

    def report_fetch_failure(self):
        """Increment the network failure counter."""
        self.failure_count += 1

    def __setstate__(self, state):
        """reset the network failure counter on load"""
        self.__dict__.update(state)
        self.failure_count = 0

    def fetch_all(self):
        """Fetch and parse all pages for the given platform with incremental updates."""
        if self.is_stale or not self.entries_by_url:
            print(f"Scraping {self.platform} Redump DB...")
            first_page = self._fetch_page(1)
            if not first_page:
                return
            max_page = self._get_max_pages(first_page)

            new_entries_by_url: dict[str, RedumpEntry] = {}
            for page in range(1, max_page + 1):
                soup = self._fetch_page(page)
                if soup:
                    entries = self._parse_table(soup)
                    new_entries_by_url.update(entries)

            # Add or replace modified entries
            for href, new_entry in new_entries_by_url.items():
                existing_entry = self.entries_by_url.get(href)
                if not existing_entry:
                    # New entry - add it
                    self.entries_by_url[href] = new_entry
                else:
                    # Check if core data has changed
                    is_modified = any(
                        getattr(existing_entry, field) != getattr(new_entry, field)
                        for field in [
                            'db_title', 'region', 'system',
                            'version', 'edition', 'languages',
                            'serials', 'status'
                        ]
                    )
                    if is_modified:
                        # Replace modified entry - this clears lazy data
                        self.entries_by_url[href] = new_entry

            # Remove entries that no longer exist in the new set
            current_hrefs = set(self.entries_by_url.keys())
            new_hrefs = set(new_entries_by_url.keys())
            for href in current_hrefs - new_hrefs:
                del self.entries_by_url[href]

            # Clear lazy-loaded lookup tables to rebuild on next access
            self._entries_by_serial.clear()
            self._entries_by_name.clear()
            self._entries_by_region.clear()
            self._entries_by_language.clear()

            self.last_fetched = datetime.now()


    def _fetch_page(self, page_num: int) -> BeautifulSoup | None:
        """Fetches a specific page and returns its BeautifulSoup object."""
        path_part = redump__platform_paths[self.platform]
        url = f"{self.base_url}{path_part}/?page={page_num}"
        time.sleep(3)  # Rate-limiting

        try:
            response = requests_retry_session().get(url, timeout=5)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'lxml')
        except Exception as e:
            print(f"[Error] Could not fetch {url}: {e}")
            self.report_fetch_failure()
            return None

    def _get_max_pages(self, soup: BeautifulSoup) -> int:
        """Returns the number of pages for this platform."""
        pages_div = soup.find('div', class_='pages')
        if pages_div:
            links = pages_div.find_all('a')
            page_numbers = [int(tag.text.strip()) for tag in links if tag.text.isdigit()]
            return max(page_numbers)
        else:
            return 1

    def _parse_table(self, soup: BeautifulSoup) -> dict[str, RedumpEntry]:
        """Parses the table on a single page and returns entries as {href: RedumpEntry}."""
        table = soup.find('table', class_='games')
        if not table:
            return {}

        parsed_entries = {}
        for row in table.find_all('tr')[1:]:
            entry = self._parse_row(row)
            if entry.href not in parsed_entries:
                parsed_entries[entry.href] = entry
            else:
                print(f"Warning: Duplicate Entry for {entry.db_title}, url {entry.href}")

        return parsed_entries

    def _parse_row(self, row):
        """Parses a single game entry from the HTML row."""
        cols = row.find_all('td')

        region_cell = cols[0]
        title_cell = cols[1]
        system_cell = cols[2]
        version_cell = cols[3]
        edition_cell = cols[4]
        languages_cell = cols[5]
        serial_cell = cols[6]
        status_cell = cols[7]

        # Extract region
        region_img = region_cell.find('img')
        region = region_img['alt'].strip() if region_img and 'alt' in region_img.attrs else ''

        # Parse title and href
        title_link = title_cell.find('a')
        href = title_link.get('href') if title_link else ''
        rtitle, localized_title = self._parse_title(title_cell)

        system = system_cell.text.strip()
        version = version_cell.text.strip()
        edition = edition_cell.text.strip()

        # Languages
        langs = [img['alt'].strip() for img in languages_cell.find_all('img')] if languages_cell else []

        # Serials
        rawserial = serial_cell.get('title') or ''
        if not rawserial and len(cols[6].text.strip()) > 0:
            rawserial = cols[6].text.strip()
        serials = [s.strip() for s in rawserial.split(',')] if ',' in rawserial else [rawserial]

        # Status
        status_img = status_cell.find('img')
        if not status_img or 'alt' not in status_img.attrs:
            status = 'Unknown'
        else:
            alt_text = status_img['alt'].strip()
            if alt_text == 'Dumped from original media':
                status = 'single'
            elif alt_text == '2 and more dumps from original media [!]':
                status = 'verified'
            else:
                status = alt_text

        return RedumpEntry(
            db=self,
            rtitle=rtitle,
            href=href.strip(),
            region=region,
            system=system,
            version=version,
            edition=edition,
            languages=langs,
            serials=serials,
            status=status,
            localized_title=localized_title
        )

    def _parse_title(self, title_cell):
        """Parses the game title and localized name from a cell."""
        br_tag = title_cell.find('br')
        if br_tag:
            first_part = br_tag.previous_sibling.strip()
            next_sibling = br_tag.next_sibling
            localized_title = next_sibling.text.strip() if next_sibling else None
            rtitle_lines = first_part.split('\n')
            return (rtitle_lines[0], localized_title)
        else:
            title_text = title_cell.get_text(strip=True).split('\n')[0]
            return (title_text, None)

    def query_entries(
        self,
        filter_type: str = 'url',
        keys: Optional[list[Any]] = None
    ) -> list[RedumpEntry]:
        """
        Query entries by type (serial, name, region, language) or URL.
        Returns a list of RedumpEntry objects with failure tracking.
        """
        if not keys:
            return []

        # Map filter_type to the appropriate dictionary
        lookup_dict: dict[Any, list[RedumpEntry]] = {
            'serial': self.entries_by_serial,
            'name': self.entries_by_name,
            'region': self.entries_by_region,
            'language': self.entries_by_language,
            'url': self.entries_by_url
        }

        target_dict = lookup_dict.get(filter_type, self.entries_by_url)

        for key in keys:
            entries: list[RedumpEntry] = []
            if filter_type == 'serial' or filter_type == 'name':
                entry = target_dict.get(key)  # type: ignore
                entries.append(entry) if entry else None
            elif filter_type == 'region' or filter_type == 'language':
                entries = [e for e in target_dict.get(key, []) if isinstance(e, RedumpEntry)]
            else:
                # URL case
                if key in self.entries_by_url:
                    entries.append(self.entries_by_url[key])

        return entries

    def safe_iterate(self, entries):
        """Yields RedumpEntry objects until failure threshold is reached."""
        entries = list(entries)
        for entry in entries:
            if self.network_failure:
                print("[Warning] Too many failures. Stopping iteration.")
                break
            yield entry

    def iterate_entries(self, filter_type='url', keys=None):
        """Safe iterator that respects failure thresholds."""
        return self.safe_iterate(
            getattr(self, f"query_entries(filter_type='{filter_type}', keys={keys})")
        )

    def refresh_entry_db_references(self):
        """Re-link all entries to this database instance."""
        for entry in self.entries_by_url.values():
            if not hasattr(entry, 'db'):
                continue  # Skip manually created or external entries
            entry.db = self