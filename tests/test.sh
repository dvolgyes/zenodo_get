#!/bin/bash
set -e
DIR=$(dirname "$0")

if [ -z "${PYVERSION+xxx}" ]; then 
    PYVERSION=3
fi

PYTHON="python$PYVERSION -m coverage run -a --source $DIR/../src/"
$PYTHON $DIR/../src/zenodo_get.py
$PYTHON $DIR/../src/zenodo_get.py -h

# tests expected to fail
$PYTHON $DIR/../src/zenodo_get.py invalid_doi && false || true
$PYTHON $DIR/../src/zenodo_get.py -1 x && false || true
$PYTHON $DIR/../src/zenodo_get.py 0 x && false || true
$PYTHON $DIR/../src/zenodo_get.py https://invalid && false || true

# tests expected to pass
$PYTHON $DIR/../src/zenodo_get.py 1215979 -m -e -k
$PYTHON $DIR/../src/zenodo_get.py -r 1215979 -w urls.txt -n
$PYTHON $DIR/../src/zenodo_get.py -r 1215979 -w -
$PYTHON $DIR/../src/zenodo_get.py 10.5281/zenodo.1215979 -R 3 -p 2 -n
$PYTHON $DIR/../src/zenodo_get.py -d 10.5281/zenodo.1215979

echo "  TESTS ARE OK!  "
