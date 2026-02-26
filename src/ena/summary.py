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

# Required columns for summary generation
REQUIRED_COLUMNS = {"tax_id", "instrument_platform", "read_count"}


def _supports_color() -> bool:
    """
    Check if the terminal supports ANSI color codes.
    
    Returns:
        True if colors are supported, False otherwise.
    """
    # Check if stderr is a TTY
    if not hasattr(sys.stderr, "isatty") or not sys.stderr.isatty():
        return False

    # Check if we're on Windows and not in a modern terminal
    import platform
    if platform.system() == "Windows":
        # Windows Terminal, VSCode terminal, and modern consoles support ANSI
        # Check for ANSICON, WT_SESSION, or TERM environment variables
        import os
        return bool(
            os.environ.get("ANSICON")
            or os.environ.get("WT_SESSION")
            or os.environ.get("TERM")
        )

    # Unix-like systems typically support colors
    return True


def _colorize(text: str, color: str = "", bold: bool = False) -> str:
    """
    Apply ANSI color codes to text if terminal supports it.
    
    Args:
        text: Text to colorize.
        color: Color name (green, cyan, blue, yellow, red, magenta).
        bold: Whether to apply bold formatting.
    
    Returns:
        Colorized text if supported, plain text otherwise.
    """
    if not _supports_color():
        return text

    colors = {
        "green": "32",
        "cyan": "36",
        "blue": "34",
        "yellow": "33",
        "red": "31",
        "magenta": "35",
    }

    codes = []
    if bold:
        codes.append("1")
    if color in colors:
        codes.append(colors[color])

    if not codes:
        return text

    return f"\033[{';'.join(codes)}m{text}\033[0m"


def _format_number(n: int | float) -> str:
    """
    Format a number with commas for thousands separator.
    
    Args:
        n: Number to format.
    
    Returns:
        Formatted number string.
    """
    return f"{int(n):,}"


def _format_percentage(part: int | float, total: int | float) -> str:
    """
    Calculate and format a percentage.
    
    Args:
        part: Partial value.
        total: Total value.
    
    Returns:
        Formatted percentage string (e.g., "25.5%").
    """
    if total == 0:
        return "0%"
    pct = (part / total) * 100
    # Show one decimal if not a whole number, otherwise no decimals
    if pct == int(pct):
        return f"{int(pct)}%"
    return f"{pct:.1f}%"


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
            df = pd.read_json(path, dtype={"tax_id": str})
        else:
            # Default to TSV with tax_id explicitly as string
            df = pd.read_csv(path, sep="\t", dtype={"tax_id": str})
    except Exception as e:
        logger.error("Failed to read output file for summary: %s", e)
        return

    if df.empty:
        logger.warning("No data retrieved. Summary is empty.")
        return

    # Validate required columns using set arithmetic
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        logger.warning("Missing columns for summary: %s. Skipping summary.", missing_cols)
        return

    # --- Data Cleaning ---
    # Ensure numeric read counts
    df["read_count"] = pd.to_numeric(df["read_count"], errors="coerce").fillna(0)

    # Normalize instrument_platform: upper case, handle NaN, convert to categorical for memory efficiency
    df["instrument_platform"] = (
        df["instrument_platform"]
        .fillna("")
        .astype(str)
        .str.upper()
        .astype("category")
    )

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

    # 3. Total Reads (already cleaned to numeric above)
    total_reads = df["read_count"].sum()
    reads_long = df.loc[df["is_long_read"], "read_count"].sum()
    reads_short = df.loc[df["is_short_read"], "read_count"].sum()

    # --- Output ---

    # Build summary with enhanced formatting
    separator = "═" * 50

    summary_lines = [
        "",
        _colorize(separator, "cyan"),
        _colorize("EnaTrieve-TX Metadata Summary", "cyan", bold=True),
        _colorize(separator, "cyan"),
        "",
        _colorize("ORGANISMS", "green", bold=True),
        f"   Total Unique: {_colorize(_format_number(unique_organisms), 'cyan', bold=True)}",
        f"   ├─ Short-Read: {_colorize(_format_number(unique_with_short), 'blue')} "
        f"({_format_percentage(unique_with_short, unique_organisms)})",
        f"   └─ Long-Read:  {_colorize(_format_number(unique_with_long), 'yellow')} "
        f"({_format_percentage(unique_with_long, unique_organisms)})",
        "",
        _colorize("SEQUENCING RUNS", "green", bold=True),
        f"   Total: {_colorize(_format_number(total_runs), 'cyan', bold=True)}",
        f"   ├─ Short-Read: {_colorize(_format_number(runs_short), 'blue')} "
        f"({_format_percentage(runs_short, total_runs)})",
        f"   └─ Long-Read:  {_colorize(_format_number(runs_long), 'yellow')} "
        f"({_format_percentage(runs_long, total_runs)})",
        "",
        _colorize("TOTAL READS", "green", bold=True),
        f"   Total: {_colorize(_format_number(total_reads), 'cyan', bold=True)}",
        f"   ├─ Short-Read: {_colorize(_format_number(reads_short), 'blue')} "
        f"({_format_percentage(reads_short, total_reads)})",
        f"   └─ Long-Read:  {_colorize(_format_number(reads_long), 'yellow')} "
        f"({_format_percentage(reads_long, total_reads)})",
        "",
        _colorize(separator, "cyan"),
        ""
    ]

    # Print to stderr
    print("\n".join(summary_lines), file=sys.stderr)
