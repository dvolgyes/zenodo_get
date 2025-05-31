import os
import shutil
import sys

# Assuming zenodo_get is installed or PYTHONPATH is set correctly
# to find the zenodo_get package.
try:
    from zenodo_get import download
except ImportError:
    # Fallback for environments where zenodo_get might not be in the default path yet
    # This might happen if tests are run before installation in some CI setups.
    # Adjust path as necessary if your project structure is different.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        from zenodo_get import download
    except ImportError:
        # If it still fails, zget might be the direct module if __init__ is not fully set up
        from zenodo_get.zget import download


def test_api_download_specific_file():
    print("Running API Test: Download specific file (*.py)")
    output_dir = "test_api_r_output"

    # Cleanup before test
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        download(
            record_or_doi="10.5281/zenodo.1215979",
            output_dir=output_dir,
            file_glob="*.py",
            start_fresh=True,  # Corresponds to -n
            exceptions_on_failure=True,  # Ensure API raises exceptions
        )
        assert os.path.exists(os.path.join(output_dir, "fetch_data.py")), (
            "fetch_data.py was not downloaded"
        )
        print(
            f"API Test: Download specific file (*.py) PASSED. Files in {output_dir}: {os.listdir(output_dir)}"
        )
    except Exception as e:
        print(f"API Test: Download specific file (*.py) FAILED: {e}")
        # Cleanup after test (even on failure)
        shutil.rmtree(output_dir, ignore_errors=True)
        raise  # Re-raise the exception to fail the test

    # Cleanup after successful test
    shutil.rmtree(output_dir, ignore_errors=True)


def test_api_error_handling():
    print("Running API Test: Error handling for invalid DOI")
    raised_expected_exception = False
    try:
        download(record_or_doi="invalid_doi_for_api_test", exceptions_on_failure=True)
    except (ValueError, ConnectionError) as ve:  # DOI resolution failure can raise ValueError or ConnectionError
        print(f"API Test: Error handling - Caught expected exception: {ve}")
        raised_expected_exception = True
    except Exception as e:  # Catch any other exception to report it
        print(
            f"API Test: Error handling - Caught unexpected exception: {type(e).__name__} - {e}"
        )
        pass  # Not the expected exception

    assert raised_expected_exception, (
        "Expected ValueError or ConnectionError was not raised for invalid DOI."
    )
    print("API Test: Error handling for invalid DOI PASSED.")


def main():
    try:
        test_api_download_specific_file()
        test_api_error_handling()
        print("All Python API tests PASSED.")
        sys.exit(0)
    except AssertionError as e:
        print(f"Python API test FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Python API test FAILED with unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
