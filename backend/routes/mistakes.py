"""
Rubrique « Mes questions à retravailler » — mémoire des erreurs de l'élève.

- Chaque réponse fausse crée/incrémente une entrée `UserMistakeDB` via
  `record_mistake()` : entraînement, questions pièges, révision, et examen
  (réponses fausses ET questions laissées sans réponse, comptées fausses dans
  la note). Un examen abandonné en cours de route reporte aussi ses réponses
  fausses (`sweep_abandoned_exams`).
- L'élève peut rejouer ses erreurs quand il veut (`POST /api/mistakes/review`).
- Deux bonnes réponses consécutives en révision font passer la question en
  `mastered = True` : elle sort de la liste active mais reste en historique.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Support des imports depuis backend/ et depuis la racine du repo
try:
    from database import get_db
    from models import (
        UserMistakeDB, QuestionDB, ExamSessionDB, User,
        MistakeReviewRequest, MistakeReviewResponse,
    )
    from auth import get_current_user, require_subscription
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import (
        UserMistakeDB, QuestionDB, ExamSessionDB, User,
        MistakeReviewRequest, MistakeReviewResponse,
    )
    from backend.auth import get_current_user, require_subscription

logger = logging.getLogger(__name__)

# Un examen dure 40 minutes : resté « en cours » bien au-delà, il a été abandonné.
EXAM_ABANDONED_AFTER = timedelta(hours=2)

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


def _apply_mistake(db: Session, user_id: str, question_id: str) -> None:
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
        db.add(UserMistakeDB(
            user_id=user_id,
            question_id=question_id,
            times_wrong=1,
            times_correct_since=0,
            mastered=False,
            first_wrong_at=now,
            last_wrong_at=now,
        ))
    else:
        entry.times_wrong = (entry.times_wrong or 0) + 1
        entry.times_correct_since = 0   # une nouvelle erreur casse la série
        entry.mastered = False          # la question revient à retravailler
        entry.last_wrong_at = now
    db.flush()


def record_mistake(db: Session, user_id: str, question_id: str, commit: bool = True) -> None:
    """Enregistre ou incrémente une erreur pour un élève.

    Réutilisable depuis n'importe quel flux (entraînement, examen, révision).
    Ne lève jamais — une erreur de suivi ne doit pas casser le parcours — mais
    n'efface pas non plus le reste du travail en cours : chaque enregistrement
    vit dans son propre point de sauvegarde. Un échec annulait auparavant TOUTE
    la transaction, donc les erreurs déjà notées du même examen, sans trace.
    """
    if not user_id or not question_id or user_id == "guest":
        return
    for attempt in range(2):
        savepoint = db.begin_nested()
        try:
            _apply_mistake(db, user_id, question_id)
            savepoint.commit()
            break
        except IntegrityError:
            # Deux réponses quasi simultanées sur la même question : l'autre
            # requête a créé la ligne ; on la relit et on l'incrémente.
            savepoint.rollback()
            if attempt == 1:
                logger.warning("Erreur non enregistrée (conflit) : %s / %s", user_id, question_id)
        except Exception:
            savepoint.rollback()
            logger.exception("Erreur non enregistrée : %s / %s", user_id, question_id)
            break
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Enregistrement des erreurs impossible pour %s", user_id)


def _is_correct(question: QuestionDB, option_id: Optional[str]) -> bool:
    return bool(option_id) and any(
        opt.get("id") == option_id and opt.get("is_correct") for opt in (question.options or [])
    )


def record_exam_mistakes(db: Session, exam: ExamSessionDB, include_unanswered: bool = True,
                         only_unanswered: bool = False) -> int:
    """Reporte les erreurs d'un examen dans « questions à retravailler ».

    Réponse fausse, et — à la fin de l'examen — question laissée sans réponse :
    la note la compte fausse, l'élève doit donc la retravailler. Renvoie le
    nombre d'erreurs reportées. Ne valide pas la transaction.
    """
    answers = exam.answers or {}
    question_ids = list(exam.question_ids or []) or list(answers.keys())
    for qid in answers:
        if qid not in question_ids:
            question_ids.append(qid)
    if not question_ids:
        return 0
    questions = {
        q.id: q for q in db.query(QuestionDB).filter(QuestionDB.id.in_(question_ids)).all()
    }
    reported = 0
    for qid in question_ids:
        question = questions.get(qid)
        if question is None:
            continue
        selected = answers.get(qid)
        if selected is None and not include_unanswered:
            continue
        if selected is not None and only_unanswered:
            continue
        if not _is_correct(question, selected):
            record_mistake(db, exam.user_id, qid, commit=False)
            reported += 1
    return reported


def sweep_abandoned_exams(db: Session, user_id: str) -> int:
    """Reporte les réponses fausses des examens abandonnés de l'élève.

    Un examen jamais terminé (onglet fermé, téléphone éteint) ne passait jamais
    par la correction : ses erreurs étaient perdues. Seules les réponses
    données comptent ici — l'élève n'a peut-être jamais vu les autres questions.
    L'examen passe en « abandoned » pour n'être compté qu'une fois.
    """
    if not user_id or user_id == "guest":
        return 0
    limit = datetime.utcnow() - EXAM_ABANDONED_AFTER
    try:
        stale = (
            db.query(ExamSessionDB)
            .filter(
                ExamSessionDB.user_id == user_id,
                ExamSessionDB.status == "in_progress",
                ExamSessionDB.created_at < limit,
            )
            .all()
        )
        reported = 0
        for exam in stale:
            reported += record_exam_mistakes(db, exam, include_unanswered=False)
            exam.status = "abandoned"
        if stale:
            db.commit()
        return reported
    except Exception:
        db.rollback()
        logger.exception("Report des examens abandonnés impossible pour %s", user_id)
        return 0


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
    sweep_abandoned_exams(db, current_user.id)

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
    sweep_abandoned_exams(db, current_user.id)
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
