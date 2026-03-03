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
from ena.summary import generate_summary, REQUIRED_COLUMNS

logger = logging.getLogger(__name__)


def load_available_fields() -> list[str]:
    """Load the list of available ENA fields from the bundled data file.
    
    Returns:
        List of available field names.
        
    Raises:
        FileNotFoundError: If the fields file cannot be found.
    """
    # Try to find the fields file in the package data directory
    fields_file = Path(__file__).parent / "data" / "ena_fields.txt"
    
    if not fields_file.exists():
        raise FileNotFoundError(
            f"Fields reference file not found at {fields_file}. "
            "This file should be bundled with the package."
        )
    
    fields = []
    with open(fields_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                fields.append(line)
    
    return fields


def display_available_fields() -> None:
    """Display all available ENA Portal API fields to stdout and exit."""
    try:
        fields = load_available_fields()
        print("Available ENA Portal API fields for read_run result type:")
        print("=" * 60)
        for field in fields:
            print(field)
        print("=" * 60)
        print(f"Total: {len(fields)} fields available")
        print()
        print("Usage: enatrieve-tx --fields run_accession,tax_id,read_count ...")
        print("Note: The ENA API always includes 'run_accession' in the response")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments into an argparse.Namespace object."""
    parser = argparse.ArgumentParser(
        description="Fetch ENA transcriptomic run metadata for a tax_id."
    )

    # Required Input
    parser.add_argument(
        "-t",
        "--tax-id",
        dest="tax_id",
        required=True,
        help="NCBI taxonomy identifier to query (string or integer)",
    )

    # Query Parameters
    parser.add_argument(
        "-s",
        "--library-strategy",
        dest="strategy",
        default="RNA-Seq",
        help="Library strategy value to filter (default 'RNA-Seq').",
    )
    parser.add_argument(
        "-n",
        "--max-records",
        dest="max_records",
        type=int,
        default=10000,
        help="Maximum number of records to request (default: 10000; use 0 for all results / no limit)",
    )
    parser.add_argument(
        "-e",
        "--exact-match",
        dest="exact",
        action="store_true",
        help="Use exact taxonomy match (tax_eq) instead of tax_tree",
    )

    # Output Control
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        default=None,
        help=(
            "Output file path (extension auto-added based on --format). Use '-' to write to stdout. "
            "Defaults to enatrieved_<tax_id>_<strategy>[_exact].<format>"
        ),
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="output_format",
        choices=["tsv", "json"],
        default="tsv",
        help="Output format (default: tsv)",
    )
    parser.add_argument(
        "-m",
        "--summary",
        dest="summary",
        action="store_true",
        help="Generate a metadata summary table (written to stderr). Not available when output is stdout.",
    )

    # Logging
    parser.add_argument(
        "-l",
        "--log-file",
        dest="log_file",
        default=None,
        help="Log file path (default: logs/<timestamp>_<tax_id>_<strategy>[_exact].log). Set to '' to disable file logging.",
    )

    # Field Customization
    parser.add_argument(
        "--fields",
        dest="fields",
        default=None,
        help="Comma-separated list of field names to retrieve (e.g., 'run_accession,tax_id,read_count'). "
             "If not specified, uses default minimal fields. Note: ENA API always includes 'run_accession'.",
    )
    parser.add_argument(
        "--list-fields",
        dest="list_fields",
        action="store_true",
        help="Display all available ENA fields and exit. Cannot be used with other options.",
    )

    return parser.parse_args()


def setup_logging(
    log_file: str | None,
    tax_id: str | None = None,
    strategy: str | None = None,
    exact: bool = False,
) -> None:
    """Configure logging with both stderr and optional file handler.

    Args:
        log_file: Path to log file. If None, creates timestamped log in logs/ directory.
                  If empty string, disables file logging (stderr only).
                  If a path is provided, uses it as-is without timestamps.
        tax_id: NCBI taxonomy identifier (used in auto-generated log filename).
        strategy: Library strategy value (used in auto-generated log filename).
        exact: Whether exact taxonomy match is used (adds _exact suffix to log filename).
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
            parts = [timestamp]
            if tax_id:
                parts.append(tax_id)
            if strategy:
                parts.append(strategy)
            if exact:
                parts.append("exact")
            log_filename = "_".join(parts) + ".log"
            log_path = Path(f"logs/{log_filename}")
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
    # Handle --list-fields before arg parsing (standalone operation)
    if "--list-fields" in sys.argv:
        display_available_fields()
        sys.exit(0)
    
    args = parse_args()

    tax_id = args.tax_id
    max_records = args.max_records
    strategy = args.strategy
    exact = getattr(args, "exact", False)
    operator = "tax_eq" if exact else "tax_tree"
    output_format = args.output_format

    # Parse user-provided fields
    user_fields = None
    if args.fields:
        user_fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    
    # Auto-add summary-required fields if summary is requested
    if args.summary and user_fields is not None:
        missing_fields = REQUIRED_COLUMNS - set(user_fields)
        if missing_fields:
            logger.warning(
                "Adding required fields for summary generation: %s",
                ", ".join(sorted(missing_fields))
            )
            user_fields.extend(sorted(missing_fields))

    # Determine file extension based on format
    extension = "tsv" if output_format == "tsv" else "json"

    # Generate output filename
    if args.output is None:
        # Default filename pattern
        parts = ["enatrieved", tax_id, strategy]
        if exact:
            parts.append("exact")
        output = "_".join(parts) + f".{extension}"
    elif args.output == "-":
        # Stdout - no extension needed
        output = "-"
    else:
        # User-specified filename - always add extension
        output = f"{args.output}.{extension}"

    setup_logging(args.log_file, tax_id, strategy, exact)

    logger.info(
        "tax_id=%s strategy=%s max_records=%d format=%s output=%s",
        tax_id, strategy, max_records, output_format, output
    )
    logger.info("Using taxonomy operator: %s", operator)

    session = create_session()

    # prepare writer
    if output == "-":
        out_fh = sys.stdout
    else:
        out_fh = open(output, "w", encoding="utf-8")

    try:
        # The ENA Portal search endpoint does not currently support an
        # "offset" parameter (requests return 400). All matching records are
        # fetched in a single request. The default max_records is 0 (no limit).
        # If the API later implements paging we can revisit this approach.
        data = build_post_data(
            tax_id, max_records, strategy, operator, output_format, fields=user_fields
        )
        logger.info("Query string: %s", data["query"])
        logger.info("Requested fields: %s", data["fields"])
        resp = fetch_stream(session, data)

        lines = write_response(resp, out_fh)
        logger.info("Wrote %d lines", lines)
        if output != "-":
            logger.info("Output saved to %s", output)
    finally:
        if output != "-":
            out_fh.close()

    if args.summary:
        if output != "-":
            logger.info("Generating summary statistics...")
            generate_summary(output, output_format=output_format)
        else:
            logger.warning("Summary statistics are not available when outputting to stdout.")
