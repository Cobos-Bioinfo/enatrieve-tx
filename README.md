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

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start
*TODO: change section for > actual test.sh scrpit*

### Basic Usage

Fetch all RNA-Seq transcriptomic data for taxonomy ID 34735 (Apoidea Superfamily):

```bash
python enatrieve_tx.py --tax_id 34735
```

This creates `ena_transcriptomics_34735.tsv` in the current directory.

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
enatrieve-tx/
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

## Technical Details

### Retry and Backoff Strategy

The tool uses `urllib3.Retry` with:
- **Total retries**: 5 attempts
- **Backoff factor**: 0.5 (exponential: 0.5s, 1.0s, 2.0s, 4.0s, 8.0s)
- **Retryable status codes**: 429 (Too Many Requests), 500, 502, 503, 504
- **HTTP methods**: POST (idempotent for this API)

### Streaming

Response content is streamed line-by-line to minimize memory usage.

### Pagination

The ENA Portal API does not currently support an explicit `offset` parameter. Instead, results are fetched in a single request using a high `limit` value. The default limit of 10,000,000 covers virtually all result sets from the API.

## Known Limitations

- Very large result sets may timeout; consider filtering by date or other metadata
- The ENA Portal API may rate-limit requests; built-in retry logic handles transient failures

## Development

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
