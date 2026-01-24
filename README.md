# zenodo_get: a downloader for Zenodo records

[![CI](https://github.com/dvolgyes/zenodo_get/actions/workflows/ci.yml/badge.svg)](https://github.com/dvolgyes/zenodo_get/actions/workflows/ci.yml)
[![CircleCI](https://circleci.com/gh/dvolgyes/zenodo_get.svg?style=svg)](https://circleci.com/gh/dvolgyes/zenodo_get)
[![Build status](https://img.shields.io/appveyor/build/dvolgyes/zenodo-get)](https://ci.appveyor.com/project/dvolgyes/zenodo-get)
[![Coverage Status](https://img.shields.io/coveralls/github/dvolgyes/zenodo_get/master)](https://coveralls.io/github/dvolgyes/zenodo_get?branch=master)
[![pyversion](https://img.shields.io/pypi/pyversions/zenodo_get.svg)](https://pypi.org/project/zenodo-get/)
[![PyPI - License](https://img.shields.io/pypi/l/zenodo_get.svg)](https://github.com/dvolgyes/zenodo_get/raw/master/LICENSE.txt)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1261812.svg)](https://doi.org/10.5281/zenodo.1261812)

A Python tool for downloading files from Zenodo records. Requires **Python 3.10+**.

## Installation

The simplest way (no installation needed) is using [uvx](https://docs.astral.sh/uv/guides/tools/), a tool runner from [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx zenodo_get RECORD_ID_OR_DOI
```

Alternatively, install with pipx or pip:

```bash
pipx install zenodo-get
# or
pip install zenodo-get
```

## Usage

```bash
uvx zenodo_get RECORD_ID_OR_DOI
```

### Common Options

| Option | Description |
|--------|-------------|
| `-o DIR` | Output directory (created if needed) |
| `-g PATTERN` | Filter files by glob pattern (e.g., `-g "*.pdf"`) |
| `-m` | Generate `md5sums.txt` for verification |
| `-w FILE` | Write URLs to file instead of downloading (`-w -` for stdout) |
| `-e` | Continue on error (skip failed files) |
| `-n` | Start fresh (don't resume previous download) |
| `-v N` | Verbosity level 0-4 (default: 2) |

### Retry Options

| Option | Description |
|--------|-------------|
| `--max-http-retries N` | HTTP retries with exponential backoff (default: 5) |
| `--backoff-factor N` | Backoff multiplier in seconds (default: 0.5) |
| `-R N` | Application-level retries for checksum failures (default: 1) |
| `-p N` | Pause between retries in seconds (default: 3) |
| `-t N` | Connection timeout in seconds (default: 25) |

### Examples

```bash
# Download all files from a record
uvx zenodo_get 1234567

# Download only PDFs to a specific directory
uvx zenodo_get 1234567 -g "*.pdf" -o ./downloads

# Generate URL list for external download manager
uvx zenodo_get 1234567 -w urls.txt

# Use DOI instead of record ID
uvx zenodo_get -d 10.5281/zenodo.1234567

```

### Exit Codes

- `0`: All files downloaded successfully
- Non-zero: Error occurred (checksum mismatch, download failure, timeout, etc.)

## Python API

You can use `zenodo_get` as a library in your Python projects.

### Installation

```bash
# Add to your project
uv add zenodo-get
# or
pip install zenodo-get
```

### Usage

```python
from zenodo_get import download

# Download all files from a record
download("10.5281/zenodo.1234567", output_dir="./data")

# Download only specific files using glob pattern
download(
    record_or_doi="1234567",
    output_dir="./data",
    file_glob="*.csv",
)

# Multiple glob patterns
download(
    record_or_doi="1234567",
    output_dir="./data",
    file_glob=["*.csv", "*.json"],
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `record_or_doi` | `str` | - | Zenodo record ID or DOI |
| `output_dir` | `str \| Path` | `"."` | Output directory |
| `file_glob` | `str \| tuple` | `"*"` | Filter files by glob pattern(s) |
| `md5` | `bool` | `False` | Generate `md5sums.txt` |
| `continue_on_error` | `bool` | `False` | Continue on download errors |
| `start_fresh` | `bool` | `False` | Don't resume previous download |
| `timeout` | `float` | `15.0` | Connection timeout in seconds |
| `exceptions_on_failure` | `bool` | `True` | Raise exceptions on errors |

## Citation

If you use this tool in academic work:

```bash
uvx zenodo_get --cite
```
