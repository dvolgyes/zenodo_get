#!/usr/bin/env python3
"""
Download and manage files from Zenodo research data repository.

This module provides both CLI and programmatic interfaces for downloading
files from Zenodo records, with features like checksum verification,
retry logic, and flexible file filtering.
"""

from contextlib import contextmanager
from fnmatch import fnmatch
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any
from collections.abc import Callable, Iterator
from urllib.parse import unquote

import click
import humanize
import httpx
from loguru import logger
import zenodo_get as zget
from zenodo_get.downloader import (
    configure_client,
    download_file,
    get_client,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_RETRY_TOTAL,
)


# see https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022
@contextmanager
def cd(newdir: str | Path) -> Iterator[None]:
    """Temporarily change to a different directory, returning to original after."""
    prevdir = Path.cwd()
    os.chdir(Path(newdir).expanduser())
    try:
        yield
    finally:
        os.chdir(prevdir)


def ctrl_c(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to register signal handler - only used in CLI mode."""
    signal.signal(signal.SIGINT, func)
    return func


abort_signal = False
abort_counter = 0


@ctrl_c
def handle_ctrl_c(*args: object, **kwargs: object) -> None:
    """Handle Ctrl+C signal - only active in CLI mode."""
    global abort_signal
    global abort_counter

    abort_signal = True
    abort_counter += 1

    if abort_counter >= 2:
        logger.error("Immediate abort. There might be unfinished files.")
        sys.exit(1)


def check_hash(filename: str, checksum: str) -> tuple[str, str]:
    """Verify file integrity by comparing MD5 checksum against expected value."""
    algorithm = "md5"
    value = checksum.strip()
    if not Path(filename).exists():
        return value, "invalid"
    h = hashlib.new(algorithm)
    with Path(filename).open("rb") as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


def _fetch_record_metadata(
    record_id: str,
    sandbox: bool,
    access_token: str | None,
    timeout_val: float,
    exceptions_on_failure: bool,
) -> dict[str, Any] | None:
    """Fetches and returns the JSON metadata for a Zenodo record."""
    api_url_base = (
        "https://sandbox.zenodo.org/api/records/"
        if sandbox
        else "https://zenodo.org/api/records/"
    )

    params = {}
    if access_token:
        params["access_token"] = access_token

    try:
        client = get_client()
        r = client.get(api_url_base + record_id, params=params, timeout=timeout_val)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        msg = f"Timeout when fetching metadata for record {record_id} from {api_url_base + record_id}"
        logger.error(msg)
        if exceptions_on_failure:
            raise ConnectionError(msg)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        msg = f"HTTP error fetching metadata for record {record_id}: {e.response.status_code} - {e.response.reason_phrase} from {api_url_base + record_id}"
        logger.error(msg)
        if exceptions_on_failure:
            raise ValueError(msg)
        sys.exit(1)
    except httpx.RequestError as e:
        msg = f"Error fetching metadata for record {record_id} from {api_url_base + record_id}: {e}"
        logger.error(msg)
        if exceptions_on_failure:
            raise ConnectionError(msg)
        sys.exit(1)


def _filter_files_from_metadata(
    metadata_json: dict[str, Any], glob_str: tuple[str, ...], record_id: str
) -> list[dict[str, Any]]:
    """Filters files from metadata based on glob patterns."""
    files_in_metadata = metadata_json.get("files", [])
    if not files_in_metadata:
        logger.error(f"No files found in metadata for record {record_id}.")
        return []

    matched_files = []
    for f_meta in files_in_metadata:
        filename = f_meta.get("filename") or f_meta.get("key")
        if filename:
            if not glob_str or any(fnmatch(filename, pattern) for pattern in glob_str):
                matched_files.append(f_meta)
        else:
            logger.warning(
                f"Skipping file metadata entry due to missing filename/key: {f_meta.get('id', 'Unknown ID')}"
            )

    if not matched_files and glob_str:
        logger.warning(
            f"Files matching patterns '{glob_str}' not found in metadata for record {record_id}"
        )

    return matched_files


def _handle_single_file_download(
    file_info: dict[str, Any],
    record_id: str,
    download_url_base: str,
    access_token: str | None,
    cont_download: bool,
    retry_limit: int,
    pause_duration: float,
    timeout_val: float,  # timeout_val is not directly used by wget.download, but good to have if we change download method
    keep_invalid: bool,
    error_continues: bool,
    verbosity: int,
    exceptions_on_failure: bool,
) -> bool:
    """
    Download one file with retry logic and checksum verification.

    Handles the download and verification of a single file.
    """
    fname = file_info.get("filename") or file_info["key"]
    # Prefer direct download link from metadata if available
    link = file_info.get("links", {}).get("self")
    if not link:  # Fallback if links.self is not present
        link = f"{download_url_base}{record_id}/files/{fname}"

    size = humanize.naturalsize(file_info.get("filesize") or file_info["size"])
    checksum = file_info["checksum"].split(":")[-1]

    # Level 4: log file details
    if verbosity >= 4:
        logger.info(f"File: {fname} ({size})")
        logger.info(f"Link: {link}")

    if cont_download:
        remote_hash_val, local_hash_val = check_hash(fname, checksum)
        if remote_hash_val == local_hash_val:
            logger.info(f"{fname} is already downloaded correctly.")
            return True

    current_retry = 0
    download_successful_flag = False
    while current_retry <= retry_limit:
        if abort_signal:
            return False  # Check before attempting download
        try:
            unquoted_link = unquote(link)
            download_target_url = (
                f"{unquoted_link}?access_token={access_token}"
                if access_token
                else unquoted_link
            )

            Path(fname).parent.mkdir(parents=True, exist_ok=True)
            wget_filename = download_file(
                download_target_url,
                out=fname,
                verbosity=verbosity,
                timeout=timeout_val,
            )

            if (
                fname != wget_filename
            ):  # Should ideally not happen if out=fname works as expected
                logger.warning(
                    f"Downloaded filename '{wget_filename}' differs from expected '{fname}'. Renaming."
                )
                Path(wget_filename).rename(fname)
            download_successful_flag = True
            break
        except Exception as e_download:
            logger.error(f"Download error for {fname}: {e_download}")
            current_retry += 1
            if current_retry <= retry_limit:
                logger.info(f"Retrying ({current_retry}/{retry_limit})...")
                time.sleep(pause_duration)
            else:
                logger.error(f"Too many errors for {fname}.")
                if not error_continues:
                    msg = f"Download aborted for {fname} after {retry_limit} retries."
                    logger.error(msg)
                    if exceptions_on_failure:
                        raise Exception(msg)
                    sys.exit(1)
                else:
                    logger.warning(
                        f"Skipping {fname} and continuing with the next file."
                    )
                    return (
                        False  # Indicate failure for this file, but allow continuation
                    )

    if (
        not download_successful_flag
    ):  # Should only be reached if error_continues was true and all retries failed
        return False

    if verbosity >= 4:
        logger.info("")  # Newline after download progress
    h1, h2 = check_hash(fname, checksum)
    if h1 == h2:
        if verbosity >= 4:
            logger.success(f"Checksum is correct for {fname}. ({h1})")
        return True
    logger.error(f"Checksum is INCORRECT for {fname}! (Expected: {h1} Got: {h2})")
    if not keep_invalid:
        if verbosity >= 4:
            logger.info(f"File {fname} is deleted.")
        try:
            Path(fname).unlink()
        except OSError as e_remove:
            logger.error(f"Error deleting file {fname}: {e_remove}")
    else:
        logger.warning(f"File {fname} is NOT deleted!")

    if not error_continues:
        msg = f"Aborting due to checksum error for {fname}."
        logger.error(msg)
        if exceptions_on_failure:
            raise Exception(msg)
        sys.exit(1)
    return False  # Checksum failed, but error_continues is true


def _zenodo_download_logic(
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
) -> None:
    """Orchestrate the complete download workflow for a Zenodo record."""
    outdir_opt.mkdir(parents=True, exist_ok=True)

    if verbosity >= 1:
        logger.info(f"Output directory: {outdir_opt.resolve()}")

    with cd(outdir_opt):
        recordID_to_fetch = actual_record
        if actual_doi is not None:
            doi_url = (
                actual_doi
                if actual_doi.startswith("http")
                else "https://doi.org/" + actual_doi
            )
            try:
                client = get_client()
                r_doi = client.get(doi_url, timeout=timeout_val_opt)
                r_doi.raise_for_status()
                recordID_to_fetch = str(r_doi.url).split("/")[-1]
            except httpx.TimeoutException:
                msg = f"Timeout resolving DOI: {doi_url}"
                logger.error(msg)
                if exceptions_on_failure:
                    raise ConnectionError(msg)
                sys.exit(1)
            except httpx.HTTPStatusError as e:
                msg = f"HTTP error resolving DOI {doi_url}: {e.response.status_code} - {e.response.reason_phrase}"
                logger.error(msg)
                if exceptions_on_failure:
                    raise ValueError(msg)
                sys.exit(1)
            except httpx.RequestError as e:
                msg = f"Error resolving DOI {doi_url}: {e}"
                logger.error(msg)
                if exceptions_on_failure:
                    raise ConnectionError(msg)
                sys.exit(1)

        if recordID_to_fetch is None:
            msg = "No record ID or DOI specified."
            logger.error(msg)
            if exceptions_on_failure:
                raise ValueError(msg)
            sys.exit(1)

        recordID_to_fetch = recordID_to_fetch.strip()

        metadata = _fetch_record_metadata(
            recordID_to_fetch,
            sandbox_opt,
            access_token_opt,
            timeout_val_opt,
            exceptions_on_failure,
        )
        if not metadata:
            return  # Error handled by _fetch_record_metadata

        files_to_download = _filter_files_from_metadata(
            metadata, glob_str_opt, recordID_to_fetch
        )

        download_url_base = (
            "https://sandbox.zenodo.org/records/"
            if sandbox_opt
            else "https://zenodo.org/records/"
        )

        if md5_opt:
            with Path("md5sums.txt").open("w") as md5file_handle:
                for f_info in files_to_download:
                    fname = f_info.get("filename") or f_info["key"]
                    checksum = f_info["checksum"].split(":")[-1]
                    md5file_handle.write(f"{checksum}  {fname}\n")
            logger.info("md5sums.txt created.")
            return  # md5_opt implies no download

        if wget_file_opt:
            if wget_file_opt == "-":
                for f_info in files_to_download:
                    fname = f_info.get("filename") or f_info["key"]
                    link = (
                        f_info.get("links", {}).get("self")
                        or f"{download_url_base}{recordID_to_fetch}/files/{fname}"
                    )
                    sys.stdout.write(link + "\n")
            else:
                with Path(wget_file_opt).open("w") as output_file:
                    for f_info in files_to_download:
                        fname = f_info.get("filename") or f_info["key"]
                        link = (
                            f_info.get("links", {}).get("self")
                            or f"{download_url_base}{recordID_to_fetch}/files/{fname}"
                        )
                        output_file.write(link + "\n")
            logger.info(
                f"URL list written to {'stdout' if wget_file_opt == '-' else wget_file_opt}."
            )
            return  # wget_file_opt implies no download

        # Proceed with actual download
        # Level 1+: record title and total size
        if verbosity >= 1:
            logger.info(f"Title: {metadata['metadata']['title']}")
        # Level 4: additional metadata
        if verbosity >= 4:
            logger.info(
                f"Keywords: {', '.join(metadata['metadata'].get('keywords', []))}"
            )
            logger.info(f"Publication date: {metadata['metadata']['publication_date']}")
            logger.info(f"DOI: {metadata['metadata']['doi']}")
        total_size_val = sum(
            (f.get("filesize") or f.get("size", 0)) for f in files_to_download
        )
        if verbosity >= 1:
            logger.info(f"Total size: {humanize.naturalsize(total_size_val)}")
            logger.info(f"Number of files: {len(files_to_download)}")

        # Level 2+: overall progress bar
        from collections.abc import Iterable

        from tqdm import tqdm

        file_iterator: Iterable[tuple[int, dict[str, Any]]]
        if verbosity >= 2:
            file_iterator = tqdm(
                enumerate(files_to_download),
                total=len(files_to_download),
                desc="Files",
                leave=False,
                unit="file",
            )
        else:
            file_iterator = enumerate(files_to_download)

        for i, file_info_item in file_iterator:
            if abort_signal:
                logger.warning(
                    "Download aborted with CTRL+C. Partially downloaded files may exist."
                )
                break

            if verbosity >= 4:
                logger.info(f"\nDownloading ({i + 1}/{len(files_to_download)}):")
            _handle_single_file_download(
                file_info=file_info_item,
                record_id=recordID_to_fetch,
                download_url_base=download_url_base,
                access_token=access_token_opt,
                cont_download=cont_opt,
                retry_limit=retry_opt,
                pause_duration=pause_opt,
                timeout_val=timeout_val_opt,
                keep_invalid=keep_opt,
                error_continues=continue_on_error_opt,
                verbosity=verbosity,
                exceptions_on_failure=exceptions_on_failure,
            )
        else:  # After for loop, if not broken by abort_signal
            if not abort_signal and verbosity >= 1:
                logger.success("All specified files have been processed.")


def download(  # Public API function
    record_or_doi: str | None = None,
    record: str | None = None,
    doi: str | None = None,
    output_dir: str | Path = ".",
    md5: bool = False,
    wget_file: str | None = None,
    continue_on_error: bool = False,
    keep_invalid: bool = False,
    start_fresh: bool = False,
    retry_attempts: int = 0,
    retry_pause: float = 0.5,
    timeout: float = 15.0,
    sandbox_url: bool = False,
    access_token: str | None = None,
    file_glob: str | tuple[str, ...] = "*",
    verbosity: int = 2,
    exceptions_on_failure: bool = True,
    max_http_retries: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> None:
    """
    Download files from a Zenodo record programmatically.

    Public API function for downloading Zenodo records.

    This function does not register signal handlers and always uses exceptions
    for error handling, making it safe for use as a library.
    """
    # Configure HTTP client with retry settings
    configure_client(
        retry_total=max_http_retries,
        backoff_factor=backoff_factor,
    )

    # Configure minimal logging for library mode
    if not logger._core.handlers:
        logger.add(sys.stderr, format="{level}: {message}", level="WARNING")

    actual_record_id = record
    actual_doi_str = doi
    if record_or_doi:
        try:
            actual_record_id = str(int(record_or_doi))
        except ValueError:
            actual_doi_str = record_or_doi

    if actual_doi_str is None and actual_record_id is None:
        if exceptions_on_failure:
            raise ValueError("Either record_or_doi, record, or doi must be provided.")
        logger.error("No record ID or DOI specified.")
        sys.exit(1)

    outdir_path = Path(output_dir) if isinstance(output_dir, str) else output_dir

    # Ensure file_glob is a tuple for consistency
    glob_tuple: tuple[str, ...]
    if isinstance(file_glob, str):
        glob_tuple = (file_glob,) if file_glob != "*" else ()
    else:
        glob_tuple = file_glob

    _zenodo_download_logic(
        actual_record_id,
        actual_doi_str,
        md5,
        wget_file,
        continue_on_error,
        keep_invalid,
        not start_fresh,
        retry_attempts,
        retry_pause,
        timeout,
        outdir_path,
        sandbox_url,
        access_token,
        glob_tuple,
        verbosity,
        exceptions_on_failure,
    )


@click.command(
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True}
)
@click.version_option(version=version("zenodo-get"), prog_name="zenodo_get")
@click.argument("record_or_doi", required=False, default=None)
@click.option(
    "-c",
    "--cite",
    "cite_opt",
    is_flag=True,
    default=False,
    help="print citation information",
)
@click.option("-r", "--record", type=str, help="Zenodo record ID")
@click.option("-d", "--doi", type=str, help="Zenodo DOI")
@click.option(
    "-m",
    "--md5",
    "md5_opt",
    is_flag=True,
    default=False,
    help="Create md5sums.txt for verification.",
)
@click.option(
    "-w",
    "--wget",
    "wget_file_opt",
    type=str,
    help="Create URL list for download managers. (Files will not be downloaded.)",
)
@click.option(
    "-e",
    "--continue-on-error",
    "continue_on_error_opt",
    is_flag=True,
    default=False,
    help="Continue with next file if error happens.",
)
@click.option(
    "-k",
    "--keep",
    "keep_opt",
    is_flag=True,
    default=False,
    help="Keep files with invalid checksum. (Default: delete them.)",
)
@click.option(
    "-n",
    "--do-not-continue",
    "start_fresh_opt",
    is_flag=True,
    default=False,
    help="Do not continue previous download attempt, start fresh.",
)
@click.option(
    "-R",
    "--retry",
    "retry_opt",
    type=int,
    default=1,
    help="Application-level retries for checksum failures and non-HTTP errors. Separate from --max-http-retries.",
)
@click.option(
    "-p",
    "--pause",
    "pause_opt",
    type=float,
    default=3,
    help="Wait N second before retry attempt, e.g. 0.5",
)
@click.option(
    "-t",
    "--time-out",
    "timeout_val_opt",
    type=float,
    default=25.0,
    help="Set connection time-out. Default: 25 [sec].",
)
@click.option(
    "-o",
    "--output-dir",
    "outdir_opt",
    type=click.Path(
        path_type=Path,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,  # type: ignore[type-var]
    ),
    default=".",
    help="Output directory, created if necessary. Default: current directory.",
)
@click.option(
    "-s",
    "--sandbox",
    "sandbox_opt",
    is_flag=True,
    default=False,
    help="Use Zenodo Sandbox URL.",
)
@click.option(
    "-a",
    "--access-token",
    "access_token_opt",
    type=str,
    default=None,
    help="Optional access token for the requests query.",
)
@click.option(
    "-g",
    "--glob",
    "glob_str_opt",
    multiple=True,
    type=str,
    default=[],
    help="Glob expressions for files, it can be used multiple times. (e.g., -g '*.txt'  -g '*.pdf'). Default: all files.",
)
@click.option(
    "-v",
    "--verbosity",
    "verbosity_opt",
    type=click.IntRange(0, 4),
    default=2,
    help="Verbosity level (0-4). 0=silent, 1=minimal, 2=normal, 3=nested progress, 4=full",
)
@click.option(
    "--max-http-retries",
    "max_http_retries_opt",
    type=int,
    default=DEFAULT_RETRY_TOTAL,
    help="HTTP transport-level retries for network errors and 429/5xx responses. Uses exponential backoff.",
)
@click.option(
    "--backoff-factor",
    "backoff_factor_opt",
    type=float,
    default=DEFAULT_BACKOFF_FACTOR,
    help="Exponential backoff factor for HTTP retries (e.g., 0.5 means 0.5s, 1s, 2s...).",
)
def cli(
    record_or_doi: str | None,
    cite_opt: bool,
    record: str | None,
    doi: str | None,
    md5_opt: bool,
    wget_file_opt: str | None,
    continue_on_error_opt: bool,
    keep_opt: bool,
    start_fresh_opt: bool,
    retry_opt: int,
    pause_opt: float,
    timeout_val_opt: float,
    outdir_opt: Path,
    sandbox_opt: bool,
    access_token_opt: str | None,
    glob_str_opt: tuple[str, ...],
    verbosity_opt: int,
    max_http_retries_opt: int,
    backoff_factor_opt: float,
) -> None:
    """
    Command-line interface for downloading files from Zenodo records.

    CLI mode - uses signal handling and can exit directly.
    """
    # Configure logging for CLI mode with tqdm compatibility
    from tqdm import tqdm

    logger.remove()  # Remove default handler
    if verbosity_opt > 0:
        logger.add(
            lambda msg: tqdm.write(msg, end=""),
            format="<level>{level}</level>: {message}",
            level="INFO",
            colorize=True,
        )

    # Configure HTTP client with retry settings
    configure_client(
        retry_total=max_http_retries_opt,
        backoff_factor=backoff_factor_opt,
    )

    cont_opt = not start_fresh_opt

    if cite_opt:
        click.echo("Reference for this software:")
        click.echo(zget.__reference__)
        click.echo()
        click.echo("Bibtex format:")
        click.echo(zget.__bibtex__)
        sys.exit(0)

    actual_record_id = record
    actual_doi_str = doi
    if record_or_doi:
        try:
            actual_record_id = str(int(record_or_doi))
        except ValueError:
            actual_doi_str = record_or_doi

    if actual_doi_str is None and actual_record_id is None:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit(1)

    try:
        _zenodo_download_logic(
            actual_record_id,
            actual_doi_str,
            md5_opt,
            wget_file_opt,
            continue_on_error_opt,
            keep_opt,
            cont_opt,
            retry_opt,
            pause_opt,
            timeout_val_opt,
            outdir_opt,
            sandbox_opt,
            access_token_opt,
            glob_str_opt,
            verbosity_opt,
            exceptions_on_failure=False,  # CLI mode uses sys.exit for errors
        )
    except (
        Exception
    ) as e:  # Catch-all for unexpected errors from _zenodo_download_logic
        logger.error(f"An unexpected error occurred in download logic: {e}")
        sys.exit(1)
