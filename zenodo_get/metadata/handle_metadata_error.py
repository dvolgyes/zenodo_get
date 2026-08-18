"""Handle metadata errors."""

import sys

from loguru import logger


def handle_metadata_error(
    message: str,
    exception_type: type[Exception],
    exceptions_on_failure: bool,
) -> None:
    """Log a metadata error and either raise it or terminate CLI processing."""
    logger.error(message)
    if exceptions_on_failure:
        raise exception_type(message)
    sys.exit(1)
