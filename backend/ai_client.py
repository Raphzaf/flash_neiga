"""
Client IA partagé pour le coach (Flash Neiga).

Fournisseur par défaut : **Google AI / Gemini** (SDK `google-genai`).
Un fournisseur Claude (SDK `anthropic`) reste disponible via AI_PROVIDER=claude.

Un fournisseur Kimi / Moonshot AI (API compatible OpenAI) est disponible via
AI_PROVIDER=moonshot.

Configuration par variables d'environnement (aucune clé n'est jamais codée en dur) :

  AI_PROVIDER   = gemini (défaut) | claude | moonshot
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

  # --- Kimi / Moonshot AI (optionnel, AI_PROVIDER=moonshot) ---
  MOONSHOT_API_KEY  = sk-...                        (obligatoire)
  MOONSHOT_BASE_URL = https://api.moonshot.ai/v1    (défaut)
  MOONSHOT_MODEL    = kimi-k3                       (défaut)

Le module n'échoue jamais à l'import : si le SDK ou la config manque,
`ai_configured()` renvoie False et les endpoints IA répondent proprement 503.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

# --- Modèles ---
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CLAUDE_MODEL = "claude-opus-4-8"

# Kimi / Moonshot AI — modèles disponibles :
#   kimi-k3        : flagship, 1M de contexte, raisonnement toujours actif, cher
#   kimi-k2.7-code : orienté code, 262k de contexte, rapide
#   kimi-k2.6      : généraliste multimodal, 262k de contexte
#   kimi-k2.5      : économique, 262k de contexte
MOONSHOT_MODEL = os.environ.get("MOONSHOT_MODEL", "kimi-k3")
MOONSHOT_BASE_URL = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")


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

try:
    import openai as _openai  # type: ignore
    _OPENAI_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover
    _openai = None  # type: ignore
    _OPENAI_IMPORT_ERROR = exc


class AICoachUnavailable(Exception):
    """Levée quand le coach IA ne peut pas répondre (non configuré ou API en erreur)."""


class AITransientError(AICoachUnavailable):
    """Échec passager côté modèle (réponse vide, JSON tronqué) : une relance peut aboutir.

    Sous-classe d'AICoachUnavailable pour que tout le code appelant existant
    (`except AICoachUnavailable`) continue de fonctionner à l'identique.
    """


# ===== Réglages de latence et de robustesse =====
# Un élève qui attend est un élève qui décroche : on préfère échouer vite et
# laisser l'appelant servir son repli plutôt que de faire patienter une minute.
_DEFAULT_REQUEST_TIMEOUT = 25.0   # durée max d'UN appel réseau
_DEFAULT_TOTAL_DEADLINE = 40.0    # budget total d'un appel logique, relances comprises
_DEFAULT_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 0.6               # 1re relance ~0,6 s, puis 1,2 s, 2,4 s…
_BACKOFF_MAX = 5.0


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def request_timeout() -> float:
    """Délai maximal d'un appel unitaire au fournisseur (secondes)."""
    return _env_float("AI_REQUEST_TIMEOUT", _DEFAULT_REQUEST_TIMEOUT)


def total_deadline() -> float:
    """Budget total accordé à un appel logique, relances comprises (secondes)."""
    return _env_float("AI_TOTAL_DEADLINE", _DEFAULT_TOTAL_DEADLINE)


def max_attempts() -> int:
    """Nombre total de tentatives (1 = aucune relance)."""
    return _env_int("AI_MAX_ATTEMPTS", _DEFAULT_MAX_ATTEMPTS)


