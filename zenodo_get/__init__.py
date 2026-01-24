#!/usr/bin/env python3
"""
Zenodo_get - Download complete records from the Zenodo research data repository.

Provides easy programmatic and command-line access to download files
from Zenodo records using record IDs or DOIs.
"""

from importlib.metadata import version

__title__ = "zenodo_get"
__summary__ = "Zenodo_get - a downloader for Zenodo records"
__uri__ = "https://github.com/dvolgyes/zenodo_get"
__license__ = "AGPL v3"
__author__ = "David Völgyes"
__email__ = "david.volgyes@ieee.org"
__doi__ = "10.5281/zenodo.1261812"
__description__ = """
This program is meant to download complete Zenodo records based
on the Zenodo record ID or the DOI. The primary goal is to ease access
to large records with dozens of files.
"""
__bibtex__ = (
    """@misc{david_volgyes_2020_"""
    + __doi__
    + """,
  author  = {David Völgyes},
  title   = {Zenodo_get: a downloader for Zenodo records.},
  month   = {2},
  year    = {2020},
  doi     = {"""
    + __doi__
    + """},
  url     = {https://doi.org/"""
    + __doi__
    + """}
}"""
)
__reference__ = (
    """David Völgyes. (2020, February 20). \
Zenodo_get: a downloader for Zenodo records (Version """
    + version("zenodo-get")
    + """).
Zenodo. https://doi.org/"""
    + __doi__
)

try:  # wget and other libs might not be present at installation
    from .zget import download  # Updated to import the new public API function

    __all__ = ["download"]  # Updated to export the new public API function
except ImportError:  # More specific exception handling
    # This can happen during initial package build where zget might not be compiled/available yet
    # Or if a user tries to import without all dependencies installed for some reason.
    # Allow the import to proceed without 'download' if it's not found,
    # as other metadata in __init__ might still be useful.
    pass
