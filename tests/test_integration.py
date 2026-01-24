#!/usr/bin/env python3
"""
Integration tests that replicate the functionality of test.sh
but can be properly measured with coverage.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zenodo_get import download

# Get project root directory relative to this test file
PROJECT_ROOT = Path(__file__).parent.parent


def test_version_command():
    """Test uv run zenodo_get --version."""
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "--version"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0
    print("✓ Testing uv run zenodo_get --version")


def test_help_command():
    """Test uv run zenodo_get -h."""
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "-h"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0
    print("✓ Testing uv run zenodo_get -h")


def test_cite_command():
    """Test uv run zenodo_get --cite."""
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "--cite"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0
    print("✓ Testing uv run zenodo_get --cite")


def test_expected_failures():
    """Test cases that are expected to fail."""
    print("Testing expected failures...")

    # Test invalid DOI
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "invalid_doi"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode != 0

    # Test invalid option -1
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "-1", "x"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode != 0

    # Test invalid argument 0
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "0", "x"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode != 0

    # Test invalid URL
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "https://invalid"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode != 0

    print("✓ Expected failures tested")


def test_url_list_generation():
    """Test -r 1215979 -w urls.txt -n."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [
                "uv",
                "run",
                "zenodo_get",
                "-r",
                "1215979",
                "-w",
                "urls.txt",
                "-n",
                "-o",
                temp_dir,
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        assert result.returncode == 0
        assert (Path(temp_dir) / "urls.txt").exists()

        # Ensure md5sums.txt is NOT created when not wanted
        assert not (Path(temp_dir) / "md5sums.txt").exists()

        print("✓ URL list written to urls.txt")


def test_md5_generation():
    """Test 1215979 -m -e -k."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [
                "uv",
                "run",
                "zenodo_get",
                "1215979",
                "-m",
                "-e",
                "-k",
                "-o",
                temp_dir,
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        assert result.returncode == 0
        assert (Path(temp_dir) / "md5sums.txt").exists()

        print("✓ md5sums.txt created")


def test_stdout_url_output():
    """Test -r 1215979 -w -."""
    result = subprocess.run(
        ["uv", "run", "zenodo_get", "-r", "1215979", "-w", "-"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0
    assert "https://zenodo.org" in result.stdout

    print("✓ URL list written to stdout")


def test_doi_download():
    """Test 10.5281/zenodo.1215979 -R 3 -p 2 -n."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [
                "uv",
                "run",
                "zenodo_get",
                "10.5281/zenodo.1215979",
                "-R",
                "3",
                "-p",
                "2",
                "-n",
                "-o",
                temp_dir,
                "-m",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        assert result.returncode == 0

        print("✓ DOI download test passed")


def test_glob_patterns():
    """Test glob pattern functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test Case 1: Download only .py files
        print("Running Test Case 1: Download only .py files")
        py_dir = Path(temp_dir) / "test_py_output"
        result = subprocess.run(
            [
                "uv",
                "run",
                "zenodo_get",
                "1215979",
                "-g",
                "*.py",
                "-o",
                str(py_dir),
                "-n",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        assert result.returncode == 0
        assert (py_dir / "fetch_data.py").exists()
        assert not (py_dir / "opencare-tags-anonymized.json").exists()
        print("✓ Test Case 1 PASSED")

        # Test Case 2: Download .json and .py files
        print("Running Test Case 2: Download .json and .py files")
        json_py_dir = Path(temp_dir) / "test_json_py_output"
        result = subprocess.run(
            [
                "uv",
                "run",
                "zenodo_get",
                "1215979",
                "-g",
                "*.json",
                "-g",
                "*.py",
                "-o",
                str(json_py_dir),
                "-n",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        assert result.returncode == 0
        assert (json_py_dir / "fetch_data.py").exists()
        assert (json_py_dir / "opencare-tags-anonymized.json").exists()
        print("✓ Test Case 2 PASSED")


def test_api_functionality():
    """Test Python API functionality."""
    print("Running Python API tests")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test API download with specific file glob
        try:
            download(
                record_or_doi="10.5281/zenodo.1215979",
                output_dir=temp_dir,
                file_glob=["*.py"],
                start_fresh=True,
                exceptions_on_failure=True,
            )

            assert (Path(temp_dir) / "fetch_data.py").exists()
            print("✓ API Test: Download specific file (*.py) PASSED")

        except Exception as e:
            print(f"✗ API Test FAILED: {e}")
            raise

    # Test API error handling
    try:
        download(record_or_doi="invalid_doi_for_api_test", exceptions_on_failure=True)
        print("✗ API Test: Error handling FAILED - should have raised exception")
        assert False, "Expected exception was not raised"
    except (ValueError, ConnectionError) as e:
        print(f"✓ API Test: Error handling - Caught expected exception: {e}")
        print("✓ API Test: Error handling for invalid DOI PASSED")

    print("✓ All Python API tests PASSED")


def run_all_tests():
    """Run all integration tests."""
    print("Starting integration tests...")

    # Clean up any leftover files
    for file in ["md5sums.txt", "urls.txt"]:
        if Path(file).exists():
            Path(file).unlink()

    try:
        test_version_command()
        test_help_command()
        test_cite_command()
        test_expected_failures()
        test_url_list_generation()
        test_md5_generation()
        test_stdout_url_output()
        test_doi_download()
        test_glob_patterns()
        test_api_functionality()

        print("\n🎉 ALL TESTS ARE OK! 🎉")
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    finally:
        # Clean up
        for file in ["md5sums.txt", "urls.txt"]:
            if Path(file).exists():
                Path(file).unlink()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
