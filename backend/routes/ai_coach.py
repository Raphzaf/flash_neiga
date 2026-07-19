"""
Coach IA — « prof de code 24h/24 » (Flash Neiga).

Regroupe les endpoints qui appellent Claude :
- POST /api/ai-coach/lesson         → mini-leçon sur une réponse fausse (Phase 2)
- POST /api/ai-coach/series-report  → bilan de série + encouragement chiffré (Phase 3)

Chaque contenu généré est mis en cache en base (AILessonDB, SeriesReportDB) :
on ne rappelle jamais Claude pour un contenu déjà produit.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import (
        QuestionDB, CourseDB, ExamSessionDB, AILessonDB, SeriesReportDB, User,
    )
    from auth import get_current_user
    from ai_client import call_structured, ai_configured, AICoachUnavailable, diagnostics
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import (
        QuestionDB, CourseDB, ExamSessionDB, AILessonDB, SeriesReportDB, User,
    )
    from backend.auth import get_current_user
    from backend.ai_client import call_structured, ai_configured, AICoachUnavailable, diagnostics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-coach", tags=["ai-coach"])

AI_UNAVAILABLE_MSG = "Le prof est momentanément indisponible, réessaie dans un instant."

PROF_SYSTEM_PROMPT = (
    "Tu es un professeur de code de la route israélien, patient et pédagogue, "
    "qui enseigne en français à des élèves francophones préparant l'examen "
    "théorique en Israël. Tu expliques simplement, tu tutoies l'élève, tu "
    "encourages sans infantiliser. Tes réponses sont courtes, concrètes et "
    "toujours exactes par rapport au code de la route israélien. Si la "
    "question fournit une explication officielle, appuie-toi dessus en "
    "priorité. Ne mentionne jamais que tu es une IA."
)

# ===== Schémas structured outputs =====
LESSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "explication": {"type": "string"},
        "regle": {"type": "string"},
        "erreurs_a_eviter": {"type": "array", "items": {"type": "string"}},
        "schema_svg": {"type": ["string", "null"]},
    },
    "required": ["explication", "regle", "erreurs_a_eviter", "schema_svg"],
    "additionalProperties": False,
}

SERIES_REPORT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "notions_maitrisees": {"type": "array", "items": {"type": "string"}},
        "notions_a_retravailler": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "notion": {"type": "string"},
                    "conseil": {"type": "string"},
                    "cours_recommande": {"type": ["string", "null"]},
                },
                "required": ["notion", "conseil", "cours_recommande"],
                "additionalProperties": False,
            },
        },
        "mini_cours": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_resume": {"type": "string"},
                    "explication_claire": {"type": "string"},
                },
                "required": ["question_resume", "explication_claire"],
                "additionalProperties": False,
            },
        },
        "message_prof": {"type": "string"},
    },
    "required": ["notions_maitrisees", "notions_a_retravailler", "mini_cours", "message_prof"],
    "additionalProperties": False,
}


# ===== Helpers =====
def _option_text(question: QuestionDB, option_id: Optional[str]) -> Optional[str]:
    for opt in (question.options or []):
        if opt.get("id") == option_id:
            return opt.get("text")
    return None


def _correct_option(question: QuestionDB):
    for opt in (question.options or []):
        if opt.get("is_correct"):
            return opt.get("id"), opt.get("text")
    return None, None


def get_or_create_lesson(db: Session, question: QuestionDB, selected_option_id: str) -> Dict[str, Any]:
    """Renvoie la mini-leçon (depuis le cache si possible, sinon génère via Claude).
    Réutilisable par la rubrique « questions pièges ». Lève AICoachUnavailable en cas d'échec IA.
    """
    cached = (
        db.query(AILessonDB)
        .filter(
            AILessonDB.question_id == question.id,
            AILessonDB.selected_option_id == selected_option_id,
        )
        .first()
    )
    if cached:
        return {**json.loads(cached.lesson_json), "cached": True}

    correct_id, correct_text = _correct_option(question)
    chosen_text = _option_text(question, selected_option_id) or "(réponse inconnue)"
    options_txt = "\n".join(
        f"- {opt.get('text')}" + (" [BONNE RÉPONSE]" if opt.get("is_correct") else "")
        for opt in (question.options or [])
    )
    user_content = (
        f"Catégorie : {question.category or 'Général'}\n"
        f"Question : {question.text}\n\n"
        f"Options :\n{options_txt}\n\n"
        f"Réponse choisie par l'élève (FAUSSE) : {chosen_text}\n"
        f"Bonne réponse : {correct_text}\n"
    )
    if question.explanation:
        user_content += f"\nExplication officielle : {question.explanation}\n"
    user_content += (
        "\nProduis une mini-leçon. Le champ schema_svg doit contenir un schéma SVG "
        "autonome (balise <svg> complète, ~300x200, texte en français) UNIQUEMENT si "
        "un schéma aide vraiment (priorités, distances, intersections, panneaux) ; "
        "sinon mets-le à null."
    )

    lesson = call_structured(
        system=PROF_SYSTEM_PROMPT,
        user_content=user_content,
        schema=LESSON_SCHEMA,
        max_tokens=8192,  # marge pour un éventuel schéma SVG (tokens lourds)
    )

    try:
        entry = AILessonDB(
            question_id=question.id,
            selected_option_id=selected_option_id,
            lesson_json=json.dumps(lesson, ensure_ascii=False),
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()  # course concurrente : une autre requête a pu écrire le même cache

    return {**lesson, "cached": False}


def _weekly_success_rate(db: Session, user_id: str) -> Dict[str, Any]:
    """Taux de réussite (%) des 7 derniers jours vs les 7 jours précédents,
    calculé en base à partir des examens terminés — chiffres exacts, jamais inventés par l'IA.
    """
    now = datetime.utcnow()
    start_current = now - timedelta(days=7)
    start_previous = now - timedelta(days=14)

    def avg_score(since: datetime, until: datetime) -> Optional[float]:
        exams = (
            db.query(ExamSessionDB)
            .filter(
                and_(
                    ExamSessionDB.user_id == user_id,
                    ExamSessionDB.status == "completed",
                    ExamSessionDB.completed_at >= since,
                    ExamSessionDB.completed_at < until,
                )
            )
            .all()
        )
        scores = [e.score for e in exams if e.score is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores))

    current = avg_score(start_current, now + timedelta(seconds=1))
    previous = avg_score(start_previous, start_current)

    return {
        "current_pct": current,
        "previous_pct": previous,
        "has_history": previous is not None and current is not None,
    }


# ===== Endpoints =====
@router.get("/health")
async def ai_health():
    """État de configuration du coach IA (pour diagnostiquer un 503). Sans secret."""
    return diagnostics()


@router.get("/selftest")
async def ai_selftest(current_user: User = Depends(get_current_user)):
    """Fait un mini-appel réel au modèle et renvoie le VRAI message d'erreur si ça
    échoue (clé invalide, modèle non autorisé, quota…). Utile pour diagnostiquer
    un 503 sans fouiller les logs. Ne renvoie jamais la clé.
    """
    if not ai_configured():
        return {"ok": False, "error": "non configuré", "diagnostics": diagnostics()}
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    try:
        result = call_structured(
            system="Tu réponds en JSON.",
            user_content="Renvoie simplement {\"ok\": true}.",
            schema=schema,
            max_tokens=100,
        )
        return {"ok": True, "model_reply": result, "diagnostics": diagnostics()}
    except AICoachUnavailable as exc:
        return {"ok": False, "error": str(exc)[:500], "diagnostics": diagnostics()}
    except Exception as exc:  # filet de sécurité : on renvoie l'erreur au lieu d'un 500 opaque
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}", "diagnostics": diagnostics()}


@router.post("/lesson")
async def generate_lesson(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mini-leçon du prof sur une réponse fausse (Phase 2)."""
    question_id = payload.get("question_id")
    selected_option_id = payload.get("selected_option_id")
    if not question_id or not selected_option_id:
        raise HTTPException(status_code=400, detail="question_id et selected_option_id requis")

    question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question introuvable")

    # Cache : servi instantanément si déjà généré (aucun appel IA).
    cached = (
        db.query(AILessonDB)
        .filter(
            AILessonDB.question_id == question_id,
            AILessonDB.selected_option_id == selected_option_id,
        )
        .first()
    )
    if cached:
        return {**json.loads(cached.lesson_json), "cached": True}

    if not ai_configured():
        raise HTTPException(status_code=503, detail=AI_UNAVAILABLE_MSG)

    try:
        return get_or_create_lesson(db, question, selected_option_id)
    except AICoachUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"{AI_UNAVAILABLE_MSG} [{str(exc)[:300]}]")


