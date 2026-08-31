"""
Coach IA — « prof de code 24h/24 » (Flash Neiga).

Regroupe les endpoints qui appellent Claude :
- POST /api/ai-coach/lesson         → mini-leçon sur une réponse fausse (Phase 2)
- POST /api/ai-coach/series-report  → bilan de série + encouragement chiffré (Phase 3)

Tout contenu produit est mémorisé en base et resservi à l'identique : une
explication générée aujourd'hui pour un élève sert à tous ceux qui commettront
la même erreur ensuite, sans nouvel appel facturé (voir `ai_cache`).

Et quand le modèle est injoignable, l'élève reçoit tout de même son explication,
construite à partir de la correction officielle de la question : la rubrique ne
tombe jamais en panne.
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
        AIAnswerCacheDB,
    )
    from auth import get_current_user, require_admin, require_subscription
    from ai_client import call_structured, call_chat, ai_configured, AICoachUnavailable, diagnostics
    import ai_cache
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import (
        QuestionDB, CourseDB, ExamSessionDB, AILessonDB, SeriesReportDB, User,
        AIAnswerCacheDB,
    )
    from backend.auth import get_current_user, require_admin, require_subscription
    from backend.ai_client import call_structured, call_chat, ai_configured, AICoachUnavailable, diagnostics
    from backend import ai_cache

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

CHAT_SYSTEM_PROMPT = (
    "Tu es le prof de code de la route israélien de l'élève, disponible 24h/24 "
    "sur le site Flash Neiga. Tu réponds en français, tu tutoies l'élève, avec "
    "des réponses claires, courtes et concrètes, toujours exactes vis-à-vis du "
    "code de la route et de la conduite en Israël. Utilise des exemples et, si "
    "utile, des listes à puces. Si la question n'a rien à voir avec la conduite, "
    "le code de la route israélien ou la préparation à l'examen, recentre "
    "gentiment l'élève sur ces sujets. Ne donne jamais de conseils dangereux ou "
    "illégaux. Ne mentionne jamais que tu es une IA."
)

MAX_CHAT_HISTORY = 20  # nombre de messages récents conservés par tour

# Une mini-leçon tient très largement dans ce budget. L'ancienne valeur (8192)
# datait d'une époque où le prof pouvait renvoyer un schéma SVG ; le prompt
# l'interdit désormais. Un plafond serré, c'est une réponse plus rapide — et,
# chez les fournisseurs qui facturent le quota d'avance, moins de 429.
LESSON_MAX_TOKENS = 1200
# Volontairement inchangé (2048) : une réponse coupée en plein milieu serait
# mémorisée puis resservie à tous les élèves suivants. Le gain de vitesse vient
# du cache, pas d'un plafond serré.
CHAT_MAX_TOKENS = 2048
SERIES_REPORT_MAX_TOKENS = 4000

# ===== Schémas structured outputs =====
LESSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "explication": {"type": "string"},
        "regle": {"type": "string"},
        "erreurs_a_eviter": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["explication", "regle", "erreurs_a_eviter"],
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


def _model_tags() -> Dict[str, Optional[str]]:
    """Fournisseur et modèle ayant produit un contenu — tracé dans le cache."""
    try:
        info = diagnostics()
        return {"provider": info.get("provider"), "model": info.get("model")}
    except Exception:  # pragma: no cover - le diagnostic ne doit jamais bloquer
        return {"provider": None, "model": None}


def _cached_reply(db: Session, cache_key: str) -> Optional[str]:
    """Réponse de chat mémorisée, ou None si absente ou inexploitable.

    Une entrée sans texte utile est traitée comme une absence : on préfère
    repayer un appel plutôt que renvoyer une bulle vide à l'élève.
    """
    cached = ai_cache.lookup(db, cache_key)
    if not isinstance(cached, dict):
        return None
    reply = cached.get("reply")
    return reply if isinstance(reply, str) and reply.strip() else None


def _lesson_cache_key(question: QuestionDB, selected_option_id: str) -> str:
    """Clé de la leçon partagée entre tous les élèves.

    L'énoncé et la correction entrent dans la clé : le jour où l'on corrige une
    question, sa leçon devient automatiquement caduque au lieu d'être resservie
    à tort — ce que la clé historique (question_id + option) ne savait pas faire.
    """
    _, correct_text = _correct_option(question)
    return ai_cache.make_key("lesson", [
        question.id,
        selected_option_id,
        question.text,
        correct_text,
        question.explanation,
    ])


def _legacy_lesson(db: Session, question_id: str, selected_option_id: str) -> Optional[Dict[str, Any]]:
    """Leçon issue de l'ancienne table `ai_lessons`.

    Conservée pour ne pas repayer la régénération de tout ce qui a déjà été
    produit en production avant la mise en place du cache partagé.
    """
    try:
        cached = (
            db.query(AILessonDB)
            .filter(
                AILessonDB.question_id == question_id,
                AILessonDB.selected_option_id == selected_option_id,
            )
            .first()
        )
        if cached:
            return json.loads(cached.lesson_json)
    except Exception as exc:
        logger.warning("Lecture de l'ancien cache de leçons impossible : %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    return None


def _store_legacy_lesson(db: Session, question_id: str, selected_option_id: str, lesson: Dict[str, Any]) -> None:
    """Double écriture dans l'ancienne table, le temps que le parc bascule."""
    try:
        db.add(AILessonDB(
            question_id=question_id,
            selected_option_id=selected_option_id,
            lesson_json=json.dumps(lesson, ensure_ascii=False),
        ))
        db.commit()
    except Exception:
        db.rollback()  # course concurrente : une autre requête a écrit la même leçon


