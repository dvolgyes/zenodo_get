"""Verify a downloaded file."""

import sys

from loguru import logger

from zenodo_get.file_download.remove_invalid_file import remove_invalid_file
from zenodo_get.file_download.types import CheckHash


def verify_download(
    filename: str,
    checksum: str,
    keep_invalid: bool,
    error_continues: bool,
    exceptions_on_failure: bool,
    verbosity: int,
    check_hash_func: CheckHash,
) -> bool:
    """Validate a downloaded file and apply invalid-file policy."""
    expected, actual = check_hash_func(filename, checksum)
    if expected == actual:
        if verbosity >= 4:
            logger.success(f"Checksum is correct for {filename}. ({expected})")
        return True
    logger.error(
        f"Checksum is INCORRECT for {filename}! (Expected: {expected} Got: {actual})"
    )
    remove_invalid_file(filename, keep_invalid, verbosity)
    if not error_continues:
        message = f"Aborting due to checksum error for {filename}."
        logger.error(message)
        if exceptions_on_failure:
            raise RuntimeError(message)
        sys.exit(1)
    return False
