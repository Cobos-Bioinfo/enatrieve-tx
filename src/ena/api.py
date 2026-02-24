"""ENA Portal API client library for querying transcriptomic data.

This module provides a clean API for fetching transcriptomic run metadata
from the ENA Portal by NCBI taxonomy ID, including subordinate taxa via
the ``tax_tree()`` operator.

Key functions:
    - build_query: construct a search query for a given tax_id
    - build_post_data: assemble the POST payload for the API
    - create_session: return a requests.Session with retry logic
    - fetch_stream: perform the HTTP request
    - write_response: stream response content to a file handle
"""

from __future__ import annotations

import logging
from typing import TextIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

API_URL = "https://www.ebi.ac.uk/ena/portal/api/search"

logger = logging.getLogger(__name__)


def build_query(tax_id: str, strategy: str, operator: str = "tax_tree") -> str:
    """Return the query string for the given taxonomic id and library strategy.

    Args:
        tax_id: NCBI taxonomy identifier.
        strategy: Library strategy value (e.g., "RNA-Seq").
        operator: Taxonomy operator to use; e.g. "tax_tree" or "tax_eq".

    Returns:
        A query string suitable for the ENA Portal API.
    """
    return f"{operator}({tax_id}) AND library_strategy=\"{strategy}\""


def build_post_data(
    tax_id: str, limit: int, strategy: str, operator: str = "tax_tree"
) -> dict[str, str]:
    """Construct the POST payload for the ENA portal search endpoint.

    The API does not currently accept an ``offset`` parameter; pagination
    is achieved by requesting a sufficiently large ``limit``. If the service
    adds explicit paging in future, this function can be extended.

    Args:
        tax_id: NCBI taxonomy identifier.
        limit: Maximum number of records to request.
        strategy: Library strategy value.

    Returns:
        A dict suitable for POST body encoding.
    """
    fields = [
        "run_accession",
        "experiment_title",
        "tax_id",
        "tax_lineage",
        "scientific_name",
        "library_source",
        "library_strategy",
        "instrument_platform",
        "read_count",
        "first_public",
    ]
    return {
        "result": "read_run",
        "query": build_query(tax_id, strategy, operator),
        "fields": ",".join(fields),
        "format": "tsv",
        "limit": str(limit),
    }


def create_session() -> requests.Session:
    """Return a requests.Session preconfigured with retry/backoff logic.

    The session is configured to retry on idempotent methods (POST included)
    with a 5-attempt limit and exponential backoff for transient failures
    (429, 500, 502, 503, 504).

    Returns:
        A configured requests.Session.
    """
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
    return session


def fetch_stream(
    session: requests.Session, data: dict[str, str]
) -> requests.Response:
    """Perform the POST request and return the Response object with streaming.

    Args:
        session: A configured requests.Session.
        data: POST body dict (will be form-encoded by requests).

    Returns:
        The requests.Response object.

    Raises:
        requests.RequestException: On network error or HTTP status != 200.
    """
    logger.info("Sending query to ENA API")
    resp = session.post(API_URL, data=data, timeout=30, stream=True)
    try:
        resp.raise_for_status()
    except requests.HTTPError as _exc:
        logger.error("HTTP error %s: %s", resp.status_code, resp.text.strip())
        raise
    return resp


def write_response(resp: requests.Response, out_fh: TextIO) -> int:
    """Write the text from ``resp`` to file-like object ``out_fh``.

    Streams the response content line-by-line to avoid loading the entire
    dataset into memory.

    Args:
        resp: A requests.Response object.
        out_fh: An open file handle or file-like object.

    Returns:
        The number of lines written (including header).
    """
    count = 0
    for chunk in resp.iter_lines(decode_unicode=True):
        if chunk is None:
            continue
        text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")
        out_fh.write(text + "\n")
        count += 1
    return count
