"""Resolve configured record identifiers."""

from collections.abc import Callable
from typing import cast

import httpx2

from zenodo_get.workflow.handle_workflow_error import handle_workflow_error
from zenodo_get.workflow.resolve_doi import resolve_doi


def resolve_record_id(
    actual_record: str | None,
    actual_doi: str | None,
    timeout: float,
    exceptions_on_failure: bool,
    get_client: Callable[[], httpx2.Client],
) -> str:
    """Resolve the configured record or DOI and validate its presence."""
    record_id = (
        resolve_doi(actual_doi, timeout, exceptions_on_failure, get_client)
        if actual_doi is not None
        else actual_record
    )
    if record_id is None:
        handle_workflow_error(
            "No record ID or DOI specified.",
            ValueError,
            exceptions_on_failure,
        )
    return cast(str, record_id).strip()
