from __future__ import annotations

from typing import Any, Optional

import oci

from oci_inventory.genai.config import GenAIConfig
from oci_inventory.genai.executive_summary import generate_executive_summary


class _Obj:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeGenerateTextDetails(_Obj):
    pass


class _FakeOnDemandServingMode(_Obj):
    pass


class _FakeLlamaReq(_Obj):
    pass


class _FakeClient:
    last_prompt: Optional[str] = None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        prompt = getattr(getattr(details, "inference_request", None), "prompt", "")
        _FakeClient.last_prompt = str(prompt)
        # Return an SDK-shaped response: resp.data.inference_response.choices[0].text
        return _Obj(
            data=_Obj(
                inference_response=_Obj(
                    choices=[_Obj(text="- Inventory completed successfully\n- No critical issues detected")]
                )
            )
        )


class _FakeServiceError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class _FakeChatClient:
    last_prompt: Optional[str] = None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        prompt = getattr(getattr(details, "inference_request", None), "prompt", "")
        _FakeChatClient.last_prompt = str(prompt)
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # details.chat_request.messages[*] includes SystemMessage + UserMessage
        msgs = getattr(getattr(details, "chat_request", None), "messages", None) or []
        txt = ""
        for m in reversed(msgs):
            role = getattr(m, "role", None)
            if role == "USER":
                content = getattr(m, "content", None) or []
                if content:
                    txt = getattr(content[0], "text", "")
                break
        _FakeChatClient.last_prompt = str(txt)

        # resp.data.chat_response.choices[0].message.content[0].text
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        _Obj(
                            message=_Obj(
                                content=[_Obj(text="- Executive summary via chat")]
                            )
                        )
                    ]
                )
            )
        )


class _FakeChatClient404(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        prompt = getattr(getattr(details, "inference_request", None), "prompt", "")
        _FakeChatClient404.last_prompt = str(prompt)
        raise _FakeServiceError(
            "Entity with key ocid1.generativeaimodel.oc1..aaaaMODEL not found",
            status=404,
        )


class _FakeChatClientDictContent(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        # Force chat fallback
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # Return dict-shaped content blocks (some SDK versions can deserialize similarly)
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        {
                            "message": {
                                "content": [
                                    {"text": "- Executive summary via chat"},
                                    {"text": "- Second bullet"},
                                ]
                            }
                        }
                    ]
                )
            )
        )


class _FakeChatClientChoicesOnData(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # Return choices directly on data (no chat_response wrapper)
        return _Obj(
            data=_Obj(
                choices=[
                    {
                        "message": {
                            "content": {"text": "- Summary from alternate shape"}
                        }
                    }
                ]
            )
        )


class _FakeChatClientEchoesModelOcid(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # Simulate the bad real-world outcome we saw: model returns an OCID string.
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        _Obj(
                            message=_Obj(
                                content=[_Obj(text="ocid1.generativeaimodel.oc1..aaaaMODEL")]
                            )
                        )
                    ]
                )
            )
        )


class _FakeChatClientRefusalOnly(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # Simulate an assistant refusal message without content.
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        _Obj(
                            message=_Obj(
                                content=[_Obj(text="")],
                                refusal="- Unable to generate summary due to safety policy.",
                            )
                        )
                    ]
                )
            )
        )


class _FakeChatClientGenericEmptyThenCohere(_FakeChatClient):
    def generate_text(self, details: Any, **_kwargs: Any) -> Any:
        # Force chat fallback
        raise _FakeServiceError(
            "model OCID ocid1.generativeaimodel.oc1..aaaaMODEL does not support TextGeneration",
            status=400,
        )

    def chat(self, details: Any, **_kwargs: Any) -> Any:
        # Detect which api_format the request is using.
        req = getattr(details, "chat_request", None)
        api_format = getattr(req, "api_format", None) or getattr(req, "_api_format", None)

        if api_format == "COHERE":
            # Return a CohereChatResponse-like shape: resp.data.chat_response.text
            return _Obj(data=_Obj(chat_response=_Obj(text="- Executive summary via cohere")))

        # Default/generic: return an SDK-ish response but with empty content.
        return _Obj(
            data=_Obj(
                chat_response=_Obj(
                    choices=[
                        _Obj(
                            message=_Obj(
                                content=[_Obj(text="")]
                            )
                        )
                    ]
                )
            )
        )


