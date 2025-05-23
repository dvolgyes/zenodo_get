#!/usr/bin/env python3
from contextlib import contextmanager
from fnmatch import fnmatch
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import signal
import sys
import time
from urllib.parse import unquote

import click
import humanize
import requests
import wget
import zenodo_get as zget


# see https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022
@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ctrl_c(func):
    signal.signal(signal.SIGINT, func)
    return func


abort_signal = False
abort_counter = 0
# Removed 'exceptions = False' as its usage will be handled by exceptions_on_failure


@ctrl_c
def handle_ctrl_c(*args, **kwargs):
    global abort_signal
    global abort_counter
    # global exceptions # No longer needed here

    abort_signal = True
    abort_counter += 1

    if abort_counter >= 2:
        eprint()
        eprint("Immediate abort. There might be unfinished files.")
        # The 'exceptions' variable logic for immediate abort is tricky
        # to maintain with the new structure. For now, direct exit.
        sys.exit(1)


def check_hash(filename, checksum):
    algorithm = "md5"
    value = checksum.strip()
    if not os.path.exists(filename):
        return value, "invalid"
    h = hashlib.new(algorithm)
    with open(filename, "rb") as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


def _fetch_record_metadata(
    record_id, sandbox, access_token, timeout_val, exceptions_on_failure
):
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
        r = requests.get(api_url_base + record_id, params=params, timeout=timeout_val)
        r.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        return r.json()
    except requests.exceptions.Timeout:
        msg = f"Timeout when fetching metadata for record {record_id} from {api_url_base + record_id}"
        eprint(msg)
        if exceptions_on_failure:
            raise ConnectionError(msg)
        else:
            sys.exit(1)
    except requests.exceptions.HTTPError as e:
        msg = f"HTTP error fetching metadata for record {record_id}: {e.response.status_code} - {e.response.reason} from {api_url_base + record_id}"
        eprint(msg)
        if exceptions_on_failure:
            raise ValueError(msg)
        else:
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        msg = f"Error fetching metadata for record {record_id} from {api_url_base + record_id}: {e}"
        eprint(msg)
        if exceptions_on_failure:
            raise ConnectionError(msg)
        else:
            sys.exit(1)
    return None  # Should ideally not be reached if errors cause exit/exception


def _filter_files_from_metadata(metadata_json, glob_str, record_id):
    """Filters files from metadata based on glob patterns."""

    files_in_metadata = metadata_json.get("files", [])
    if not files_in_metadata:
        eprint(f"No files found in metadata for record {record_id}.")
        return []

    matched_files = []
    for f_meta in files_in_metadata:
        filename = f_meta.get("filename") or f_meta.get("key")
        if filename:
            if not glob_str:
                matched_files.append(f_meta)
            elif any(fnmatch(filename, pattern) for pattern in glob_str):
                matched_files.append(f_meta)
        else:
            eprint(
                f"Skipping file metadata entry due to missing filename/key: {f_meta.get('id', 'Unknown ID')}"
            )

    if not matched_files and glob_str:
        eprint(
            f"Files matching patterns '{glob_str}' not found in metadata for record {record_id}"
        )

    return matched_files


def _handle_single_file_download(
    file_info,
    record_id,
    download_url_base,
    access_token,
    cont_download,
    retry_limit,
    pause_duration,
    timeout_val,  # timeout_val is not directly used by wget.download, but good to have if we change download method
    keep_invalid,
    error_continues,
    exceptions_on_failure,
):
    """Handles the download and verification of a single file."""
    global abort_signal  # Allow checking abort_signal

    fname = file_info.get("filename") or file_info["key"]
    # Prefer direct download link from metadata if available
    link = file_info.get("links", {}).get("self")
    if not link:  # Fallback if links.self is not present
        link = f"{download_url_base}{record_id}/files/{fname}"

    size = humanize.naturalsize(file_info.get("filesize") or file_info["size"])
    checksum = file_info["checksum"].split(":")[-1]

    eprint(f"File: {fname} ({size})")
    eprint(f"Link: {link}")

    if cont_download:
        remote_hash_val, local_hash_val = check_hash(fname, checksum)
        if remote_hash_val == local_hash_val:
            eprint(f"{fname} is already downloaded correctly.")
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
            wget_filename = wget.download(download_target_url, out=fname)

            if (
                fname != wget_filename
            ):  # Should ideally not happen if out=fname works as expected
                eprint(
                    f"Warning: Downloaded filename '{wget_filename}' differs from expected '{fname}'. Renaming."
                )
                os.rename(wget_filename, fname)
            download_successful_flag = True
            break
        except Exception as e_download:
            eprint(f"  Download error for {fname}: {e_download}")
            current_retry += 1
            if current_retry <= retry_limit:
                eprint(f"  Retrying ({current_retry}/{retry_limit})...")
                time.sleep(pause_duration)
            else:
                eprint(f"  Too many errors for {fname}.")
                if not error_continues:
                    msg = f"Download aborted for {fname} after {retry_limit} retries."
                    eprint(msg)
                    if exceptions_on_failure:
                        raise Exception(msg)
                    else:
                        sys.exit(1)
                else:
                    eprint(f"  Skipping {fname} and continuing with the next file.")
                    return (
                        False  # Indicate failure for this file, but allow continuation
                    )

    if (
        not download_successful_flag
    ):  # Should only be reached if error_continues was true and all retries failed
        return False

    eprint()  # Newline after download progress
    h1, h2 = check_hash(fname, checksum)
    if h1 == h2:
        eprint(f"Checksum is correct for {fname}. ({h1})")
        return True
    else:
        eprint(f"Checksum is INCORRECT for {fname}! (Expected: {h1} Got: {h2})")
        if not keep_invalid:
            eprint(f"  File {fname} is deleted.")
            try:
                os.remove(fname)
            except OSError as e_remove:
                eprint(f"  Error deleting file {fname}: {e_remove}")
        else:
            eprint(f"  File {fname} is NOT deleted!")

        if not error_continues:
            msg = f"Aborting due to checksum error for {fname}."
            eprint(msg)
            if exceptions_on_failure:
                raise Exception(msg)
            else:
                sys.exit(1)
        return False  # Checksum failed, but error_continues is true


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
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
    help="Retry on error N more times.",
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
        path_type=Path, file_okay=False, dir_okay=True, writable=True, resolve_path=True
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
def cli(
    record_or_doi,
    cite_opt,
    record,
    doi,
    md5_opt,
    wget_file_opt,
    continue_on_error_opt,
    keep_opt,
    start_fresh_opt,
    retry_opt,
    pause_opt,
    timeout_val_opt,
    outdir_opt,
    sandbox_opt,
    access_token_opt,
    glob_str_opt,
):
    cont_opt = not start_fresh_opt

    if cite_opt:
        print("Reference for this software:")
        print(zget.__reference__)
        print()
        print("Bibtex format:")
        print(zget.__bibtex__)
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
            exceptions_on_failure=False,
        )
    except (
        Exception
    ) as e:  # Catch-all for unexpected errors from _zenodo_download_logic
        eprint(f"An unexpected error occurred in download logic: {e}")
        sys.exit(1)


