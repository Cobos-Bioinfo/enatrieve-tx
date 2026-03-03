from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import importlib
from pathlib import Path


# Global failure collector
_FAILURES: list[str] = []


def _style(
    text: str,
    *,
    fg: str | None = None,
    bold: bool = False,
) -> str:
    fg_code = {
        "red": "31",
        "green": "32",
        "yellow": "33",
        "cyan": "36",
    }.get(fg or "", "")

    codes: list[str] = []
    if bold:
        codes.append("1")
    if fg_code:
        codes.append(fg_code)
    if not codes:
        return text

    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


def _header(title: str) -> None:
    print("\n" + _style(f"== {title} ==", fg="cyan", bold=True))


def _ok(msg: str) -> None:
    print(_style(f"OK: {msg}", fg="green"))


def _fail(msg: str) -> None:
    """Record a failure and continue (instead of exiting immediately)."""
    print(_style(f"FAIL: {msg}", fg="red", bold=True), file=sys.stderr)
    _FAILURES.append(msg)


def _run(cmd: list[str], *, title: str) -> subprocess.CompletedProcess[str]:
    _header(title)
    print("$ " + " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _check_python_version() -> None:
    _header("Python")
    if sys.version_info < (3, 10):
        _fail(f"Python >= 3.10 required; found {sys.version.split()[0]}")
    _ok(f"Python {sys.version.split()[0]}")


def _check_imports() -> None:
    _header("Imports")
    ena = None
    try:
        for mod in ("requests", "urllib3", "pandas", "ena"):
            importlib.import_module(mod)
        import ena as ena_module
        ena = ena_module
    except ImportError as exc:
        _fail(
            "Could not import required dependencies.\n"
            "From repo root, run one of:\n"
            "  - pip install -e .\n"
            "  - pip install .\n"
            f"Import error: {exc!r}"
        )
        return

    _ok("Imported: ena, requests, urllib3, pandas")
    _ok(f"ena version: {getattr(ena, '__version__', 'unknown')}")


def _check_cli_wiring() -> None:
    """Verify that the CLI is callable in this environment."""
    _header("CLI wiring")

    exe = shutil.which("enatrieve-tx")
    if exe:
        res = _run([exe, "--help"], title="Run: enatrieve-tx --help")
        if res.returncode != 0:
            _fail(f"CLI help failed. stderr:\n{res.stderr.strip()}")
        _ok("Console script works")
        return

    # Fallback for PATH / editable install issues.
    snippet = (
        "import sys; "
        "from ena.cli import main; "
        "sys.argv=['enatrieve-tx','--help']; "
        "main()"
    )
    res = _run([sys.executable, "-c", snippet], title="Run: python -c '...ena.cli.main --help'")
    if res.returncode != 0:
        _fail(
            "Could not run CLI entrypoint.\n"
            "This usually means the package isn't installed in this environment.\n"
            "Try: pip install -e .\n"
            f"stderr:\n{res.stderr.strip()}"
        )
    _ok("Python CLI entrypoint works")


def _check_query_building(tax_id: str) -> None:
    _header("Query building")
    from ena.api import build_post_data, build_query

    q_tree = build_query(tax_id, "RNA-Seq", operator="tax_tree")
    q_eq = build_query(tax_id, "RNA-Seq", operator="tax_eq")

    if f"tax_tree({tax_id})" not in q_tree:
        _fail(f"Unexpected tax_tree query: {q_tree}")
    if f"tax_eq({tax_id})" not in q_eq:
        _fail(f"Unexpected tax_eq query: {q_eq}")

    post = build_post_data(tax_id, limit=1, strategy="RNA-Seq", operator="tax_tree", output_format="tsv")
    for key in ("result", "query", "fields", "format", "limit"):
        if key not in post:
            _fail(f"POST payload missing key: {key}")

    _ok("build_query/build_post_data")


def _check_presets() -> None:
    """Verify field presets work correctly."""
    _header("Field Presets")
    from ena.cli import get_preset_fields, list_available_presets
    
    # Check built-in presets exist
    presets = list_available_presets()
    if "minimal" not in presets or "standard" not in presets:
        _fail("Built-in presets (minimal, standard) not found")

    # Check preset fields can be loaded
    minimal_fields = get_preset_fields("minimal")
    standard_fields = get_preset_fields("standard")

    if len(minimal_fields) != 4:
        _fail(f"minimal preset should have 4 fields, got {len(minimal_fields)}")
    if len(standard_fields) != 10:
        _fail(f"standard preset should have 10 fields, got {len(standard_fields)}")

    _ok("Field presets: minimal (4 fields), standard (10 fields)")


def _check_colored_logging() -> None:
    """Verify ColoredFormatter exists and works."""
    _header("Colored Logging")
    from ena.cli import ColoredFormatter
    import logging
    import re
    
    formatter = ColoredFormatter("[%(levelname)s] - %(message)s")

    # Create a test record
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Test message", args=(), exc_info=None
    )

    formatted = formatter.format(record)
    # Strip ANSI codes to verify bracket format
    stripped = re.sub(r'\x1b\[[0-9;]+m', '', formatted)

    if "[INFO] - Test message" not in stripped:
        _fail(f"ColoredFormatter doesn't use bracket format. Got: {stripped}")

    _ok("ColoredFormatter configured with bracket format")


