#!/bin/bash
set -e

CMD="python3 -m coverage run -a --source zenodo_get -m zenodo_get"
$CMD 
$CMD  -h
$CMD  --cite

# tests expected to fail
$CMD  invalid_doi && false || true
$CMD  -1 x && false || true
$CMD  0 x && false || true
$CMD  https://invalid && false || true

# tests expected to pass
$CMD  1215979 -m -e -k
$CMD  -r 1215979 -w urls.txt -n
$CMD  -r 1215979 -w -
$CMD  10.5281/zenodo.1215979 -R 3 -p 2 -n
$CMD  -d 10.5281/zenodo.1215979

echo "  TESTS ARE OK!  "
