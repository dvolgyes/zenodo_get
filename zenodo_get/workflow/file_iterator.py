"""Create progress-aware file iterators."""

from collections.abc import Iterable
from typing import Any, cast

from tqdm import tqdm


def file_iterator(
    files: list[dict[str, Any]], verbosity: int
) -> Iterable[tuple[int, dict[str, Any]]]:
    """Create the configured progress iterator."""
    if verbosity >= 2:
        return cast(
            Iterable[tuple[int, dict[str, Any]]],
            tqdm(
                enumerate(files),
                total=len(files),
                desc="Files",
                leave=False,
                unit="file",
            ),
        )
    return enumerate(files)
