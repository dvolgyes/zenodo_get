"""Log record summary information."""

from typing import Any

import humanize
from loguru import logger


def log_record_summary(
    metadata: dict[str, Any],
    files: list[dict[str, Any]],
    verbosity: int,
) -> None:
    """Log record metadata and aggregate file information."""
    record_metadata = metadata["metadata"]
    if verbosity >= 1:
        logger.info(f"Title: {record_metadata['title']}")
    if verbosity >= 4:
        logger.info(f"Keywords: {', '.join(record_metadata.get('keywords', []))}")
        logger.info(f"Publication date: {record_metadata['publication_date']}")
        logger.info(f"DOI: {record_metadata['doi']}")
    total_size = sum(file.get("filesize") or file.get("size", 0) for file in files)
    if verbosity >= 1:
        logger.info(f"Total size: {humanize.naturalsize(total_size)}")
        logger.info(f"Number of files: {len(files)}")
