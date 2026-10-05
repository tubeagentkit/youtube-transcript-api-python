"""Verify batch-completion webhooks sent by the GetYouTubeTranscript API.

Each delivery carries an ``X-GYT-Signature: t=<unix seconds>,v1=<hex>``
header, where ``v1`` is the HMAC-SHA256 of ``"<t>.<raw request body>"`` keyed
with the ``webhook_secret`` that :meth:`Client.create_batch` returned.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional, Union

DEFAULT_TOLERANCE_SECONDS = 300


def verify_webhook_signature(
    body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> bool:
    """Return True if a webhook delivery is genuine and recent.

    Args:
        body: The raw request body exactly as received. Don't re-serialize
            parsed JSON: any whitespace change breaks the signature.
        signature_header: The ``X-GYT-Signature`` header value.
        secret: The batch's ``webhook_secret`` (``whsec_...``).
        tolerance_seconds: Reject signatures older (or newer) than this, to
            limit replays. Pass 0 to skip the age check.
        now: Current Unix time, for tests. Defaults to ``time.time()``.
    """
    if not signature_header or not secret:
        return False
    parts = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
    timestamp, signature = parts.get("t", ""), parts.get("v1", "")
    if not timestamp.isdigit() or not signature:
        return False
    if tolerance_seconds and abs((time.time() if now is None else now) - int(timestamp)) > tolerance_seconds:
        return False

    raw = body.encode("utf-8") if isinstance(body, str) else body
    expected = hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
