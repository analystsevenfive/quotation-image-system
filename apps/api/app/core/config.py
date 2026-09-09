"""Application configuration and constants."""

from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """Core settings for Phase 1 PDF engine."""

    app_name: str = "Quotation Image Automation System"
    version: str = "0.1.0"

    # Network / Download settings
    http_timeout_seconds: float = 10.0
    max_image_bytes: int = 10 * 1024 * 1024  # 10 MB limit per image
    max_retries: int = 2

    # Output defaults
    default_output_suffix: str = "_with_images.pdf"


settings = Settings()
