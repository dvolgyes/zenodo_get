"""Build download URLs from file metadata."""

from typing import Any


def file_url(
    file_info: dict[str, Any], record_id: str, download_url_base: str
) -> str:
    """Build the direct download URL for one metadata entry."""
    filename = file_info.get("filename") or file_info["key"]
    return file_info.get("links", {}).get("self") or (
        f"{download_url_base}{record_id}/files/{filename}"
    )

