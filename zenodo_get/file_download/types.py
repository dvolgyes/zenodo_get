"""Callable contracts for file download policies."""

from collections.abc import Callable

CheckHash = Callable[[str, str], tuple[str, str]]
DownloadFile = Callable[..., str]
