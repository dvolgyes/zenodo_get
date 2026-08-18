"""HTTP file download utilities using httpx2.

Provides a replacement for wget.download() with httpx2-based streaming downloads,
automatic filename detection, and configurable verbosity.
"""

import atexit
import ipaddress
import os
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlparse, urlsplit, urlunsplit

import httpx2
from loguru import logger

# Module-level client and configuration defaults
_client: httpx2.Client | None = None

# Default retry configuration
DEFAULT_RETRY_TOTAL = 5
DEFAULT_BACKOFF_FACTOR = 0.5
DEFAULT_MAX_BACKOFF_WAIT = 120.0
DEFAULT_RESPECT_RETRY_AFTER_HEADER = True


@dataclass(frozen=True)
class _ProxySettings:
    """Resolved proxy settings for one client."""

    https_proxy: str | None = None
    all_proxy: str | None = None
    no_proxy: str | None = None
    https_proxy_source: str | None = None
    all_proxy_source: str | None = None


class _RetryTransport(httpx2.BaseTransport):  # type: ignore[misc]
    """Retry selected HTTP requests using an httpx2 transport."""

    def __init__(
        self,
        transport: httpx2.BaseTransport,
        retry_total: int,
        backoff_factor: float,
        max_backoff_wait: float,
        respect_retry_after_header: bool,
    ) -> None:
        self._transport = transport
        self._retry_total = retry_total
        self._backoff_factor = backoff_factor
        self._max_backoff_wait = max_backoff_wait
        self._respect_retry_after_header = respect_retry_after_header

    def close(self) -> None:
        """Close the wrapped transport."""
        self._transport.close()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Send a request, retrying transient network and HTTP failures."""
        retryable_methods = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"}
        retryable_statuses = {429, 502, 503, 504}
        response: httpx2.Response | None = None

        for attempt in range(self._retry_total + 1):
            if response is not None:
                response.close()

            try:
                response = self._transport.handle_request(request)
            except httpx2.RequestError:
                if (
                    request.method not in retryable_methods
                    or attempt >= self._retry_total
                ):
                    raise
                self._sleep(attempt)
                continue

            if (
                request.method not in retryable_methods
                or response.status_code not in retryable_statuses
                or attempt >= self._retry_total
            ):
                return response

            self._sleep(attempt, response)

        if response is None:
            raise RuntimeError("Retry transport completed without a response")
        return response

    def _sleep(self, attempt: int, response: httpx2.Response | None = None) -> None:
        """Wait before a retry, honoring Retry-After when configured."""
        delay = self._backoff_factor * (2**attempt)
        if self._respect_retry_after_header and response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    retry_at = parsedate_to_datetime(retry_after).timestamp()
                    delay = max(0.0, retry_at - time.time())
        time.sleep(min(self._max_backoff_wait, delay))


class _ProxyRoutingTransport(httpx2.BaseTransport):  # type: ignore[misc]
    """Route requests through scheme-aware proxy or direct transports."""

    def __init__(
        self,
        direct_transport: _RetryTransport,
        https_transport: _RetryTransport | None,
        all_transport: _RetryTransport | None,
        no_proxy: str | None,
    ) -> None:
        self._direct_transport = direct_transport
        self._https_transport = https_transport
        self._all_transport = all_transport
        self._no_proxy = no_proxy

    def close(self) -> None:
        """Close all unique transports owned by this router."""
        transports = {
            id(transport): transport
            for transport in (
                self._direct_transport,
                self._https_transport,
                self._all_transport,
            )
            if transport is not None
        }
        for transport in transports.values():
            transport.close()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Send a request using the selected proxy route."""
        host_value = request.url.host
        host = (
            host_value.decode("ascii") if isinstance(host_value, bytes) else host_value
        ).lower()
        if _matches_no_proxy(host, request.url.port, self._no_proxy):
            return self._direct_transport.handle_request(request)

        if request.url.scheme == "https" and self._https_transport is not None:
            return self._https_transport.handle_request(request)
        if self._all_transport is not None:
            return self._all_transport.handle_request(request)
        return self._direct_transport.handle_request(request)


def _create_retry_transport(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
    proxy: str | None = None,
) -> _RetryTransport:
    """Create a retry transport with the specified configuration."""
    transport = httpx2.HTTPTransport(proxy=proxy)
    return _RetryTransport(
        transport=transport,
        retry_total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
    )