# ===== Disjoncteur =====
class _CircuitBreaker:
    """Coupe-circuit par fournisseur.

    Quand l'API du modèle tombe, chaque requête coûte un timeout complet à
    l'élève. Après `AI_BREAKER_THRESHOLD` échecs passagers consécutifs, on
    ouvre le circuit : les appels suivants échouent instantanément (l'appelant
    sert alors son repli) pendant `AI_BREAKER_COOLDOWN` secondes, puis une
    requête « sonde » est de nouveau laissée passer.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: Dict[str, int] = {}
        self._open_until: Dict[str, float] = {}

    def blocked_for(self, provider: str) -> float:
        """Secondes restantes avant réouverture (0 si le circuit est fermé)."""
        with self._lock:
            remaining = self._open_until.get(provider, 0.0) - time.monotonic()
        return remaining if remaining > 0 else 0.0

    def record_success(self, provider: str) -> None:
        with self._lock:
            self._failures.pop(provider, None)
            self._open_until.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        threshold = _env_int("AI_BREAKER_THRESHOLD", 4)
        cooldown = _env_float("AI_BREAKER_COOLDOWN", 30.0)
        with self._lock:
            count = self._failures.get(provider, 0) + 1
            self._failures[provider] = count
            if count >= threshold:
                self._open_until[provider] = time.monotonic() + cooldown

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            return {
                "consecutive_failures": dict(self._failures),
                "open_providers": {
                    prov: round(until - now, 1)
                    for prov, until in self._open_until.items()
                    if until > now
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._open_until.clear()


_breaker = _CircuitBreaker()


def reset_breaker() -> None:
    """Referme le disjoncteur (utilisé par les tests et l'endpoint d'admin)."""
    _breaker.reset()


# ===== Classement des erreurs =====
# Un 401 (clé invalide) ou un 400 (schéma refusé) ne guérira pas tout seul :
# relancer ne ferait qu'ajouter de l'attente. Seuls les codes ci-dessous valent
# une relance.
_TRANSIENT_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}
_TRANSIENT_MARKERS = (
    "timeout", "timed out", "deadline", "temporarily", "unavailable",
    "overloaded", "rate limit", "too many requests", "connection",
    "broken pipe", "reset by peer", "try again", "internal error",
    "service_unavailable", "server error",
)


def _status_code(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _is_transient(exc: Exception) -> bool:
    """L'erreur vaut-elle une relance ?"""
    if isinstance(exc, AITransientError):
        return True
    if isinstance(exc, AICoachUnavailable):
        return False  # erreur de configuration : inutile d'insister
    status = _status_code(exc)
    if status is not None:
        return status in _TRANSIENT_STATUS
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    haystack = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in haystack for marker in _TRANSIENT_MARKERS)


_T = TypeVar("_T")


def _with_retries(provider: str, operation: str, fn: Callable[[], _T]) -> _T:
    """Exécute `fn` avec relances à backoff exponentiel, sous disjoncteur.

    Le budget total prime sur le nombre de tentatives : on ne relance jamais si
    le temps restant ne permet pas d'aboutir — mieux vaut rendre la main à
    l'appelant, qui a un repli à servir, que de dépasser le délai.
    """
    blocked = _breaker.blocked_for(provider)
    if blocked > 0:
        raise AICoachUnavailable(
            f"Service « {provider} » temporairement coupé après plusieurs échecs "
            f"(nouvelle tentative possible dans {blocked:.0f} s)."
        )

    deadline = time.monotonic() + total_deadline()
    attempts = max_attempts()
    last_exc: Optional[Exception] = None
    used = 0

    for attempt in range(1, attempts + 1):
        used = attempt
        try:
            result = fn()
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc):
                raise
            _breaker.record_failure(provider)
            remaining = deadline - time.monotonic()
            if attempt >= attempts or remaining <= 0:
                break
            delay = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_MAX)
            delay += random.uniform(0, delay / 2)  # jitter : évite les rafales synchronisées
            if delay >= remaining:
                break
            logger.warning(
                "IA %s/%s : tentative %s/%s en échec (%s) — relance dans %.1f s",
                provider, operation, attempt, attempts, exc, delay,
            )
            time.sleep(delay)
            continue
        _breaker.record_success(provider)
        return result

    detail = str(last_exc) if last_exc else "cause inconnue"
    raise AICoachUnavailable(
        f"Le modèle « {provider} » n'a pas répondu après {used} tentative(s) : {detail}"
    )


_client = None  # cache du client
_client_provider: Optional[str] = None  # fournisseur pour lequel `_client` a été construit


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


def _moonshot_configured() -> bool:
    if _openai is None:
        return False
    return bool(os.environ.get("MOONSHOT_API_KEY"))


