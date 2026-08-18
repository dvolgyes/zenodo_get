"""Download all selected files from a record."""

from collections.abc import Callable
from typing import Any

from loguru import logger

from zenodo_get.workflow.file_iterator import file_iterator
from zenodo_get.workflow.handle_skipped_files import handle_skipped_files
from zenodo_get.workflow.log_record_summary import log_record_summary

HandleFile = Callable[..., bool | str]


def download_files(
    metadata: dict[str, Any],
    files: list[dict[str, Any]],
    record_id: str,
    download_url_base: str,
    access_token: str | None,
    continue_download: bool,
    retry_limit: int,
    pause_duration: float,
    timeout: float,
    keep_invalid: bool,
    error_continues: bool,
    verbosity: int,
    exceptions_on_failure: bool,
    existing_file_mode: str,
    no_overwrite_mode: str,
    handle_file: HandleFile,
    abort_requested: Callable[[], bool],
) -> None:
    """Download and verify each selected file."""
    log_record_summary(metadata, files, verbosity)
    skipped_count = 0
    for index, file_info in file_iterator(files, verbosity):
        if abort_requested():
            logger.warning(
                "Download aborted with CTRL+C. Partially downloaded files may exist."
            )
            break
        if verbosity >= 4:
            logger.info(f"\nDownloading ({index + 1}/{len(files)}):")
        result = handle_file(
            file_info=file_info,
            record_id=record_id,
            download_url_base=download_url_base,
            access_token=access_token,
            cont_download=continue_download,
            retry_limit=retry_limit,
            pause_duration=pause_duration,
            timeout_val=timeout,
            keep_invalid=keep_invalid,
            error_continues=error_continues,
            verbosity=verbosity,
            exceptions_on_failure=exceptions_on_failure,
            existing_file_mode=existing_file_mode,
        )
        if result == "skipped":
            skipped_count += 1
    else:
        if not abort_requested() and verbosity >= 1:
            logger.success("All specified files have been processed.")
    handle_skipped_files(
        skipped_count,
        existing_file_mode,
        no_overwrite_mode,
        exceptions_on_failure,
    )
