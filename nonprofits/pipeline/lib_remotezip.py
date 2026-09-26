"""Read members of a remote zip file with HTTP Range requests (no full download).

The IRS publishes 990 e-file XML in multi-GB zip files. zipfile only needs the
end-of-central-directory, the central directory, and each member's bytes, so a
seekable file-like object backed by Range requests lets us extract just the
returns we need. Every request has a timeout.
"""
import io, time, zipfile
import requests

class HttpFile(io.RawIOBase):
    def __init__(self, url, session=None, timeout=120, block=1 << 16):
        self.url, self.timeout = url, timeout
        self.s = session or requests.Session()
        r = self._req("HEAD")
        self.size = int(r.headers["Content-Length"])
        self.pos = 0
        self.block = block
        self._cache = {}  # (start) -> bytes, tiny LRU for small reads

    def _req(self, method, headers=None):
        for attempt in range(6):
            try:
                r = self.s.request(method, self.url, headers=headers or {}, timeout=self.timeout)
                if r.status_code in (200, 206):
                    return r
                raise IOError(f"HTTP {r.status_code}")
            except Exception as e:  # noqa
                if attempt == 5:
                    raise
                time.sleep(3 * (attempt + 1))

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        if whence == 0:
            self.pos = off
        elif whence == 1:
            self.pos += off
        else:
            self.pos = self.size + off
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        # serve small reads from a block cache
        if n <= self.block:
            bstart = self.pos
            blk = self._cache.get("blk")
            if blk and blk[0] <= self.pos and end < blk[0] + len(blk[1]):
                data = blk[1][self.pos - blk[0]: end - blk[0] + 1]
                self.pos = end + 1
                return data
            bend = min(bstart + self.block, self.size) - 1
            r = self._req("GET", {"Range": f"bytes={bstart}-{bend}"})
            self._cache["blk"] = (bstart, r.content)
            data = r.content[: end - bstart + 1]
            self.pos = end + 1
            return data
        r = self._req("GET", {"Range": f"bytes={self.pos}-{end}"})
        data = r.content
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def open_remote_zip(url, session=None):
    return zipfile.ZipFile(HttpFile(url, session=session))


def read_member(z, name):
    """Read a member, handling Deflate64 (method 9) via the inflate64 package."""
    info = z.getinfo(name)
    if info.compress_type != 9:
        return z.read(name)
    import struct
    import inflate64
    fp = z.fp
    fp.seek(info.header_offset)
    h = fp.read(30)
    n, m = struct.unpack("<HH", h[26:30])
    fp.seek(info.header_offset + 30 + n + m)
    raw = fp.read(info.compress_size)
    return inflate64.Inflater().inflate(raw)