def ai_configured() -> bool:
    """Le coach IA est-il utilisable (SDK présent + credentials disponibles) ?"""
    provider = _provider()
    if provider == "claude":
        return _claude_configured()
    if provider == "moonshot":
        return _moonshot_configured()
    return _gemini_configured()


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
    elif provider == "moonshot":
        sdk_installed = _openai is not None
        use_vertex = False
        has_credentials = bool(os.environ.get("MOONSHOT_API_KEY"))
        sdk_name = "openai"
        model = MOONSHOT_MODEL
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
        "request_timeout_s": request_timeout(),
        "total_deadline_s": total_deadline(),
        "max_attempts": max_attempts(),
        "breaker": _breaker.snapshot(),
    }


# ===== Construction du client =====
def _gemini_http_options():
    """HttpOptions avec timeout, si la version du SDK les expose.

    Sans timeout explicite, un incident réseau côté Google fait attendre l'élève
    indéfiniment. Les SDK plus anciens n'ont pas `HttpOptions` : on dégrade
    proprement plutôt que de casser l'app.
    """
    if _genai_types is None or not hasattr(_genai_types, "HttpOptions"):
        return None
    try:
        # Le SDK google-genai attend des millisecondes.
        return _genai_types.HttpOptions(timeout=int(request_timeout() * 1000))
    except Exception:  # pragma: no cover - dépend de la version du SDK
        return None


def _new_gemini_client():
    http_options = _gemini_http_options()
    if _gemini_use_vertex():
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        if not (project and location):
            raise AICoachUnavailable(
                "Config Vertex (Gemini) incomplète : GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION requis."
            )
        kwargs: Dict[str, Any] = dict(vertexai=True, project=project, location=location)
    else:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise AICoachUnavailable("GEMINI_API_KEY (ou GOOGLE_API_KEY) manquant.")
        kwargs = dict(api_key=api_key)

    if http_options is not None:
        try:
            return _genai.Client(http_options=http_options, **kwargs)
        except TypeError:  # pragma: no cover - SDK sans http_options
            logger.info("SDK google-genai sans http_options : client sans timeout explicite.")
    return _genai.Client(**kwargs)


def reset_client() -> None:
    """Oublie le client mis en cache (changement de config, tests)."""
    global _client, _client_provider
    _client = None
    _client_provider = None


def get_client():
    """Retourne (et met en cache) le client IA adapté au fournisseur/config."""
    global _client, _client_provider

    provider = _provider()
    # Le cache est indexé par fournisseur : changer AI_PROVIDER en cours de vie
    # du process doit reconstruire le client, pas réutiliser l'ancien.
    if _client is not None and _client_provider == provider:
        return _client

    if provider == "claude":
        if _anthropic is None:
            raise AICoachUnavailable(f"SDK anthropic indisponible : {_ANTHROPIC_IMPORT_ERROR}")
        if _claude_use_vertex():
            project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            region = os.environ.get("CLOUD_ML_REGION") or os.environ.get("ANTHROPIC_VERTEX_REGION")
            if not (project_id and region):
                raise AICoachUnavailable("Config Vertex (Claude) incomplète.")
            from anthropic import AnthropicVertex  # type: ignore
            _client = AnthropicVertex(
                project_id=project_id,
                region=region,
                timeout=request_timeout(),
                max_retries=0,  # les relances sont pilotées par _with_retries
            )
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise AICoachUnavailable("ANTHROPIC_API_KEY manquant.")
            _client = _anthropic.Anthropic(timeout=request_timeout(), max_retries=0)
        _client_provider = provider
        return _client

    if provider == "moonshot":
        if _openai is None:
            raise AICoachUnavailable(f"SDK openai indisponible : {_OPENAI_IMPORT_ERROR}")
        api_key = os.environ.get("MOONSHOT_API_KEY")
        if not api_key:
            raise AICoachUnavailable("MOONSHOT_API_KEY manquant.")
        # max_retries=0 est CRITIQUE : Moonshot supporte mal les relances
        # automatiques du SDK (elles amplifient les 429 au lieu de les absorber).
        _client = _openai.OpenAI(
            api_key=api_key,
            base_url=MOONSHOT_BASE_URL,
            max_retries=0,
            timeout=request_timeout(),
        )
        _client_provider = provider
        return _client

    # --- Gemini (défaut) ---
    if _genai is None:
        raise AICoachUnavailable(f"SDK google-genai indisponible : {_GENAI_IMPORT_ERROR}")
    _client = _new_gemini_client()
    _client_provider = provider
    return _client


