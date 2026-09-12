"""SKU and model normalization functions."""

import re
from typing import Optional

# Unicode dashes to normalize to ASCII hyphen-minus '-'
# Includes en-dash (\u2013), em-dash (\u2014), horizontal bar (\u2015), minus sign (\u2212), figure dash (\u2012)
UNICODE_DASHES_PATTERN = re.compile(r"[\u00AD\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]")

# Whitespace cleaner: tabs, newlines, zero-width spaces, repeated spaces
WHITESPACE_PATTERN = re.compile(r"[\s\u200B\uFEFF]+")


def normalize_sku(raw_sku: Optional[str]) -> str:
    """
    Normalizes an SKU string for reliable matching.
    
    Operations:
    1. Strip leading and trailing whitespace/newlines
    2. Convert to uppercase
    3. Normalize various Unicode dash/hyphen characters to standard ASCII '-'
    4. Remove internal linebreaks and collapse consecutive spaces
    5. Strip non-standard surrounding punctuation (quotes, brackets)
    """
    if not raw_sku:
        return ""

    s = str(raw_sku).strip()
    if not s:
        return ""

    # Replace newlines and tabs with space
    s = s.replace("\r", " ").replace("\n", " ")

    # Normalize unicode dashes
    s = UNICODE_DASHES_PATTERN.sub("-", s)

    # Convert to uppercase
    s = s.upper()

    # Collapse multiple spaces
    s = WHITESPACE_PATTERN.sub(" ", s).strip()

    # Strip accidental wrapping quotes or parenthesis
    s = s.strip("'\"()[]{}")

    return s


def extract_model_from_sku(sku: Optional[str]) -> Optional[str]:
    """
    Extracts a candidate model from a brand-prefixed SKU.
    For example:
      'BER1-BMCFP4' -> 'BMCFP4'
      'CW-76' -> '76'
    Returns None if no standard prefix separator is present or result is too short.
    """
    norm = normalize_sku(sku)
    if not norm:
        return None

    # If there's a hyphen or slash separator, try taking the part after the first prefix
    if "-" in norm:
        parts = norm.split("-", 1)
        suffix = parts[1].strip()
        if len(suffix) >= 2:
            return suffix
    elif "/" in norm:
        parts = norm.split("/", 1)
        suffix = parts[1].strip()
        if len(suffix) >= 2:
            return suffix

    return None


def normalize_image_url(url: Optional[str], width: int = 200) -> Optional[str]:
    """Ensure Shopify CDN image URLs include width optimization parameter."""
    if not url or "cdn.shopify.com" not in url:
        return url
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["width"] = [str(width)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


