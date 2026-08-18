"""Resolve a DOI to a record identifier."""

from collections.abc import Callable

import httpx2

from zenodo_get.workflow.handle_workflow_error import handle_workflow_error


def resolve_doi(
    doi: str,
    timeout: float,
    exceptions_on_failure: bool,
    get_client: Callable[[], httpx2.Client],
) -> str:
    """Resolve a DOI to its final Zenodo record identifier."""
    doi_url = doi if doi.startswith("http") else "https://doi.org/" + doi
    try:
        response = get_client().get(doi_url, timeout=timeout)
        response.raise_for_status()
        return str(response.url).split("/")[-1]
    except httpx2.TimeoutException:
        handle_workflow_error(
            f"Timeout resolving DOI: {doi_url}",
            ConnectionError,
            exceptions_on_failure,
        )
    except httpx2.HTTPStatusError as error:
        handle_workflow_error(
            f"HTTP error resolving DOI {doi_url}: {error.response.status_code} - "
            f"{error.response.reason_phrase}",
            ValueError,
            exceptions_on_failure,
        )
    except httpx2.RequestError as error:
        handle_workflow_error(
            f"Error resolving DOI {doi_url}: {error}",
            ConnectionError,
            exceptions_on_failure,
        )
    raise RuntimeError("DOI resolution completed without a record identifier")
