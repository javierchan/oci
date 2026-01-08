from __future__ import annotations

from typing import Any

import oci

from oci_inventory.genai.chat_runner import run_genai_chat
from oci_inventory.genai.config import GenAIConfig


class _Obj:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Ctx:
    def __init__(self) -> None:
        self.config_dict = {"user": "x", "fingerprint": "y", "tenancy": "z", "region": "us-chicago-1"}
        self.signer = object()


class _FakeClientGeneric:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def chat(self, _details: Any, **_kwargs: Any) -> Any:
        # resp.data.chat_response.choices[0].message.content[0].text
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        _Obj(message=_Obj(content=[_Obj(text="- ok")], refusal=None))
                    ]
                )
            )
        )


class _FakeClientCohere:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def chat(self, _details: Any, **_kwargs: Any) -> Any:
        # resp.data.chat_response.text
        return _Obj(data=_Obj(chat_response=_Obj(text="- cohere ok")))


def test_run_genai_chat_generic_parses_text(monkeypatch: Any) -> None:
    import oci_inventory.genai.chat_runner as cr

    monkeypatch.setattr(cr, "resolve_auth", lambda *_a, **_k: _Ctx())
    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeClientGeneric  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out, hint = run_genai_chat(message="hello", api_format="GENERIC", genai_cfg=cfg)
    assert out.startswith("-")
    assert hint.get("api_format") == "GENERIC"


def test_run_genai_chat_cohere_parses_text(monkeypatch: Any) -> None:
    import oci_inventory.genai.chat_runner as cr

    monkeypatch.setattr(cr, "resolve_auth", lambda *_a, **_k: _Ctx())
    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeClientCohere  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out, hint = run_genai_chat(message="hello", api_format="COHERE", genai_cfg=cfg)
    assert "cohere" in out
    assert hint.get("api_format") == "COHERE"
