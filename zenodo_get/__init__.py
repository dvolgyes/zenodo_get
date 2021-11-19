#!/usr/bin/env python3

__version__ = '1.3.4'
__title__ = 'zenodo_get'
__summary__ = 'Zenodo_get - a downloader for Zenodo records'
__uri__ = 'https://gitlab.com/dvolgyes/zenodo_get'
__license__ = 'AGPL v3'
__author__ = 'David Völgyes'
__email__ = 'david.volgyes@ieee.org'
__doi__ = '10.5281/zenodo.1261812'
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
    + __version__
    + """).
Zenodo. https://doi.org/"""
    + __doi__
)

try: # wget and other libs might not be present at installation
    from .zget import zenodo_get
    __all__ = ['zenodo_get']
except:
    pass
