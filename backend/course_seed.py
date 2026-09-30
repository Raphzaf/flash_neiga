"""
Cours fournis avec le site, chargés en base une seule fois.

Le support « Code de la route » (converti depuis Word par
scripts/docx_to_courses.py) vit dans data/courses_code_de_la_route.json. Au
démarrage, ses chapitres sont ajoutés à la table des cours, puis un marqueur
est posé dans app_settings : un cours que l'administrateur supprime ou modifie
ensuite dans le CMS n'est donc jamais recréé ni écrasé.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

try:
    from models import AppSettingDB, CourseDB
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.models import AppSettingDB, CourseDB

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# (fichier, marqueur) — changer le marqueur recharge le fichier une fois de plus.
BUNDLED_COURSES = (
    ("courses_code_de_la_route.json", "SEED_COURSES_CODE_DE_LA_ROUTE_V1"),
)

_FIELDS = ("title", "description", "content", "order", "video_url", "pdf_url", "image_url", "category")


def seed_bundled_courses(db: Session, data_dir: Path = DATA_DIR) -> int:
    """Ajoute les cours fournis qui n'ont pas encore été chargés. Renvoie le nombre créé."""
    created = 0
    for filename, marker in BUNDLED_COURSES:
        if db.query(AppSettingDB).filter(AppSettingDB.key == marker).first():
            continue
        path = data_dir / filename
        if not path.exists():
            logger.warning("Cours fournis introuvables : %s", path)
            continue

        courses: List[dict] = json.loads(path.read_text(encoding="utf-8"))
        existing = {title for (title,) in db.query(CourseDB.title).all()}
        for item in courses:
            if item["title"] in existing:
                continue
            db.add(CourseDB(**{field: item.get(field) for field in _FIELDS}))
            created += 1

        db.add(AppSettingDB(
            key=marker,
            value=datetime.utcnow().isoformat(),
            updated_by="course_seed",
        ))
        db.commit()
        logger.info("Cours « %s » chargés : %s ajouté(s)", filename, created)
    return created
