"""Apply existing-file download policy."""

from loguru import logger

from zenodo_get.file_download.constants import (
    EXISTING_FILE_IGNORE,
    EXISTING_FILE_NO_OVERWRITE,
)
from zenodo_get.file_download.types import CheckHash


def existing_file_result(
    filename: str,
    checksum: str,
    continue_download: bool,
    existing_file_mode: str,
    verbosity: int,
    check_hash_func: CheckHash,
) -> bool | str | None:
    """Return the result for an existing file, or ``None`` to download it."""
    if not continue_download:
        return None
    remote_hash, local_hash = check_hash_func(filename, checksum)
    if remote_hash == local_hash:
        logger.info(f"{filename} is already downloaded correctly.")
        return True
    if local_hash == "invalid":
        return None
    if existing_file_mode == EXISTING_FILE_NO_OVERWRITE:
        if verbosity >= 2:
            logger.error(f"{filename} exists but not overwritten with new content")
        return "skipped"
    if existing_file_mode == EXISTING_FILE_IGNORE:
        if verbosity >= 2:
            logger.warning(f"{filename} exists and ignored (not updating content)")
        return True
    if verbosity >= 2:
        logger.warning(f"{filename} exists but overwriting with new content")
    return None
