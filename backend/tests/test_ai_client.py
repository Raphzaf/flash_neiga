"""
Tests de la couche IA partagée (ai_client) — fournisseur Gemini par défaut.
On injecte un faux client : aucun appel réseau.
"""
import json
import sys
import time
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


def test_call_structured_ignores_extra_data(monkeypatch):
    # Le modèle renvoie un objet valide puis du contenu en trop -> on garde le 1er objet.
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    client = _FakeGeminiClient('{"a": 1, "b": "x"}\n\nvoici mon explication en trop')
    assert ai_client.call_structured("s", "u", {}, client=client) == {"a": 1, "b": "x"}


def test_call_structured_handles_leading_text(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    client = _FakeGeminiClient('Bien sûr !\n{"a": 1}')
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


# ===== Durcissement : relances, classement des erreurs, disjoncteur =====
class _HttpError(Exception):
    """Erreur façon SDK, porteuse d'un code HTTP."""

    def __init__(self, status_code, message="boom"):
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    """Backoff écrasé et disjoncteur remis à zéro : tests rapides et isolés."""
    monkeypatch.setattr(ai_client, "_BACKOFF_BASE", 0.001)
    monkeypatch.setattr(ai_client, "_BACKOFF_MAX", 0.002)
    ai_client.reset_breaker()
    ai_client.reset_client()
    yield
    ai_client.reset_breaker()
    ai_client.reset_client()


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_erreurs_passageres_reconnues(status):
    assert ai_client._is_transient(_HttpError(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_erreurs_definitives_non_retentees(status):
    """Une clé invalide ne guérit pas : insister ne ferait qu'ajouter de l'attente."""
    assert ai_client._is_transient(_HttpError(status)) is False


def test_erreur_de_configuration_non_retentee():
    assert ai_client._is_transient(ai_client.AICoachUnavailable("clé manquante")) is False


def test_reponse_tronquee_est_retentee():
    assert ai_client._is_transient(ai_client.AITransientError("JSON invalide")) is True


def test_timeout_reseau_reconnu_sans_code_http():
    assert ai_client._is_transient(TimeoutError("read timed out")) is True


def test_relance_puis_succes():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _HttpError(503)
        return "ok"

    assert ai_client._with_retries("gemini", "test", flaky) == "ok"
    assert calls["n"] == 3


def test_abandon_apres_le_nombre_max_de_tentatives(monkeypatch):
    monkeypatch.setenv("AI_MAX_ATTEMPTS", "2")
    calls = {"n": 0}

    def always_down():
        calls["n"] += 1
        raise _HttpError(503)

    with pytest.raises(ai_client.AICoachUnavailable):
        ai_client._with_retries("gemini", "test", always_down)
    assert calls["n"] == 2


def test_aucune_relance_sur_erreur_definitive():
    calls = {"n": 0}

    def bad_key():
        calls["n"] += 1
        raise _HttpError(401)

    with pytest.raises(_HttpError):
        ai_client._with_retries("gemini", "test", bad_key)
    assert calls["n"] == 1  # échec immédiat, l'élève n'attend pas


def test_disjoncteur_coupe_apres_plusieurs_pannes(monkeypatch):
    """En panne durable, on cesse d'appeler : l'élève reçoit son repli tout de suite."""
    monkeypatch.setenv("AI_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("AI_BREAKER_THRESHOLD", "3")
    monkeypatch.setenv("AI_BREAKER_COOLDOWN", "60")

    calls = {"n": 0}

    def down():
        calls["n"] += 1
        raise _HttpError(503)

    for _ in range(3):
        with pytest.raises(ai_client.AICoachUnavailable):
            ai_client._with_retries("gemini", "test", down)
    assert calls["n"] == 3

    # Circuit ouvert : l'appel suivant échoue sans toucher au réseau.
    with pytest.raises(ai_client.AICoachUnavailable) as exc:
        ai_client._with_retries("gemini", "test", down)
    assert calls["n"] == 3
    assert "coupé" in str(exc.value)


def test_disjoncteur_referme_apres_un_succes(monkeypatch):
    monkeypatch.setenv("AI_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("AI_BREAKER_THRESHOLD", "3")

    def down():
        raise _HttpError(503)

    for _ in range(2):  # sous le seuil
        with pytest.raises(ai_client.AICoachUnavailable):
            ai_client._with_retries("gemini", "test", down)

    assert ai_client._with_retries("gemini", "test", lambda: "ok") == "ok"

    # Le compteur est reparti de zéro : deux nouvelles pannes n'ouvrent pas encore.
    for _ in range(2):
        with pytest.raises(ai_client.AICoachUnavailable):
            ai_client._with_retries("gemini", "test", down)
    assert ai_client._breaker.blocked_for("gemini") == 0


def test_disjoncteur_isole_les_fournisseurs(monkeypatch):
    monkeypatch.setenv("AI_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("AI_BREAKER_THRESHOLD", "1")
    monkeypatch.setenv("AI_BREAKER_COOLDOWN", "60")

    with pytest.raises(ai_client.AICoachUnavailable):
        ai_client._with_retries("gemini", "test", lambda: (_ for _ in ()).throw(_HttpError(503)))

    assert ai_client._breaker.blocked_for("gemini") > 0
    assert ai_client._breaker.blocked_for("moonshot") == 0


def test_budget_total_borne_l_attente(monkeypatch):
    """Le budget prime sur le nombre de tentatives : on rend la main à temps."""
    monkeypatch.setenv("AI_MAX_ATTEMPTS", "50")
    monkeypatch.setenv("AI_TOTAL_DEADLINE", "0.05")

    started = time.monotonic()
    with pytest.raises(ai_client.AICoachUnavailable):
        ai_client._with_retries("gemini", "test",
                                lambda: (_ for _ in ()).throw(_HttpError(503)))
    assert time.monotonic() - started < 2.0


def test_client_reconstruit_quand_le_fournisseur_change(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    first = ai_client.get_client()
    assert ai_client.get_client() is first  # même fournisseur : client réutilisé

    monkeypatch.setenv("AI_PROVIDER", "moonshot")
    monkeypatch.setenv("MOONSHOT_API_KEY", "dummy")
    assert ai_client.get_client() is not first  # sinon on parlerait au mauvais service


def test_json_invalide_est_classe_comme_passager():
    with pytest.raises(ai_client.AITransientError):
        ai_client._parse_json("ceci n'est pas du JSON")
