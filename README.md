# ENA Transcriptomic Data Retriever (enatrieve_tx)

A Python tool for efficiently querying and downloading transcriptomic sequencing data from the EMBL-EBI ENA Portal API by NCBI taxonomy identifier.

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

### Requirements

- Python 3.10 or later
- pip or equivalent package manager

### Steps

1. Clone or download the repository:
   ```bash
   git clone <repository-url>
   cd query-ena
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

Both `requests` and `urllib3` will be installed with compatible versions.

## Quick Start

### Basic Usage

Fetch all RNA-Seq transcriptomic data for taxonomy ID 2759 (Eukaryota):

```bash
python enatrieve_tx.py --tax_id 2759
```

This creates `ena_transcriptomics_2759.tsv` in the current directory.

### Common Examples

**Save to custom output file:**
```bash
python enatrieve_tx.py --tax_id 562 --output escherichia_coli_rna.tsv
```

**Output to stdout for piping:**
```bash
python enatrieve_tx.py --tax_id 1 --output - | head -10
```

**Reduce result limit for testing:**
```bash
python enatrieve_tx.py --tax_id 2759 --limit 100 --output test_results.tsv
```

**Query for a different sequencing strategy:**
```bash
python enatrieve_tx.py --tax_id 9606 --strategy miRNA-Seq --output human_mirna.tsv
```

## Usage

### Command-Line Interface

```
usage: enatrieve_tx.py [-h] --tax_id TAX_ID [--output OUTPUT] 
                       [--limit LIMIT] [--strategy STRATEGY] [--log LOG]

Fetch ENA transcriptomic run metadata for a tax_id.

options:
  -h, --help          show this help message and exit
  --tax_id TAX_ID     NCBI taxonomy identifier to query (string or integer) [required]
  --output OUTPUT     Output file path (TSV). Use '-' to write to stdout. 
                      Defaults to ena_transcriptomics_<tax_id>.tsv
  --limit LIMIT       Maximum number of records to request in a single API call 
                      (default: 10000000)
  --strategy STRATEGY Library strategy value to filter (default: RNA-Seq)
```

### Output Format

Results are returned as tab-separated values (TSV) with the following columns:

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

Progress messages are written to stderr and do not interfere with stdout/TSV output:

```
INFO: tax_id=562 strategy=RNA-Seq limit=10000000 output=escherichia_coli_rna.tsv
INFO: Sending query to ENA API
INFO: Wrote 1234 lines
INFO: Output saved to escherichia_coli_rna.tsv
```

## Project Structure

```
query-ena/
├── src/
│   └── ena/
│       ├── __init__.py       # Package initialization
│       └── api.py            # Core library module
├── logs/                      # Timestamped log files (auto-created)
├── enatrieve_tx.py           # CLI entry point
├── requirements.txt          # Python dependencies
├── .gitignore                # Git ignore patterns
└── README.md                 # This file
```

### Module Descriptions

#### `src/ena/api.py`

Core library module providing reusable functions:

- `build_query(tax_id, strategy)` - Constructs ENA Portal query string
- `build_post_data(tax_id, limit, strategy)` - Builds POST payload
- `create_session()` - Returns configured requests.Session with retry logic
- `fetch_stream(session, data)` - Performs HTTP request with streaming
- `write_response(resp, out_fh)` - Streams response to file handle

All functions include type hints and comprehensive docstrings.

#### `enatrieve_tx.py`

Command-line interface that orchestrates the library functions:

- `parse_args()` - Parses command-line arguments
- `main()` - Primary entry point; handles file I/O and logging

## API Reference

### ena_api Module

For programmatic usage, import functions from the `ena` package:

```python
from ena import build_post_data, create_session, fetch_stream, write_response
import sys

# Build query parameters
data = build_post_data(
    tax_id="2759",
    limit=10_000_000,
    strategy="RNA-Seq"
)

# Create HTTP session with retry logic
session = create_session()

# Fetch from API
response = fetch_stream(session, data)

# Stream results to stdout
write_response(response, sys.stdout)
```

## Technical Details

### Retry and Backoff Strategy

The tool uses `urllib3.Retry` with:
- **Total retries**: 5 attempts
- **Backoff factor**: 0.5 (exponential: 0.5s, 1.0s, 2.0s, 4.0s, 8.0s)
- **Retryable status codes**: 429 (Too Many Requests), 500, 502, 503, 504
- **HTTP methods**: POST (idempotent for this API)

### Streaming

Response content is streamed line-by-line to minimize memory usage, making it suitable for large result sets.

### Pagination

The ENA Portal API does not currently support an explicit `offset` parameter. Instead, results are fetched in a single request using a high `limit` value. The default limit of 10,000,000 covers virtually all result sets from the API.

## Known Limitations

- The API does not support pagination with an `offset` parameter; a single request with high `limit` is used instead
- `library_source` and `library_strategy` field availability may vary depending on the result type
- Very large result sets (>10M records) may timeout; consider filtering by date or other metadata
- The ENA Portal API may rate-limit requests; built-in retry logic handles transient failures

## Dependencies

- `requests` (>= 2.28) - HTTP client library
- `urllib3` (>= 1.26) - Connection pool and retry logic

Both are included in `requirements.txt` for easy installation.

## Development

### Running Tests

To verify basic functionality:

```bash
python enatrieve_tx.py --tax_id 562 --limit 1 --output - | head -3
```

Expected output format:
```
INFO: tax_id=562 strategy=RNA-Seq limit=1 output=-
INFO: Sending query to ENA API
run_accession   experiment_title   ...
```

### Code Style

The project uses type hints and follows PEP 8. All functions include docstrings.

### Version History

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
- Your own work if you modify or extend this tool