def _fallback_lesson(question: QuestionDB, selected_option_id: str) -> Optional[Dict[str, Any]]:
    """Explication de secours, construite sans IA à partir de la correction officielle.

    C'est ce qui permet à la rubrique de ne jamais tomber en panne : modèle
    injoignable, quota épuisé, coupure réseau — l'élève comprend quand même son
    erreur. Renvoie None si la question ne porte aucune matière exploitable,
    auquel cas mieux vaut un message d'indisponibilité honnête.
    """
    _, correct_text = _correct_option(question)
    chosen_text = _option_text(question, selected_option_id)
    explanation = (question.explanation or "").strip()

    if not explanation and not correct_text:
        return None

    phrases: List[str] = []
    if chosen_text:
        phrases.append(f"Tu as répondu « {chosen_text} », et ce n'était pas la bonne réponse.")
    if correct_text:
        phrases.append(f"La bonne réponse était « {correct_text} ».")
    if explanation:
        phrases.append(explanation)

    erreurs = []
    if chosen_text:
        erreurs.append(f"Ne plus choisir « {chosen_text} » sur ce type de question.")
    erreurs.append("Relire l'énoncé en entier avant de répondre : un seul mot peut changer la règle.")

    return {
        "explication": " ".join(phrases),
        "regle": explanation or (f"La réponse attendue est : {correct_text}." if correct_text else ""),
        "erreurs_a_eviter": erreurs,
        "cached": False,
        "source": "fallback",
        # Le front peut proposer « redemander au prof » plus tard : cette
        # explication est correcte mais plus sèche qu'une vraie leçon.
        "degraded": True,
    }


def _generate_lesson(question: QuestionDB, selected_option_id: str) -> Dict[str, Any]:
    """Appelle le modèle pour produire la mini-leçon. Lève AICoachUnavailable."""
    _, correct_text = _correct_option(question)
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
        "\nProduis une mini-leçon uniquement en texte : une explication claire, "
        "un rappel de la règle, et les erreurs à éviter. N'inclus aucune image, "
        "aucun schéma, aucun SVG."
    )

    return call_structured(
        system=PROF_SYSTEM_PROMPT,
        user_content=user_content,
        schema=LESSON_SCHEMA,
        max_tokens=LESSON_MAX_TOKENS,
    )


def lookup_lesson(db: Session, question: QuestionDB, selected_option_id: str) -> Optional[Dict[str, Any]]:
    """Leçon déjà mémorisée pour cette erreur, sans jamais appeler le modèle.

    Volontairement indépendante de l'état du fournisseur d'IA : une leçon écrite
    l'an dernier doit être resservie même si la clé API a expiré depuis.
    """
    key = _lesson_cache_key(question, selected_option_id)
    cached = ai_cache.lookup(db, key)
    if cached is None:
        cached = _legacy_lesson(db, question.id, selected_option_id)
    if cached is None:
        return None
    return {**cached, "cached": True, "source": "cache"}


def get_or_create_lesson(db: Session, question: QuestionDB, selected_option_id: str) -> Dict[str, Any]:
    """Mini-leçon sur une réponse fausse, servie depuis la mémoire partagée si possible.

    Ordre : cache partagé → ancien cache → production (un seul appel même en
    rafale). Lève `AICoachUnavailable` si le modèle ne répond pas ; c'est à
    l'appelant de servir `_fallback_lesson`.
    """
    key = _lesson_cache_key(question, selected_option_id)

    cached = lookup_lesson(db, question, selected_option_id)
    if cached is not None:
        return cached

    # Rafale sur la même question : un seul appel part, les autres attendent ici
    # puis relisent le résultat au lieu de le repayer.
    with ai_cache.single_flight(key):
        cached = lookup_lesson(db, question, selected_option_id)
        if cached is not None:
            return cached

        lesson = _generate_lesson(question, selected_option_id)

        ai_cache.store(
            db, key, "lesson", lesson,
            subject_id=question.id,
            prompt_preview=f"[{question.category or 'Général'}] {question.text}",
            **_model_tags(),
        )
        _store_legacy_lesson(db, question.id, selected_option_id, lesson)

    return {**lesson, "cached": False, "source": "ai"}


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
def ai_selftest(current_user: User = Depends(get_current_user)):
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


