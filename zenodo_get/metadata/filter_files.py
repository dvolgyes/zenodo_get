"""Select files from Zenodo metadata."""

from fnmatch import fnmatch
from typing import Any

from loguru import logger


def filter_files_from_metadata(
    metadata_json: dict[str, Any],
    glob_str: tuple[str, ...],
    record_id: str,
) -> list[dict[str, Any]]:
    """Select metadata file entries matching the requested glob patterns."""
    files_in_metadata = metadata_json.get("files", [])
    if not files_in_metadata:
        logger.error(f"No files found in metadata for record {record_id}.")
        return []

    matched_files = []
    for file_info in files_in_metadata:
        filename = file_info.get("filename") or file_info.get("key")
        if filename:
            if not glob_str or any(
                fnmatch(filename, pattern) for pattern in glob_str
            ):
                matched_files.append(file_info)
        else:
            logger.warning(
                "Skipping file metadata entry due to missing filename/key: "
                f"{file_info.get('id', 'Unknown ID')}"
            )

    if not matched_files and glob_str:
        logger.warning(
            f"Files matching patterns '{glob_str}' not found in metadata for record "
            f"{record_id}"
        )
    return matched_files

