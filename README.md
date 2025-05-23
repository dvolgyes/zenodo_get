zenodo_get: a downloader for Zenodo records
===========================================

AppVeyor:[![Build status](https://ci.appveyor.com/api/projects/status/f6hw96rhdl104ch9?svg=true)](https://ci.appveyor.com/project/dvolgyes/zenodo-get)
CircleCI:[![Build status](https://circleci.com/gh/dvolgyes/zenodo_get.svg?style=svg)](https://app.circleci.com/pipelines/github/dvolgyes/zenodo_get?branch=master)

Coveralls:[![Coverage Status](https://img.shields.io/coveralls/github/dvolgyes/zenodo_get/master)](https://coveralls.io/github/dvolgyes/zenodo_get?branch=master)
Codecov:[![codecov](https://codecov.io/gh/dvolgyes/zenodo_get/branch/master/graph/badge.svg)](https://codecov.io/gh/dvolgyes/zenodo_get)


This is a Python3 tool that can mass-download files from Zenodo records.

[![pyversion](https://img.shields.io/pypi/pyversions/zenodo_get.svg)](https://pypi.org/project/zenodo-get/)
[![PyPI - License](https://img.shields.io/pypi/l/zenodo_get.svg)](https://github.com/dvolgyes/zenodo_get/raw/master/LICENSE.txt)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1261812.svg)](https://doi.org/10.5281/zenodo.1261812)

Source code
-----------

The code is hosted at Github.

Installation
------------

It is recommended to use `uv` for managing Python environments and installing this package.
`zenodo-get` requires **Python 3.10 or newer**.

1.  Install `uv` (if you haven't already):
    ```bash
    # On macOS and Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # On Windows
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
2.  Create a virtual environment and install `zenodo-get`:
    *   From PyPI:
        ```bash
        uv venv
        uv pip install zenodo-get
        source .venv/bin/activate # Or .venv\Scripts\activate on Windows
        ```
    *   Or from a local source checkout:
        ```bash
        uv venv
        uv pip install .
        source .venv/bin/activate # Or .venv\Scripts\activate on Windows
        ```

Traditional pip installation is also supported:
```bash
pip install zenodo-get # Ensure pip is for Python 3.10+
```

Afterwards, you can query the command line options:
```bash
zenodo_get -h
```

but the default settings should work for most use cases:
```bash
zenodo_get RECORD_ID_OR_DOI
```

### Running with `uv run`

Once your project is set up with `uv` (either by installing dependencies via `uv pip install .` or by just having the `pyproject.toml` present), you can use `uv run` to execute the `zenodo_get` command directly without needing to activate the virtual environment in your current shell:

```bash
# Example: Show help message
uv run zenodo_get -- --help

# Example: Download a record (replace YOUR_RECORD_ID)
uv run zenodo_get -- YOUR_RECORD_ID -o output_directory

# Example: Using a script defined in pyproject.toml (zenodo_get is defined there)
# uv run zenodo_get -- YOUR_RECORD_ID
```
Note the `--` which separates arguments for `uv run` itself from the arguments for the script (`zenodo_get`).
This is often the most convenient way to run the tool if you are frequently working with `uv`-managed projects.


Documentation
-------------
The tool itself is simple, and the help message is reasonable:

```
zenodo_get -h
```

but if you need more, open a github ticket and explain what is missing.

Basic usage:
```bash
zenodo_get RECORD_ID_OR_DOI
```

### Filtering by File Type
You can use the `-g` or `--glob` option to specify file patterns. To download multiple specific file types, provide a comma-separated list of glob patterns:
```bash
zenodo_get RECORD_ID_OR_DOI -g "*.txt,*.pdf,images/*.png"
```

Other Special parameters:
- `-m` : generate `md5sums.txt` for verification. Beware, if `md5sums.txt` is
  present in the dataset, it will overwrite this generated file. Verification example:
  `md5sum -c md5sums.txt`
- `-w FILE` : instead of downloading the record files, it will
   generate a FILE (or print to stdout if `FILE` is `-`) which contains direct links to the Zenodo site. These links
   could be downloaded with any download manager, e.g. with wget:
   `wget -i urls.txt`
- ``-e`` : continue on error. It will skip the files with errors, but it will
    try to download the rest of the files.
- ``-k`` : keep files: it will keep files with invalid md5 checksum. The main purpose
   is debugging.
- ``-R N``: retry on error N times.
- ``-p N``: Waiting time in sec before retry attempt. Default: 0.5 sec.
- ``-n`` : do not continue. The default behaviour is to download only the files
   which are not yet download or where the checksum does not match with the file.
   This flag disables this feature, and it will force download existing files,
   and assigning a new name to the files (e.g. file(1).ext )


Remark for batch processing: the program always exits with non-zero exit code, if any error has happened,
for instance, checksum mismatch, download error, time-out, etc. Only perfectly correct
downloads end with 0 exit code.

Citation
--------

You don't really need to cite this software, except if you use it for another academic publication.
E.g. if you download something from Zenodo with zenodo-get: no need to cite anything.
If you download a lot from Zenodo, and you publish about Zenodo,
and my tool is integral part of the methodology, then you could cite it.
You could always ask the code to print the most up-to-date reference producing plain text and
bibtex references too:

```
zenodo_get --cite
```
