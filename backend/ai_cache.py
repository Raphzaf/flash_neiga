"""
Mémoire partagée du prof IA (Flash Neiga).

Principe : **une réponse produite une fois sert à tout le monde, pour toujours.**

Quand un élève se trompe sur une question et que le prof lui explique son erreur,
l'explication est écrite en base. Le prochain élève qui commet la même erreur —
dix minutes ou trois ans plus tard — reçoit cette explication instantanément,
sans le moindre appel facturé au fournisseur d'IA.

Le module apporte trois garanties :

1. **Reconnaissance robuste.** Deux formulations qui ne diffèrent que par la
   casse, les accents, la ponctuation ou les espaces sont considérées comme la
   même demande (« C'est quoi la distance de sécurité ? » = « cest quoi la
   distance de securite »). Sans cela, le cache raterait la moitié des reprises.

2. **Un seul appel en cas de rafale.** Si trente élèves butent sur la même
   question à la même seconde, un seul appel part au modèle : les vingt-neuf
   autres attendent son résultat et le partagent (« single-flight »).

3. **Aucune fuite de données personnelles.** Une question qui contient un
   e-mail, un téléphone ou un nom propre n'est jamais mise en cache : elle ne
   doit pas ressortir dans la session d'un autre élève.

Le cache ne fait jamais échouer une requête : toute erreur d'écriture ou de
lecture est absorbée et journalisée. Au pire, on rappelle le modèle.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

try:
    from models import AIAnswerCacheDB
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.models import AIAnswerCacheDB

logger = logging.getLogger(__name__)

# Version des consignes pédagogiques. À incrémenter dès que l'on change un
# prompt système ou un schéma de sortie : les réponses produites avec l'ancienne
# version cessent alors d'être servies, sans purge manuelle de la table.
PROMPT_VERSION = "v1"

# Bornes de mise en cache d'une question libre. Trop court = pas assez
# discriminant ; trop long = question personnelle, propre à un seul élève.
MIN_CACHEABLE_QUESTION = 8
MAX_CACHEABLE_QUESTION = 400


# ===== Normalisation =====
# L'apostrophe d'élision est SUPPRIMÉE, pas remplacée par un espace : « c'est »
# et « cest » doivent tomber sur la même entrée, sinon un élève qui tape vite
# repaie une réponse déjà connue. Les autres signes deviennent des espaces.
_APOSTROPHE_RE = re.compile(r"['’ʼ`]", flags=re.UNICODE)
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+", flags=re.UNICODE)


def normalize_text(text: Optional[str]) -> str:
    """Réduit un texte à sa forme comparable.

    Minuscules, accents retirés, ponctuation supprimée, espaces normalisés :
    ce qui reste est ce qui distingue vraiment deux demandes.
    """
    if not text:
        return ""
    # NFD sépare les lettres de leurs accents, qu'on peut alors retirer.
    decomposed = unicodedata.normalize("NFD", str(text))
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = _APOSTROPHE_RE.sub("", without_accents.lower())
    cleaned = _PUNCT_RE.sub(" ", lowered)
    return _SPACE_RE.sub(" ", cleaned).strip()


def make_key(kind: str, parts: Sequence[Optional[str]], version: str = PROMPT_VERSION) -> str:
    """Clé de cache stable et sans collision pour une demande donnée.

    Les composants sont joints par un séparateur qui ne peut pas apparaître dans
    un texte normalisé : sans lui, ("ab", "c") et ("a", "bc") donneraient la
    même clé et un élève recevrait la réponse d'une autre question.
    """
    payload = "\x1f".join([kind, version] + [normalize_text(part) for part in parts])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ===== Confidentialité =====
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Suite d'au moins 7 chiffres, tolérant espaces/points/tirets : téléphone, carte,
# numéro de permis… Rien de tout cela n'a sa place dans un cache partagé.
_LONG_DIGITS_RE = re.compile(r"(?:\d[\s.\-]?){7,}")
# Formules par lesquelles un élève parle de lui : la réponse sera personnelle.
_PERSONAL_MARKERS = (
    "je mappelle", "mon nom", "mon prenom", "mon numero",
    "mon telephone", "mon email", "mon mail", "mon adresse", "mon permis",
    "mon compte", "ma carte", "mon abonnement", "mon paiement", "ma facture",
    "mon dossier", "mon rendez vous", "mon examen est", "je passe lexamen le",
)


def is_cacheable_question(question: Optional[str]) -> bool:
    """Cette question peut-elle être mémorisée pour d'autres élèves ?

    On refuse tout ce qui est propre à une personne. Resservir « Mon examen est
    le 12/03, suis-je prêt ? » à un autre élève serait à la fois faux et une
    fuite de données : dans le doute, on ne met pas en cache.
    """
    if not question:
        return False
    raw = str(question).strip()
    if not (MIN_CACHEABLE_QUESTION <= len(raw) <= MAX_CACHEABLE_QUESTION):
        return False
    if _EMAIL_RE.search(raw) or _LONG_DIGITS_RE.search(raw):
        return False
    normalized = normalize_text(raw)
    return not any(marker in normalized for marker in _PERSONAL_MARKERS)


# ===== Single-flight =====
# Un verrou par clé, créé à la demande et détruit dès que plus personne ne
# l'attend : sans ce comptage, la table de verrous grossirait indéfiniment.
_locks_guard = threading.Lock()
_locks: Dict[str, "threading.Lock"] = {}
_lock_waiters: Dict[str, int] = {}


# Au-delà de cette attente, on renonce à mutualiser et on produit sa propre
# réponse. Cela coûte un appel, mais garantit qu'un thread bloqué ne peut jamais
# immobiliser le pool de FastAPI — donc jamais figer le site entier.
LOCK_WAIT_SECONDS = 60.0


@contextmanager
def single_flight(cache_key: str) -> Iterator[None]:
    """Sérialise les productions concurrentes portant sur la même clé.

    Trente élèves qui butent au même instant sur la même question ne doivent
    déclencher qu'un seul appel facturé : le premier produit la réponse et
    l'écrit, les autres la relisent depuis le cache en sortant d'ici.

    L'appelant DOIT relire le cache après être entré dans le bloc.
    """
    with _locks_guard:
        lock = _locks.setdefault(cache_key, threading.Lock())
        _lock_waiters[cache_key] = _lock_waiters.get(cache_key, 0) + 1

    acquired = lock.acquire(timeout=LOCK_WAIT_SECONDS)
    if not acquired:
        # Le producteur est anormalement lent : mieux vaut un appel de trop
        # qu'un élève qui attend sans fin.
        logger.warning("Attente du verrou dépassée pour %s — production en parallèle.", cache_key[:12])
    try:
        yield
    finally:
        if acquired:
            lock.release()
        with _locks_guard:
            remaining = _lock_waiters.get(cache_key, 1) - 1
            if remaining <= 0:
                _lock_waiters.pop(cache_key, None)
                _locks.pop(cache_key, None)
            else:
                _lock_waiters[cache_key] = remaining


# ===== Lecture / écriture =====
def lookup(db: Session, cache_key: str, *, count_hit: bool = True) -> Optional[Dict[str, Any]]:
    """Renvoie la réponse mémorisée pour cette clé, ou None.

    Ne lève jamais : un cache en erreur doit dégrader vers un appel au modèle,
    pas casser la page de l'élève.
    """
    try:
        entry = (
            db.query(AIAnswerCacheDB)
            .filter(AIAnswerCacheDB.cache_key == cache_key)
            .first()
        )
    except Exception as exc:
        logger.warning("Lecture du cache IA impossible (%s) — on rappellera le modèle.", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None

    if entry is None:
        return None

    try:
        payload = json.loads(entry.payload_json)
    except (TypeError, ValueError) as exc:
        # Entrée corrompue : on la retire pour qu'elle soit régénérée proprement.
        logger.warning("Entrée de cache IA illisible (%s) — suppression.", exc)
        try:
            db.delete(entry)
            db.commit()
        except Exception:
            db.rollback()
        return None

    if count_hit:
        _record_hit(db, entry)

    return payload


def _record_hit(db: Session, entry: AIAnswerCacheDB) -> None:
    """Compte la réutilisation (= un appel API économisé). Best-effort."""
    try:
        entry.hit_count = (entry.hit_count or 0) + 1
        entry.last_used_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()  # un compteur raté ne doit jamais priver l'élève de sa réponse


def store(
    db: Session,
    cache_key: str,
    kind: str,
    payload: Any,
    *,
    subject_id: Optional[str] = None,
    prompt_preview: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    version: str = PROMPT_VERSION,
) -> None:
    """Mémorise une réponse pour tous les élèves suivants. Ne lève jamais.

    Une écriture concurrente sur la même clé viole la contrainte d'unicité :
    ce n'est pas une erreur, c'est la preuve qu'un autre processus a déjà
    enregistré la même réponse.
    """
    try:
        db.add(AIAnswerCacheDB(
            cache_key=cache_key,
            kind=kind,
            subject_id=subject_id,
            prompt_preview=(prompt_preview or "")[:2000] or None,
            payload_json=json.dumps(payload, ensure_ascii=False),
            provider=provider,
            model=model,
            prompt_version=version,
            hit_count=0,
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.info("Réponse IA non mémorisée (%s) — sans conséquence pour l'élève.", exc)


def invalidate_subject(db: Session, subject_id: str) -> int:
    """Oublie toutes les réponses liées à un sujet (question corrigée, par ex.).

    Renvoie le nombre d'entrées supprimées.
    """
    try:
        deleted = (
            db.query(AIAnswerCacheDB)
            .filter(AIAnswerCacheDB.subject_id == subject_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(deleted or 0)
    except Exception as exc:
        db.rollback()
        logger.warning("Invalidation du cache IA impossible pour %s : %s", subject_id, exc)
        return 0


def stats(db: Session) -> Dict[str, Any]:
    """Photographie du cache : combien d'entrées, combien d'appels évités."""
    try:
        rows = (
            db.query(
                AIAnswerCacheDB.kind,
                func.count(AIAnswerCacheDB.id),
                func.coalesce(func.sum(AIAnswerCacheDB.hit_count), 0),
            )
            .group_by(AIAnswerCacheDB.kind)
            .all()
        )
    except Exception as exc:
        logger.warning("Statistiques du cache IA indisponibles : %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return {"available": False, "reason": str(exc)[:200]}

    by_kind = {
        kind: {"entries": int(count or 0), "reuses": int(hits or 0)}
        for kind, count, hits in rows
    }
    entries = sum(item["entries"] for item in by_kind.values())
    reuses = sum(item["reuses"] for item in by_kind.values())
    total = entries + reuses  # une entrée = 1 appel payé, une réutilisation = 0
    return {
        "available": True,
        "prompt_version": PROMPT_VERSION,
        "entries": entries,
        "reuses": reuses,
        "api_calls_saved": reuses,
        "hit_rate_pct": round(100 * reuses / total) if total else 0,
        "by_kind": by_kind,
    }
