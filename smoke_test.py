from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import importlib
from pathlib import Path
from typing import NoReturn


def _header(title: str) -> None:
    print(f"\n== {title} ==")


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _fail(msg: str, code: int = 1) -> NoReturn:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


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
    try:
        for mod in ("requests", "urllib3", "pandas", "ena"):
            importlib.import_module(mod)
        import ena
    except ImportError as exc:
        _fail(
            "Could not import required dependencies.\n"
            "From repo root, run one of:\n"
            "  - pip install -e .\n"
            "  - pip install .\n"
            f"Import error: {exc!r}"
        )

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


def _live_ena_fetch(tax_id: str, limit: int) -> None:
    _header("Live ENA fetch")

    from ena.api import build_post_data, create_session, fetch_stream, write_response
    from ena.summary import generate_summary
    import requests

    expected_cols = {
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
    }

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
        )
        try:
            resp = fetch_stream(session, data)
        except requests.RequestException as exc:
            _fail(
                "Live ENA request failed. This tool requires network access to the ENA Portal API.\n"
                f"Error: {exc!r}"
            )

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
    limit = 5

    _check_python_version()
    _check_imports()
    _check_cli_wiring()
    _check_query_building(tax_id)
    _live_ena_fetch(tax_id, limit)

    _header("Result")
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
