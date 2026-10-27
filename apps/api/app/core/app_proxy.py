"""Verify Shopify app proxy signatures.

Shopify signs every storefront request it forwards through the app proxy. The
`logged_in_customer_id` parameter can only be trusted after this check passes.
"""

import hashlib
import hmac
import time
from collections.abc import Iterable

MAX_SIGNATURE_AGE_SECONDS = 300


def proxy_signature(params: Iterable[tuple[str, str]], secret: str) -> str:
    grouped: dict[str, list[str]] = {}
    for key, value in params:
        if key != 'signature':
            grouped.setdefault(key, []).append(value)
    message = ''.join(f'{key}={",".join(values)}' for key, values in sorted(grouped.items()))
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verified_proxy_params(params: Iterable[tuple[str, str]], secret: str, shop: str, now: float | None = None) -> dict | None:
    """Return the signed query parameters, or None when the request is not from Shopify."""
    params = list(params)
    values = dict(params)
    provided = values.get('signature', '')
    if not secret or not provided:
        return None
    if not hmac.compare_digest(proxy_signature(params, secret), provided):
        return None
    if shop and values.get('shop') != shop:
        return None
    try:
        timestamp = int(values.get('timestamp', ''))
    except ValueError:
        return None
    if abs((now if now is not None else time.time()) - timestamp) > MAX_SIGNATURE_AGE_SECONDS:
        return None
    return values
