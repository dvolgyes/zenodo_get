"""Handle one file download error."""

import sys
from collections.abc import Callable

from loguru import logger


def handle_download_error(
    filename: str,
    error: Exception,
    current_retry: int,
    retry_limit: int,
    pause_duration: float,
    error_continues: bool,
    exceptions_on_failure: bool,
    sleep_func: Callable[[float], None],
) -> bool:
    """Handle an attempt failure and return whether another attempt is allowed."""
    logger.error(f"Download error for {filename}: {error}")
    next_retry = current_retry + 1
    if next_retry <= retry_limit:
        logger.info(f"Retrying ({next_retry}/{retry_limit})...")
        sleep_func(pause_duration)
        return True
    if not error_continues:
        message = f"Download aborted for {filename} after {retry_limit} retries."
        logger.error(f"Too many errors for {filename}.")
        logger.error(message)
        if exceptions_on_failure:
            raise RuntimeError(message)
        sys.exit(1)
    logger.warning(f"Skipping {filename} and continuing with the next file.")
    return False

