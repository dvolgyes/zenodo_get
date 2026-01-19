"""Tests for the downloader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from zenodo_get.downloader import (
    _client,
    _extract_filename_from_content_disposition,
    _extract_filename_from_url,
    download_file,
)


class TestExtractFilenameFromContentDisposition:
    """Tests for Content-Disposition header parsing."""

    def test_quoted_filename(self) -> None:
        """Test extraction of quoted filename."""
        header = 'attachment; filename="test_file.txt"'
        assert _extract_filename_from_content_disposition(header) == "test_file.txt"

    def test_unquoted_filename(self) -> None:
        """Test extraction of unquoted filename."""
        header = "attachment; filename=test_file.txt"
        assert _extract_filename_from_content_disposition(header) == "test_file.txt"

    def test_rfc5987_encoded_filename(self) -> None:
        """Test extraction of RFC 5987 encoded filename."""
        header = "attachment; filename*=UTF-8''test%20file.txt"
        assert _extract_filename_from_content_disposition(header) == "test file.txt"

    def test_rfc5987_lowercase(self) -> None:
        """Test RFC 5987 with lowercase encoding."""
        header = "attachment; filename*=utf-8''encoded%20name.pdf"
        assert _extract_filename_from_content_disposition(header) == "encoded name.pdf"

    def test_both_filename_and_filename_star(self) -> None:
        """Test that filename* takes precedence over filename."""
        header = "attachment; filename=\"fallback.txt\"; filename*=UTF-8''preferred.txt"
        assert _extract_filename_from_content_disposition(header) == "preferred.txt"

    def test_none_header(self) -> None:
        """Test handling of None header."""
        assert _extract_filename_from_content_disposition(None) is None

    def test_empty_header(self) -> None:
        """Test handling of empty header."""
        assert _extract_filename_from_content_disposition("") is None

    def test_no_filename_in_header(self) -> None:
        """Test header without filename."""
        header = "attachment"
        assert _extract_filename_from_content_disposition(header) is None


class TestExtractFilenameFromUrl:
    """Tests for URL path filename extraction."""

    def test_simple_url(self) -> None:
        """Test filename extraction from simple URL."""
        url = "https://example.com/path/to/file.txt"
        assert _extract_filename_from_url(url) == "file.txt"

    def test_url_with_query_params(self) -> None:
        """Test filename extraction ignores query parameters."""
        url = "https://example.com/file.txt?access_token=abc123"
        assert _extract_filename_from_url(url) == "file.txt"

    def test_url_encoded_filename(self) -> None:
        """Test filename extraction with URL-encoded characters."""
        url = "https://example.com/path/my%20file.txt"
        assert _extract_filename_from_url(url) == "my file.txt"

    def test_url_without_path(self) -> None:
        """Test URL without a path returns None."""
        url = "https://example.com"
        assert _extract_filename_from_url(url) is None

    def test_url_with_trailing_slash(self) -> None:
        """Test URL with trailing slash returns None."""
        url = "https://example.com/path/"
        assert _extract_filename_from_url(url) is None


class TestDownloadFile:
    """Tests for download_file function."""

    @pytest.fixture
    def output_dir(self, tmp_path: Path) -> Path:
        """Create a temporary output directory."""
        test_dir = tmp_path / "download_test"
        test_dir.mkdir(parents=True, exist_ok=True)
        return test_dir

    @pytest.fixture
    def cleanup_files(self) -> list[Path]:
        """Track files created during tests for cleanup."""
        files: list[Path] = []
        yield files
        for f in files:
            if f.exists():
                f.unlink()

    def test_download_with_explicit_output(self, output_dir: Path) -> None:
        """Test download with explicit output filename."""
        output_file = output_dir / "explicit_output.txt"
        test_content = b"Hello, World!"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.url = "https://example.com/original.txt"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            result = download_file(
                "https://example.com/original.txt",
                out=str(output_file),
                verbosity="quiet",
            )

        assert result == str(output_file)
        assert output_file.exists()
        assert output_file.read_bytes() == test_content

    def test_download_quiet_mode(self, output_dir: Path) -> None:
        """Test download with quiet verbosity."""
        output_file = output_dir / "quiet_test.txt"
        test_content = b"Quiet content"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.url = "https://example.com/file.txt"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with patch("zenodo_get.downloader.logger") as mock_logger:
                download_file(
                    "https://example.com/file.txt",
                    out=str(output_file),
                    verbosity="quiet",
                )
                mock_logger.debug.assert_not_called()

    def test_download_normal_mode_logs(self, output_dir: Path) -> None:
        """Test download with normal verbosity logs messages."""
        output_file = output_dir / "normal_test.txt"
        test_content = b"Normal content"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.url = "https://example.com/file.txt"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with patch("zenodo_get.downloader.logger") as mock_logger:
                download_file(
                    "https://example.com/file.txt",
                    out=str(output_file),
                    verbosity="normal",
                )
                assert mock_logger.debug.call_count == 2

    def test_download_filename_from_content_disposition(self, output_dir: Path) -> None:
        """Test filename detection from Content-Disposition header."""
        test_content = b"Content-disposition content"
        expected_file = output_dir / "detected.txt"

        mock_response = MagicMock()
        mock_response.headers = {"content-disposition": 'attachment; filename="detected.txt"'}
        mock_response.url = f"file://{output_dir}/api/download"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            result = download_file(
                "https://example.com/api/download",
                out=str(expected_file),
                verbosity="quiet",
            )

        assert result == str(expected_file)
        assert expected_file.exists()
        assert expected_file.read_bytes() == test_content

    def test_download_timeout_handling(self, output_dir: Path) -> None:
        """Test that timeout exceptions are propagated."""
        with patch.object(
            _client, "stream", side_effect=httpx.TimeoutException("Connection timed out")
        ):
            with pytest.raises(httpx.TimeoutException):
                download_file(
                    "https://example.com/file.txt",
                    out=str(output_dir / "timeout_test.txt"),
                    timeout=5.0,
                )

    def test_download_http_error_handling(self, output_dir: Path) -> None:
        """Test that HTTP errors are propagated."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
        )
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                download_file(
                    "https://example.com/notfound.txt",
                    out=str(output_dir / "error_test.txt"),
                )

    def test_download_no_filename_raises_error(self, output_dir: Path) -> None:
        """Test that ValueError is raised when filename cannot be determined."""
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.url = "https://example.com/"
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with pytest.raises(ValueError, match="Could not determine filename"):
                download_file("https://example.com/", verbosity="quiet")

    def test_download_progress_mode_with_tqdm(self, output_dir: Path) -> None:
        """Test download with progress verbosity shows tqdm progress bar."""
        output_file = output_dir / "progress_test.txt"
        test_content = b"Progress content data"
        content_length = len(test_content)

        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(content_length)}
        mock_response.url = "https://example.com/file.txt"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with patch("tqdm.tqdm") as mock_tqdm:
                mock_pbar = MagicMock()
                mock_tqdm.return_value.__enter__ = MagicMock(return_value=mock_pbar)
                mock_tqdm.return_value.__exit__ = MagicMock(return_value=False)

                result = download_file(
                    "https://example.com/file.txt",
                    out=str(output_file),
                    verbosity="progress",
                )

                mock_tqdm.assert_called_once_with(
                    total=content_length,
                    unit="B",
                    unit_scale=True,
                    desc=str(output_file),
                    leave=False,
                )
                mock_pbar.update.assert_called_with(len(test_content))

        assert result == str(output_file)
        assert output_file.exists()

    def test_download_progress_mode_no_content_length(self, output_dir: Path) -> None:
        """Test progress mode falls back to no progress bar when content-length missing."""
        output_file = output_dir / "no_content_length.txt"
        test_content = b"No content length"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.url = "https://example.com/file.txt"
        mock_response.iter_bytes = MagicMock(return_value=iter([test_content]))
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(_client, "stream", return_value=mock_response):
            with patch("tqdm.tqdm") as mock_tqdm:
                download_file(
                    "https://example.com/file.txt",
                    out=str(output_file),
                    verbosity="progress",
                )
                # tqdm should not be called when content-length is 0
                mock_tqdm.assert_not_called()

        assert output_file.exists()
        assert output_file.read_bytes() == test_content


class TestGlobalClient:
    """Tests for global httpx client."""

    def test_global_client_exists(self) -> None:
        """Test that global client is created."""
        assert _client is not None
        assert isinstance(_client, httpx.Client)

    def test_global_client_follows_redirects(self) -> None:
        """Test that global client is configured to follow redirects."""
        assert _client.follow_redirects is True