@router.post("/series-report")
async def series_report(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bilan de série par le prof + encouragement chiffré (Phase 3)."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requis")

    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == session_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Série introuvable")

    # L'élève ne peut demander que le bilan de ses propres séries (ou d'une série anonyme).
    if exam.user_id not in (current_user.id, "guest"):
        raise HTTPException(status_code=403, detail="Accès refusé à cette série")

    # Progression chiffrée : toujours recalculée en SQL (chiffres exacts).
    encouragement = _weekly_success_rate(db, exam.user_id)

    # Bilan (texte) : servi depuis le cache si déjà généré.
    cached = db.query(SeriesReportDB).filter(SeriesReportDB.session_id == session_id).first()
    if cached:
        return {"report": json.loads(cached.report_json), "encouragement": encouragement, "cached": True}

    if not ai_configured():
        raise HTTPException(status_code=503, detail=AI_UNAVAILABLE_MSG)

    # Rassembler les données de la série
    question_ids = exam.question_ids or []
    answers = exam.answers or {}
    wrong: List[Dict[str, Any]] = []
    correct_categories: List[str] = []
    wrong_categories: Dict[str, int] = {}

    for qid in question_ids:
        q = db.query(QuestionDB).filter(QuestionDB.id == qid).first()
        if not q:
            continue
        selected = answers.get(qid)
        correct_id, correct_text = _correct_option(q)
        is_correct = bool(selected and selected == correct_id)
        if is_correct:
            if q.category:
                correct_categories.append(q.category)
        else:
            wrong.append({
                "text": q.text,
                "category": q.category or "Général",
                "reponse_donnee": _option_text(q, selected) or "(non répondu)",
                "bonne_reponse": correct_text,
                "explication": q.explanation or "",
            })
            if q.category:
                wrong_categories[q.category] = wrong_categories.get(q.category, 0) + 1

    # Cours réels du site pour les catégories à retravailler
    courses = db.query(CourseDB).all()
    courses_txt = "\n".join(
        f"- id={c.id} | titre=\"{c.title}\"" + (f" | catégorie={c.category}" if c.category else "")
        for c in courses
    ) or "(aucun cours disponible)"

    total = len(question_ids) or 0
    score = exam.score if exam.score is not None else (
        round(100 * (total - len(wrong)) / total) if total else 0
    )

    wrong_txt = "\n\n".join(
        f"{i+1}. [{w['category']}] {w['text']}\n"
        f"   Réponse de l'élève : {w['reponse_donnee']}\n"
        f"   Bonne réponse : {w['bonne_reponse']}\n"
        f"   Explication officielle : {w['explication'] or '—'}"
        for i, w in enumerate(wrong)
    ) or "Aucune erreur sur cette série."

    user_content = (
        f"Score de la série : {score}% ({total - len(wrong)}/{total} bonnes réponses).\n"
        f"Catégories réussies : {', '.join(sorted(set(correct_categories))) or '—'}.\n"
        f"Répartition des erreurs par catégorie : "
        f"{', '.join(f'{k} ({v})' for k, v in wrong_categories.items()) or 'aucune'}.\n\n"
        f"Erreurs de la série :\n{wrong_txt}\n\n"
        f"Cours disponibles sur le site (pour cours_recommande, réutilise EXACTEMENT "
        f"un titre ci-dessous, ou null si aucun ne correspond) :\n{courses_txt}\n\n"
    )
    if encouragement["has_history"]:
        user_content += (
            f"Progression de l'élève : {encouragement['previous_pct']}% la semaine dernière, "
            f"{encouragement['current_pct']}% cette semaine. Reprends ces chiffres dans message_prof "
            f"pour l'encourager.\n\n"
        )
    user_content += (
        "Rédige un bilan : notions_maitrisees (d'après les réussites), "
        "notions_a_retravailler (avec un conseil et un cours du site quand pertinent), "
        "mini_cours (UN objet par erreur ci-dessus, avec une explication BIEN CLAIRE de la faute), "
        "et message_prof (2-3 phrases motivantes)."
    )

    try:
        report = call_structured(
            system=PROF_SYSTEM_PROMPT,
            user_content=user_content,
            schema=SERIES_REPORT_SCHEMA,
            max_tokens=8000,
        )
    except AICoachUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"{AI_UNAVAILABLE_MSG} [{str(exc)[:300]}]")

    try:
        db.add(SeriesReportDB(
            user_id=exam.user_id,
            session_id=session_id,
            report_json=json.dumps(report, ensure_ascii=False),
        ))
        db.commit()
    except Exception:
        db.rollback()

    return {"report": report, "encouragement": encouragement, "cached": False}
