"""Coordinate one file download."""

from collections.abc import Callable
from typing import Any

from loguru import logger

from zenodo_get.file_download.download_with_retries import download_with_retries
from zenodo_get.file_download.existing_file_result import existing_file_result
from zenodo_get.file_download.file_details import file_details
from zenodo_get.file_download.types import CheckHash, DownloadFile
from zenodo_get.file_download.verify_download import verify_download


def handle_single_file_download(
    file_info: dict[str, Any],
    record_id: str,
    download_url_base: str,
    access_token: str | None,
    cont_download: bool,
    retry_limit: int,
    pause_duration: float,
    timeout_val: float,
    keep_invalid: bool,
    error_continues: bool,
    verbosity: int,
    exceptions_on_failure: bool,
    existing_file_mode: str,
    abort_requested: Callable[[], bool],
    download_file_func: DownloadFile,
    check_hash_func: CheckHash,
    sleep_func: Callable[[float], None],
) -> bool | str:
    """Download one file, retry failures, and verify its checksum."""
    filename, link, size, checksum = file_details(
        file_info, record_id, download_url_base
    )
    if verbosity >= 4:
        logger.info(f"File: {filename} ({size})")
        logger.info(f"Link: {link}")

    existing_result = existing_file_result(
        filename,
        checksum,
        cont_download,
        existing_file_mode,
        verbosity,
        check_hash_func,
    )
    if existing_result is not None:
        return existing_result
    if not download_with_retries(
        filename,
        link,
        access_token,
        retry_limit,
        pause_duration,
        timeout_val,
        verbosity,
        error_continues,
        exceptions_on_failure,
        abort_requested,
        download_file_func,
        sleep_func,
    ):
        return False
    if verbosity >= 4:
        logger.info("")
    return verify_download(
        filename,
        checksum,
        keep_invalid,
        error_continues,
        exceptions_on_failure,
        verbosity,
        check_hash_func,
    )

