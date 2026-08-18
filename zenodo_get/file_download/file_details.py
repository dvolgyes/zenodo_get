"""Resolve file metadata details."""

from typing import Any

import humanize


def file_details(
    file_info: dict[str, Any],
    record_id: str,
    download_url_base: str,
) -> tuple[str, str, str, str]:
    """Resolve the filename, link, display size, and checksum."""
    filename = file_info.get("filename") or file_info["key"]
    link = file_info.get("links", {}).get("self") or (
        f"{download_url_base}{record_id}/files/{filename}"
    )
    size = humanize.naturalsize(file_info.get("filesize") or file_info["size"])
    checksum = file_info["checksum"].split(":")[-1]
    return filename, link, size, checksum

