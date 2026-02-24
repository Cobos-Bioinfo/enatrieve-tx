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

## Usage

### Command-Line Interface

```
usage: enatrieve-tx [-h] -t TAX_ID [-o OUTPUT] [-l LIMIT] [-s STRATEGY] [-L LOG] [-e] [-f {tsv,json}]

Fetch ENA transcriptomic run metadata for a tax_id.

options:
   -h, --help            show this help message and exit
   -t, --tax-id TAX_ID   NCBI taxonomy identifier to query (string or integer) [required]
   -o, --output OUTPUT   Output file path (extension auto-added based on --format). Use '-' to write to stdout.
                                    Defaults to enatrieved_<tax_id>_<strategy>[_exact].<format>
   -l, --limit LIMIT     Maximum number of records to request (default: 0 = no limit)
   -s, --strategy STRATEGY
                                    Library strategy value to filter (default: RNA-Seq)
   -L, --log LOG         Log file path (default: logs/<timestamp>_<tax_id>_<strategy>[_exact].log). Set to '' to disable file logging.
   -e, --exact           Use exact taxonomy match (tax_eq) instead of tax_tree
   -f, --format {tsv,json}
                                    Output format (default: tsv)
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

Example log output:

```
INFO: tax_id=562 strategy=RNA-Seq limit=0 format=tsv output=enatrieved_562_RNA-Seq.tsv
INFO: Using taxonomy operator: tax_tree
INFO: Query string: tax_tree(562) AND library_strategy="RNA-Seq"
INFO: Requested fields: run_accession,experiment_title,tax_id,tax_lineage,scientific_name,library_source,library_strategy,instrument_platform,read_count,first_public
INFO: Sending POST request to: https://www.ebi.ac.uk/ena/portal/api/search
INFO: POST data: {'result': 'read_run', 'query': 'tax_tree(562) AND library_strategy="RNA-Seq"', 'fields': 'run_accession,experiment_title,tax_id,tax_lineage,scientific_name,library_source,library_strategy,instrument_platform,read_count,first_public', 'format': 'tsv', 'limit': '0'}
INFO: Wrote 1234 lines
INFO: Output saved to enatrieved_562_RNA-Seq.tsv
```

## Project Structure

```
enatrieve-tx/
├── src/
│   └── ena/
│       ├── __init__.py       # Package initialization
│       ├── api.py            # Core library module
│       └── cli.py            # CLI implementation (console script entry point)
├── logs/                     # Timestamped log files (auto-created)
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

The ENA Portal API does not currently support an explicit `offset` parameter. Results are fetched in a single request. The default limit is 0 (no limit), which retrieves all matching records. You can use the `--limit` flag to restrict the number of records if needed.

### Known Limitations

- Very large result sets may timeout; consider filtering by date or other metadata
- The ENA Portal API may rate-limit requests; built-in retry logic handles transient failures

### Version History

- **0.2.0** - Added operator toggle (`-e/--exact`) and short CLI flags; refactored packaging (src layout, console script) and removed top‑level script.
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
