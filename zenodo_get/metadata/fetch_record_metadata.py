"""Fetch metadata for one Zenodo record."""

from collections.abc import Callable
from typing import Any

import httpx2

from zenodo_get.metadata.handle_metadata_error import handle_metadata_error


def fetch_record_metadata(
    record_id: str,
    sandbox: bool,
    access_token: str | None,
    timeout_val: float,
    exceptions_on_failure: bool,
    get_client: Callable[[], httpx2.Client],
) -> dict[str, Any] | None:
    """Fetch and validate metadata for a Zenodo record."""
    api_url_base = (
        "https://sandbox.zenodo.org/api/records/"
        if sandbox
        else "https://zenodo.org/api/records/"
    )
    params: dict[str, str] = {}
    if access_token:
        params["access_token"] = access_token

    try:
        response = get_client().get(
            api_url_base + record_id,
            params=params,
            timeout=timeout_val,
        )
        response.raise_for_status()
        metadata = response.json()
        if not isinstance(metadata, dict):
            raise TypeError("Zenodo metadata response must be a JSON object")
        return metadata
    except httpx2.TimeoutException:
        handle_metadata_error(
            f"Timeout when fetching metadata for record {record_id} from "
            f"{api_url_base + record_id}",
            ConnectionError,
            exceptions_on_failure,
        )
    except httpx2.HTTPStatusError as error:
        handle_metadata_error(
            f"HTTP error fetching metadata for record {record_id}: "
            f"{error.response.status_code} - {error.response.reason_phrase} from "
            f"{api_url_base + record_id}",
            ValueError,
            exceptions_on_failure,
        )
    except httpx2.RequestError as error:
        handle_metadata_error(
            f"Error fetching metadata for record {record_id} from "
            f"{api_url_base + record_id}: {error}",
            ConnectionError,
            exceptions_on_failure,
        )
    return None
