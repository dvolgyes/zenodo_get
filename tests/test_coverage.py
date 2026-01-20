#!/usr/bin/env python3
"""
Comprehensive tests to improve code coverage for zenodo_get.
Tests focus on poorly covered functions:
- _fetch_record_metadata (33.3% coverage)
- download (6.7% coverage)
- handle_ctrl_c (14.3% coverage)
- _handle_single_file_download (52.2% coverage)
"""

import os
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path
import httpx
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zenodo_get.zget import (
    _fetch_record_metadata,
    download,
    handle_ctrl_c,
    _handle_single_file_download,
)


class TestFetchRecordMetadata:
    """Test _fetch_record_metadata function with various scenarios."""

    def test_successful_fetch(self):
        """Test successful metadata fetch."""
        result = _fetch_record_metadata("1215979", False, None, 30.0, True)
        assert result is not None
        assert "metadata" in result
        assert "files" in result

    def test_sandbox_fetch(self):
        """Test fetch from sandbox environment."""
        # Use a smaller record that might exist in sandbox
        try:
            result = _fetch_record_metadata("1", True, None, 30.0, True)
            # Sandbox might not have this record, so we expect an exception
        except (ValueError, ConnectionError):
            # This is expected for non-existent sandbox records
            pass

    def test_fetch_with_access_token(self):
        """Test fetch with access token parameter."""
        result = _fetch_record_metadata("1215979", False, "fake_token", 30.0, True)
        assert result is not None

    def test_fetch_timeout_exception(self):
        """Test timeout handling with exceptions enabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.TimeoutException("Timeout error")
            )

            with pytest.raises(ConnectionError, match="Timeout when fetching"):
                _fetch_record_metadata("1215979", False, None, 30.0, True)

    def test_fetch_timeout_no_exception(self):
        """Test timeout handling with exceptions disabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.TimeoutException("Timeout error")
            )

            with mock.patch("sys.exit") as mock_exit:
                result = _fetch_record_metadata("1215979", False, None, 30.0, False)
                mock_exit.assert_called_once_with(1)

    def test_fetch_http_error_exception(self):
        """Test HTTP error handling with exceptions enabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_response.reason_phrase = "Not Found"
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.HTTPStatusError(
                    "404 Not Found", request=mock.Mock(), response=mock_response
                )
            )

            with pytest.raises(ValueError, match="HTTP error fetching"):
                _fetch_record_metadata("invalid_id", False, None, 30.0, True)

    def test_fetch_http_error_no_exception(self):
        """Test HTTP error handling with exceptions disabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_response.reason_phrase = "Not Found"
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.HTTPStatusError(
                    "404 Not Found", request=mock.Mock(), response=mock_response
                )
            )

            with mock.patch("sys.exit") as mock_exit:
                result = _fetch_record_metadata("invalid_id", False, None, 30.0, False)
                mock_exit.assert_called_once_with(1)

    def test_fetch_request_exception_exception(self):
        """Test general request exception handling with exceptions enabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.RequestError("Connection failed")
            )

            with pytest.raises(ConnectionError, match="Error fetching metadata"):
                _fetch_record_metadata("1215979", False, None, 30.0, True)

    def test_fetch_request_exception_no_exception(self):
        """Test general request exception handling with exceptions disabled."""
        with mock.patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = (
                httpx.RequestError("Connection failed")
            )

            with mock.patch("sys.exit") as mock_exit:
                result = _fetch_record_metadata("1215979", False, None, 30.0, False)
                mock_exit.assert_called_once_with(1)


class TestDownloadFunction:
    """Test public download function with various parameter combinations."""

    def test_download_no_record_or_doi_exception(self):
        """Test download with no record or DOI and exceptions enabled."""
        with pytest.raises(
            ValueError, match="Either record_or_doi, record, or doi must be provided"
        ):
            download(exceptions_on_failure=True)

    def test_download_no_record_or_doi_no_exception(self):
        """Test download with no record or DOI and exceptions disabled."""
        with mock.patch("sys.exit", side_effect=SystemExit(1)) as mock_exit:
            with pytest.raises(SystemExit):
                download(exceptions_on_failure=False)
            mock_exit.assert_called_once_with(1)

    def test_download_with_record_int(self):
        """Test download with integer record ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                record_or_doi=1215979,
                output_dir=temp_dir,
                md5=True,
                exceptions_on_failure=True,
            )
            # Should create md5sums.txt
            assert os.path.exists(os.path.join(temp_dir, "md5sums.txt"))

    def test_download_with_record_string(self):
        """Test download with string record ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                record_or_doi="1215979",
                output_dir=temp_dir,
                md5=True,
                exceptions_on_failure=True,
            )
            assert os.path.exists(os.path.join(temp_dir, "md5sums.txt"))

    def test_download_with_doi_string(self):
        """Test download with DOI string."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                record_or_doi="10.5281/zenodo.1215979",
                output_dir=temp_dir,
                md5=True,
                exceptions_on_failure=True,
            )
            assert os.path.exists(os.path.join(temp_dir, "md5sums.txt"))

    def test_download_explicit_record_parameter(self):
        """Test download with explicit record parameter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                record="1215979",
                output_dir=temp_dir,
                md5=True,
                exceptions_on_failure=True,
            )
            assert os.path.exists(os.path.join(temp_dir, "md5sums.txt"))

    def test_download_explicit_doi_parameter(self):
        """Test download with explicit DOI parameter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                doi="10.5281/zenodo.1215979",
                output_dir=temp_dir,
                md5=True,
                exceptions_on_failure=True,
            )
            assert os.path.exists(os.path.join(temp_dir, "md5sums.txt"))

    def test_download_with_path_object(self):
        """Test download with Path object as output_dir."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path_obj = Path(temp_dir)
            download(
                record="1215979",
                output_dir=path_obj,
                md5=True,
                exceptions_on_failure=True,
            )
            assert os.path.exists(path_obj / "md5sums.txt")

    def test_download_wget_file_mode(self):
        """Test download in wget file mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            wget_file = os.path.join(temp_dir, "urls.txt")
            download(
                record="1215979",
                output_dir=temp_dir,
                wget_file=wget_file,
                exceptions_on_failure=True,
            )
            assert os.path.exists(wget_file)
            with open(wget_file) as f:
                content = f.read()
                assert "zenodo.org" in content

    def test_download_various_parameters(self):
        """Test download with various parameter combinations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            download(
                record="1215979",
                output_dir=temp_dir,
                continue_on_error=True,
                keep_invalid=True,
                start_fresh=True,
                retry_attempts=2,
                retry_pause=0.1,
                timeout=30.0,
                sandbox_url=False,
                access_token=None,
                file_glob=["*.py"],
                exceptions_on_failure=True,
            )


class TestHandleCtrlC:
    """Test handle_ctrl_c function."""

    def test_single_ctrl_c(self):
        """Test single Ctrl+C signal."""
        import zenodo_get.zget as zget_module

        original_abort_signal = zget_module.abort_signal
        original_abort_counter = zget_module.abort_counter

        try:
            zget_module.abort_signal = False
            zget_module.abort_counter = 0

            handle_ctrl_c()
            assert zget_module.abort_signal == True
            assert zget_module.abort_counter == 1
        finally:
            zget_module.abort_signal = original_abort_signal
            zget_module.abort_counter = original_abort_counter

    def test_double_ctrl_c(self):
        """Test double Ctrl+C signal triggers exit."""
        import zenodo_get.zget as zget_module

        original_abort_signal = zget_module.abort_signal
        original_abort_counter = zget_module.abort_counter

        try:
            zget_module.abort_signal = False
            zget_module.abort_counter = 1  # Simulate one previous call

            with mock.patch("sys.exit") as mock_exit:
                handle_ctrl_c()
                mock_exit.assert_called_once_with(1)

            assert zget_module.abort_signal == True
            assert zget_module.abort_counter == 2
        finally:
            zget_module.abort_signal = original_abort_signal
            zget_module.abort_counter = original_abort_counter


class TestHandleSingleFileDownload:
    """Test _handle_single_file_download function with various scenarios."""

    def test_download_with_existing_correct_file(self):
        """Test download when file already exists with correct checksum."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:d41d8cd98f00b204e9800998ecf8427e",  # Empty file hash
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                # Create empty file
                with open("test_file.txt", "w") as f:
                    pass

                result = _handle_single_file_download(
                    file_info=file_info,
                    record_id="test",
                    download_url_base="https://test.com/",
                    access_token=None,
                    cont_download=True,
                    retry_limit=1,
                    pause_duration=0.1,
                    timeout_val=30.0,
                    keep_invalid=False,
                    error_continues=False,
                    verbosity=2,
                    exceptions_on_failure=True,
                )
                assert result == True
            finally:
                os.chdir(original_cwd)

    def test_download_with_abort_signal(self):
        """Test download when abort signal is set."""
        import zenodo_get.zget as zget_module

        original_abort_signal = zget_module.abort_signal
        zget_module.abort_signal = True

        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:d41d8cd98f00b204e9800998ecf8427e",
        }

        try:
            result = _handle_single_file_download(
                file_info=file_info,
                record_id="test",
                download_url_base="https://test.com/",
                access_token=None,
                cont_download=False,
                retry_limit=1,
                pause_duration=0.1,
                timeout_val=30.0,
                keep_invalid=False,
                error_continues=False,
                verbosity=2,
                exceptions_on_failure=True,
            )
            assert result == False
        finally:
            zget_module.abort_signal = original_abort_signal

    def test_download_with_access_token(self):
        """Test download URL construction with access token."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:fakehash",
            "links": {"self": "https://test.com/file"},
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)

                with mock.patch("zenodo_get.zget.download_file") as mock_download:
                    mock_download.side_effect = Exception("Download failed")

                    with mock.patch("sys.exit"):
                        result = _handle_single_file_download(
                            file_info=file_info,
                            record_id="test",
                            download_url_base="https://test.com/",
                            access_token="test_token",
                            cont_download=False,
                            retry_limit=0,
                            pause_duration=0.1,
                            timeout_val=30.0,
                            keep_invalid=False,
                            error_continues=False,
                            verbosity=2,
                            exceptions_on_failure=False,
                        )

                    # Verify access token was added to URL
                    call_args = mock_download.call_args[0][0]
                    assert "access_token=test_token" in call_args
            finally:
                os.chdir(original_cwd)

    def test_download_retry_logic(self):
        """Test download retry logic on failure."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:fakehash",
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)

                with mock.patch("zenodo_get.zget.download_file") as mock_download:
                    mock_download.side_effect = Exception("Download failed")

                    with mock.patch("time.sleep") as mock_sleep:
                        with mock.patch("sys.exit"):
                            result = _handle_single_file_download(
                                file_info=file_info,
                                record_id="test",
                                download_url_base="https://test.com/",
                                access_token=None,
                                cont_download=False,
                                retry_limit=2,
                                pause_duration=0.5,
                                timeout_val=30.0,
                                keep_invalid=False,
                                error_continues=False,
                                verbosity=2,
                                exceptions_on_failure=False,
                            )

                    # Verify retries occurred
                    assert mock_download.call_count == 3  # 1 initial + 2 retries
                    assert mock_sleep.call_count == 2  # Sleep between retries
            finally:
                os.chdir(original_cwd)

    def test_download_with_error_continues(self):
        """Test download with error_continues=True."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:fakehash",
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)

                with mock.patch("zenodo_get.zget.download_file") as mock_download:
                    mock_download.side_effect = Exception("Download failed")

                    result = _handle_single_file_download(
                        file_info=file_info,
                        record_id="test",
                        download_url_base="https://test.com/",
                        access_token=None,
                        cont_download=False,
                        retry_limit=1,
                        pause_duration=0.1,
                        timeout_val=30.0,
                        keep_invalid=False,
                        error_continues=True,
                        verbosity=2,
                        exceptions_on_failure=True,
                    )

                    assert result == False  # Failed but continued
            finally:
                os.chdir(original_cwd)

    def test_checksum_validation_failure(self):
        """Test checksum validation failure handling."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:wronghash",
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)

                # Create a file with different content
                with open("test_file.txt", "w") as f:
                    f.write("test content")

                with mock.patch("zenodo_get.zget.download_file") as mock_download:
                    mock_download.return_value = "test_file.txt"

                    result = _handle_single_file_download(
                        file_info=file_info,
                        record_id="test",
                        download_url_base="https://test.com/",
                        access_token=None,
                        cont_download=False,
                        retry_limit=0,
                        pause_duration=0.1,
                        timeout_val=30.0,
                        keep_invalid=False,
                        error_continues=True,
                        verbosity=2,
                        exceptions_on_failure=True,
                    )

                    assert result == False  # Checksum failed
                    assert not os.path.exists("test_file.txt")  # File deleted
            finally:
                os.chdir(original_cwd)

    def test_checksum_validation_failure_keep_invalid(self):
        """Test checksum validation failure with keep_invalid=True."""
        file_info = {
            "filename": "test_file.txt",
            "size": 100,
            "checksum": "md5:wronghash",
        }

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)

                # Create a file with different content
                with open("test_file.txt", "w") as f:
                    f.write("test content")

                with mock.patch("zenodo_get.zget.download_file") as mock_download:
                    mock_download.return_value = "test_file.txt"

                    result = _handle_single_file_download(
                        file_info=file_info,
                        record_id="test",
                        download_url_base="https://test.com/",
                        access_token=None,
                        cont_download=False,
                        retry_limit=0,
                        pause_duration=0.1,
                        timeout_val=30.0,
                        keep_invalid=True,
                        error_continues=True,
                        verbosity=2,
                        exceptions_on_failure=True,
                    )

                    assert result == False  # Checksum failed
                    assert os.path.exists("test_file.txt")  # File kept
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests manually if needed
    import pytest

    pytest.main([__file__, "-v"])
