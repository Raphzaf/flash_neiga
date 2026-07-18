"""
Client Claude partagé pour le coach IA (Flash Neiga).

Prend en charge deux modes d'authentification, choisis automatiquement selon
les variables d'environnement présentes (aucune clé n'est jamais codée en dur) :

1. Google Cloud Vertex AI (recommandé ici — le projet fournit une credential GCP) :
     ANTHROPIC_VERTEX_PROJECT_ID = <id ou numéro de projet, ex: 239164849877>
     CLOUD_ML_REGION            = <région Vertex où claude-opus-4-8 est activé, ex: europe-west1>
   Auth GCP via ADC (GOOGLE_APPLICATION_CREDENTIALS pointant vers un JSON de
   compte de service, ou `gcloud auth application-default login`).

2. API Claude première partie :
     ANTHROPIC_API_KEY = sk-ant-...

Le module ne lève jamais à l'import : si le SDK ou la config manque,
`ai_configured()` renvoie False et les endpoints IA répondent proprement 503.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-opus-4-8"

# Import « souple » du SDK : l'app doit démarrer même si anthropic n'est pas installé.
try:
    import anthropic  # type: ignore
    _ANTHROPIC_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover
    anthropic = None  # type: ignore
    _ANTHROPIC_IMPORT_ERROR = exc


class AICoachUnavailable(Exception):
    """Levée quand le coach IA ne peut pas répondre (non configuré ou API en erreur)."""


_client = None  # cache du client (créé à la première utilisation)


def _use_vertex() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
        or os.environ.get("CLAUDE_CODE_USE_VERTEX")
    )


def ai_configured() -> bool:
    """Le coach IA est-il utilisable (SDK présent + credentials disponibles) ?"""
    if anthropic is None:
        return False
    if _use_vertex():
        return bool(
            os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            and (os.environ.get("CLOUD_ML_REGION") or os.environ.get("ANTHROPIC_VERTEX_REGION"))
        )
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_client():
    """Retourne (et met en cache) le client Claude adapté à la config d'environnement."""
    global _client
    if _client is not None:
        return _client

    if anthropic is None:
        raise AICoachUnavailable(
            f"SDK anthropic indisponible : {_ANTHROPIC_IMPORT_ERROR}"
        )

    if _use_vertex():
        project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
        region = os.environ.get("CLOUD_ML_REGION") or os.environ.get("ANTHROPIC_VERTEX_REGION")
        if not project_id or not region:
            raise AICoachUnavailable(
                "Config Vertex incomplète : ANTHROPIC_VERTEX_PROJECT_ID et CLOUD_ML_REGION requis."
            )
        try:
            from anthropic import AnthropicVertex  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise AICoachUnavailable(
                f"Support Vertex indisponible (installer anthropic[vertex]) : {exc}"
            )
        _client = AnthropicVertex(project_id=project_id, region=region)
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AICoachUnavailable("ANTHROPIC_API_KEY manquant.")
        _client = anthropic.Anthropic()

    return _client


def call_structured(
    system: str,
    user_content: str,
    schema: Dict[str, Any],
    max_tokens: int = 2048,
    client=None,
) -> Dict[str, Any]:
    """Appelle Claude en mode structured output et renvoie le JSON parsé.

    - `system` est mis en cache (prompt caching) : contenu stable en premier.
    - `schema` : JSON Schema (additionalProperties=False, champs required).
    - Lève `AICoachUnavailable` sur refus, réponse tronquée ou erreur API/SDK.
    """
    cli = client or get_client()

    try:
        response = cli.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except Exception as exc:
        # anthropic.RateLimitError / APIStatusError / APIConnectionError, etc.
        logger.warning("Appel Claude en échec : %s", exc)
        raise AICoachUnavailable(str(exc)) from exc

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        raise AICoachUnavailable("La réponse a été refusée par le modèle.")
    if stop_reason == "max_tokens":
        logger.warning("Réponse Claude tronquée (max_tokens).")

    text = None
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text = block.text
            break
    if not text:
        raise AICoachUnavailable("Réponse Claude vide.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AICoachUnavailable(f"JSON invalide renvoyé par le modèle : {exc}") from exc
