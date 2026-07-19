"""
Client IA partagé pour le coach (Flash Neiga).

Fournisseur par défaut : **Google AI / Gemini** (SDK `google-genai`).
Un fournisseur Claude (SDK `anthropic`) reste disponible via AI_PROVIDER=claude.

Configuration par variables d'environnement (aucune clé n'est jamais codée en dur) :

  AI_PROVIDER   = gemini (défaut) | claude
  GEMINI_MODEL  = gemini-2.5-flash (défaut) | gemini-2.5-pro | ...

  # --- Google AI Studio (chemin simple, recommandé) ---
  GEMINI_API_KEY = <ta clé Google AI Studio>        (ou GOOGLE_API_KEY)

  # --- OU Vertex AI (si tu passes par Google Cloud) ---
  GOOGLE_GENAI_USE_VERTEXAI = true
  GOOGLE_CLOUD_PROJECT       = 239164849877
  GOOGLE_CLOUD_LOCATION      = europe-west1
  # + auth GCP (GOOGLE_APPLICATION_CREDENTIALS)

  # --- Claude (optionnel, AI_PROVIDER=claude) ---
  ANTHROPIC_API_KEY = sk-ant-...
  # ou Vertex : ANTHROPIC_VERTEX_PROJECT_ID + CLOUD_ML_REGION

Le module n'échoue jamais à l'import : si le SDK ou la config manque,
`ai_configured()` renvoie False et les endpoints IA répondent proprement 503.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# --- Modèles ---
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CLAUDE_MODEL = "claude-opus-4-8"


def _provider() -> str:
    return (os.environ.get("AI_PROVIDER") or "gemini").strip().lower()


# --- Imports « souples » : l'app doit démarrer même sans SDK installé ---
try:
    from google import genai as _genai  # type: ignore
    from google.genai import types as _genai_types  # type: ignore
    _GENAI_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover
    _genai = None  # type: ignore
    _genai_types = None  # type: ignore
    _GENAI_IMPORT_ERROR = exc

try:
    import anthropic as _anthropic  # type: ignore
    _ANTHROPIC_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover
    _anthropic = None  # type: ignore
    _ANTHROPIC_IMPORT_ERROR = exc


class AICoachUnavailable(Exception):
    """Levée quand le coach IA ne peut pas répondre (non configuré ou API en erreur)."""


_client = None  # cache du client


# ===== Détection de configuration =====
def _gemini_use_vertex() -> bool:
    val = (os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower()
    return val in ("1", "true", "yes")


def _gemini_configured() -> bool:
    if _genai is None:
        return False
    if _gemini_use_vertex():
        return bool(os.environ.get("GOOGLE_CLOUD_PROJECT") and os.environ.get("GOOGLE_CLOUD_LOCATION"))
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _claude_use_vertex() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID") or os.environ.get("CLAUDE_CODE_USE_VERTEX")
    )


def _claude_configured() -> bool:
    if _anthropic is None:
        return False
    if _claude_use_vertex():
        return bool(
            os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            and (os.environ.get("CLOUD_ML_REGION") or os.environ.get("ANTHROPIC_VERTEX_REGION"))
        )
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ai_configured() -> bool:
    """Le coach IA est-il utilisable (SDK présent + credentials disponibles) ?"""
    return _claude_configured() if _provider() == "claude" else _gemini_configured()


def diagnostics() -> Dict[str, Any]:
    """État de configuration du coach IA — sans jamais exposer de secret.
    Sert à comprendre un 503 en production (SDK manquant ? clé absente ?)."""
    provider = _provider()
    if provider == "claude":
        sdk_installed = _anthropic is not None
        use_vertex = _claude_use_vertex()
        has_credentials = bool(
            os.environ.get("ANTHROPIC_API_KEY")
            or (use_vertex and os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"))
        )
        sdk_name = "anthropic"
        model = CLAUDE_MODEL
    else:
        sdk_installed = _genai is not None
        use_vertex = _gemini_use_vertex()
        has_credentials = bool(
            (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
            or (use_vertex and os.environ.get("GOOGLE_CLOUD_PROJECT") and os.environ.get("GOOGLE_CLOUD_LOCATION"))
        )
        sdk_name = "google-genai"
        model = GEMINI_MODEL

    reason = "ok"
    if not sdk_installed:
        reason = f"SDK '{sdk_name}' non installé sur le serveur"
    elif not has_credentials:
        reason = "credentials manquantes (clé API ou config Vertex non définie)"

    return {
        "provider": provider,
        "model": model,
        "sdk_installed": sdk_installed,
        "has_credentials": has_credentials,
        "use_vertex": use_vertex,
        "configured": ai_configured(),
        "reason": reason,
    }


# ===== Construction du client =====
def get_client():
    """Retourne (et met en cache) le client IA adapté au fournisseur/config."""
    global _client
    if _client is not None:
        return _client

    provider = _provider()

    if provider == "claude":
        if _anthropic is None:
            raise AICoachUnavailable(f"SDK anthropic indisponible : {_ANTHROPIC_IMPORT_ERROR}")
        if _claude_use_vertex():
            project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            region = os.environ.get("CLOUD_ML_REGION") or os.environ.get("ANTHROPIC_VERTEX_REGION")
            if not (project_id and region):
                raise AICoachUnavailable("Config Vertex (Claude) incomplète.")
            from anthropic import AnthropicVertex  # type: ignore
            _client = AnthropicVertex(project_id=project_id, region=region)
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise AICoachUnavailable("ANTHROPIC_API_KEY manquant.")
            _client = _anthropic.Anthropic()
        return _client

    # --- Gemini (défaut) ---
    if _genai is None:
        raise AICoachUnavailable(f"SDK google-genai indisponible : {_GENAI_IMPORT_ERROR}")
    if _gemini_use_vertex():
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        if not (project and location):
            raise AICoachUnavailable("Config Vertex (Gemini) incomplète : GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION requis.")
        _client = _genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise AICoachUnavailable("GEMINI_API_KEY (ou GOOGLE_API_KEY) manquant.")
        _client = _genai.Client(api_key=api_key)
    return _client


# ===== Appels structurés (JSON) =====
def _thinking_budget() -> int:
    # 0 = thinking désactivé (défaut) : sur les modèles 2.5 (flash/flash-latest),
    # le "thinking" consomme le budget de sortie et peut vider la réponse JSON.
    try:
        return int(os.environ.get("GEMINI_THINKING_BUDGET", "0"))
    except ValueError:
        return 0


def _gemini_config(system: str, max_tokens: int, with_thinking: bool):
    kwargs: Dict[str, Any] = dict(
        system_instruction=system,
        response_mime_type="application/json",
        max_output_tokens=max_tokens,
    )
    if with_thinking and hasattr(_genai_types, "ThinkingConfig"):
        kwargs["thinking_config"] = _genai_types.ThinkingConfig(thinking_budget=_thinking_budget())
    return _genai_types.GenerateContentConfig(**kwargs)


def _describe_empty(response) -> str:
    parts = []
    try:
        pf = getattr(response, "prompt_feedback", None)
        if pf and getattr(pf, "block_reason", None):
            parts.append(f"block_reason={pf.block_reason}")
    except Exception:
        pass
    try:
        cands = getattr(response, "candidates", None) or []
        if cands and getattr(cands[0], "finish_reason", None):
            parts.append(f"finish_reason={cands[0].finish_reason}")
    except Exception:
        pass
    return ", ".join(parts) or "aucun texte renvoyé"


def _call_gemini(system: str, user_content: str, schema: Dict[str, Any], max_tokens: int, client) -> Dict[str, Any]:
    # JSON mode + schéma décrit dans le prompt : robuste quelle que soit la
    # version du SDK, sans dépendre du format de response_schema propre à Gemini.
    prompt = (
        f"{user_content}\n\n"
        "Réponds UNIQUEMENT avec un objet JSON valide (aucun texte autour, pas de balise Markdown) "
        "respectant exactement ce schéma JSON :\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )

    def _do(with_thinking: bool):
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=_gemini_config(system, max_tokens, with_thinking),
        )

    try:
        response = _do(with_thinking=True)
    except Exception as exc:
        # Certains modèles (ex: 2.0) refusent thinking_config → réessai sans.
        try:
            response = _do(with_thinking=False)
        except Exception as exc2:
            logger.warning("Appel Gemini en échec : %s", exc2)
            raise AICoachUnavailable(str(exc2)) from exc2

    text = getattr(response, "text", None)
    if not text:
        raise AICoachUnavailable(f"Réponse Gemini vide ou bloquée ({_describe_empty(response)}).")
    return _parse_json(text)


def _call_claude(system: str, user_content: str, schema: Dict[str, Any], max_tokens: int, client) -> Dict[str, Any]:
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except Exception as exc:
        logger.warning("Appel Claude en échec : %s", exc)
        raise AICoachUnavailable(str(exc)) from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise AICoachUnavailable("La réponse a été refusée par le modèle.")

    text = None
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text = block.text
            break
    if not text:
        raise AICoachUnavailable("Réponse Claude vide.")
    return _parse_json(text)


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Nettoyage défensif d'éventuelles fences ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    decoder = json.JSONDecoder()
    # 1) Premier objet JSON à partir du début (ignore tout "Extra data" qui suit).
    try:
        obj, _ = decoder.raw_decode(text)
        return obj
    except json.JSONDecodeError:
        pass
    # 2) Sinon, on cherche le premier '{' (au cas où le modèle ajoute du texte avant).
    start = text.find("{")
    if start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            return obj
        except json.JSONDecodeError as exc:
            raise AICoachUnavailable(f"JSON invalide renvoyé par le modèle : {exc}") from exc
    raise AICoachUnavailable("Réponse du modèle sans JSON exploitable.")


def call_structured(
    system: str,
    user_content: str,
    schema: Dict[str, Any],
    max_tokens: int = 2048,
    client=None,
) -> Dict[str, Any]:
    """Appelle le modèle en mode JSON structuré et renvoie le dict parsé.

    Interface stable pour toutes les routes IA (indépendante du fournisseur).
    Lève `AICoachUnavailable` en cas d'erreur (refus, vide, JSON invalide, API).
    """
    cli = client or get_client()
    if _provider() == "claude":
        return _call_claude(system, user_content, schema, max_tokens, cli)
    return _call_gemini(system, user_content, schema, max_tokens, cli)
