"""Write record download URLs."""

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from zenodo_get.workflow.file_url import file_url


def write_urls(
    files: list[dict[str, Any]],
    record_id: str,
    download_url_base: str,
    output: str,
) -> None:
    """Write direct file URLs to stdout or a named file."""
    urls = (file_url(file_info, record_id, download_url_base) for file_info in files)
    if output == "-":
        for url in urls:
            sys.stdout.write(url + "\n")
    else:
        with Path(output).open("w") as output_file:
            output_file.writelines(url + "\n" for url in urls)
    logger.info(f"URL list written to {'stdout' if output == '-' else output}.")
