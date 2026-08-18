#!/usr/bin/env python3
"""Download and manage files from Zenodo research data repository.

This module provides both CLI and programmatic interfaces for downloading
files from Zenodo records, with features like checksum verification,
retry logic, and flexible file filtering.
"""

import signal
import sys
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import click
import httpx2
from loguru import logger

import zenodo_get as zget
from zenodo_get.downloader import (
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_RETRY_TOTAL,
    configure_client,
    download_file,
    get_client,
)
from zenodo_get.file_download import (
    EXISTING_FILE_IGNORE,
    EXISTING_FILE_NO_OVERWRITE,
    EXISTING_FILE_OVERWRITE,
    check_hash,
    handle_single_file_download,
)
from zenodo_get.metadata import fetch_record_metadata, filter_files_from_metadata
from zenodo_get.workflow import run_download


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


def _fetch_record_metadata(
    record_id: str,
    sandbox: bool,
    access_token: str | None,
    timeout_val: float,
    exceptions_on_failure: bool,
) -> dict[str, Any] | None:
    """Fetch record metadata through the configured client."""
    return fetch_record_metadata(
        record_id,
        sandbox,
        access_token,
        timeout_val,
        exceptions_on_failure,
        get_client=get_client,
    )


def _filter_files_from_metadata(
    metadata_json: dict[str, Any], glob_str: tuple[str, ...], record_id: str
) -> list[dict[str, Any]]:
    """Select record files through the metadata policy."""
    return filter_files_from_metadata(metadata_json, glob_str, record_id)


def _handle_single_file_download(
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
    existing_file_mode: str = EXISTING_FILE_OVERWRITE,
) -> bool | str:
    """Download one file through the file-transfer policy."""
    return handle_single_file_download(
        file_info=file_info,
        record_id=record_id,
        download_url_base=download_url_base,
        access_token=access_token,
        cont_download=cont_download,
        retry_limit=retry_limit,
        pause_duration=pause_duration,
        timeout_val=timeout_val,
        keep_invalid=keep_invalid,
        error_continues=error_continues,
        verbosity=verbosity,
        exceptions_on_failure=exceptions_on_failure,
        existing_file_mode=existing_file_mode,
        abort_requested=lambda: abort_signal,
        download_file_func=download_file,
        check_hash_func=check_hash,
        sleep_func=time.sleep,
    )


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
    existing_file_mode: str = EXISTING_FILE_OVERWRITE,
) -> None:
    """Run the record workflow through its policy modules."""
    run_download(
        actual_record=actual_record,
        actual_doi=actual_doi,
        md5_opt=md5_opt,
        wget_file_opt=wget_file_opt,
        continue_on_error_opt=continue_on_error_opt,
        keep_opt=keep_opt,
        cont_opt=cont_opt,
        retry_opt=retry_opt,
        pause_opt=pause_opt,
        timeout_val_opt=timeout_val_opt,
        outdir_opt=outdir_opt,
        sandbox_opt=sandbox_opt,
        access_token_opt=access_token_opt,
        glob_str_opt=glob_str_opt,
        verbosity=verbosity,
        exceptions_on_failure=exceptions_on_failure,
        existing_file_mode=existing_file_mode,
        no_overwrite_mode=EXISTING_FILE_NO_OVERWRITE,
        fetch_metadata=_fetch_record_metadata,
        filter_files=_filter_files_from_metadata,
        handle_file=_handle_single_file_download,
        get_client=get_client,
        abort_requested=lambda: abort_signal,
    )


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
    existing_file_mode: str = "overwrite",
    proxy: str | None = None,
    no_proxy: bool = False,
) -> None:
    """Download files from a Zenodo record programmatically.

    Public API function for downloading Zenodo records.

    This function does not register signal handlers and always uses exceptions
    for error handling, making it safe for use as a library.
    """
    # Validate existing_file_mode parameter
    valid_modes = (
        EXISTING_FILE_OVERWRITE,
        EXISTING_FILE_NO_OVERWRITE,
        EXISTING_FILE_IGNORE,
    )
    if existing_file_mode not in valid_modes:
        raise ValueError(
            f"Invalid existing_file_mode: '{existing_file_mode}'. "
            f"Must be one of: {', '.join(valid_modes)}"
        )
    if proxy is not None and no_proxy:
        raise ValueError("proxy and no_proxy cannot both be configured")

    # Configure HTTP client with retry settings
    configure_client(
        retry_total=max_http_retries,
        backoff_factor=backoff_factor,
        proxy=proxy,
        use_environment_proxy=proxy is None and not no_proxy,
        disable_proxy=no_proxy,
        verbosity=verbosity,
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
        existing_file_mode,
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
@click.option(
    "--proxy",
    "proxy_opt",
    type=str,
    default=None,
    help="Use an HTTP(S) or SOCKS5 proxy, e.g. http://proxy:8080 or socks5://proxy:1080.",
)
@click.option(
    "--no-proxy",
    "no_proxy_opt",
    is_flag=True,
    default=False,
    help="Disable proxy use, including proxy environment variables.",
)
@click.option(
    "--overwrite",
    "overwrite_opt",
    is_flag=True,
    default=False,
    help="Re-download and overwrite existing files with mismatched checksums. (Default behavior)",
)
@click.option(
    "--no-overwrite",
    "no_overwrite_opt",
    is_flag=True,
    default=False,
    help="Do not overwrite existing files with mismatched checksums. Exit with error at end.",
)
@click.option(
    "--ignore-existing-files",
    "ignore_existing_opt",
    is_flag=True,
    default=False,
    help="Ignore existing files with mismatched checksums. Do not overwrite, no error.",
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
    proxy_opt: str | None,
    no_proxy_opt: bool,
    overwrite_opt: bool,
    no_overwrite_opt: bool,
    ignore_existing_opt: bool,
) -> None:
    """Command-line interface for downloading files from Zenodo records.

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
    if proxy_opt is not None and no_proxy_opt:
        raise click.UsageError("Options --proxy and --no-proxy are mutually exclusive.")
    configure_client(
        retry_total=max_http_retries_opt,
        backoff_factor=backoff_factor_opt,
        proxy=proxy_opt,
        use_environment_proxy=proxy_opt is None and not no_proxy_opt,
        disable_proxy=no_proxy_opt,
        verbosity=verbosity_opt,
    )

    cont_opt = not start_fresh_opt

    # Validate mutual exclusivity of existing file mode options
    mode_count = sum([overwrite_opt, no_overwrite_opt, ignore_existing_opt])
    if mode_count > 1:
        raise click.UsageError(
            "Options --overwrite, --no-overwrite, and --ignore-existing-files "
            "are mutually exclusive."
        )

    # Determine existing file mode
    if no_overwrite_opt:
        existing_file_mode = EXISTING_FILE_NO_OVERWRITE
    elif ignore_existing_opt:
        existing_file_mode = EXISTING_FILE_IGNORE
    else:
        existing_file_mode = EXISTING_FILE_OVERWRITE

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
            existing_file_mode=existing_file_mode,
        )
    except (
        ConnectionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        httpx2.RequestError,
        httpx2.HTTPStatusError,
    ) as e:
        logger.error(f"An unexpected error occurred in download logic: {e}")
        sys.exit(1)
