"""Perform one file download attempt."""

from pathlib import Path
from urllib.parse import unquote

from loguru import logger

from zenodo_get.file_download.types import DownloadFile


def download_once(
    filename: str,
    link: str,
    access_token: str | None,
    verbosity: int,
    timeout_val: float,
    download_file_func: DownloadFile,
) -> None:
    """Perform one download attempt and normalize its resulting filename."""
    unquoted_link = unquote(link)
    download_target_url = (
        f"{unquoted_link}?access_token={access_token}"
        if access_token
        else unquoted_link
    )
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    downloaded_filename = download_file_func(
        download_target_url,
        out=filename,
        verbosity=verbosity,
        timeout=timeout_val,
    )
    if filename != downloaded_filename:
        logger.warning(
            f"Downloaded filename '{downloaded_filename}' differs from expected "
            f"'{filename}'. Renaming."
        )
        Path(downloaded_filename).rename(filename)

