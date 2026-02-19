#!/usr/bin/env python3
"""CLI for retrieving transcriptomic data from the ENA Portal API by taxonomy ID.

Usage:
    python ena_fetch.py --tax_id 2759

The script queries the ENA Portal API for transcriptomic runs and writes
results to a TSV file or stdout. The query uses the ``tax_tree()`` operator
to include subordinate taxa and filters on ``library_strategy="RNA-Seq"``
by default. Progress is logged to stderr.

Designed for Python 3.10+
"""

from __future__ import annotations

import argparse
import logging
import sys

from ena_api import (
    build_post_data,
    create_session,
    fetch_stream,
    write_response,
)

# configure module-level logger
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch ENA transcriptomic run metadata for a tax_id."
    )
    parser.add_argument(
        "--tax_id",
        required=True,
        help="NCBI taxonomy identifier to query (string or integer)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output file path (TSV). Use '-' to write to stdout. "
            "Defaults to ena_transcriptomics_<tax_id>.tsv"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10_000_000,
        help="Maximum number of records to request in a single API call",
    )
    parser.add_argument(
        "--strategy",
        default="RNA-Seq",
        help="Library strategy value to filter (default 'RNA-Seq').",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tax_id = args.tax_id
    output = args.output or f"ena_transcriptomics_{tax_id}.tsv"
    limit = args.limit
    strategy = args.strategy

    logger.info("tax_id=%s strategy=%s limit=%d output=%s", tax_id, strategy, limit, output)

    session = create_session()

    # prepare writer
    if output == "-":
        out_fh = sys.stdout
    else:
        out_fh = open(output, "w", encoding="utf-8")

    try:
        # The ENA Portal search endpoint does not currently support an
        # "offset" parameter (requests return 400).  The example usage relies
        # on specifying a very large ``limit`` instead.  We therefore perform a
        # single request and write whatever is returned.  If the API later
        # implements paging we can revisit this loop.
        data = build_post_data(tax_id, limit, strategy)
        resp = fetch_stream(session, data)

        lines = write_response(resp, out_fh)
        logger.info("Wrote %d lines", lines)
        if output != "-":
            logger.info("Output saved to %s", output)
    finally:
        if output != "-":
            out_fh.close()


if __name__ == "__main__":
    main()
