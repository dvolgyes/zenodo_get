"""Behavioral tests for proxy routing."""

from __future__ import annotations

import select
import socket
import socketserver
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from zenodo_get.downloader import create_configured_client
from zenodo_get.zget import cli


class _OriginHandler(BaseHTTPRequestHandler):
    """Serve a deterministic local response."""

    def do_GET(self) -> None:
        """Return the direct-origin response."""
        body = b"origin"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Suppress test-server logging."""


class _HttpProxyHandler(BaseHTTPRequestHandler):
    """Return a response directly from a local forward proxy."""

    def do_GET(self) -> None:
        """Record the proxied request and return proxy content."""
        self.server.seen.append(self.path)  # type: ignore[attr-defined]
        body = b"http-proxy"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Suppress test-server logging."""


class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
    """Threaded test server with reusable ephemeral ports."""

    allow_reuse_address = True
    daemon_threads = True


class _Socks5Handler(socketserver.BaseRequestHandler):
    """Minimal no-auth SOCKS5 CONNECT server for tests."""

    def handle(self) -> None:
        """Accept one SOCKS5 connection and relay bytes."""
        client = self.request
        version, method_count = _read_exact(client, 2)
        if version != 5:
            return
        _read_exact(client, method_count)
        client.sendall(b"\x05\x00")

        version, command, _reserved, address_type = _read_exact(client, 4)
        if version != 5 or command != 1:
            return
        target_host = _read_socks_host(client, address_type)
        target_port = int.from_bytes(_read_exact(client, 2), "big")

        try:
            upstream = socket.create_connection((target_host, target_port), timeout=5)
        except OSError:
            client.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            return

        with upstream:
            client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            _relay(client, upstream)


def _read_exact(connection: socket.socket, size: int) -> bytes:
    """Read exactly ``size`` bytes from a socket."""
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("SOCKS5 client closed the connection")
        data += chunk
    return data


def _read_socks_host(connection: socket.socket, address_type: int) -> str:
    """Read a SOCKS5 destination address."""
    if address_type == 1:
        return socket.inet_ntoa(_read_exact(connection, 4))
    if address_type == 3:
        size = _read_exact(connection, 1)[0]
        return _read_exact(connection, size).decode("idna")
    if address_type == 4:
        return socket.inet_ntop(socket.AF_INET6, _read_exact(connection, 16))
    raise ValueError(f"Unsupported SOCKS5 address type: {address_type}")


def _relay(left: socket.socket, right: socket.socket) -> None:
    """Relay bytes between two connected sockets."""
    sockets = [left, right]
    while True:
        readable, _, _ = select.select(sockets, [], [], 2)
        if not readable:
            return
        for source in readable:
            payload = source.recv(65536)
            if not payload:
                return
            destination = right if source is left else left
            destination.sendall(payload)


@dataclass(frozen=True)
class _Origin:
    """Local origin endpoint."""

    url: str
    server: ThreadingHTTPServer


@dataclass(frozen=True)
class _Proxy:
    """Local proxy endpoint."""

    url: str
    server: socketserver.BaseServer


@pytest.fixture
def origin_server() -> Iterator[_Origin]:
    """Start a local HTTP origin server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OriginHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Origin(
            url=f"http://127.0.0.1:{server.server_port}/file.txt",
            server=server,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def http_proxy() -> Iterator[_Proxy]:
    """Start a local HTTP forward proxy."""
    server = _ThreadingTCPServer(("127.0.0.1", 0), _HttpProxyHandler)
    server.seen = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Proxy(url=f"http://127.0.0.1:{server.server_address[1]}", server=server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def socks_proxy() -> Iterator[_Proxy]:
    """Start a local no-auth SOCKS5 proxy."""
    server = _ThreadingTCPServer(("127.0.0.1", 0), _Socks5Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Proxy(
            url=f"socks5://127.0.0.1:{server.server_address[1]}", server=server
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _clear_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove proxy variables that could affect an isolated test."""
    for name in (
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(name, raising=False)


def test_explicit_http_proxy_routes_request(
    http_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an explicit HTTP proxy receives the request."""
    _clear_proxy_environment(monkeypatch)
    client = create_configured_client(proxy=http_proxy.url, verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "http-proxy"
    assert http_proxy.server.seen  # type: ignore[attr-defined]


def test_no_proxy_environment_bypasses_proxy(
    http_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that NO_PROXY bypasses a configured all-protocol proxy."""
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("ALL_PROXY", http_proxy.url)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    client = create_configured_client(verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "origin"
    assert not http_proxy.server.seen  # type: ignore[attr-defined]


def test_https_proxy_does_not_proxy_http_request(
    http_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that HTTPS_PROXY is not used for HTTP requests."""
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", http_proxy.url)
    client = create_configured_client(verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "origin"
    assert not http_proxy.server.seen  # type: ignore[attr-defined]


def test_http_proxy_environment_is_ignored(
    http_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test curl-compatible rejection of HTTP_PROXY variables."""
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", http_proxy.url)
    monkeypatch.setenv("http_proxy", http_proxy.url)
    client = create_configured_client(verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "origin"
    assert not http_proxy.server.seen  # type: ignore[attr-defined]


def test_no_proxy_flag_bypasses_environment_proxy(
    http_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that explicit direct mode bypasses environment proxies."""
    _clear_proxy_environment(monkeypatch)
    monkeypatch.setenv("ALL_PROXY", http_proxy.url)
    client = create_configured_client(disable_proxy=True, verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "origin"
    assert not http_proxy.server.seen  # type: ignore[attr-defined]


def test_socks5_proxy_routes_request(
    socks_proxy: _Proxy,
    origin_server: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an explicit SOCKS5 proxy routes the request."""
    _clear_proxy_environment(monkeypatch)
    client = create_configured_client(proxy=socks_proxy.url, verbosity=0)
    try:
        response = client.get(origin_server.url)
    finally:
        client.close()

    assert response.text == "origin"


def test_cli_proxy_option_configures_explicit_proxy() -> None:
    """Test that --proxy reaches the client factory."""
    with (
        patch("zenodo_get.zget.configure_client") as configure,
        patch("zenodo_get.zget._zenodo_download_logic"),
    ):
        result = CliRunner().invoke(
            cli,
            ["123", "--proxy", "socks5://proxy.example:1080", "--verbosity", "0"],
        )

    assert result.exit_code == 0
    assert configure.call_args.kwargs["proxy"] == "socks5://proxy.example:1080"
    assert configure.call_args.kwargs["use_environment_proxy"] is False
    assert configure.call_args.kwargs["disable_proxy"] is False


def test_cli_no_proxy_option_disables_proxy() -> None:
    """Test that --no-proxy disables environment proxy use."""
    with (
        patch("zenodo_get.zget.configure_client") as configure,
        patch("zenodo_get.zget._zenodo_download_logic"),
    ):
        result = CliRunner().invoke(cli, ["123", "--no-proxy", "--verbosity", "0"])

    assert result.exit_code == 0
    assert configure.call_args.kwargs["proxy"] is None
    assert configure.call_args.kwargs["use_environment_proxy"] is False
    assert configure.call_args.kwargs["disable_proxy"] is True


def test_cli_proxy_options_are_mutually_exclusive() -> None:
    """Test that --proxy and --no-proxy cannot be combined."""
    result = CliRunner().invoke(
        cli,
        ["123", "--proxy", "http://proxy.example:8080", "--no-proxy"],
    )

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
