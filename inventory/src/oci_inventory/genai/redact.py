from __future__ import annotations

import re

# Conservative redaction: enough to avoid leaking OCIDs/URLs, but still readable.
_OCID_RE = re.compile(r"\bocid1\.[a-zA-Z0-9._-]+\b")
_URL_RE = re.compile(r"\bhttps?://\S+\b")


def redact_text(text: str) -> str:
    if not text:
        return ""
    out = str(text)
    out = _OCID_RE.sub("<ocid>", out)
    out = _URL_RE.sub("<url>", out)
    return out
