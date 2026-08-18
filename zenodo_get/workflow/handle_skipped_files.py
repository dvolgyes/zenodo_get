"""Apply final existing-file policies."""

import sys

from loguru import logger


def handle_skipped_files(
    skipped_count: int,
    existing_file_mode: str,
    no_overwrite_mode: str,
    exceptions_on_failure: bool,
) -> None:
    """Apply the final no-overwrite policy after processing files."""
    if skipped_count == 0 or existing_file_mode != no_overwrite_mode:
        return
    message = (
        f"{skipped_count} file(s) exist with mismatched checksums and were not "
        "overwritten."
    )
    logger.error(message)
    if exceptions_on_failure:
        raise RuntimeError(message)
    sys.exit(1)