# ===== Appels structurés (JSON) =====
def _thinking_budget() -> int:
    # 0 = thinking désactivé (défaut) : sur les modèles 2.5 (flash/flash-latest),
    # le "thinking" consomme le budget de sortie et peut vider la réponse JSON.
    try:
        return int(os.environ.get("GEMINI_THINKING_BUDGET", "0"))
    except ValueError:
        return 0


_GEMINI_TYPE_MAP = {
    "object": "OBJECT", "string": "STRING", "array": "ARRAY",
    "boolean": "BOOLEAN", "integer": "INTEGER", "number": "NUMBER",
}


def _to_gemini_schema(schema: Any) -> Any:
    """Convertit un JSON Schema (le nôtre) vers le format response_schema de Gemini :
    types en MAJUSCULES, `["string","null"]` -> nullable, sans additionalProperties.
    Garantit un JSON de sortie bien formé (le SDK gère l'échappement, ex. SVG)."""
    if not isinstance(schema, dict):
        return schema
    out: Dict[str, Any] = {}
    t = schema.get("type")
    nullable = False
    if isinstance(t, list):
        nullable = "null" in t
        non_null = [x for x in t if x != "null"]
        t = non_null[0] if non_null else "string"
    if isinstance(t, str):
        out["type"] = _GEMINI_TYPE_MAP.get(t.lower(), t.upper())
    if nullable:
        out["nullable"] = True
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if "properties" in schema:
        out["properties"] = {k: _to_gemini_schema(v) for k, v in schema["properties"].items()}
        out["propertyOrdering"] = list(schema["properties"].keys())
    if "required" in schema:
        out["required"] = schema["required"]
    if "items" in schema:
        out["items"] = _to_gemini_schema(schema["items"])
    return out


def _gemini_config(system: str, max_tokens: int, with_thinking: bool, response_schema=None):
    kwargs: Dict[str, Any] = dict(
        system_instruction=system,
        response_mime_type="application/json",
        max_output_tokens=max_tokens,
    )
    if response_schema is not None:
        kwargs["response_schema"] = response_schema
    if with_thinking and hasattr(_genai_types, "ThinkingConfig"):
        kwargs["thinking_config"] = _genai_types.ThinkingConfig(thinking_budget=_thinking_budget())
    return _genai_types.GenerateContentConfig(**kwargs)


def _block_reason(response) -> Optional[str]:
    try:
        pf = getattr(response, "prompt_feedback", None)
        reason = getattr(pf, "block_reason", None) if pf else None
        return str(reason) if reason else None
    except Exception:
        return None


def _describe_empty(response) -> str:
    parts = []
    blocked = _block_reason(response)
    if blocked:
        parts.append(f"block_reason={blocked}")
    try:
        cands = getattr(response, "candidates", None) or []
        if cands and getattr(cands[0], "finish_reason", None):
            parts.append(f"finish_reason={cands[0].finish_reason}")
    except Exception:
        pass
    return ", ".join(parts) or "aucun texte renvoyé"


def _empty_response_error(response) -> AICoachUnavailable:
    """Un blocage sécurité se reproduira à l'identique : inutile de relancer.
    Une réponse vide sans motif, elle, est un aléa du modèle : on retente."""
    detail = _describe_empty(response)
    if _block_reason(response):
        return AICoachUnavailable(f"Réponse du modèle bloquée ({detail}).")
    return AITransientError(f"Réponse du modèle vide ({detail}).")