def _create_client_transport(
    retry_total: int,
    backoff_factor: float,
    max_backoff_wait: float,
    respect_retry_after_header: bool,
    proxy: str | None,
    use_environment_proxy: bool,
    disable_proxy: bool,
    verbosity: int,
) -> _ProxyRoutingTransport:
    """Create a retrying, scheme-aware proxy routing transport."""
    settings = _resolve_proxy_settings(
        proxy=proxy,
        use_environment_proxy=use_environment_proxy,
        disable_proxy=disable_proxy,
    )
    if verbosity > 0:
        _log_proxy_settings(settings, explicit_proxy=proxy, disabled=disable_proxy)

    def create_transport(proxy_url: str | None) -> _RetryTransport:
        return _create_retry_transport(
            retry_total=retry_total,
            backoff_factor=backoff_factor,
            max_backoff_wait=max_backoff_wait,
            respect_retry_after_header=respect_retry_after_header,
            proxy=proxy_url,
        )

    direct_transport = create_transport(None)
    proxy_transports: dict[str, _RetryTransport] = {}
    for proxy_url in (settings.https_proxy, settings.all_proxy):
        if proxy_url is not None and proxy_url not in proxy_transports:
            proxy_transports[proxy_url] = create_transport(proxy_url)

    return _ProxyRoutingTransport(
        direct_transport=direct_transport,
        https_transport=(
            proxy_transports.get(settings.https_proxy)
            if settings.https_proxy is not None
            else None
        ),
        all_transport=(
            proxy_transports.get(settings.all_proxy)
            if settings.all_proxy is not None
            else None
        ),
        no_proxy=settings.no_proxy,
    )


def _resolve_proxy_settings(
    proxy: str | None,
    use_environment_proxy: bool,
    disable_proxy: bool,
) -> _ProxySettings:
    """Resolve explicit or curl-compatible environment proxy settings."""
    if proxy is not None and disable_proxy:
        raise ValueError("proxy and disable_proxy cannot both be configured")
    if disable_proxy:
        return _ProxySettings()
    no_proxy = _environment_value("NO_PROXY", "no_proxy")
    if proxy is not None:
        return _ProxySettings(all_proxy=proxy, no_proxy=no_proxy)
    if not use_environment_proxy:
        return _ProxySettings()
    https_proxy_source, https_proxy = _environment_setting("HTTPS_PROXY", "https_proxy")
    all_proxy_source, all_proxy = _environment_setting("ALL_PROXY", "all_proxy")
    return _ProxySettings(
        https_proxy=https_proxy,
        all_proxy=all_proxy,
        no_proxy=no_proxy,
        https_proxy_source=https_proxy_source,
        all_proxy_source=all_proxy_source,
    )


def _environment_value(*names: str) -> str | None:
    """Return the first non-empty environment value for the given names."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _environment_setting(*names: str) -> tuple[str | None, str | None]:
    """Return the name and first non-empty value of an environment setting."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return name, value
    return None, None


def _log_proxy_settings(
    settings: _ProxySettings,
    explicit_proxy: str | None,
    disabled: bool,
) -> None:
    """Log effective proxy selection without exposing credentials."""
    if disabled:
        logger.info("Proxy disabled")
        return
    if explicit_proxy is not None:
        logger.info(f"Using explicit proxy: {_redact_proxy_url(explicit_proxy)}")
        return
    if settings.https_proxy is not None:
        logger.info(
            f"Detected HTTPS proxy from {settings.https_proxy_source}: "
            f"{_redact_proxy_url(settings.https_proxy)}"
        )
    if settings.all_proxy is not None:
        logger.info(
            f"Detected all-protocol proxy from {settings.all_proxy_source}: "
            f"{_redact_proxy_url(settings.all_proxy)}"
        )


def _matches_no_proxy(host: str, port: int, no_proxy: str | None) -> bool:
    """Return whether a host and port match a curl-style NO_PROXY list."""
    if not no_proxy:
        return False
    for entry in no_proxy.split(","):
        candidate = entry.strip().lower()
        if not candidate:
            continue
        if candidate == "*":
            return True
        candidate_host, candidate_port = _split_no_proxy_entry(candidate)
        if candidate_port is not None and candidate_port != port:
            continue
        if _matches_no_proxy_host(host, candidate_host):
            return True
    return False


