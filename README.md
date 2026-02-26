# ENA Transcriptomic Data Retriever (enatrieve_tx)

A Python tool for efficiently querying and downloading transcriptomic sequencing data from the EMBL-EBI ENA Portal API by NCBI taxonomy identifier.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![python](https://shields.io/badge/python-3.10+-orange)

## Overview

This project provides a modular Python library and CLI tool for retrieving RNA-Seq metadata from the ENA Portal. It uses the `tax_tree()` operator to automatically include all subordinate taxa, making it easy to fetch comprehensive transcriptomic datasets for entire clades or organism groups.

The tool streams results directly to TSV format, supports both file and stdout output, and includes automatic retry logic with exponential backoff for reliable API communication.

## Features

- Query ENA Portal API by NCBI taxonomy ID with automatic subordinate taxa inclusion
- Filter by sequencing strategy (default: RNA-Seq, easily configurable)
- Generate metadata summaries directly from the CLI (-m/--summary)
- Stream large result sets with minimal memory overhead
- Automatic retry handling with exponential backoff for transient failures
- Output to file or stdout for easy piping integration
- Detailed progress logging to stderr
- Type-hinted, modular design for reusability
- Comprehensive error handling

## Installation

1. Clone or download the repository:
   ```bash
   git clone https://github.com/Cobos-Bioinfo/enatrieve-tx.git
   cd enatrieve-tx
   ```

2. Install the package and its dependencies:
   ```bash
   # development install
   pip install -e .

   # or a normal install
   pip install .
   ```

## Smoke test (new clone)

After cloning and installing, you can run a quick smoke test to verify the CLI wiring, imports, and a small ENA fetch work on your machine.

This smoke test requires network access to the ENA Portal API.

```bash
python smoke_test.py
```

Defaults:
- Uses TaxID **7460** (Apis mellifera — Honey bee)
- Uses `max-records=5` for the live ENA call

## Usage

### Command-Line Interface

```
usage: enatrieve-tx [-h] -t TAX_ID [-s LIBRARY_STRATEGY] [-n MAX_RECORDS] [-e] [-o OUTPUT] [-f {tsv,json}] [-m] [-l LOG_FILE]

Fetch ENA transcriptomic run metadata for a tax_id.

options:
  -h, --help            show this help message and exit
  -t, --tax-id TAX_ID   NCBI taxonomy identifier to query (string or integer) [required]
  -s, --library-strategy LIBRARY_STRATEGY
                        Library strategy value to filter (default: RNA-Seq)
  -n, --max-records MAX_RECORDS
                        Maximum number of records to request (default: 0 = no limit)
  -e, --exact-match     Use exact taxonomy match (tax_eq) instead of tax_tree
  -o, --output OUTPUT   Output file path (extension auto-added based on --format). Use '-' to write to stdout.
                        Defaults to enatrieved_<tax_id>_<strategy>[_exact].<format>
  -f, --format {tsv,json}
                        Output format (default: tsv)
  -m, --summary         Generate a metadata summary table (written to stderr). Not available when output is stdout.
  -l, --log-file LOG_FILE
                        Log file path (default: logs/<timestamp>_<tax_id>_<strategy>[_exact].log). Set to '' to disable file logging.
```

### Output Format

Results are returned in the requested format (TSV or JSON) with the following fields:

- `run_accession` - Run accession number (e.g., DRR055433)
- `experiment_title` - Experiment description
- `tax_id` - NCBI taxonomy ID
- `tax_lineage` - Full taxonomic lineage (semicolon-separated)
- `scientific_name` - Organism scientific name
- `library_source` - Library source material type
- `library_strategy` - Sequencing strategy (RNA-Seq, miRNA-Seq, etc.)
- `instrument_platform` - Sequencing platform (ILLUMINA, PACBIO, etc.)
- `read_count` - Total number of reads in the run
- `first_public` - Date first made public

### Logging

Progress messages are written to stderr and do not interfere with stdout/TSV output.

By default, logs are also written to a file in the `logs/` directory with a descriptive name including timestamp, taxonomy ID, and library strategy. For example:
- `logs/2026-02-24_10-30-15_562_RNA-Seq.log` (using tax_tree)
- `logs/2026-02-24_10-30-15_562_RNA-Seq_exact.log` (using --exact flag)

## Project Structure

```
enatrieve-tx/
├── smoke_test.py             # New-clone smoke test (runs a small ENA fetch)
├── src/
│   └── ena/
│       ├── __init__.py       # Package initialization
│       ├── api.py            # Core library module
│       ├── cli.py            # CLI implementation (console script entry point)
│       └── summary.py        # Summary generation for retrieved metadata
├── logs/                     # Timestamped log files
├── LICENSE
├── pyproject.toml            # Packaging metadata (PEP 621)
├── .gitignore                # Git ignore patterns
└── README.md                 # This file
```

## Technical Details

### Retry and Backoff Strategy

The tool uses `urllib3.Retry` with:
- **Total retries**: 5 attempts
- **Backoff factor**: 0.5 (exponential: 0.5s, 1.0s, 2.0s, 4.0s, 8.0s)
- **Retryable status codes**: 429 (Too Many Requests), 500, 502, 503, 504
- **HTTP methods**: POST (idempotent for this API)

### Pagination

The ENA Portal API does not currently support an explicit `offset` parameter. Results are fetched in a single request. The default max_records is 0 (no limit), which retrieves all matching records. You can use the `--max-records` flag to restrict the number of records if needed.

### Known Limitations

- Very large result sets may timeout; consider filtering by date or other metadata
- The ENA Portal API may rate-limit requests; built-in retry logic handles transient failures

### Version History

- **0.3.0** - Added a new-clone smoke test (`smoke_test.py`), metadata summary option (`-m/--summary`) and updated documentation.
- **0.2.0** - Added operator toggle (`-e/--exact-match`) and short CLI flags; refactored packaging (src layout, console script) and removed top‑level script.
- **0.1.0** - Initial release with modular library and CLI interface

## Contributing

Contributions are welcome. For major changes, please open an issue first to discuss proposed modifications.

## Support and Documentation

For more information on the ENA Portal API, refer to:
- [ENA Portal Documentation](https://ena-docs.readthedocs.io/)
- [NCBI Taxonomy Database](https://www.ncbi.nlm.nih.gov/taxonomy)

## License

This project is provided as-is for research and educational purposes.

## Citation

If you use this tool in your research, please cite:
- The ENA Portal: Fischer et al. Database 2017