def _call_gemini(system: str, user_content: str, schema: Dict[str, Any], max_tokens: int, client) -> Dict[str, Any]:
    # JSON mode + schéma décrit dans le prompt : robuste quelle que soit la
    # version du SDK, sans dépendre du format de response_schema propre à Gemini.
    prompt = (
        f"{user_content}\n\n"
        "Réponds UNIQUEMENT avec un objet JSON valide (aucun texte autour, pas de balise Markdown) "
        "respectant exactement ce schéma JSON :\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )

    gemini_schema = _to_gemini_schema(schema)

    def _do(with_thinking: bool, response_schema):
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=_gemini_config(system, max_tokens, with_thinking, response_schema),
        )

    # Ordre des tentatives : JSON structuré natif (fiable) → sans thinking_config
    # (modèles 2.0) → JSON mode simple (schéma décrit dans le prompt) en dernier recours.
    attempts = [
        (True, gemini_schema),
        (False, gemini_schema),
        (False, None),
    ]
    last_exc = None
    response = None
    for with_thinking, rs in attempts:
        try:
            response = _do(with_thinking, rs)
            break
        except Exception as exc:
            last_exc = exc
            # Une panne ou un quota ne se règle pas en changeant de variante de
            # config : on remonte tout de suite pour que _with_retries applique
            # son backoff, au lieu d'enchaîner 3 appels dans la seconde.
            if _is_transient(exc):
                raise
            continue
    if response is None:
        logger.warning("Appel Gemini en échec : %s", last_exc)
        raise AICoachUnavailable(str(last_exc))

    text = getattr(response, "text", None)
    if not text:
        raise _empty_response_error(response)
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
        # On laisse l'exception d'origine remonter : _is_transient a besoin de
        # son status_code pour décider s'il faut relancer.
        raise

    if getattr(response, "stop_reason", None) == "refusal":
        raise AICoachUnavailable("La réponse a été refusée par le modèle.")

    text = None
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text = block.text
            break
    if not text:
        raise AITransientError("Réponse Claude vide.")
    return _parse_json(text)


def _moonshot_error(exc: Exception) -> AICoachUnavailable:
    """Traduit une erreur Moonshot en message exploitable.

    Le 429 est le cas le plus fréquent : Moonshot facture le quota *à l'avance*
    (tokens d'entrée + max_completion_tokens), donc une valeur de sortie trop
    haute déclenche un 429 immédiat, même sans trafic.
    """
    status = _status_code(exc)
    if status == 429:
        # Retentable : une relance espacée passe souvent (le quota se libère).
        return AITransientError(
            "Limite de débit Moonshot atteinte (429). Réduis max_completion_tokens "
            "ou recharge le compte pour passer au palier supérieur."
        )
    if status == 401:
        return AICoachUnavailable("Clé MOONSHOT_API_KEY invalide ou non activée (401).")
    if status in _TRANSIENT_STATUS or _is_transient(exc):
        return AITransientError(f"Appel Moonshot en échec (passager) : {exc}")
    return AICoachUnavailable(f"Appel Moonshot en échec : {exc}")