def test_generate_executive_summary_mocks_sdk_and_redacts() -> None:
    import oci.generative_ai_inference  # noqa: F401
    import oci.generative_ai_inference.models  # noqa: F401

    # Patch OCI SDK classes used by generate_executive_summary.
    # This keeps tests offline and deterministic.
    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeClient  # type: ignore[attr-defined]
    oci.generative_ai_inference.models.GenerateTextDetails = _FakeGenerateTextDetails  # type: ignore[attr-defined]
    oci.generative_ai_inference.models.OnDemandServingMode = _FakeOnDemandServingMode  # type: ignore[attr-defined]
    oci.generative_ai_inference.models.LlamaLlmInferenceRequest = _FakeLlamaReq  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[{"region": "us-dallas-1", "reason": "401 NotAuthenticated ocid1.user.oc1..aaa"}],
        metrics={
            "total_discovered": 12,
            "counts_by_enrich_status": {"OK": 10, "ERROR": 2, "NOT_IMPLEMENTED": 0},
            "counts_by_resource_type": {"oci.core.instance": 8, "oci.objectstorage.bucket": 4},
        },
    )

    assert out.startswith("-")

    prompt = _FakeClient.last_prompt or ""
    # Ensure we are not leaking OCIDs or URLs in the prompt.
    assert "ocid1." not in prompt
    assert "https://" not in prompt
    assert "Excluded regions" in prompt
    assert "us-dallas-1" in prompt


def test_generate_executive_summary_falls_back_to_chat_when_text_generation_unsupported() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClient  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "chat" in out.lower() or out.startswith("-")

    prompt = _FakeChatClient.last_prompt or ""
    assert "ocid1." not in prompt
    assert "https://" not in prompt


def test_generate_executive_summary_retries_chat_with_cohere_format_when_generic_is_empty() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClientGenericEmptyThenCohere  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "cohere" in out.lower()


def test_generate_executive_summary_falls_back_to_chat_when_generate_text_model_not_found() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClient404  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "chat" in out.lower() or out.startswith("-")


def test_generate_executive_summary_chat_parses_dict_content_blocks() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClientDictContent  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "Executive summary via chat" in out
    assert "Second bullet" in out


def test_generate_executive_summary_chat_parses_choices_on_data_shape() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClientChoicesOnData  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "alternate shape" in out


def test_generate_executive_summary_rejects_ocid_only_chat_output() -> None:
    import pytest
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClientEchoesModelOcid  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    with pytest.raises(RuntimeError):
        generate_executive_summary(
            genai_cfg=cfg,
            status="OK",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            subscribed_regions=["mx-queretaro-1"],
            requested_regions=None,
            excluded_regions=[],
            metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
        )


def test_generate_executive_summary_uses_refusal_when_content_empty() -> None:
    import oci.generative_ai_inference  # noqa: F401

    oci.generative_ai_inference.GenerativeAiInferenceClient = _FakeChatClientRefusalOnly  # type: ignore[attr-defined]

    cfg = GenAIConfig(
        oci_profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..aaaaSECRET",
        endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        base_model_id="ocid1.generativeaimodel.oc1..aaaaMODEL",
        vision_model_id=None,
    )

    out = generate_executive_summary(
        genai_cfg=cfg,
        status="OK",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        metrics={"total_discovered": 1, "counts_by_enrich_status": {"OK": 1}},
    )

    assert "safety" in out.lower()
