"""
Rubrique « Mes questions à retravailler » — mémoire des erreurs de l'élève.

- Chaque réponse fausse (entraînement ou examen) crée/incrémente une entrée
  `UserMistakeDB` via `record_mistake()`.
- L'élève peut rejouer ses erreurs quand il veut (`POST /api/mistakes/review`).
- Deux bonnes réponses consécutives en révision font passer la question en
  `mastered = True` : elle sort de la liste active mais reste en historique.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Support des imports depuis backend/ et depuis la racine du repo
try:
    from database import get_db
    from models import (
        UserMistakeDB, QuestionDB, User,
        MistakeReviewRequest, MistakeReviewResponse,
    )
    from auth import get_current_user, require_subscription
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import (
        UserMistakeDB, QuestionDB, User,
        MistakeReviewRequest, MistakeReviewResponse,
    )
    from backend.auth import get_current_user, require_subscription

router = APIRouter(
    prefix="/api/mistakes",
    tags=["mistakes"],
    dependencies=[Depends(require_subscription)],
)


# ===== Helpers réutilisables (appelés depuis training/exam) =====
def _correct_option_id(question: QuestionDB) -> Optional[str]:
    for opt in (question.options or []):
        if opt.get("is_correct"):
            return opt.get("id")
    return None


def record_mistake(db: Session, user_id: str, question_id: str, commit: bool = True) -> None:
    """Enregistre ou incrémente une erreur pour un élève.

    Idempotent au sens métier : réutilisable depuis n'importe quel flux (training,
    examen). Ne lève jamais — une erreur de suivi ne doit pas casser le parcours.
    """
    if not user_id or not question_id:
        return
    try:
        entry = (
            db.query(UserMistakeDB)
            .filter(
                UserMistakeDB.user_id == user_id,
                UserMistakeDB.question_id == question_id,
            )
            .first()
        )
        now = datetime.utcnow()
        if entry is None:
            entry = UserMistakeDB(
                user_id=user_id,
                question_id=question_id,
                times_wrong=1,
                times_correct_since=0,
                mastered=False,
                first_wrong_at=now,
                last_wrong_at=now,
            )
            db.add(entry)
        else:
            entry.times_wrong = (entry.times_wrong or 0) + 1
            entry.times_correct_since = 0   # une nouvelle erreur casse la série
            entry.mastered = False          # la question revient à retravailler
            entry.last_wrong_at = now
        if commit:
            db.commit()
    except Exception:
        db.rollback()


# ===== Endpoints =====
@router.get("")
async def list_mistakes(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste paginée des questions non maîtrisées de l'élève, groupées par catégorie."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    base_query = (
        db.query(UserMistakeDB)
        .filter(
            UserMistakeDB.user_id == current_user.id,
            UserMistakeDB.mastered == False,  # noqa: E712
        )
        .order_by(UserMistakeDB.last_wrong_at.desc())
    )
    total = base_query.count()
    entries = base_query.offset(offset).limit(limit).all()

    items = []
    for entry in entries:
        question = db.query(QuestionDB).filter(QuestionDB.id == entry.question_id).first()
        if not question:
            continue  # question supprimée entre-temps
        items.append({
            "question": {
                "id": question.id,
                "text": question.text,
                "category": question.category,
                "options": question.options,
                "explanation": question.explanation,
                "image_url": question.image_url,
            },
            "stats": {
                "times_wrong": entry.times_wrong,
                "times_correct_since": entry.times_correct_since,
                "last_wrong_at": entry.last_wrong_at,
                "first_wrong_at": entry.first_wrong_at,
            },
        })

    # Regroupement par catégorie pour l'affichage
    categories: dict = {}
    for item in items:
        cat = item["question"]["category"] or "Autre"
        categories.setdefault(cat, []).append(item)
    grouped = [
        {"category": cat, "questions": qs}
        for cat, qs in sorted(categories.items(), key=lambda kv: kv[0].lower())
    ]

    return {
        "total": total,
        "count": len(items),
        "items": items,
        "categories": grouped,
    }


@router.get("/count")
async def mistakes_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Nombre de questions à retravailler (pour le badge du tableau de bord)."""
    count = (
        db.query(UserMistakeDB)
        .filter(
            UserMistakeDB.user_id == current_user.id,
            UserMistakeDB.mastered == False,  # noqa: E712
        )
        .count()
    )
    return {"count": count}


@router.post("/review", response_model=MistakeReviewResponse)
async def review_mistake(
    payload: MistakeReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soumet une réponse en mode révision et met à jour les compteurs de maîtrise."""
    question = db.query(QuestionDB).filter(QuestionDB.id == payload.question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question introuvable")

    correct_id = _correct_option_id(question)
    is_correct = bool(correct_id and payload.selected_option_id == correct_id)

    entry = (
        db.query(UserMistakeDB)
        .filter(
            UserMistakeDB.user_id == current_user.id,
            UserMistakeDB.question_id == payload.question_id,
        )
        .first()
    )
    now = datetime.utcnow()

    if entry is None:
        # L'élève révise une question qui n'était pas (ou plus) suivie.
        if is_correct:
            return MistakeReviewResponse(
                is_correct=True,
                correct_option_id=correct_id,
                explanation=question.explanation,
                mastered=True,
                times_correct_since=1,
            )
        # Première erreur constatée ici → on l'ajoute au suivi.
        record_mistake(db, current_user.id, payload.question_id)
        return MistakeReviewResponse(
            is_correct=False,
            correct_option_id=correct_id,
            explanation=question.explanation,
            mastered=False,
            times_correct_since=0,
        )

    if is_correct:
        entry.times_correct_since = (entry.times_correct_since or 0) + 1
        if entry.times_correct_since >= 2:
            entry.mastered = True
    else:
        entry.times_wrong = (entry.times_wrong or 0) + 1
        entry.times_correct_since = 0
        entry.mastered = False
        entry.last_wrong_at = now

    db.commit()
    db.refresh(entry)

    return MistakeReviewResponse(
        is_correct=is_correct,
        correct_option_id=correct_id,
        explanation=question.explanation,
        mastered=entry.mastered,
        times_correct_since=entry.times_correct_since,
    )
