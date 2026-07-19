"""
Rubrique « Les questions pièges les plus fréquentes au code » (Phase 4).

Agrège les erreurs de TOUS les élèves confondus (UserMistakeDB) pour faire
remonter les questions qui collectent le plus de réponses fausses, et fournit
une synthèse pédagogique générée par Claude (régénérable par l'admin).
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import UserMistakeDB, QuestionDB, AILessonDB, TrapSynthesisDB, User
    from auth import get_current_user
    from ai_client import call_structured, ai_configured, AICoachUnavailable
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import UserMistakeDB, QuestionDB, AILessonDB, TrapSynthesisDB, User
    from backend.auth import get_current_user
    from backend.ai_client import call_structured, ai_configured, AICoachUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trap-questions"])

AI_UNAVAILABLE_MSG = "Le prof est momentanément indisponible, réessaie dans un instant."

SYNTHESIS_SYSTEM_PROMPT = (
    "Tu es un professeur de code de la route israélien qui enseigne en français. "
    "On te donne les questions qui piègent le plus les élèves. Tu produis une "
    "synthèse pédagogique claire et motivante, en tutoyant l'élève, pour l'aider "
    "à repérer et éviter ces pièges. Ne mentionne jamais que tu es une IA."
)

SYNTHESIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "intro": {"type": "string"},
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titre": {"type": "string"},
                    "pourquoi": {"type": "string"},
                    "conseil": {"type": "string"},
                },
                "required": ["titre", "pourquoi", "conseil"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["intro", "themes"],
    "additionalProperties": False,
}


def _aggregate_traps(db: Session, limit: int) -> List[Dict[str, Any]]:
    """Top des questions les plus ratées, tous élèves confondus."""
    total_students = db.query(func.count(func.distinct(UserMistakeDB.user_id))).scalar() or 0

    rows = (
        db.query(
            UserMistakeDB.question_id.label("question_id"),
            func.sum(UserMistakeDB.times_wrong).label("total_wrong"),
            func.count(func.distinct(UserMistakeDB.user_id)).label("distinct_users"),
        )
        .group_by(UserMistakeDB.question_id)
        .order_by(func.sum(UserMistakeDB.times_wrong).desc())
        .limit(limit)
        .all()
    )

    results: List[Dict[str, Any]] = []
    for row in rows:
        q = db.query(QuestionDB).filter(QuestionDB.id == row.question_id).first()
        if not q:
            continue
        distinct_users = int(row.distinct_users or 0)
        pct = round(100 * distinct_users / total_students) if total_students else 0
        # Leçon en cache (si déjà générée) pour la mauvaise réponse la plus fréquente
        cached_lesson = (
            db.query(AILessonDB)
            .filter(AILessonDB.question_id == q.id)
            .order_by(AILessonDB.created_at.desc())
            .first()
        )
        results.append({
            "question": {
                "id": q.id,
                "text": q.text,
                "category": q.category,
                "options": q.options,
                "explanation": q.explanation,
                "image_url": q.image_url,
            },
            "stats": {
                "total_wrong": int(row.total_wrong or 0),
                "distinct_users": distinct_users,
                "percent_trapped": pct,
            },
            "lesson": json.loads(cached_lesson.lesson_json) if cached_lesson else None,
        })
    return results


@router.get("/api/trap-questions")
async def list_trap_questions(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Classement des questions pièges + synthèse pédagogique si disponible."""
    limit = max(1, min(limit, 100))
    traps = _aggregate_traps(db, limit)
    synthesis_row = (
        db.query(TrapSynthesisDB).order_by(TrapSynthesisDB.created_at.desc()).first()
    )
    synthesis = json.loads(synthesis_row.synthesis_json) if synthesis_row else None
    return {
        "count": len(traps),
        "questions": traps,
        "synthesis": synthesis,
        "synthesis_updated_at": synthesis_row.created_at if synthesis_row else None,
    }


@router.get("/api/trap-questions/synthesis")
async def get_trap_synthesis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(TrapSynthesisDB).order_by(TrapSynthesisDB.created_at.desc()).first()
    if not row:
        return {"synthesis": None, "updated_at": None}
    return {"synthesis": json.loads(row.synthesis_json), "updated_at": row.created_at}


@router.post("/api/admin/trap-questions/synthesis")
async def generate_trap_synthesis(
    db: Session = Depends(get_db),
    x_admin_token: str = Header(None),
):
    """Génère (admin) la synthèse pédagogique des questions pièges via Claude.
    Gate identique aux autres routes admin : ADMIN_TOKEN via header X-Admin-Token si défini.
    """
    if os.environ.get("ADMIN_TOKEN") and x_admin_token != os.environ.get("ADMIN_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not ai_configured():
        raise HTTPException(status_code=503, detail=AI_UNAVAILABLE_MSG)

    traps = _aggregate_traps(db, 30)
    if not traps:
        raise HTTPException(status_code=400, detail="Pas encore assez de données d'erreurs à synthétiser.")

    listing = "\n".join(
        f"{i+1}. [{t['question']['category'] or 'Général'}] {t['question']['text']} "
        f"— {t['stats']['distinct_users']} élève(s) piégé(s) ({t['stats']['percent_trapped']}%), "
        f"{t['stats']['total_wrong']} erreurs au total."
        for i, t in enumerate(traps)
    )
    user_content = (
        "Voici les questions qui piègent le plus les élèves au code israélien, "
        "classées par fréquence d'erreurs :\n\n"
        f"{listing}\n\n"
        "Produis une synthèse : une courte intro motivante, puis les grands thèmes "
        "pièges (titre, pourquoi les élèves tombent dedans, conseil concret pour les éviter)."
    )

    try:
        synthesis = call_structured(
            system=SYNTHESIS_SYSTEM_PROMPT,
            user_content=user_content,
            schema=SYNTHESIS_SCHEMA,
            max_tokens=8000,
        )
    except AICoachUnavailable:
        raise HTTPException(status_code=503, detail=AI_UNAVAILABLE_MSG)

    try:
        # On ne garde que la dernière synthèse
        db.query(TrapSynthesisDB).delete()
        db.add(TrapSynthesisDB(synthesis_json=json.dumps(synthesis, ensure_ascii=False)))
        db.commit()
    except Exception:
        db.rollback()

    return {"synthesis": synthesis, "updated_at": datetime.utcnow()}
