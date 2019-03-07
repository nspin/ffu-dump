import uuid
from collections import namedtuple

from fmt import make_struct

GPT = namedtuple('GPT', ['header', 'entries'])

class GPTHeader(make_struct('GPTHeader', [
    ('signature', '8s'),
    ('revision', '4s'),
    ('header_size', 'L'),
    ('crc32', 'L'),
    (None, '4s'),
    ('current_lba', 'Q'),
    ('backup_lba', 'Q'),
    ('first_usable_lba', 'Q'),
    ('last_usable_lba', 'Q'),
    ('disk_guid', '16s'),
    ('part_entry_start_lba', 'Q'),
    ('num_part_entries', 'L'),
    ('part_entry_size', 'L'),
    ('crc32_part_array', 'L'),
    ])):

    def _after(self, f):
        if self.signature != b'EFI PART':
            raise Exception('bad signature:', self.signature)
        if self.revision != b'\x00\x00\x01\x00':
            raise Exception('bad revision:', self.revision)
        if self.header_size < 92:
            raise Exception('bad header size:', self.header_size)
        return self._replace(
            disk_guid=uuid.UUID(bytes_le=self.disk_guid),
        )

class GPTEntry(make_struct('GPTEntry', [
    ('type', '16s'),
    ('unique', '16s'),
    ('first_lba', 'Q'),
    ('last_lba', 'Q'),
    ('flags', 'Q'),
    ('name', '72s'),
    ])):

    def _after(self, f):
        if self.type != 16*b'\x00':
            return self._replace(
                type=str(uuid.UUID(bytes_le=self.type)),
                unique=str(uuid.UUID(bytes_le=self.unique)),
                name=self.name.decode('utf-16').split('\0', 1)[0],
                )

def parse_gpt(f, lba_size=512):
    start = f.tell()
    header = GPTHeader._read(f)
    f.seek(start + header.part_entry_start_lba * lba_size)
    entries = []
    for _ in range(header.num_part_entries):
        pos = f.tell()
        entry = GPTEntry._read(f)
        f.seek(pos + header.part_entry_size)
        entries.append(entry)
    return GPT(header, entries)
