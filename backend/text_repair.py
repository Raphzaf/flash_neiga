"""
Réparation des textes « mojibake » (UTF-8 lu comme du latin-1).

Symptôme constaté en base de production : « SÃ©curitÃ© » au lieu de
« Sécurité », « Connaissance du vÃ©hicule » au lieu de « véhicule ». 510
questions sur 1842 — 28 % du catalogue — affichaient une catégorie abîmée dans
le filtre d'entraînement et dans les statistiques de l'élève.

La cause est toujours la même : un texte déjà encodé en UTF-8 a été relu comme
du latin-1, puis ré-encodé en UTF-8. L'opération est réversible exactement —
`encode('latin-1').decode('utf-8')` retrouve l'original — à condition de ne
l'appliquer qu'aux chaînes réellement abîmées. C'est tout l'objet de ce module :
décider, sans se tromper, si une chaîne est du mojibake.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Séquences que produit le double encodage d'un caractère accentué. « Ã » seul
# ne suffit pas comme indice : « Ã » est une lettre légitime du portugais.
# On exige donc une des séquences que le double encodage produit réellement.
_MOJIBAKE_MARKERS = (
    "Ã©", "Ã¨", "Ãª", "Ã«",        # é è ê ë
    "Ã ", "Ã¢", "Ã¤",              # à â ä
    "Ã®", "Ã¯",                     # î ï
    "Ã´", "Ã¶",                     # ô ö
    "Ã¹", "Ã»", "Ã¼",              # ù û ü
    "Ã§",                            # ç
    "Ã‰", "Ãˆ",                     # É È
    "Â°", "Â«", "Â»", "Â ",        # ° « » espace insécable
    "â€™", "â€œ", "â€", "â€“", "â€”",  # apostrophes et tirets typographiques
)


def looks_like_mojibake(value: str) -> bool:
    """Vrai si la chaîne porte la trace d'un double encodage."""
    return any(marker in value for marker in _MOJIBAKE_MARKERS)


def repair_mojibake(value: Optional[str]) -> Optional[str]:
    """Rend à une chaîne abîmée son texte d'origine. Sans effet sur les autres.

    Prudence volontaire :

    * une chaîne qui ne porte aucune marque de double encodage est renvoyée
      telle quelle — on ne touche pas à ce qui va bien ;
    * si la conversion échoue (la chaîne contenait autre chose qu'un simple
      double encodage), l'original est conservé : mieux vaut un accent abîmé
      qu'un texte mutilé ;
    * la fonction est idempotente. Appliquée deux fois, elle ne casse pas le
      texte qu'elle vient de réparer, ce qui permet de la relancer sans risque.
    """
    if not value or not isinstance(value, str):
        return value
    if not looks_like_mojibake(value):
        return value

    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # La chaîne mélange du mojibake et des caractères hors latin-1 : la
        # réparation globale n'est pas sûre, on préfère ne rien faire.
        return value

    # Un double encodage peut avoir eu lieu deux fois. On déroule, mais jamais
    # au-delà : une chaîne qui « se réparerait » indéfiniment signalerait que
    # notre détection se trompe.
    for _ in range(2):
        if not looks_like_mojibake(repaired):
            break
        try:
            repaired = repaired.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break

    return repaired


def repair_question_categories(db) -> dict:
    """Répare les catégories abîmées des questions et des panneaux.

    Seule la catégorie est concernée : le relevé fait sur la base de production
    a montré que l'énoncé, les options et l'explication étaient intacts. On s'en
    tient donc à ce qui est réellement abîmé, plutôt que de réécrire en masse
    des colonnes qui vont bien.

    Renvoie le détail de ce qui a été corrigé, pour l'afficher à l'exploitant.
    """
    try:
        from models import QuestionDB, TrafficSignDB
    except ImportError:  # pragma: no cover - import depuis la racine du dépôt
        from backend.models import QuestionDB, TrafficSignDB

    report = {"questions": 0, "panneaux": 0, "corrections": {}}

    for model, key in ((QuestionDB, "questions"), (TrafficSignDB, "panneaux")):
        rows = db.query(model).filter(model.category.isnot(None)).all()
        for row in rows:
            repaired = repair_mojibake(row.category)
            if repaired and repaired != row.category:
                report["corrections"].setdefault(row.category, repaired)
                row.category = repaired
                report[key] += 1

    if report["questions"] or report["panneaux"]:
        db.commit()
        logger.info(
            "Catégories réparées : %s question(s), %s panneau(x) — %s",
            report["questions"], report["panneaux"],
            ", ".join(f"{bad!r} → {good!r}" for bad, good in report["corrections"].items()),
        )

    return report