def _split_no_proxy_entry(entry: str) -> tuple[str, int | None]:
    """Split a NO_PROXY host entry and optional port."""
    if entry.startswith("["):
        closing_bracket = entry.find("]")
        if closing_bracket != -1:
            host = entry[1:closing_bracket]
            port = (
                entry[closing_bracket + 2 :]
                if entry[closing_bracket + 1 :].startswith(":")
                else ""
            )
            return host, int(port) if port else None
    if entry.count(":") == 1:
        host, port = entry.rsplit(":", 1)
        if port.isdigit():
            return host, int(port)
    return entry, None


def _matches_no_proxy_host(host: str, candidate: str) -> bool:
    """Match a hostname, IP address, or CIDR entry."""
    candidate = candidate.strip("[]")
    if "/" in candidate:
        try:
            return ipaddress.ip_address(host) in ipaddress.ip_network(
                candidate, strict=False
            )
        except ValueError:
            return False
    if candidate.startswith("."):
        return host.endswith(candidate)
    return host == candidate or host.endswith(f".{candidate}")


def _redact_proxy_url(proxy: str) -> str:
    """Remove proxy credentials before a proxy URL is written to logs."""
    parsed = urlsplit(proxy)
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


def _close_client() -> None:
    """Close the module-level client if it exists."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client(verbosity: int = 2) -> httpx2.Client:
    """Get the module-level HTTP client.

    Creates a new client with default retry settings if none exists.
    """
    global _client
    if _client is None:
        transport = _create_client_transport(
            retry_total=DEFAULT_RETRY_TOTAL,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            max_backoff_wait=DEFAULT_MAX_BACKOFF_WAIT,
            respect_retry_after_header=DEFAULT_RESPECT_RETRY_AFTER_HEADER,
            proxy=None,
            use_environment_proxy=True,
            disable_proxy=False,
            verbosity=verbosity,
        )
        _client = httpx2.Client(follow_redirects=True, transport=transport)
        atexit.register(_close_client)
    return _client


def configure_client(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
    proxy: str | None = None,
    use_environment_proxy: bool = True,
    disable_proxy: bool = False,
    verbosity: int = 2,
) -> None:
    """Configure the module-level client with specified retry settings.

    Closes any existing client and creates a new one with the given settings.
    """
    global _client
    _close_client()
    transport = _create_client_transport(
        retry_total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
        proxy=proxy,
        use_environment_proxy=use_environment_proxy,
        disable_proxy=disable_proxy,
        verbosity=verbosity,
    )
    _client = httpx2.Client(follow_redirects=True, transport=transport)
    atexit.register(_close_client)


def create_configured_client(
    retry_total: int = DEFAULT_RETRY_TOTAL,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_wait: float = DEFAULT_MAX_BACKOFF_WAIT,
    respect_retry_after_header: bool = DEFAULT_RESPECT_RETRY_AFTER_HEADER,
    proxy: str | None = None,
    use_environment_proxy: bool = True,
    disable_proxy: bool = False,
    verbosity: int = 2,
) -> httpx2.Client:
    """Create an independent HTTP client with specified retry settings.

    The caller is responsible for closing this client.
    """
    transport = _create_client_transport(
        retry_total=retry_total,
        backoff_factor=backoff_factor,
        max_backoff_wait=max_backoff_wait,
        respect_retry_after_header=respect_retry_after_header,
        proxy=proxy,
        use_environment_proxy=use_environment_proxy,
        disable_proxy=disable_proxy,
        verbosity=verbosity,
    )
    return httpx2.Client(follow_redirects=True, transport=transport)


def _extract_filename_from_content_disposition(header: str | None) -> str | None:
    """Extract filename from Content-Disposition header.

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
    """Download a file from URL using httpx2 with streaming.

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
        httpx2.TimeoutException: If the connection times out.
        httpx2.HTTPStatusError: If the server returns an error status.
        httpx2.RequestError: If a request error occurs.
        ValueError: If no filename can be determined.

    """
    with get_client(verbosity=verbosity).stream(
        "GET", url, timeout=timeout
    ) as response:
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
