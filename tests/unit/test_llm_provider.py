import json

from app.core.llm import MockProvider


def test_mock_provider_never_calls_network_and_returns_conservative_json():
    provider = MockProvider()
    resp = provider.complete("[TASK:attribute_extraction] extract stuff", "some product text")
    data = resp.json()
    assert data == {"claims": []}
    assert resp.provider == "mock"


def test_mock_provider_classification_task_defers_to_deterministic_layer():
    provider = MockProvider()
    resp = provider.complete("[TASK:classification] classify", "user content")
    data = resp.json()
    assert data["classpath"] is None
    assert data["confidence"] == 0.0


def test_json_extraction_handles_fenced_code_block():
    from app.core.llm import LLMResponse

    resp = LLMResponse(text="Here you go:\n```json\n{\"a\": 1}\n```", model="x", provider="mock")
    assert resp.json() == {"a": 1}