def _zenodo_download_logic(
    actual_record,
    actual_doi,
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
    exceptions_on_failure,
):
    outdir_opt.mkdir(parents=True, exist_ok=True)

    with cd(outdir_opt):
        recordID_to_fetch = actual_record
        if actual_doi is not None:
            doi_url = (
                actual_doi
                if actual_doi.startswith("http")
                else "https://doi.org/" + actual_doi
            )
            try:
                r_doi = requests.get(doi_url, timeout=timeout_val_opt)
                r_doi.raise_for_status()
                recordID_to_fetch = r_doi.url.split("/")[-1]
            except requests.exceptions.Timeout:
                msg = f"Timeout resolving DOI: {doi_url}"
                eprint(msg)
                if exceptions_on_failure:
                    raise ConnectionError(msg)
                else:
                    sys.exit(1)
            except requests.exceptions.RequestException as e:
                msg = f"Error resolving DOI {doi_url}: {e}"
                eprint(msg)
                if exceptions_on_failure:
                    raise ValueError(msg)
                else:
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
            with open("md5sums.txt", "wt") as md5file_handle:
                for f_info in files_to_download:
                    fname = f_info.get("filename") or f_info["key"]
                    checksum = f_info["checksum"].split(":")[-1]
                    md5file_handle.write(f"{checksum}  {fname}\n")
            eprint("md5sums.txt created.")
            return  # md5_opt implies no download

        if wget_file_opt:
            output_target = (
                sys.stdout if wget_file_opt == "-" else open(wget_file_opt, "wt")
            )
            try:
                for f_info in files_to_download:
                    fname = f_info.get("filename") or f_info["key"]
                    # Use direct link if available, else construct
                    link = (
                        f_info.get("links", {}).get("self")
                        or f"{download_url_base}{recordID_to_fetch}/files/{fname}"
                    )
                    output_target.write(link + "\n")
            finally:
                if wget_file_opt != "-":
                    output_target.close()
            eprint(
                f"URL list written to {'stdout' if wget_file_opt == '-' else wget_file_opt}."
            )
            return  # wget_file_opt implies no download

        # Proceed with actual download
        eprint(f"Title: {metadata['metadata']['title']}")
        eprint(f"Keywords: {', '.join(metadata['metadata'].get('keywords', []))}")
        eprint(f"Publication date: {metadata['metadata']['publication_date']}")
        eprint(f"DOI: {metadata['metadata']['doi']}")
        total_size_val = sum(
            (f.get("filesize") or f.get("size")) for f in files_to_download
        )
        eprint(f"Total size: {humanize.naturalsize(total_size_val)}")

        for i, file_info_item in enumerate(files_to_download):
            if abort_signal:
                eprint(
                    "Download aborted with CTRL+C. Partially downloaded files may exist."
                )
                break

            eprint(f"\nDownloading ({i + 1}/{len(files_to_download)}):")
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
                exceptions_on_failure=exceptions_on_failure,
            )
        else:  # After for loop, if not broken by abort_signal
            if not abort_signal:
                eprint("\nAll specified files have been processed.")


def download(  # Public API function
    record_or_doi=None,
    record=None,
    doi=None,
    output_dir=".",
    md5=False,
    wget_file=None,
    continue_on_error=False,
    keep_invalid=False,
    start_fresh=False,
    retry_attempts=0,
    retry_pause=0.5,
    timeout=15.0,
    sandbox_url=False,
    access_token=None,
    file_glob="*",
    exceptions_on_failure=True,
):
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
        else:
            eprint("Error: No record ID or DOI specified.")
            sys.exit(1)

    outdir_path = Path(output_dir) if isinstance(output_dir, str) else output_dir

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
        file_glob,
        exceptions_on_failure,
    )
