"""Remove invalid downloaded files."""

from pathlib import Path

from loguru import logger


def remove_invalid_file(filename: str, keep_invalid: bool, verbosity: int) -> None:
    """Delete an invalid download unless the caller asked to keep it."""
    if keep_invalid:
        logger.warning(f"File {filename} is NOT deleted!")
        return
    if verbosity >= 4:
        logger.info(f"File {filename} is deleted.")
    try:
        Path(filename).unlink()
    except OSError as error:
        logger.error(f"Error deleting file {filename}: {error}")