@router.get("/cache-coverage", dependencies=[Depends(require_admin)])
def cache_coverage(db: Session = Depends(get_db)):
    """Couverture du préchargement : combien d'erreurs possibles sont déjà expliquées.

    Répond à la question « reste-t-il des élèves qui attendront ? ». Le
    préchargement lui-même se lance avec `backend/scripts/warm_ai_cache.py` :
    plusieurs milliers d'appels ne tiennent pas dans une requête web, qu'un
    redéploiement interromprait.
    """
    questions = db.query(QuestionDB).all()

    expected: Dict[str, str] = {}   # clé de cache -> catégorie
    skipped_questions = 0
    for question in questions:
        options = question.options or []
        if not any(opt.get("is_correct") for opt in options):
            # Sans bonne réponse identifiée, aucune erreur n'est explicable.
            skipped_questions += 1
            continue
        for opt in options:
            if opt.get("is_correct") or not opt.get("id"):
                continue
            expected[_lesson_cache_key(question, opt["id"])] = question.category or "Général"

    cached_keys = {
        row[0] for row in
        db.query(AIAnswerCacheDB.cache_key).filter(AIAnswerCacheDB.kind == "lesson").all()
    }

    missing_by_category: Dict[str, int] = {}
    covered = 0
    for key, category in expected.items():
        if key in cached_keys:
            covered += 1
        else:
            missing_by_category[category] = missing_by_category.get(category, 0) + 1

    total = len(expected)
    return {
        "questions": len(questions),
        "questions_sans_bonne_reponse": skipped_questions,
        "explications_attendues": total,
        "explications_en_cache": covered,
        "explications_manquantes": total - covered,
        "couverture_pct": round(100 * covered / total) if total else 0,
        "manquantes_par_categorie": dict(
            sorted(missing_by_category.items(), key=lambda kv: -kv[1])[:20]
        ),
    }


@router.get("/cache-stats", dependencies=[Depends(require_admin)])
def cache_stats(db: Session = Depends(get_db)):
    """Rendement du cache : entrées mémorisées et appels API évités."""
    return ai_cache.stats(db)


