from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models import Opportunity


_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}


def canonicalize_url(value: str) -> str:
    """Return a stable URL while preserving parameters that identify the vacancy."""
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.casefold()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_PARAMETERS:
            continue
        query_items.append((key, item_value))
    query_items.sort(key=lambda item: (item[0].casefold(), item[1]))

    return urlunsplit((scheme, hostname, path, urlencode(query_items, doseq=True), ""))


def normalize_identity_text(value: str) -> str:
    """Normalize provider-specific text noise before creating an exact fingerprint."""
    normalized = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def opportunity_fingerprint(opportunity: Opportunity) -> str:
    fields = (
        opportunity.company_name,
        opportunity.title,
        opportunity.location,
        opportunity.description,
    )
    payload = "\x1f".join(normalize_identity_text(value) for value in fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

