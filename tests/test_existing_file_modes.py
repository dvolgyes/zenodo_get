#!/usr/bin/env python3
"""
Tests for existing file handling modes (--overwrite, --no-overwrite, --ignore-existing-files).
"""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from zenodo_get.zget import (
    EXISTING_FILE_IGNORE,
    EXISTING_FILE_NO_OVERWRITE,
    EXISTING_FILE_OVERWRITE,
    cli,
    download,
)


class TestMutualExclusivity:
    """Test that --overwrite, --no-overwrite, and --ignore-existing-files are mutually exclusive."""

    def test_overwrite_and_no_overwrite_error(self):
        """Test error when both --overwrite and --no-overwrite are specified."""
        runner = CliRunner()
        result = runner.invoke(cli, ["1215979", "--overwrite", "--no-overwrite", "-m"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_overwrite_and_ignore_error(self):
        """Test error when both --overwrite and --ignore-existing-files are specified."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["1215979", "--overwrite", "--ignore-existing-files", "-m"]
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_no_overwrite_and_ignore_error(self):
        """Test error when both --no-overwrite and --ignore-existing-files are specified."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["1215979", "--no-overwrite", "--ignore-existing-files", "-m"]
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_all_three_error(self):
        """Test error when all three options are specified."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "1215979",
                "--overwrite",
                "--no-overwrite",
                "--ignore-existing-files",
                "-m",
            ],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output


class TestOverwriteMode:
    """Test --overwrite mode behavior."""

    def test_overwrite_mode_replaces_file(self):
        """Test that --overwrite mode overwrites existing file with mismatched checksum."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # First download the file
            runner = CliRunner()
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            target_file = Path(temp_dir) / "fetch_data.py"
            assert target_file.exists()

            # Record original content
            original_content = target_file.read_text()

            # Modify the file
            target_file.write_text("modified content")
            assert target_file.read_text() != original_content

            # Re-download with --overwrite
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "--overwrite", "-v", "3"]
            )
            assert result.exit_code == 0
            assert "overwriting" in result.output.lower()

            # File should be restored
            assert target_file.read_text() == original_content

    def test_default_behavior_is_overwrite(self):
        """Test that default behavior (no flag) is same as --overwrite."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            # First download
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            target_file = Path(temp_dir) / "fetch_data.py"
            original_content = target_file.read_text()

            # Modify
            target_file.write_text("modified")

            # Re-download with no flag (default should be overwrite)
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            # File should be restored
            assert target_file.read_text() == original_content


class TestNoOverwriteMode:
    """Test --no-overwrite mode behavior."""

    def test_no_overwrite_mode_skips_and_errors(self):
        """Test that --no-overwrite mode skips file and exits with error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            # First download
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            target_file = Path(temp_dir) / "fetch_data.py"

            # Modify the file to create checksum mismatch
            target_file.write_text("modified content")
            modified_content = target_file.read_text()

            # Re-download with --no-overwrite
            result = runner.invoke(
                cli,
                ["1215979", "-g", "*.py", "-o", temp_dir, "--no-overwrite", "-v", "3"],
            )
            assert result.exit_code == 1
            assert "not overwritten" in result.output.lower()
            assert "mismatched checksums" in result.output.lower()

            # File should NOT be changed
            assert target_file.read_text() == modified_content


class TestIgnoreExistingFilesMode:
    """Test --ignore-existing-files mode behavior."""

    def test_ignore_mode_skips_silently(self):
        """Test that --ignore-existing-files mode skips file without error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            # First download
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            target_file = Path(temp_dir) / "fetch_data.py"

            # Modify the file to create checksum mismatch
            target_file.write_text("modified content")
            modified_content = target_file.read_text()

            # Re-download with --ignore-existing-files
            result = runner.invoke(
                cli,
                [
                    "1215979",
                    "-g",
                    "*.py",
                    "-o",
                    temp_dir,
                    "--ignore-existing-files",
                    "-v",
                    "3",
                ],
            )
            # Should exit successfully
            assert result.exit_code == 0
            assert "ignored" in result.output.lower()

            # File should NOT be changed
            assert target_file.read_text() == modified_content


class TestAPIParameterValidation:
    """Test the download() API function parameter validation."""

    def test_valid_modes(self):
        """Test that valid modes are accepted."""
        # Validation happens early, before network call
        # We test with invalid record to trigger error after validation passes
        for mode in [
            EXISTING_FILE_OVERWRITE,
            EXISTING_FILE_NO_OVERWRITE,
            EXISTING_FILE_IGNORE,
        ]:
            with tempfile.TemporaryDirectory() as temp_dir:
                # This should not raise ValueError for invalid mode
                with pytest.raises(Exception) as exc_info:
                    download(
                        record="999999999",  # Non-existent record
                        output_dir=temp_dir,
                        existing_file_mode=mode,
                    )
                # Error should be about record, not invalid mode
                assert "Invalid existing_file_mode" not in str(exc_info.value)

    def test_invalid_mode_raises_value_error(self):
        """Test that invalid mode raises ValueError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError) as exc_info:
                download(
                    record="1215979",
                    output_dir=temp_dir,
                    existing_file_mode="invalid_mode",
                )
            assert "Invalid existing_file_mode" in str(exc_info.value)
            assert "invalid_mode" in str(exc_info.value)


class TestAPIExceptionHandling:
    """Test that API raises exceptions correctly for no_overwrite mode."""

    def test_no_overwrite_raises_exception_when_files_skipped(self):
        """Test that no_overwrite mode raises exception when files are skipped."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # First download
            download(
                record="1215979",
                file_glob="*.py",
                output_dir=temp_dir,
                verbosity=0,
            )

            target_file = Path(temp_dir) / "fetch_data.py"

            # Modify file
            target_file.write_text("modified content")

            # Re-download with no_overwrite should raise
            with pytest.raises(Exception) as exc_info:
                download(
                    record="1215979",
                    file_glob="*.py",
                    output_dir=temp_dir,
                    existing_file_mode=EXISTING_FILE_NO_OVERWRITE,
                    verbosity=0,
                )
            assert "mismatched checksums" in str(exc_info.value).lower()


class TestHelpOutput:
    """Test that help output includes the new options."""

    def test_help_shows_overwrite_options(self):
        """Test that help output shows all three overwrite options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--overwrite" in result.output
        assert "--no-overwrite" in result.output
        assert "--ignore-existing-files" in result.output


class TestMatchingChecksumSkipsDownload:
    """Test that files with matching checksums are skipped (no re-download needed)."""

    def test_matching_checksum_skips_download(self):
        """Test that file with matching checksum is not re-downloaded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = CliRunner()
            # First download
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0

            # Re-download (without modification)
            result = runner.invoke(
                cli, ["1215979", "-g", "*.py", "-o", temp_dir, "-v", "3"]
            )
            assert result.exit_code == 0
            # Should indicate file is already downloaded correctly
            assert "already downloaded correctly" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