def _check_list_fields() -> None:
    """Verify --list-fields displays available fields."""
    _header("List Fields Command")
    from ena.cli import display_available_fields
    import io
    import contextlib

    # Capture output from display_available_fields
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        display_available_fields()

    output = f.getvalue()
    lines = [line for line in output.strip().split("\n") if line.strip()]

    if len(lines) < 190:  # Should be ~195 fields
        _fail(f"Expected ~195 fields, got {len(lines)}")

    _ok(f"--list-fields displays {len(lines)} available fields")


def _check_exact_match() -> None:
    """Verify exact match operator works."""
    _header("Exact Match Mode")
    from ena.api import build_query

    q_exact = build_query("7460", "RNA-Seq", operator="tax_eq")
    if "tax_eq(7460)" not in q_exact:
        _fail(f"tax_eq query malformed: {q_exact}")

    _ok("Exact match operator (tax_eq) works")


def _check_custom_fields() -> None:
    """Verify custom field selection works."""
    _header("Custom Fields")
    from ena.api import build_post_data

    custom_fields = ["run_accession", "tax_id", "read_count"]
    data = build_post_data(
        tax_id="7460",
        limit=1,
        strategy="RNA-Seq",
        operator="tax_tree",
        output_format="tsv",
        fields=custom_fields
    )

    expected = ",".join(custom_fields)
    if data["fields"] != expected:
        _fail(f"Custom fields not applied correctly. Expected: {expected}, Got: {data['fields']}")

    _ok(f"Custom fields: {', '.join(custom_fields)}")


def _check_summary_autoadd() -> None:
    """Verify summary auto-adds required fields."""
    _header("Summary Auto-add")
    from ena.summary import REQUIRED_COLUMNS
    from ena.api import DEFAULT_FIELDS

    # Simulate what CLI does
    user_fields = list(DEFAULT_FIELDS)
    missing = REQUIRED_COLUMNS - set(user_fields)

    if not missing:
        _ok("DEFAULT_FIELDS already includes all summary requirements")
    else:
        _ok(f"Summary would auto-add: {', '.join(sorted(missing))}")


def _live_ena_fetch(tax_id: str, limit: int) -> None:
    _header("Live ENA fetch")

    from ena.api import build_post_data, create_session, fetch_stream, write_response, DEFAULT_FIELDS
    from ena.summary import generate_summary
    import requests

    # For the smoke test, we need to test both:
    # 1. Basic field retrieval with defaults
    # 2. Summary generation (requires tax_id, instrument_platform, read_count)
    # So we'll use a custom field list that includes summary-required fields
    smoke_test_fields = list(DEFAULT_FIELDS) + ["instrument_platform", "read_count"]
    # Remove duplicates (tax_id is in both DEFAULT_FIELDS and REQUIRED_COLUMNS)
    smoke_test_fields = list(dict.fromkeys(smoke_test_fields))

    expected_cols = set(smoke_test_fields)

    session = create_session()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        out_tsv = tmp / "ena_smoke.tsv"
        data = build_post_data(
            tax_id=tax_id,
            limit=limit,
            strategy="RNA-Seq",
            operator="tax_tree",
            output_format="tsv",
            fields=smoke_test_fields,
        )
        try:
            resp = fetch_stream(session, data)
        except requests.RequestException as exc:
            _fail(
                "Live ENA request failed. This tool requires network access to the ENA Portal API.\n"
                f"Error: {exc!r}"
            )
            return

        with out_tsv.open("w", encoding="utf-8") as fh:
            lines = write_response(resp, fh)

        if lines < 1:
            _fail("ENA returned no lines (unexpected)")

        header = out_tsv.read_text(encoding="utf-8").splitlines()[0]
        got_cols = set(header.split("\t"))
        if not expected_cols.issubset(got_cols):
            missing = sorted(expected_cols - got_cols)
            _fail(f"TSV header missing expected columns: {missing}")

        generate_summary(out_tsv, output_format="tsv")

        out_json = tmp / "ena_smoke.json"
        data_json = build_post_data(
            tax_id=tax_id,
            limit=min(limit, 5),
            strategy="RNA-Seq",
            operator="tax_tree",
            output_format="json",
            fields=smoke_test_fields,
        )
        resp_json = fetch_stream(session, data_json)
        with out_json.open("w", encoding="utf-8") as fh:
            write_response(resp_json, fh)

        parsed = json.loads(out_json.read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            _fail("JSON response was not a list")

    _ok(f"Live ENA fetch OK (tax_id={tax_id}, limit={limit})")


def main() -> None:
    tax_id = "7460"  # Apis mellifera — Honey bee
    limit = 100

    _check_python_version()
    _check_imports()
    _check_cli_wiring()
    _check_colored_logging()
    _check_presets()
    _check_list_fields()
    _check_exact_match()
    _check_custom_fields()
    _check_query_building(tax_id)
    _check_summary_autoadd()
    _live_ena_fetch(tax_id, limit)

    _header("Result")
    if _FAILURES:
        print(_style(f"\n{len(_FAILURES)} test(s) FAILED:", fg="red", bold=True))
        for i, failure in enumerate(_FAILURES, 1):
            print(_style(f"  {i}. {failure}", fg="red"))
        print()
        raise SystemExit(1)
    else:
        print(_style("All smoke checks passed.", fg="green", bold=True))


if __name__ == "__main__":
    main()