@router.post("/cache/invalidate", dependencies=[Depends(require_admin)])
def cache_invalidate(payload: dict, db: Session = Depends(get_db)):
    """Oublie les réponses mémorisées d'une question (énoncé ou correction modifiés).

    Body : { "question_id": "..." }
    """
    question_id = str(payload.get("question_id") or "").strip()
    if not question_id:
        raise HTTPException(status_code=400, detail="question_id requis")

    removed = ai_cache.invalidate_subject(db, question_id)

    # L'ancienne table doit suivre, sinon elle resservirait la leçon périmée.
    try:
        removed += (
            db.query(AILessonDB)
            .filter(AILessonDB.question_id == question_id)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Purge de l'ancien cache impossible pour %s : %s", question_id, exc)

    return {"question_id": question_id, "removed": removed}


@router.post("/chat", dependencies=[Depends(require_subscription)])
def chat(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chatbot « prof 24h/24 » : conversation libre en français.

    Body : { messages: [{role: "user"|"assistant", content: str}], context?: str }
    Le backend est sans état : le front renvoie l'historique récent à chaque tour.
    """
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages requis")

    # Nettoyage + on ne garde que les derniers échanges
    history = [
        {"role": ("assistant" if m.get("role") == "assistant" else "user"),
         "content": str(m.get("content") or "").strip()}
        for m in messages if str(m.get("content") or "").strip()
    ][-MAX_CHAT_HISTORY:]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Le dernier message doit venir de l'élève.")

    context = str(payload.get("context") or "").strip()
    question = history[-1]["content"]

    # Une PREMIÈRE question, générique, est très souvent reposée à l'identique
    # par d'autres élèves : celle-là, on la mémorise. Dès qu'il y a un historique,
    # la réponse dépend de la conversation propre à l'élève et n'est plus
    # partageable ; une question personnelle ne l'est jamais non plus.
    cache_key = None
    if len(history) == 1 and ai_cache.is_cacheable_question(question):
        cache_key = ai_cache.make_key("chat", [question, context])
        cached_reply = _cached_reply(db, cache_key)
        if cached_reply is not None:
            return {"reply": cached_reply, "cached": True, "source": "cache"}

    if not ai_configured():
        raise HTTPException(status_code=503, detail=AI_UNAVAILABLE_MSG)

    system = CHAT_SYSTEM_PROMPT
    if context:
        system += f"\n\nContexte de l'élève (question en cours) : {context[:1500]}"

    def _ask() -> str:
        return call_chat(system=system, history=history, max_tokens=CHAT_MAX_TOKENS)

    try:
        if cache_key is None:
            reply = _ask()
        else:
            # Même question posée en rafale : un seul appel part.
            with ai_cache.single_flight(cache_key):
                cached_reply = _cached_reply(db, cache_key)
                if cached_reply is not None:
                    return {"reply": cached_reply, "cached": True, "source": "cache"}
                reply = _ask()
                ai_cache.store(
                    db, cache_key, "chat", {"reply": reply},
                    prompt_preview=question,
                    **_model_tags(),
                )
    except AICoachUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"{AI_UNAVAILABLE_MSG} [{str(exc)[:300]}]")

    return {"reply": reply, "cached": False, "source": "ai"}


@router.post("/lesson/peek", dependencies=[Depends(require_subscription)])
def peek_lesson(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renvoie la leçon UNIQUEMENT si elle est déjà mémorisée. N'appelle jamais l'IA.

    Le front interroge cette route dès que l'élève se trompe : si la leçon existe
    (cas le plus fréquent une fois le cache constitué), elle est affichée à
    l'instant où il clique, sans attente ni coût. Sinon on ne fait rien —
    précharger via /lesson paierait des leçons que personne ne lira.
    """
    question_id = payload.get("question_id")
    selected_option_id = payload.get("selected_option_id")
    if not question_id or not selected_option_id:
        raise HTTPException(status_code=400, detail="question_id et selected_option_id requis")

    question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question introuvable")

    lesson = lookup_lesson(db, question, selected_option_id)
    if lesson is None:
        return {"available": False}

    return {"available": True, "lesson": lesson}


@router.post("/lesson", dependencies=[Depends(require_subscription)])
def generate_lesson(
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

    # Le cache d'abord, toujours : c'est gratuit, instantané, et cela reste
    # valable même si le fournisseur d'IA est en panne ou plus configuré.
    cached = lookup_lesson(db, question, selected_option_id)
    if cached is not None:
        return cached

    reason: Optional[str] = None
    if ai_configured():
        try:
            # Sert le cache partagé si la leçon existe déjà (aucun appel IA),
            # sinon la produit une seule fois pour tous les élèves suivants.
            return get_or_create_lesson(db, question, selected_option_id)
        except AICoachUnavailable as exc:
            reason = str(exc)[:300]
            logger.warning("Leçon indisponible pour la question %s : %s", question_id, reason)
    else:
        reason = "coach IA non configuré"

    # Dernier rempart : l'élève doit toujours comprendre son erreur, même si le
    # modèle est injoignable. On lui rend la correction officielle mise en forme.
    fallback = _fallback_lesson(question, selected_option_id)
    if fallback is not None:
        return fallback

    raise HTTPException(status_code=503, detail=f"{AI_UNAVAILABLE_MSG} [{reason}]")


@router.post("/series-report", dependencies=[Depends(require_subscription)])
def series_report(
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

    # Une seule requête pour toute la série : la boucle faisait auparavant un
    # aller-retour SQL par question (30 requêtes pour un examen).
    questions_by_id = {}
    if question_ids:
        questions_by_id = {
            q.id: q
            for q in db.query(QuestionDB).filter(QuestionDB.id.in_(question_ids)).all()
        }

    for qid in question_ids:
        q = questions_by_id.get(qid)
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

    # Deux séries d'erreurs identiques donnent le même bilan : inutile de le
    # repayer. La clé porte sur le contenu pédagogique de la série, pas sur son
    # identifiant — c'est ce qui permet le partage entre élèves.
    report_key = ai_cache.make_key("series_report", [user_content])
    report = ai_cache.lookup(db, report_key)

    if report is None:
        try:
            report = call_structured(
                system=PROF_SYSTEM_PROMPT,
                user_content=user_content,
                schema=SERIES_REPORT_SCHEMA,
                max_tokens=SERIES_REPORT_MAX_TOKENS,
            )
        except AICoachUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"{AI_UNAVAILABLE_MSG} [{str(exc)[:300]}]")

        ai_cache.store(
            db, report_key, "series_report", report,
            prompt_preview=f"Série {score}% — {len(wrong)} erreur(s)",
            **_model_tags(),
        )

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
