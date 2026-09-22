"""
Réglages d'exploitation modifiables depuis l'espace administrateur.

Certains réglages ne sont pas des secrets : la raison sociale de l'entreprise,
son numéro d'identification, son adresse. Les enfermer dans des variables
d'environnement obligeait à redéployer le serveur pour corriger une virgule — et,
tant que personne ne le faisait, aucune facture n'était émise.

Ces réglages vivent donc en base, et l'environnement ne sert plus que de valeur
par défaut :

    base  >  variable d'environnement  >  valeur par défaut du code

Les secrets (clés d'API, mots de passe de terminal) restent, eux, exclusivement
dans l'environnement : `ALLOWED_KEYS` en est la garantie, seules les clés qu'elle
liste peuvent être écrites ou relues ici.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, Optional

from sqlalchemy.orm import Session

try:
    from models import AppSettingDB
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.models import AppSettingDB

logger = logging.getLogger(__name__)

# Liste blanche : seules ces clés sont lisibles et modifiables par cette voie.
# Elle empêche qu'une requête d'administration devienne un moyen de lire ou
# d'écrire n'importe quelle variable du serveur.
ALLOWED_KEYS = (
    # Identité légale de l'émetteur des factures
    "INVOICE_COMPANY_NAME",
    "INVOICE_COMPANY_LEGAL_ID",
    "INVOICE_COMPANY_ADDRESS",
    "INVOICE_COMPANY_CITY",
    "INVOICE_COMPANY_COUNTRY",
    "INVOICE_COMPANY_EMAIL",
    "INVOICE_COMPANY_PHONE",
    "INVOICE_COMPANY_VAT_ID",
    "INVOICE_FOOTER",
    # Paramètres de facturation
    "INVOICE_VAT_RATE",
    "INVOICE_PRICES_INCLUDE_VAT",
)

# Durée de vie du cache mémoire. Les réglages sont lus à chaque émission de
# facture : les relire en base chaque fois serait du gaspillage, mais un réglage
# corrigé doit être pris en compte tout de suite — d'où un cache court, purgé
# explicitement à l'écriture.
_CACHE_TTL_S = 30.0

_lock = threading.Lock()
_cache: Dict[str, Optional[str]] = {}
_cache_expires_at: float = 0.0


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def invalidate_cache() -> None:
    """Oublie les valeurs en mémoire : la prochaine lecture repasse par la base."""
    global _cache_expires_at
    with _lock:
        _cache.clear()
        _cache_expires_at = 0.0


def _load_all(db: Session) -> Dict[str, Optional[str]]:
    """Charge les réglages connus depuis la base, avec le cache en tampon."""
    global _cache_expires_at

    now = time.monotonic()
    with _lock:
        if _cache and now < _cache_expires_at:
            return dict(_cache)

    values: Dict[str, Optional[str]] = {}
    try:
        rows = db.query(AppSettingDB).filter(AppSettingDB.key.in_(ALLOWED_KEYS)).all()
        for row in rows:
            values[row.key] = _clean(row.value)
    except Exception as exc:
        # La table peut ne pas encore exister (tout premier démarrage) : on se
        # rabat alors sur l'environnement plutôt que de faire échouer l'appel.
        logger.debug("Réglages illisibles en base (%s) — environnement utilisé.", exc)
        return {}

    with _lock:
        _cache.clear()
        _cache.update(values)
        _cache_expires_at = time.monotonic() + _CACHE_TTL_S
    return dict(values)


def get(key: str, db: Optional[Session] = None, default: str = "") -> str:
    """Valeur d'un réglage : base, puis environnement, puis `default`."""
    if key not in ALLOWED_KEYS:
        raise KeyError(f"Réglage inconnu : {key}")

    if db is not None:
        stored = _load_all(db).get(key)
        if stored:
            return stored
    else:
        # Sans session fournie, on se contente de ce que le cache sait déjà :
        # ouvrir une session ici rendrait le module dépendant du moteur.
        with _lock:
            cached = _cache.get(key) if time.monotonic() < _cache_expires_at else None
        if cached:
            return cached

    return (os.environ.get(key) or default).strip()


def get_many(db: Optional[Session] = None) -> Dict[str, str]:
    """Tous les réglages autorisés, résolus dans l'ordre base → environnement."""
    return {key: get(key, db=db) for key in ALLOWED_KEYS}


def sources(db: Optional[Session] = None) -> Dict[str, str]:
    """D'où vient chaque valeur : « base », « environnement » ou « absent ».

    Affiché à l'administrateur pour qu'il sache ce qu'il est en train de
    surcharger — sans quoi un réglage renseigné dans l'environnement et vide en
    base passe pour manquant.
    """
    stored = _load_all(db) if db is not None else {}
    result: Dict[str, str] = {}
    for key in ALLOWED_KEYS:
        if stored.get(key):
            result[key] = "base"
        elif (os.environ.get(key) or "").strip():
            result[key] = "environnement"
        else:
            result[key] = "absent"
    return result


def set_many(db: Session, values: Dict[str, Optional[str]], updated_by: Optional[str] = None) -> Dict[str, str]:
    """Enregistre des réglages. Une valeur vide efface la ligne (retour à l'environnement).

    Les clés hors liste blanche sont refusées, et non silencieusement ignorées :
    une faute de frappe dans un nom de réglage doit se voir.
    """
    unknown = [key for key in values if key not in ALLOWED_KEYS]
    if unknown:
        raise KeyError("Réglages inconnus : " + ", ".join(sorted(unknown)))

    for key, raw in values.items():
        cleaned = _clean(raw)
        row = db.query(AppSettingDB).filter(AppSettingDB.key == key).first()
        if cleaned is None:
            # Effacer le réglage, plutôt que d'enregistrer une chaîne vide :
            # la valeur de l'environnement reprend alors la main.
            if row is not None:
                db.delete(row)
            continue
        if row is None:
            db.add(AppSettingDB(key=key, value=cleaned, updated_by=updated_by))
        else:
            row.value = cleaned
            row.updated_by = updated_by

    db.commit()
    invalidate_cache()
    return get_many(db)
