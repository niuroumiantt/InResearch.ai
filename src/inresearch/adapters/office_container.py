"""OLE compound container; independent of document interpretation."""
from __future__ import annotations
import struct


OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

FREE_SECTOR = 0xFFFFFFFF

END_OF_CHAIN = 0xFFFFFFFE

class OleFile:
    """Minimal reader for the streams inside a compound file.

    Implements only what is needed to pull one named stream out: the FAT, the
    mini FAT and the directory.  No writing, no storages beyond name lookup.
    """

    def __init__(self, raw: bytes):
        if not raw.startswith(OLE_MAGIC):
            raise ValueError('not an OLE2 compound file')
        self.raw = raw
        self.sector_size = 1 << struct.unpack_from('<H', raw, 0x1E)[0]
        self.mini_size = 1 << struct.unpack_from('<H', raw, 0x20)[0]
        self.cutoff = struct.unpack_from('<I', raw, 0x38)[0]
        first_dir = struct.unpack_from('<I', raw, 0x30)[0]
        first_mini_fat = struct.unpack_from('<I', raw, 0x3C)[0]
        self.fat = self._read_fat()
        self.dir_entries = self._read_directory(first_dir)
        self.mini_fat = self._read_chain_as_uints(first_mini_fat)
        self.mini_stream = self._read_mini_stream()

    def _sector(self, n: int) -> bytes:
        start = 512 + n * self.sector_size
        return self.raw[start:start + self.sector_size]

    def _difat(self) -> list[int]:
        """Sector numbers holding the FAT: 109 inline, the rest chained."""
        entries = list(struct.unpack_from('<109I', self.raw, 0x4C))
        nxt = struct.unpack_from('<I', self.raw, 0x44)[0]
        guard = 0
        while nxt not in (END_OF_CHAIN, FREE_SECTOR) and guard < 4096:
            block = self._sector(nxt)
            if len(block) < self.sector_size: break
            count = self.sector_size // 4 - 1
            entries.extend(struct.unpack_from('<%dI' % count, block, 0))
            nxt = struct.unpack_from('<I', block, self.sector_size - 4)[0]
            guard += 1
        return [e for e in entries if e not in (FREE_SECTOR, END_OF_CHAIN)]

    def _read_fat(self) -> list[int]:
        fat: list[int] = []
        per = self.sector_size // 4
        for sector in self._difat():
            block = self._sector(sector)
            if len(block) < self.sector_size: break
            fat.extend(struct.unpack_from('<%dI' % per, block, 0))
        return fat

    def _chain(self, start: int) -> list[int]:
        out, seen, cur = [], set(), start
        while cur not in (END_OF_CHAIN, FREE_SECTOR) and 0 <= cur < len(self.fat):
            if cur in seen: break            # a corrupt file can loop
            seen.add(cur); out.append(cur)
            cur = self.fat[cur]
        return out

    def _read_chain_bytes(self, start: int, size: int | None = None) -> bytes:
        data = b''.join(self._sector(s) for s in self._chain(start))
        return data if size is None else data[:size]

    def _read_chain_as_uints(self, start: int) -> list[int]:
        data = self._read_chain_bytes(start)
        return list(struct.unpack_from('<%dI' % (len(data) // 4), data, 0)) if data else []

    def _read_directory(self, first: int) -> list[dict]:
        data = self._read_chain_bytes(first)
        out = []
        for off in range(0, len(data) - 127, 128):
            name_len = struct.unpack_from('<H', data, off + 0x40)[0]
            if not 2 <= name_len <= 64: continue
            name = data[off:off + name_len - 2].decode('utf-16-le', 'ignore')
            out.append({
                'name': name,
                'type': data[off + 0x42],
                'start': struct.unpack_from('<I', data, off + 0x74)[0],
                'size': struct.unpack_from('<Q', data, off + 0x78)[0],
            })
        return out

    def _read_mini_stream(self) -> bytes:
        for e in self.dir_entries:
            if e['type'] == 5:               # root storage holds the mini stream
                return self._read_chain_bytes(e['start'], e['size'])
        return b''

    def _read_mini_chain(self, start: int, size: int) -> bytes:
        out, seen, cur = [], set(), start
        while cur not in (END_OF_CHAIN, FREE_SECTOR) and 0 <= cur < len(self.mini_fat):
            if cur in seen: break
            seen.add(cur)
            off = cur * self.mini_size
            out.append(self.mini_stream[off:off + self.mini_size])
            cur = self.mini_fat[cur]
        return b''.join(out)[:size]

    def stream(self, *names: str) -> bytes:
        """First stream matching any of `names`, empty if none is present."""
        wanted = {n.lower() for n in names}
        for e in self.dir_entries:
            if e['type'] == 2 and e['name'].lower() in wanted:
                if e['size'] < self.cutoff:
                    return self._read_mini_chain(e['start'], e['size'])
                return self._read_chain_bytes(e['start'], e['size'])
        return b''
