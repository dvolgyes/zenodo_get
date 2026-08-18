"""Filesystem boundary helpers for download workflows."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def cd(newdir: str | Path) -> Iterator[None]:
    """Temporarily change the current working directory."""
    previous_directory = Path.cwd()
    os.chdir(Path(newdir).expanduser())
    try:
        yield
    finally:
        os.chdir(previous_directory)