def _log_moonshot_usage(response) -> None:
    """Journalise la consommation de tokens (utile pour suivre le quota)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    logger.info(
        "Moonshot %s — tokens: %s entrée + %s sortie = %s",
        MOONSHOT_MODEL,
        getattr(usage, "prompt_tokens", "?"),
        getattr(usage, "completion_tokens", "?"),
        getattr(usage, "total_tokens", "?"),
    )


def _moonshot_text(response) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise AITransientError("Réponse Moonshot vide.")
    content = getattr(choices[0].message, "content", None)
    if not content or not content.strip():
        raise AITransientError("Réponse Moonshot vide.")
    return content.strip()


def _call_moonshot(system: str, user_content: str, schema: Dict[str, Any], max_tokens: int, client) -> Dict[str, Any]:
    prompt = (
        f"{user_content}\n\n"
        "Réponds UNIQUEMENT avec un objet JSON valide (aucun texte autour, pas de balise Markdown) "
        "respectant exactement ce schéma JSON :\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    try:
        response = client.chat.completions.create(
            model=MOONSHOT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            # max_completion_tokens remplace max_tokens (déprécié).
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("Appel Moonshot en échec : %s", exc)
        raise _moonshot_error(exc) from exc

    _log_moonshot_usage(response)
    return _parse_json(_moonshot_text(response))


def _chat_moonshot(system: str, history: list, max_tokens: int, client) -> str:
    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": ("assistant" if m.get("role") == "assistant" else "user"), "content": m.get("content") or ""}
        for m in history if (m.get("content") or "").strip()
    ]
    if len(messages) == 1:
        raise AICoachUnavailable("Message vide.")
    try:
        response = client.chat.completions.create(
            model=MOONSHOT_MODEL,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning("Chat Moonshot en échec : %s", exc)
        raise _moonshot_error(exc) from exc

    _log_moonshot_usage(response)
    return _moonshot_text(response)


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
            raise AITransientError(f"JSON invalide renvoyé par le modèle : {exc}") from exc
    raise AITransientError("Réponse du modèle sans JSON exploitable.")


def _chat_gemini(system: str, history: list, max_tokens: int, client) -> str:
    contents = []
    for msg in history:
        role = "model" if msg.get("role") == "assistant" else "user"
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        contents.append(_genai_types.Content(role=role, parts=[_genai_types.Part(text=text)]))
    if not contents:
        raise AICoachUnavailable("Message vide.")

    def _cfg(with_thinking: bool):
        kwargs: Dict[str, Any] = dict(system_instruction=system, max_output_tokens=max_tokens)
        if with_thinking and hasattr(_genai_types, "ThinkingConfig"):
            kwargs["thinking_config"] = _genai_types.ThinkingConfig(thinking_budget=_thinking_budget())
        return _genai_types.GenerateContentConfig(**kwargs)

    def _do(with_thinking: bool):
        return client.models.generate_content(model=GEMINI_MODEL, contents=contents, config=_cfg(with_thinking))

    try:
        response = _do(with_thinking=True)
    except Exception as exc:
        if _is_transient(exc):
            raise  # backoff géré par _with_retries, pas de second appel immédiat
        try:
            response = _do(with_thinking=False)
        except Exception as exc2:
            logger.warning("Chat Gemini en échec : %s", exc2)
            raise

    text = getattr(response, "text", None)
    if not text:
        raise _empty_response_error(response)
    return text.strip()


def _chat_claude(system: str, history: list, max_tokens: int, client) -> str:
    messages = [
        {"role": ("assistant" if m.get("role") == "assistant" else "user"), "content": m.get("content") or ""}
        for m in history if (m.get("content") or "").strip()
    ]
    if not messages:
        raise AICoachUnavailable("Message vide.")
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
    except Exception as exc:
        logger.warning("Chat Claude en échec : %s", exc)
        raise
    if getattr(response, "stop_reason", None) == "refusal":
        raise AICoachUnavailable("La réponse a été refusée par le modèle.")
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text.strip()
    raise AITransientError("Réponse Claude vide.")


def call_chat(system: str, history: list, max_tokens: int = 2048, client=None) -> str:
    """Conversation libre (multi-tours) avec le prof IA.

    `history` : liste de {role: "user"|"assistant", content: str}, se terminant
    par le dernier message de l'élève. Renvoie la réponse texte du prof.

    Relances automatiques sur incident passager, sous disjoncteur : en cas de
    panne durable du fournisseur, l'appel échoue immédiatement au lieu de faire
    patienter l'élève pendant tout le timeout.
    """
    cli = client or get_client()
    provider = _provider()

    def _run() -> str:
        if provider == "claude":
            return _chat_claude(system, history, max_tokens, cli)
        if provider == "moonshot":
            return _chat_moonshot(system, history, max_tokens, cli)
        return _chat_gemini(system, history, max_tokens, cli)

    return _with_retries(provider, "chat", _run)


def call_structured(
    system: str,
    user_content: str,
    schema: Dict[str, Any],
    max_tokens: int = 2048,
    client=None,
) -> Dict[str, Any]:
    """Appelle le modèle en mode JSON structuré et renvoie le dict parsé.

    Interface stable pour toutes les routes IA (indépendante du fournisseur).
    Relance automatiquement les incidents passagers (429, 5xx, JSON tronqué) avec
    backoff, dans la limite du budget `AI_TOTAL_DEADLINE`, et lève
    `AICoachUnavailable` quand il n'y a plus rien à tenter.
    """
    cli = client or get_client()
    provider = _provider()

    def _run() -> Dict[str, Any]:
        if provider == "claude":
            return _call_claude(system, user_content, schema, max_tokens, cli)
        if provider == "moonshot":
            return _call_moonshot(system, user_content, schema, max_tokens, cli)
        return _call_gemini(system, user_content, schema, max_tokens, cli)

    return _with_retries(provider, "structured", _run)
