"""HTTP file download utilities using httpx.

Provides a replacement for wget.download() with httpx-based streaming downloads,
automatic filename detection, and configurable verbosity.
"""

import atexit
import re
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

import httpx
from loguru import logger

# Long-lived global client for TCP connection reuse
_client = httpx.Client(follow_redirects=True)
atexit.register(_client.close)


def _extract_filename_from_content_disposition(header: str | None) -> str | None:
    """Extract filename from Content-Disposition header.

    Handles quoted, unquoted, and RFC 5987 encoded filenames.
    """
    if not header:
        return None

    # Try RFC 5987 encoded filename* first (takes precedence)
    match = re.search(r"filename\*\s*=\s*(?:UTF-8''|utf-8'')(.+?)(?:;|$)", header, re.IGNORECASE)
    if match:
        return unquote(match.group(1).strip())

    # Try quoted filename
    match = re.search(r'filename\s*=\s*"([^"]+)"', header)
    if match:
        return match.group(1).strip()

    # Try unquoted filename
    match = re.search(r"filename\s*=\s*([^;\s]+)", header)
    if match:
        return match.group(1).strip()

    return None


def _extract_filename_from_url(url: str) -> str | None:
    """Extract filename from URL path."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if path and "/" in path:
        filename = path.rsplit("/", 1)[-1]
        if filename:
            return filename
    return None


def download_file(
    url: str,
    out: str | Path | None = None,
    verbosity: Literal["quiet", "normal", "progress"] = "normal",
    timeout: float = 30.0,
    chunk_size: int = 8192,
) -> str:
    """Download a file from URL using httpx with streaming.

    Args:
        url: The URL to download from.
        out: Output filename or path. If None, filename is detected from
            Content-Disposition header or URL path.
        verbosity: "quiet" for no logs, "normal" or "progress" for debug logs.
        timeout: Connection timeout in seconds.
        chunk_size: Size of chunks to read during streaming download.

    Returns:
        The actual filename where the file was saved.

    Raises:
        httpx.TimeoutException: If the connection times out.
        httpx.HTTPStatusError: If the server returns an error status.
        httpx.RequestError: If a request error occurs.
        ValueError: If no filename can be determined.
    """
    with _client.stream("GET", url, timeout=timeout) as response:
        response.raise_for_status()

        # Determine output filename
        filename: str
        if out is not None:
            filename = str(out)
        else:
            # Try Content-Disposition header first
            content_disposition = response.headers.get("content-disposition")
            detected_filename = _extract_filename_from_content_disposition(content_disposition)

            # Fall back to URL path
            if not detected_filename:
                detected_filename = _extract_filename_from_url(str(response.url))

            if not detected_filename:
                raise ValueError(f"Could not determine filename for URL: {url}")

            filename = detected_filename

        if verbosity != "quiet":
            logger.debug(f"Downloading {url} to {filename}")

        # Create parent directories if needed
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get("content-length", 0))

        # Stream download to file
        with output_path.open("wb") as f:
            if verbosity == "progress" and total_size > 0:
                from tqdm import tqdm

                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc=filename,
                    leave=False,
                ) as pbar:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    f.write(chunk)

        if verbosity != "quiet":
            logger.debug(f"Downloaded {filename}")

        return filename
