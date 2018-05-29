#!/bin/bash
set -e
DIR=$(dirname "$0")

PYTHON="python -m coverage run -a --source $DIR/../src/"
$PYTHON $DIR/../src/zenodo_get.py
$PYTHON $DIR/../src/zenodo_get.py -h

# expected failed tests
$PYTHON $DIR/../src/zenodo_get.py invalid_doi && false || true
$PYTHON $DIR/../src/zenodo_get.py -1 x && false || true
$PYTHON $DIR/../src/zenodo_get.py https://invalid && false || true

$PYTHON $DIR/../src/zenodo_get.py 1215979
$PYTHON $DIR/../src/zenodo_get.py -r 1215979
$PYTHON $DIR/../src/zenodo_get.py 10.5281/zenodo.1215979
$PYTHON $DIR/../src/zenodo_get.py -d 10.5281/zenodo.1215979

echo "  TESTS ARE OK!  "
