"""
HTTP file download utilities using httpx.

Provides a replacement for wget.download() with httpx-based streaming downloads,
automatic filename detection, and configurable verbosity.
"""

import atexit
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from httpx_retries import RetryTransport, Retry
from loguru import logger

# Module-level client and configuration defaults
_client: httpx.Client | None = None

# Default retry configuration
DEFAULT_RETRY_TOTAL = 5
DEFAULT_BACKOFF_FACTOR = 0.5
DEFAULT_MAX_BACKOFF_WAIT = 120.0
DEFAULT_RESPECT_RETRY_AFTER_HEADER = True


def _create_retry_transport(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
) -> RetryTransport:
    """Create a retry transport with the specified configuration."""
    retry = Retry(
        total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
    )
    return RetryTransport(retry=retry)


def _close_client() -> None:
    """Close the module-level client if it exists."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client() -> httpx.Client:
    """
    Get the module-level HTTP client.

    Creates a new client with default retry settings if none exists.
    """
    global _client
    if _client is None:
        transport = _create_retry_transport()
        _client = httpx.Client(follow_redirects=True, transport=transport)
        atexit.register(_close_client)
    return _client


def configure_client(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
) -> None:
    """
    Configure the module-level client with specified retry settings.

    Closes any existing client and creates a new one with the given settings.
    """
    global _client
    _close_client()
    transport = _create_retry_transport(
        retry_total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
    )
    _client = httpx.Client(follow_redirects=True, transport=transport)
    atexit.register(_close_client)


def create_configured_client(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
) -> httpx.Client:
    """
    Create an independent HTTP client with specified retry settings.

    The caller is responsible for closing this client.
    """
    transport = _create_retry_transport(
        retry_total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
    )
    return httpx.Client(follow_redirects=True, transport=transport)


def _extract_filename_from_content_disposition(header: str | None) -> str | None:
    """
    Extract filename from Content-Disposition header.

    Handles quoted, unquoted, and RFC 5987 encoded filenames.
    """
    if not header:
        return None

    # Try RFC 5987 encoded filename* first (takes precedence)
    match = re.search(
        r"filename\*\s*=\s*(?:UTF-8''|utf-8'')(.+?)(?:;|$)", header, re.IGNORECASE
    )
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
    verbosity: int = 2,
    timeout: float = 30.0,
    chunk_size: int = 8192,
) -> str:
    """
    Download a file from URL using httpx with streaming.

    Args:
        url: The URL to download from.
        out: Output filename or path. If None, filename is detected from
            Content-Disposition header or URL path.
        verbosity: Integer verbosity level (0-4).
            0=silent, 1=minimal, 2=normal, 3=nested progress bars, 4=full.
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
    with get_client().stream("GET", url, timeout=timeout) as response:
        response.raise_for_status()

        # Determine output filename
        filename: str
        if out is not None:
            filename = str(out)
        else:
            # Try Content-Disposition header first
            content_disposition = response.headers.get("content-disposition")
            detected_filename = _extract_filename_from_content_disposition(
                content_disposition
            )

            # Fall back to URL path
            if not detected_filename:
                detected_filename = _extract_filename_from_url(str(response.url))

            if not detected_filename:
                raise ValueError(f"Could not determine filename for URL: {url}")

            filename = detected_filename

        if verbosity >= 3:
            logger.debug(f"Downloading {url} to {filename}")

        # Create parent directories if needed
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get("content-length", 0))

        # Stream download to file
        with output_path.open("wb") as f:
            if verbosity >= 3 and total_size > 0:
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

        if verbosity >= 3:
            logger.debug(f"Downloaded {filename}")

        return filename
