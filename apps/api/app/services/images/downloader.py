"""Resilient image downloading with HTTP timeouts, retries, and format validation."""

import io
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import urllib.parse

import httpx
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}
SUPPORTED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/x-png",
    "image/pjpeg",
}


class ImageDownloadError(Exception):
    """Raised when an image cannot be downloaded or validated."""


class ImageDownloader:
    """
    Downloads and validates product images from Shopify CDN or HTTP URLs.
    Includes in-memory caching and offline local path support.
    """

    def __init__(
        self,
        timeout: float = settings.http_timeout_seconds,
        max_bytes: int = settings.max_image_bytes,
        max_retries: int = settings.max_retries,
    ):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_retries = max_retries
        self._cache: Dict[str, bytes] = {}

    def get_image(self, url_or_path: str) -> Optional[bytes]:
        """
        Retrieves and validates image bytes.
        Returns bytes if valid, or None if image cannot be loaded.
        Does not raise exceptions to ensure broken images never crash the pipeline.
        """
        if not url_or_path:
            return None

        # Check in-memory cache
        if url_or_path in self._cache:
            return self._cache[url_or_path]

        try:
            image_bytes = self._fetch_bytes(url_or_path)
            self._validate_image(image_bytes)
            # Bound the temporary image cache in a long-running web process.
            if sum(map(len, self._cache.values())) + len(image_bytes) > 64 * 1024 * 1024:
                self._cache.clear()
            self._cache[url_or_path] = image_bytes
            return image_bytes
        except Exception as e:
            logger.warning("Failed to retrieve image '%s': %s", url_or_path, str(e))
            return None

    def _fetch_bytes(self, url_or_path: str) -> bytes:
        """Fetches raw bytes from local file or HTTP URL."""
        # Check if local file path or file:// URI
        if url_or_path.startswith("file://"):
            local_path = Path(urllib.parse.unquote(url_or_path[7:]))
            if not local_path.is_file():
                raise ImageDownloadError(f"Local image file not found: {local_path}")
            return local_path.read_bytes()

        path_obj = Path(url_or_path)
        if path_obj.is_file():
            return path_obj.read_bytes()

        # Otherwise treat as HTTP/HTTPS URL
        if not url_or_path.startswith(("http://", "https://")):
            raise ImageDownloadError(f"Unsupported image protocol or path: {url_or_path}")

        headers = {
            "User-Agent": "QuotationImageSystem/0.1 (FastAPI/PyMuPDF; internal-tools)"
        }

        transport = httpx.HTTPTransport(retries=self.max_retries)
        with httpx.Client(timeout=self.timeout, transport=transport, follow_redirects=False) as client:
            with client.stream('GET', url_or_path, headers=headers) as resp:
                if resp.status_code != 200:
                    raise ImageDownloadError(f"HTTP GET returned status {resp.status_code}")
                if resp.headers.get('content-type', '').split(';')[0].strip().lower() not in SUPPORTED_CONTENT_TYPES:
                    raise ImageDownloadError('Unsupported image Content-Type')
                content_length = resp.headers.get('content-length')
                if content_length and int(content_length) > self.max_bytes:
                    raise ImageDownloadError('Image exceeds max byte limit')
                data = bytearray()
                for chunk in resp.iter_bytes(65536):
                    data.extend(chunk)
                    if len(data) > self.max_bytes:
                        raise ImageDownloadError('Image exceeds max byte limit')
                return bytes(data)

    def _validate_image(self, data: bytes) -> Tuple[int, int, str]:
        """
        Validates that raw bytes represent a valid, decodable image.
        Returns (width, height, format).
        """
        if not data:
            raise ImageDownloadError("Empty image payload")

        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()  # verify integrity
                width, height = img.size
                img_format = img.format
                if img_format not in SUPPORTED_FORMATS:
                    raise ImageDownloadError(f"Unsupported image format: {img_format}")
                if width <= 0 or height <= 0:
                    raise ImageDownloadError(f"Invalid image dimensions: {width}x{height}")
                return width, height, img_format
        except Exception as e:
            raise ImageDownloadError(f"Corrupt or unreadable image data: {str(e)}") from e
