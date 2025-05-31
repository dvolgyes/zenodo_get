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
# These commands should fail - if they succeed, we fail the test
if $CMD invalid_doi; then
    echo "ERROR: 'invalid_doi' should have failed but succeeded"
    false  # fail is invoked because this test is not supposed to finish successfully
fi

if $CMD -1 x; then
    echo "ERROR: '-1 x' should have failed but succeeded"
    false  # fail is invoked because this test is not supposed to finish successfully
fi

if $CMD 0 x; then
    echo "ERROR: '0 x' should have failed but succeeded"
    false  # fail is invoked because this test is not supposed to finish successfully
fi

if $CMD https://invalid; then
    echo "ERROR: 'https://invalid' should have failed but succeeded"
    false  # fail is invoked because this test is not supposed to finish successfully
fi

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


# New Test Case 1: Download only .py files
echo "Running Test Case 1: Download only .py files"
$CMD 1215979 -g "*.py" -o test_json_py_output -n
[ -f "test_json_py_output/fetch_data.py" ]
[ ! -f "test_json_py_output/opencare-tags-anonymized.json" ]
[ ! -f "test_ipynb_output/example.bib" ]
rm -rf test_ipynb_output
echo "Test Case 2 PASSED"

# New Test Case 2: Download .json and .py files
echo "Running Test Case 2: Download .json and .py files"
$CMD 1215979 -g "*.json" -g "*.py" -o test_json_py_output -n
[ -f "test_json_py_output/fetch_data.py" ]
[ -f "test_json_py_output/opencare-tags-anonymized.json" ]
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
