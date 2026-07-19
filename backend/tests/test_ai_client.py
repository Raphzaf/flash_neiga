"""
Tests de la couche IA partagée (ai_client) — fournisseur Gemini par défaut.
On injecte un faux client : aucun appel réseau.
"""
import json
import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import ai_client  # noqa: E402


class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text):
        self._text = text
        self.captured = None

    def generate_content(self, **kwargs):
        self.captured = kwargs
        return _FakeResp(self._text)


class _FakeGeminiClient:
    def __init__(self, text):
        self.models = _FakeModels(text)


def test_ai_configured_true_with_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    assert ai_client.ai_configured() is True


def test_ai_configured_false_without_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    assert ai_client.ai_configured() is False


def test_call_structured_gemini_shape(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    payload = {"explication": "x", "regle": "y", "erreurs_a_eviter": ["a"], "schema_svg": None}
    client = _FakeGeminiClient(json.dumps(payload))
    out = ai_client.call_structured("SYS", "USER", {"type": "object", "properties": {}},
                                    max_tokens=2048, client=client)
    cfg = client.models.captured["config"]
    assert client.models.captured["model"] == ai_client.GEMINI_MODEL
    assert cfg.system_instruction == "SYS"
    assert cfg.response_mime_type == "application/json"
    assert cfg.max_output_tokens == 2048
    assert "schéma JSON" in client.models.captured["contents"]
    assert out == payload


def test_call_structured_parses_fenced_json(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    client = _FakeGeminiClient("```json\n{\"a\": 1}\n```")
    assert ai_client.call_structured("s", "u", {}, client=client) == {"a": 1}


def test_call_structured_empty_response_raises(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    client = _FakeGeminiClient(None)
    with pytest.raises(ai_client.AICoachUnavailable):
        ai_client.call_structured("s", "u", {}, client=client)


def test_call_structured_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    client = _FakeGeminiClient("pas du json")
    with pytest.raises(ai_client.AICoachUnavailable):
        ai_client.call_structured("s", "u", {}, client=client)
