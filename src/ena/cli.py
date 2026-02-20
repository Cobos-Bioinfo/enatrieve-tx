from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from ena import (
    build_post_data,
    create_session,
    fetch_stream,
    write_response,
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments into an argparse.Namespace object.

    Returns:
        argparse.Namespace: populated with the parsed arguments.
    """
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
    parser.add_argument(
        "--log",
        default=None,
        help="Log file path (default: logs/enatrieve_tx_<timestamp>.log). Set to '' to disable file logging.",
    )

    return parser.parse_args()


def setup_logging(log_file: str | None) -> None:
    """Configure logging with both stderr and optional file handler.

    Args:
        log_file: Path to log file. If None, creates timestamped log in logs/ directory.
                  If empty string, disables file logging (stderr only).
                  If a path is provided, uses it as-is without timestamps.
    """
    # Configure root logger to capture all levels
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Formatter for all handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Stderr handler (always enabled)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    root_logger.addHandler(stderr_handler)

    # File handler (if log_file is not empty string)
    if log_file != "":
        # Generate timestamped filename if log_file is None
        if log_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_path = Path(f"logs/enatrieve_tx_{timestamp}.log")
        else:
            log_path = Path(log_file)

        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logger.info("Logging to file: %s", log_path.absolute())


def main() -> None:
    """Main entry point for the CLI.

    Reads command-line arguments, constructs a single API query,
    writes the response to a TSV file or stdout, and logs progress
    to stderr and optionally to a log file.

    """
    args = parse_args()
    setup_logging(args.log)

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
