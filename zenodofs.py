#!/usr/bin/env python3

from time import time
import json

from functools import lru_cache as cache
import logging
from stat import S_IFREG, S_IFDIR
import sys

try:
    import requests
    from box import SBox
    from fuse import FUSE, Operations, LoggingMixIn
except ImportError as e:
    logging.getLogger().critical(e)
    logging.getLogger().critical("You need to install python-box, requests and fusepy.")
    sys.exit(1)


class WebFile:

    def __init__(self, url, size, chunksize=64, largefile=1024):
        self.url = url
        self.r = None
        self.content = None
        if url is not None and size < (largefile * 1024):
            with requests.get(url, stream=False) as r:
                self.content = r.content
        self.chunksize = 64
        self.last_page = bytearray()
        self.last_offset = 0
        self.iterator = None

    def reset(self):
        self.last_offset = 0
        self.r = requests.get(self.url, stream=True)
        self.iterator = self.r.iter_content(chunk_size=self.chunksize * 1024)

    def close(self):
        self.last_offset = 0
        self.last_page = bytearray()
        self.r = None
        self.iterator = None

    def read_next(self):
        try:
            if self.iterator is None:
                self.reset()
            self.last_offset += len(self.last_page)
            self.last_page = next(self.iterator)
            return self.last_page

        except StopIteration:
            return bytearray()

    def __getitem__(self, domain):
        if self.content is not None:
            return self.content[domain]

        if domain.start > domain.stop:
            return bytes()

        response = bytes()

        if self.last_offset > domain.start:
            self.reset()

        if self.last_offset <= domain.start + len(self.last_page):
            while self.last_offset + len(self.last_page) <= domain.start:
                chunk = self.read_next()
                if len(chunk) == 0:
                    break

            L = self.last_offset + len(self.last_page)
            end = max(min(domain.stop, L) - self.last_offset, 0)

            if end <= 0:
                return bytes()

            start = domain.start - self.last_offset
            response = response + self.last_page[start:end]

            N = max(end - start, 0)

            if domain.start + N < domain.stop:
                response = response + self[domain.start + N : domain.stop]
        return response


class ZenodoFS(LoggingMixIn, Operations):

    def __init__(self, recordIDs, sandbox_recordIDs, chunksize=64, largefile=1024):
        self.records = {
            "sandbox": [],
            "zenodo": [],
        }
        self.attr_cache = SBox(default_box=True)
        self.dir_cache = SBox(default_box=True)
        self.open_files = {}
        self.content = {}
        self.chunksize = chunksize
        self.largefile = largefile
        self.logger = logging.getLogger()
        for rid in recordIDs:
            self.get_metadata(rid, sandbox=False)
        for rid in sandbox_recordIDs:
            self.get_metadata(rid, sandbox=True)

    @cache(maxsize=1024)
    def get_metadata(self, recordID, sandbox=False, exceptions=True, timeout=15):
        if not sandbox:
            url = "https://zenodo.org/api/records/"
        else:
            url = "https://sandbox.zenodo.org/api/records/"

        try:
            r = requests.get(url + recordID, timeout=timeout)
        except requests.exceptions.ConnectTimeout:
            self.logger.critical("Connection timeout during metadata reading.")
            raise
        except Exception:
            self.logger.critical("Connection error during metadata reading.")
            raise

        js = {}
        if r.ok:
            js = json.loads(r.text)["files"]
            for f in json.loads(r.text)["files"]:
                path = "zenodo" if not sandbox else "sandbox"
                self.attr_cache[f'/{path}/{recordID}/{f["key"]}'] = SBox(
                    f, default_box=True
                )

            self.content[f"/{path}/{recordID}.json"] = (
                SBox(metadata=js).to_json() + "\n"
            ).encode()
            self.content[f"/{path}/{recordID}.yaml"] = (
                SBox(metadata=js).to_yaml().encode()
            )
        return js

    def readdir(self, path, fh):
        level = len(path.split("/"))
        content = [name for name in self.attr_cache.keys() if name.startswith(path)]
        if path == "/":
            return [".", "sandbox", "zenodo"]

        elif path in ("/sandbox", "/zenodo"):
            content = [name for name in self.attr_cache.keys() if name.startswith(path)]
        else:
            parts = path.split("/")
            if len(parts) >= 3:
                recordID = parts[2]
                self.get_metadata(recordID)
                content = [
                    name for name in self.attr_cache.keys() if name.startswith(path)
                ]

        N = len(path) + 1
        content = list(
            {
                name[N:].split("/")[0]
                for name in content
                if len(name) > N and name[N - 1] == "/"
            }
        )
        if level == 2:
            content = (
                content
                + [f"{name}.yaml" for name in content if name.find(".") == -1]
                + [f"{name}.json" for name in content if name.find(".") == -1]
            )
        return list(set(content))

    def getattr(self, path, fh=None):
        parts = path.split("/")
        level = len(parts)
        st = {}
        if path in ["/", "/sandbox", "/zenodo"]:
            st["st_mode"] = S_IFDIR | 0o755
            st["st_nlink"] = 2
        elif level == 3:
            if path.find(".") > -1:
                size = len(self.content[path])
                st = {"st_mode": (S_IFREG | 0o444), "st_size": size}
            else:
                st["st_mode"] = S_IFDIR | 0o755
                st["st_nlink"] = 2
        else:
            size = 0
            st = {"st_mode": (S_IFREG | 0o444), "st_size": size}
            if level >= 3:
                recordID = parts[2]
                self.get_metadata(recordID)

            if level == 4:
                fn = self.attr_cache[path]
                if "size" in fn:
                    st["st_size"] = fn["size"]
        st["st_ctime"] = st["st_mtime"] = st["st_atime"] = time()
        return st

    def open(self, path, mode):
        if path not in self.open_files:
            url = self.attr_cache[path]["links"].get("self")
            size = self.attr_cache[path].get("size", 0)
            self.open_files[path] = WebFile(url, size, self.chunksize, self.largefile)
        return 0

    def read(self, path, size, offset, fh):
        if path in self.content:
            return self.content[path][offset : offset + size]

        return self.open_files[path][offset : offset + size]

    def release(self, path, fh):
        if path in self.open_files:
            wf = self.open_files.pop(path)
            wf.close()


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint", type=str, help="mount point")
    parser.add_argument(
        "-r", "--record", nargs="+", action="extend", default=[], help="record ID(s)"
    )
    parser.add_argument(
        "-s",
        "--sandbox",
        nargs="+",
        action="extend",
        default=[],
        help="sandbox record ID(s)",
    )
    parser.add_argument(
        "-c",
        "--chunk_size",
        type=int,
        default=64,
        help="chunk size [KB] for network download (default: 64)",
    )
    parser.add_argument(
        "-l",
        "--large_file_limit",
        type=int,
        default=256,
        help="file size [KB] which is downloaded without splitting into chunks (default: 256)",
    )

    parser.add_argument(
        "-L",
        "--log_level",
        default="error",
        const="error",
        nargs="?",
        choices=["critical", "error", "warning", "info", "debug"],
        help="log level (default: error)",
    )

    parser.add_argument("-f", "--foreground", action="store_true", default=False)
    parser.add_argument("-d", "--debug", action="store_true", default=False)

    args = parser.parse_args()

    level = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }[args.log_level]

    logging.basicConfig(level=level)

    fuse = FUSE(
        ZenodoFS(
            args.record,
            args.sandbox,
            chunksize=args.chunk_size,
            largefile=args.large_file_limit,
        ),
        args.mountpoint,
        foreground=args.foreground,
        nothreads=True,
        debug=args.debug,
    )
