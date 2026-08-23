"""LLM provider abstraction.

Deterministic string/number work never reaches this module (casing, UOM
conversion, fraction lookup, exact validation). This is reserved for the
genuinely ambiguous steps: hard classification, complex extraction, entity
adjudication, conflict resolution, and grounded description generation.

APP_MODE=mock uses MockProvider (deterministic, template-based, offline,
zero external calls) so the whole pipeline, API, and test suite run without
credentials. APP_MODE=claude routes to ClaudeProvider.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config.settings import settings


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: dict | None = None

    def json(self) -> dict:
        """Best-effort extraction of a JSON object from the response text."""
        text = self.text.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidate = fence.group(1) if fence else text
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            brace = re.search(r"\{.*\}", text, re.DOTALL)
            if brace:
                try:
                    return json.loads(brace.group(0))
                except json.JSONDecodeError:
                    pass
            return {}


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def complete(self, system: str, user: str, *, model: str | None = None, max_tokens: int = 1024) -> LLMResponse:
        ...


class MockProvider(LLMProvider):
    """Deterministic offline provider. Does not call any network. Used for
    APP_MODE=mock, tests, CI, and any environment without an API key.

    It doesn't try to "fake being an LLM" generically - each call site in
    this codebase passes a `task` hint via the system prompt tag
    ([TASK:xxx]) so the mock can return a structurally valid, honestly
    conservative response (often UNKNOWN) rather than a hallucinated fact.
    """
    name = "mock"

    def complete(self, system: str, user: str, *, model: str | None = None, max_tokens: int = 1024) -> LLMResponse:
        task_match = re.search(r"\[TASK:(\w+)\]", system)
        task = task_match.group(1) if task_match else "generic"
        payload = self._mock_response(task, user)
        return LLMResponse(text=json.dumps(payload), model="mock-deterministic-v1", provider=self.name)

    def _mock_response(self, task: str, user: str) -> dict:
        if task == "classification":
            return {"classpath": None, "confidence": 0.0, "reason": "mock provider: no classpath asserted beyond deterministic keyword rules"}
        if task == "attribute_extraction":
            return {"claims": []}
        if task == "entity_resolution":
            return {"selected_candidate": None, "confidence": 0.0, "reason": "mock provider defers to deterministic master-data match"}
        if task == "conflict_resolution":
            return {"resolution": "UNRESOLVED", "reason": "mock provider does not adjudicate; flagged for human review"}
        if task == "description_generation":
            return {"text": "", "reason": "mock provider does not generate free text beyond grounded templates"}
        if task == "evidence_validation":
            return {"grounded": False, "reason": "mock provider: no external evidence available"}
        if task == "review_assistant":
            return {"summary": "mock provider: see structured review-queue fields"}
        return {}


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str | None = None):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)

    def complete(self, system: str, user: str, *, model: str | None = None, max_tokens: int = 1024) -> LLMResponse:
        model = model or settings.CLAUDE_MODEL
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        return LLMResponse(text=text, model=model, provider=self.name, usage=usage)


_provider_singleton: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton
    if settings.APP_MODE == "claude" and settings.ANTHROPIC_API_KEY:
        try:
            _provider_singleton = ClaudeProvider()
        except Exception:
            _provider_singleton = MockProvider()
    else:
        _provider_singleton = MockProvider()
    return _provider_singleton


def set_provider(provider: LLMProvider):
    """Test hook — lets tests/integration inject a MockProvider explicitly."""
    global _provider_singleton
    _provider_singleton = provider
