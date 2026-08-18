"""Run the complete record download workflow."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
from loguru import logger

from zenodo_get.workflow.change_directory import cd
from zenodo_get.workflow.download_files import download_files
from zenodo_get.workflow.resolve_record_id import resolve_record_id
from zenodo_get.workflow.write_md5sums import write_md5sums
from zenodo_get.workflow.write_urls import write_urls

FetchMetadata = Callable[..., dict[str, Any] | None]
FilterFiles = Callable[..., list[dict[str, Any]]]
HandleFile = Callable[..., bool | str]

def run_download(
    actual_record: str | None,
    actual_doi: str | None,
    md5_opt: bool,
    wget_file_opt: str | None,
    continue_on_error_opt: bool,
    keep_opt: bool,
    cont_opt: bool,
    retry_opt: int,
    pause_opt: float,
    timeout_val_opt: float,
    outdir_opt: Path,
    sandbox_opt: bool,
    access_token_opt: str | None,
    glob_str_opt: tuple[str, ...],
    verbosity: int,
    exceptions_on_failure: bool,
    existing_file_mode: str,
    no_overwrite_mode: str,
    fetch_metadata: FetchMetadata,
    filter_files: FilterFiles,
    handle_file: HandleFile,
    get_client: Callable[[], httpx2.Client],
    abort_requested: Callable[[], bool],
) -> None:
    """Run the metadata, selection, and download workflow for one record."""
    outdir_opt.mkdir(parents=True, exist_ok=True)
    if verbosity >= 1:
        logger.info(f"Output directory: {outdir_opt.resolve()}")

    with cd(outdir_opt):
        record_id = resolve_record_id(
            actual_record,
            actual_doi,
            timeout_val_opt,
            exceptions_on_failure,
            get_client,
        )
        metadata = fetch_metadata(
            record_id,
            sandbox_opt,
            access_token_opt,
            timeout_val_opt,
            exceptions_on_failure,
        )
        if not metadata:
            return
        files = filter_files(metadata, glob_str_opt, record_id)
        download_url_base = (
            "https://sandbox.zenodo.org/records/"
            if sandbox_opt
            else "https://zenodo.org/records/"
        )
        if md5_opt:
            write_md5sums(files)
            return
        if wget_file_opt:
            write_urls(files, record_id, download_url_base, wget_file_opt)
            return
        download_files(
            metadata,
            files,
            record_id,
            download_url_base,
            access_token_opt,
            cont_opt,
            retry_opt,
            pause_opt,
            timeout_val_opt,
            keep_opt,
            continue_on_error_opt,
            verbosity,
            exceptions_on_failure,
            existing_file_mode,
            no_overwrite_mode,
            handle_file,
            abort_requested,
        )

