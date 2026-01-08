from __future__ import annotations

from oci_inventory.genai.redact import redact_text


def test_redact_text_removes_ocids_and_urls() -> None:
    text = "compartment ocid1.compartment.oc1..aaaa and url https://example.com/x"
    out = redact_text(text)
    assert "ocid1." not in out
    assert "https://" not in out
    assert "<ocid>" in out
    assert "<url>" in out
