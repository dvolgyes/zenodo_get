"""Checksum verification."""

import hashlib
from pathlib import Path


def check_hash(filename: str, checksum: str) -> tuple[str, str]:
    """Verify file integrity by comparing its MD5 checksum."""
    value = checksum.strip()
    if not Path(filename).exists():
        return value, "invalid"
    digest = hashlib.md5(usedforsecurity=False)
    with Path(filename).open("rb") as file_handle:
        for data in iter(lambda: file_handle.read(4096), b""):
            digest.update(data)
    return value, digest.hexdigest()
