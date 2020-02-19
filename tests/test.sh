#!/bin/bash
set -e
cd ..

PYTHON="python3 -m coverage run -a --source src/"
$PYTHON ./zenodo_get.py
$PYTHON ./zenodo_get.py -h

# tests expected to fail
$PYTHON ./zenodo_get.py invalid_doi && false || true
$PYTHON ./zenodo_get.py -1 x && false || true
$PYTHON ./zenodo_get.py 0 x && false || true
$PYTHON ./zenodo_get.py https://invalid && false || true

# tests expected to pass
$PYTHON ./zenodo_get.py 1215979 -m -e -k
$PYTHON ./zenodo_get.py -r 1215979 -w urls.txt -n
$PYTHON ./zenodo_get.py -r 1215979 -w -
$PYTHON ./zenodo_get.py 10.5281/zenodo.1215979 -R 3 -p 2 -n
$PYTHON ./zenodo_get.py -d 10.5281/zenodo.1215979

echo "  TESTS ARE OK!  "
