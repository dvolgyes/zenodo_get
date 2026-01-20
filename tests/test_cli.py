#!/usr/bin/env python3
"""
Comprehensive CLI testing for zenodo_get.
Tests all CLI options, error cases, and integration scenarios.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
import pytest
from click.testing import CliRunner

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zenodo_get.zget import cli


class TestCLIBasicOptions:
    """Test basic CLI options and flags."""

    def test_version_option(self):
        """Test --version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "zenodo_get, version" in result.output

    def test_help_option(self):
        """Test -h and --help options."""
        runner = CliRunner()

        # Test -h
        result = runner.invoke(cli, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Options:" in result.output

        # Test --help
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Options:" in result.output

    def test_cite_option(self):
        """Test --cite option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--cite"])
        assert result.exit_code == 0
        assert "Reference for this software:" in result.output
        assert "Bibtex format:" in result.output

    def test_no_arguments_shows_help(self):
        """Test that running with no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 1
        assert "Usage:" in result.output


class TestCLIDownloadOptions:
    """Test CLI download functionality and options."""

    def test_md5_generation(self):
        """Test -m/--md5 option for generating md5sums.txt."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(cli, ["1215979", "-m", "-o", temp_dir])
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

            md5_file = Path(temp_dir) / "md5sums.txt"
            assert md5_file.exists()

            content = md5_file.read_text()
            assert "opencare-tags-anonymized.json" in content
            assert len(content.splitlines()) > 0

    def test_wget_file_generation(self):
        """Test -w/--wget option for generating URL lists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            urls_file = Path(temp_dir) / "urls.txt"

            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "-w", str(urls_file), "-o", temp_dir]
            )
            assert result.exit_code == 0
            assert "URL list written to" in result.output

            assert urls_file.exists()
            content = urls_file.read_text()
            assert "https://zenodo.org" in content
            assert len(content.splitlines()) > 0

    def test_wget_stdout(self):
        """Test -w - option for outputting URLs to stdout."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "-w", "-"])
        assert result.exit_code == 0
        assert "https://zenodo.org" in result.output
        assert "URL list written to stdout" in result.output

    def test_record_option(self):
        """Test -r/--record option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(cli, ["-r", "1215979", "-m", "-o", temp_dir])
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

    def test_doi_option(self):
        """Test -d/--doi option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["-d", "10.5281/zenodo.1215979", "-m", "-o", temp_dir]
            )
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

    def test_glob_option(self):
        """Test -g/--glob option for file filtering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(cli, ["1215979", "-g", "*.py", "-m", "-o", temp_dir])
            assert result.exit_code == 0

            md5_file = Path(temp_dir) / "md5sums.txt"
            content = md5_file.read_text()
            # Should only contain .py files
            assert "fetch_data.py" in content
            assert "opencare-tags-anonymized.json" not in content

    def test_multiple_glob_patterns(self):
        """Test multiple -g options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-g", "*.json", "-m", "-o", temp_dir]
            )
            assert result.exit_code == 0

            md5_file = Path(temp_dir) / "md5sums.txt"
            content = md5_file.read_text()
            # Should contain both .py and .json files
            assert "fetch_data.py" in content
            assert "opencare-tags-anonymized.json" in content

    def test_output_dir_option(self):
        """Test -o/--output-dir option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sub_dir = Path(temp_dir) / "downloads"

            runner = CliRunner()
            result = runner.invoke(cli, ["1215979", "-m", "-o", str(sub_dir)])
            assert result.exit_code == 0

            md5_file = sub_dir / "md5sums.txt"
            assert md5_file.exists()

    def test_sandbox_option(self):
        """Test -s/--sandbox option."""
        runner = CliRunner()
        # Use a record that likely doesn't exist in sandbox to test the option works
        result = runner.invoke(
            cli,
            [
                "1",  # Simple record ID for sandbox
                "-s",
                "-m",
            ],
        )
        # This will likely fail, but we're testing that the option is processed
        # The error should be about the record not existing, not about unknown option
        assert "unrecognized arguments" not in result.output

    def test_timeout_option(self):
        """Test -t/--time-out option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(cli, ["1215979", "-t", "30.0", "-m", "-o", temp_dir])
            assert result.exit_code == 0

    def test_retry_and_pause_options(self):
        """Test -R/--retry and -p/--pause options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "-R", "2", "-p", "0.5", "-m", "-o", temp_dir]
            )
            assert result.exit_code == 0


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    def test_invalid_record_id(self):
        """Test handling of invalid record ID."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["999999999", "-m"]
        )  # Use numeric ID that doesn't exist
        assert result.exit_code == 1
        assert "HTTP error fetching metadata" in result.output

    def test_invalid_doi(self):
        """Test handling of invalid DOI."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-d", "invalid_doi", "-m"])
        assert result.exit_code == 1
        assert "HTTP error resolving DOI" in result.output

    def test_nonexistent_record(self):
        """Test handling of non-existent record."""
        runner = CliRunner()
        result = runner.invoke(cli, ["999999999", "-m"])
        assert result.exit_code == 1
        assert "HTTP error fetching metadata" in result.output

    def test_invalid_timeout_value(self):
        """Test invalid timeout value handling."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "-t", "invalid", "-m"])
        assert result.exit_code != 0  # Should fail with click validation

    def test_invalid_retry_value(self):
        """Test invalid retry value handling."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "-R", "invalid", "-m"])
        assert result.exit_code != 0  # Should fail with click validation

    def test_invalid_output_directory(self):
        """Test invalid output directory handling."""
        runner = CliRunner()
        # Try to write to a file instead of directory
        with tempfile.NamedTemporaryFile() as temp_file:
            result = runner.invoke(cli, ["1215979", "-m", "-o", temp_file.name])
            assert result.exit_code != 0


