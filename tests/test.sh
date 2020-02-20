#!/bin/bash
set -e

PYTHON="python3 -m coverage run -a --source zenodo_get"
$PYTHON zenodo_get
$PYTHON zenodo_get -h
$PYTHON zenodo_get --cite

# tests expected to fail
$PYTHON zenodo_get invalid_doi && false || true
$PYTHON zenodo_get -1 x && false || true
$PYTHON zenodo_get 0 x && false || true
$PYTHON zenodo_get https://invalid && false || true

# tests expected to pass
$PYTHON zenodo_get 1215979 -m -e -k
$PYTHON zenodo_get -r 1215979 -w urls.txt -n
$PYTHON zenodo_get -r 1215979 -w -
$PYTHON zenodo_get 10.5281/zenodo.1215979 -R 3 -p 2 -n
$PYTHON zenodo_get -d 10.5281/zenodo.1215979

echo "  TESTS ARE OK!  "
