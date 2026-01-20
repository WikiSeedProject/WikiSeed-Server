"""Download client with resumable downloads and checksum verification."""

import hashlib
import time
from pathlib import Path
from typing import Optional

import requests

from src.common.logging import setup_logging

logger = setup_logging(__name__)


class DownloadError(Exception):
    """Download failed."""

    pass


class ChecksumError(Exception):
    """Checksum verification failed."""

    pass


class DownloadClient:
    """Client for downloading files with resume support and verification."""

    USER_AGENT = "WikiSeed/0.1.0 (https://wikiseed.app; hello@wikiseed.app)"
    CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks for streaming
    REQUEST_TIMEOUT = 300  # 5 minutes

    def __init__(self, download_dir: Path, max_retries: int = 3) -> None:
        """Initialize download client.

        Args:
            download_dir: Directory to save downloaded files
            max_retries: Maximum number of retries for failed requests
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def download(
        self,
        url: str,
        filename: str,
        expected_size: Optional[int] = None,
        expected_md5: Optional[str] = None,
        expected_sha1: Optional[str] = None,
    ) -> Path:
        """Download a file with resume support and checksum verification.

        Args:
            url: URL to download from
            filename: Filename to save as
            expected_size: Expected file size in bytes
            expected_md5: Expected MD5 checksum
            expected_sha1: Expected SHA1 checksum

        Returns:
            Path to downloaded file

        Raises:
            DownloadError: If download fails
            ChecksumError: If checksum verification fails
        """
        local_path = self.download_dir / filename

        # Check if file already exists and is complete
        if local_path.exists() and expected_size:
            current_size = local_path.stat().st_size
            if current_size == expected_size:
                logger.info(f"File already exists with correct size: {local_path}")

                # Verify checksums if provided
                if expected_md5 or expected_sha1:
                    try:
                        self._verify_checksums(local_path, expected_md5, expected_sha1)
                        logger.info(f"File verified: {local_path}")
                        return local_path
                    except ChecksumError:
                        logger.warning(f"Existing file has incorrect checksum, re-downloading: {local_path}")
                        local_path.unlink()
                else:
                    return local_path

        # Download with resume support
        resume_byte_pos = 0
        if local_path.exists():
            resume_byte_pos = local_path.stat().st_size
            logger.info(f"Resuming download from byte {resume_byte_pos}")

        for attempt in range(self.max_retries):
            try:
                self._download_with_resume(url, local_path, resume_byte_pos)

                # Verify size
                if expected_size:
                    actual_size = local_path.stat().st_size
                    if actual_size != expected_size:
                        raise DownloadError(
                            f"Size mismatch: expected {expected_size} bytes, got {actual_size} bytes"
                        )

                # Verify checksums
                if expected_md5 or expected_sha1:
                    self._verify_checksums(local_path, expected_md5, expected_sha1)

                logger.info(f"Download successful: {local_path}")
                return local_path

            except (requests.exceptions.RequestException, DownloadError, ChecksumError) as e:
                logger.warning(f"Download attempt {attempt + 1}/{self.max_retries} failed: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

                    # Update resume position if file was partially downloaded
                    if local_path.exists():
                        resume_byte_pos = local_path.stat().st_size
                else:
                    # Last attempt failed - clean up partial file
                    if local_path.exists():
                        local_path.unlink()
                    raise DownloadError(f"Failed to download {url} after {self.max_retries} attempts: {e}")

        raise DownloadError(f"Failed to download {url}")

    def _download_with_resume(self, url: str, local_path: Path, resume_byte_pos: int = 0) -> None:
        """Download a file with resume support.

        Args:
            url: URL to download from
            local_path: Path to save file to
            resume_byte_pos: Byte position to resume from (0 for new download)

        Raises:
            DownloadError: If download fails
            requests.exceptions.RequestException: If HTTP request fails
        """
        headers = {}
        if resume_byte_pos > 0:
            headers["Range"] = f"bytes={resume_byte_pos}-"

        logger.debug(f"Downloading {url} to {local_path} (resume from {resume_byte_pos})")

        response = self.session.get(url, headers=headers, stream=True, timeout=self.REQUEST_TIMEOUT)

        # Check response
        if resume_byte_pos > 0 and response.status_code == 206:
            # Partial content - resuming
            mode = "ab"
        elif resume_byte_pos == 0 and response.status_code == 200:
            # Full content - new download
            mode = "wb"
        elif response.status_code == 200 and resume_byte_pos > 0:
            # Server doesn't support resume - start over
            logger.warning("Server doesn't support resume, starting from beginning")
            mode = "wb"
            resume_byte_pos = 0
        else:
            raise DownloadError(f"Unexpected status code: {response.status_code}")

        # Get total size
        content_length = response.headers.get("Content-Length")
        if content_length:
            total_size = int(content_length) + resume_byte_pos
            logger.info(f"Total size: {total_size:,} bytes")

        # Download in chunks
        downloaded_bytes = resume_byte_pos
        start_time = time.time()
        last_log_time = start_time

        with open(local_path, mode) as f:
            for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

                    # Log progress every 10 seconds
                    current_time = time.time()
                    if current_time - last_log_time >= 10:
                        elapsed = current_time - start_time
                        speed = (downloaded_bytes - resume_byte_pos) / elapsed if elapsed > 0 else 0
                        speed_mb = speed / (1024 * 1024)

                        if content_length:
                            progress_pct = (downloaded_bytes / total_size) * 100
                            logger.info(
                                f"Progress: {downloaded_bytes:,} / {total_size:,} bytes ({progress_pct:.1f}%) "
                                f"@ {speed_mb:.2f} MB/s"
                            )
                        else:
                            logger.info(f"Downloaded: {downloaded_bytes:,} bytes @ {speed_mb:.2f} MB/s")

                        last_log_time = current_time

        # Final log
        elapsed = time.time() - start_time
        avg_speed_mb = ((downloaded_bytes - resume_byte_pos) / elapsed / (1024 * 1024)) if elapsed > 0 else 0
        logger.info(
            f"Download complete: {downloaded_bytes:,} bytes in {elapsed:.1f}s (avg {avg_speed_mb:.2f} MB/s)"
        )

    def _verify_checksums(
        self, file_path: Path, expected_md5: Optional[str] = None, expected_sha1: Optional[str] = None
    ) -> None:
        """Verify file checksums.

        Args:
            file_path: Path to file to verify
            expected_md5: Expected MD5 checksum (optional)
            expected_sha1: Expected SHA1 checksum (optional)

        Raises:
            ChecksumError: If checksum doesn't match
        """
        logger.info(f"Verifying checksums for {file_path.name}")

        # Calculate checksums
        md5_hash = hashlib.md5()
        sha1_hash = hashlib.sha1()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.CHUNK_SIZE), b""):
                if expected_md5:
                    md5_hash.update(chunk)
                if expected_sha1:
                    sha1_hash.update(chunk)

        # Verify MD5
        if expected_md5:
            actual_md5 = md5_hash.hexdigest()
            if actual_md5.lower() != expected_md5.lower():
                raise ChecksumError(f"MD5 mismatch: expected {expected_md5}, got {actual_md5}")
            logger.debug(f"MD5 verified: {actual_md5}")

        # Verify SHA1
        if expected_sha1:
            actual_sha1 = sha1_hash.hexdigest()
            if actual_sha1.lower() != expected_sha1.lower():
                raise ChecksumError(f"SHA1 mismatch: expected {expected_sha1}, got {actual_sha1}")
            logger.debug(f"SHA1 verified: {actual_sha1}")

        logger.info(f"Checksum verification passed for {file_path.name}")
