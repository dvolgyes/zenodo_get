"""Retry one file download."""

from collections.abc import Callable

import httpx2

from zenodo_get.file_download.download_once import download_once
from zenodo_get.file_download.handle_download_error import handle_download_error
from zenodo_get.file_download.types import DownloadFile


def download_with_retries(
    filename: str,
    link: str,
    access_token: str | None,
    retry_limit: int,
    pause_duration: float,
    timeout_val: float,
    verbosity: int,
    error_continues: bool,
    exceptions_on_failure: bool,
    abort_requested: Callable[[], bool],
    download_file_func: DownloadFile,
    sleep_func: Callable[[float], None],
) -> bool:
    """Download one file until it succeeds, aborts, or exhausts retries."""
    for current_retry in range(retry_limit + 1):
        if abort_requested():
            return False
        try:
            download_once(
                filename,
                link,
                access_token,
                verbosity,
                timeout_val,
                download_file_func,
            )
            return True
        except (
            OSError,
            ValueError,
            RuntimeError,
            httpx2.RequestError,
            httpx2.HTTPStatusError,
        ) as error:
            if not handle_download_error(
                filename,
                error,
                current_retry,
                retry_limit,
                pause_duration,
                error_continues,
                exceptions_on_failure,
                sleep_func,
            ):
                return False
    return False
