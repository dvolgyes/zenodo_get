#!/bin/bash
set -e

# Updated CMD to use uv run and target zenodo_get.__main__ for module execution
CMD="uv run coverage run -a --source zenodo_get -m zenodo_get.__main__"

# Test basic uv run invocations
echo "Testing uv run zenodo_get --version"
uv run zenodo_get --version > /dev/null

echo "Testing uv run zenodo_get -h"
uv run zenodo_get -h > /dev/null 

echo "Testing uv run zenodo_get --cite"
uv run zenodo_get --cite > /dev/null

# tests expected to fail (using the new CMD)
$CMD invalid_doi && false || true
$CMD -1 x && false || true
$CMD 0 x && false || true
$CMD https://invalid && false || true

# tests expected to pass
# Clean up any potential leftovers from previous runs
rm -f md5sums.txt urls.txt
rm -rf test_bib_xml_output test_ipynb_output test_api_r_output

$CMD -r 1215979 -w urls.txt -n

# Ensure that md5sums.txt is not created when it is not wanted
[ ! -f "md5sums.txt" ]

# Ensure that md5sums.txt is created when it is wanted
$CMD 1215979 -m -e -k
[ -f "md5sums.txt" ]

$CMD -r 1215979 -w -
$CMD 10.5281/zenodo.1215979 -R 3 -p 2 -n
$CMD -d 10.5281/zenodo.1215979


# New Test Case 1: Download only .ipynb files
echo "Running Test Case 1: Download only .ipynb files"
$CMD 1215979 -g "*.ipynb" -o test_ipynb_output -n
[ -f "test_ipynb_output/example.ipynb" ]
[ ! -f "test_ipynb_output/example.bib" ]
rm -rf test_ipynb_output
echo "Test Case 2 PASSED"

# New Test Case 2: Download .bib and .xml files
echo "Running Test Case 2: Download .bib and .xml files"
$CMD 1215979 -g "*.bib" -g "*.xml" -o test_bib_xml_output -n
[ -f "test_bib_xml_output/example.bib" ]
[ -f "test_bib_xml_output/example.xml" ]
[ ! -f "test_bib_xml_output/example.ipynb" ]
rm -rf test_bib_xml_output
echo "Test Case 1 PASSED"

# Run Python API tests using uv run if possible, or fallback to python3
echo "Running Python API tests (tests/test_api.py)"
if command -v uv &> /dev/null; then
  uv run python tests/test_api.py
else
  python3 tests/test_api.py
fi

# Final cleanup
rm -f md5sums.txt urls.txt
# test_api_r_output is cleaned up by test_api.py itself

echo "  ALL TESTS ARE OK!  "