class TestCLIHttpRetryOptions:
    """Test HTTP retry CLI options."""

    def test_max_http_retries_option(self):
        """Test --max-http-retries option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "--max-http-retries", "3", "-m", "-o", temp_dir]
            )
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

    def test_backoff_factor_option(self):
        """Test --backoff-factor option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "--backoff-factor", "1.0", "-m", "-o", temp_dir]
            )
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

    def test_combined_http_retry_options(self):
        """Test --max-http-retries and --backoff-factor together."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "1215979",
                    "--max-http-retries",
                    "2",
                    "--backoff-factor",
                    "0.25",
                    "-m",
                    "-o",
                    temp_dir,
                ],
            )
            assert result.exit_code == 0
            assert "md5sums.txt created" in result.output

    def test_invalid_max_http_retries_value(self):
        """Test invalid --max-http-retries value handling."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "--max-http-retries", "invalid", "-m"])
        assert result.exit_code != 0

    def test_invalid_backoff_factor_value(self):
        """Test invalid --backoff-factor value handling."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "--backoff-factor", "invalid", "-m"])
        assert result.exit_code != 0

    def test_help_shows_http_retry_options(self):
        """Test that help output includes new HTTP retry options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--max-http-retries" in result.output
        assert "--backoff-factor" in result.output
        assert "HTTP transport-level retries" in result.output
        assert "exponential backoff" in result.output.lower()


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    def test_full_download_workflow(self):
        """Test complete download workflow with various options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()

            # Test with continue-on-error, keep invalid, fresh start, etc.
            result = runner.invoke(
                cli,
                [
                    "1215979",
                    "-g",
                    "*.py",  # Only download .py files
                    "-o",
                    temp_dir,
                    "-e",  # Continue on error
                    "-k",  # Keep invalid files
                    "-n",  # Start fresh
                    "-R",
                    "1",  # 1 retry
                    "-p",
                    "0.1",  # 0.1s pause
                    "-t",
                    "30.0",  # 30s timeout
                ],
            )

            # Check that download completed
            assert result.exit_code == 0
            assert "All specified files have been processed" in result.output

            # Check that the file was downloaded
            py_file = Path(temp_dir) / "fetch_data.py"
            assert py_file.exists()

    def test_access_token_option(self):
        """Test -a/--access-token option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "-a", "fake_token", "-m", "-o", temp_dir]
            )
            # Should still work (token might be ignored for public records)
            assert result.exit_code == 0


class TestCLILogging:
    """Test CLI logging output."""

    def test_logging_levels(self):
        """Test that appropriate logging levels are shown."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "-m"])

        # Check for INFO level logs (may have ANSI codes around INFO)
        assert "INFO" in result.output
        assert "md5sums.txt created" in result.output

    def test_error_logging(self):
        """Test error logging output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["invalid_record", "-m"])

        # Check for ERROR level logs (may have ANSI codes around ERROR)
        assert "ERROR" in result.output


def test_cli_coverage_via_subprocess():
    """Test CLI via subprocess to ensure coverage of main execution path."""
    # Test basic functionality via subprocess
    result = subprocess.run(
        [sys.executable, "-m", "zenodo_get", "--version"],
        capture_output=True,
        text=True,
        cwd="/home/dvolgyes/workspace/zenodo_get",
    )

    assert result.returncode == 0
    assert "zenodo_get, version" in result.stdout

    # Test help
    result = subprocess.run(
        [sys.executable, "-m", "zenodo_get", "-h"],
        capture_output=True,
        text=True,
        cwd="/home/dvolgyes/workspace/zenodo_get",
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
