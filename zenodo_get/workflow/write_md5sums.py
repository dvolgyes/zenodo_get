"""Write record checksums."""

from pathlib import Path
from typing import Any

from loguru import logger


def write_md5sums(files: list[dict[str, Any]]) -> None:
    """Write the record's checksums to ``md5sums.txt``."""
    with Path("md5sums.txt").open("w") as md5_file:
        for file_info in files:
            filename = file_info.get("filename") or file_info["key"]
            checksum = file_info["checksum"].split(":")[-1]
            md5_file.write(f"{checksum}  {filename}\n")
    logger.info("md5sums.txt created.")

