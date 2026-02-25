"""
Module to generate summary of retrieved metadata.
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys

import pandas as pd

logger = logging.getLogger(__name__)

# Platforms considered Long-Read
LONG_READ_PLATFORMS = {"OXFORD_NANOPORE", "PACBIO_SMRT"}


def generate_summary(file_path: str | Path, output_format: str = "tsv") -> None:
    """
    Reads the given output file and prints a metadata summary table to stderr.
    
    Args:
        file_path: Path to the TSV or JSON file containing ENA metadata.
        output_format: Output format, either "tsv" or "json" (default: "tsv").
    """
    path = Path(file_path)
    if not path.exists():
        logger.error("Cannot generate summary: File %s not found.", path)
        return

    try:
        # Use format parameter from CLI
        if output_format.lower() == "json":
            # ENA portal usually returns a JSON list.
            df = pd.read_json(path)
        else:
            # Default to TSV
            df = pd.read_csv(path, sep="\t")
    except Exception as e:
        logger.error("Failed to read output file for summary: %s", e)
        return

    if df.empty:
        logger.warning("No data retrieved. Summary is empty.")
        return

    # Check required columns. Note: tax_id is sometimes implicitly numeric.
    # instrument_platform and read_count are strings/numbers.
    required_cols = ["tax_id", "instrument_platform", "read_count"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        # Depending on exactly what API returns, sometimes columns might be missing if empty?
        # But we requested them.
        logger.warning("Missing columns for summary: %s. Skipping summary.", missing)
        return

    # Normalize instrument_platform
    # Convert to string, upper case, handle NaN
    # Note: NaN in pandas is float, check for data type first or fillna
    df["instrument_platform"] = df["instrument_platform"].fillna("").astype(str).str.upper()

    # Identify Long/Short reads
    df["is_long_read"] = df["instrument_platform"].isin(LONG_READ_PLATFORMS)
    df["is_short_read"] = ~df["is_long_read"]

    # --- Calculations ---

    # 1. Total Unique Organisms
    unique_organisms = df["tax_id"].nunique()

    # Organisms having Long/Short Data
    # Group by tax_id, check if any run is long/short
    org_stats = df.groupby("tax_id")[["is_long_read", "is_short_read"]].any()
    unique_with_long = org_stats["is_long_read"].sum()
    unique_with_short = org_stats["is_short_read"].sum()

    # 2. Total Runs
    total_runs = len(df)
    runs_long = df["is_long_read"].sum()
    runs_short = df["is_short_read"].sum()

    # 3. Total Reads
    # read_count can be numeric or string (if "234234"). Coerce to numeric.
    df["read_count_numeric"] = pd.to_numeric(df["read_count"], errors='coerce').fillna(0)

    total_reads = df["read_count_numeric"].sum()
    reads_long = df.loc[df["is_long_read"], "read_count_numeric"].sum()
    reads_short = df.loc[df["is_short_read"], "read_count_numeric"].sum()

    # --- Output ---

    # Format numbers with commas
    def fmt(n):
        return f"{int(n):,}"

    summary_text = [
        "",
        "-----------------------------",
        "EnaTrieve-TX Metadata Summary",
        "-----------------------------",
        f"Total Unique Organisms: {fmt(unique_organisms)}",
        f"  - With Long-Read Data: {fmt(unique_with_long)}",
        f"  - With Short-Read Data: {fmt(unique_with_short)}",
        "",
        f"Total Runs: {fmt(total_runs)}",
        f"  - Long-Read Runs: {fmt(runs_long)}",
        f"  - Short-Read Runs: {fmt(runs_short)}",
        "",
        f"Total Reads: {fmt(total_reads)}",
        f"  - Long-Read Reads: {fmt(reads_long)}",
        f"  - Short-Read Reads: {fmt(reads_short)}",
        "-----------------------------",
        ""
    ]

    # Print to stderr
    print("\n".join(summary_text), file=sys.stderr)
