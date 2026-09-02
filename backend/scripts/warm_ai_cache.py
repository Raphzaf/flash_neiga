#!/usr/bin/env python3
"""
Préchargement des explications du prof IA — « une fois pour toutes ».

Génère la mini-leçon de CHAQUE couple (question, mauvaise réponse) du corpus et
l'écrit dans le cache partagé. Une fois ce script passé, plus aucun élève
n'attend : toutes les explications sont déjà en base, servies instantanément et
sans appel facturé.

Le script est fait pour être relancé sans risque : il saute tout ce qui est déjà
en cache. Interrompu (Ctrl-C, coupure, redéploiement), il reprend où il en était.

Utilisation
-----------
    # Ce qui serait généré, sans rien appeler ni dépenser :
    python backend/scripts/warm_ai_cache.py --dry-run

    # Préchargement complet (compter environ 1 h avec 4 tâches parallèles) :
    python backend/scripts/warm_ai_cache.py

    # Se limiter à une catégorie, ou à un lot d'essai :
    python backend/scripts/warm_ai_cache.py --category "Panneaux" --limit 20

Options utiles
--------------
    --workers N      tâches en parallèle (défaut 4 ; monter avec prudence : le
                     fournisseur renvoie des 429 s'il est bousculé)
    --delay S        pause entre deux appels d'une même tâche (défaut 0.5 s)
    --limit N        s'arrêter après N leçons produites (essai de coût)
    --category NOM   ne traiter qu'une catégorie
    --retry-failed   retenter les couples ayant échoué lors d'un passage précédent
"""
from __future__ import annotations

import argparse
import logging
import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Le script s'exécute aussi bien depuis la racine du dépôt que depuis backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models import QuestionDB  # noqa: E402
import ai_cache  # noqa: E402
from ai_client import AICoachUnavailable, ai_configured, diagnostics  # noqa: E402
from routes.ai_coach import (  # noqa: E402
    _generate_lesson, _lesson_cache_key, _legacy_lesson, _model_tags, _store_legacy_lesson,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("warm")
# Les relances internes du client IA sont déjà résumées par nos propres lignes.
logging.getLogger("ai_client").setLevel(logging.ERROR)


@dataclass
class Pair:
    """Un couple (question, mauvaise réponse) à expliquer."""
    question_id: str
    option_id: str
    category: str


@dataclass
class Progress:
    """Compteurs partagés entre les tâches."""
    done: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0
    started_at: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def bump(self, field_name: str) -> None:
        with self.lock:
            setattr(self, field_name, getattr(self, field_name) + 1)

    def summary(self) -> str:
        with self.lock:
            treated = self.done + self.skipped + self.failed
            elapsed = time.monotonic() - self.started_at
            rate = self.done / elapsed if elapsed > 0 and self.done else 0
            remaining = self.total - treated
            eta = remaining / rate if rate > 0 else 0
            eta_txt = f" — fin estimée dans {eta / 60:.0f} min" if rate > 0 and remaining else ""
            return (
                f"{treated}/{self.total} traités — "
                f"{self.done} générées, {self.skipped} déjà en cache, {self.failed} en échec{eta_txt}"
            )


_stop = threading.Event()


def _handle_interrupt(signum, frame):  # pragma: no cover - dépend du terminal
    if not _stop.is_set():
        logger.warning("Interruption demandée — les tâches en cours se terminent, "
                       "relance le script pour reprendre.")
        _stop.set()


def collect_pairs(category: Optional[str] = None) -> List[Pair]:
    """Tous les couples (question, mauvaise réponse) du corpus.

    Une question sans bonne réponse identifiée est ignorée : on ne saurait pas
    expliquer l'erreur, et le prof produirait n'importe quoi.
    """
    session = SessionLocal()
    try:
        query = session.query(QuestionDB)
        if category:
            query = query.filter(QuestionDB.category == category)

        pairs: List[Pair] = []
        for question in query.all():
            options = question.options or []
            if not any(opt.get("is_correct") for opt in options):
                logger.debug("Question %s sans bonne réponse — ignorée.", question.id)
                continue
            for opt in options:
                if opt.get("is_correct") or not opt.get("id"):
                    continue
                pairs.append(Pair(question.id, opt["id"], question.category or "Général"))
        return pairs
    finally:
        session.close()


def already_cached(session, question: QuestionDB, option_id: str) -> bool:
    """La leçon existe-t-elle déjà ? (sans compter de réutilisation)"""
    key = _lesson_cache_key(question, option_id)
    if ai_cache.lookup(session, key, count_hit=False) is not None:
        return True
    return _legacy_lesson(session, question.id, option_id) is not None


def warm_one(session, pair: Pair, progress: Progress, delay: float) -> None:
    """Produit et mémorise une leçon. Ne lève jamais : un échec isolé ne doit
    pas interrompre un préchargement de plusieurs heures."""
    question = session.query(QuestionDB).filter(QuestionDB.id == pair.question_id).first()
    if question is None:
        progress.bump("skipped")
        return

    if already_cached(session, question, pair.option_id):
        progress.bump("skipped")
        return

    try:
        lesson = _generate_lesson(question, pair.option_id)
    except AICoachUnavailable as exc:
        progress.bump("failed")
        logger.warning("Échec %s/%s : %s", pair.question_id[:8], pair.option_id, str(exc)[:160])
        # Le disjoncteur du client IA vient peut-être de s'ouvrir : on souffle
        # un peu plutôt que de marteler un service déjà en difficulté.
        _stop.wait(timeout=2.0)
        return
    except Exception as exc:  # pragma: no cover - filet de sécurité
        progress.bump("failed")
        logger.warning("Erreur inattendue %s/%s : %s", pair.question_id[:8], pair.option_id, exc)
        return

    ai_cache.store(
        session,
        _lesson_cache_key(question, pair.option_id),
        "lesson",
        lesson,
        subject_id=question.id,
        prompt_preview=f"[{pair.category}] {question.text}",
        **_model_tags(),
    )
    _store_legacy_lesson(session, question.id, pair.option_id, lesson)
    progress.bump("done")

    # Espacer les appels : c'est ce qui évite les 429 sur un long préchargement.
    if delay > 0:
        _stop.wait(timeout=delay)


def worker(tasks: "queue.Queue[Pair]", progress: Progress, delay: float, limit: Optional[int]) -> None:
    """Chaque tâche a SA session : une session SQLAlchemy n'est pas partageable
    entre threads."""
    session = SessionLocal()
    try:
        while not _stop.is_set():
            try:
                pair = tasks.get_nowait()
            except queue.Empty:
                return
            try:
                if limit is not None and progress.done >= limit:
                    _stop.set()
                    return
                warm_one(session, pair, progress, delay)
            finally:
                tasks.task_done()
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Précharge toutes les explications du prof IA dans le cache partagé.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Compter ce qui serait généré, sans appeler le modèle.")
    parser.add_argument("--workers", type=int, default=4, help="Tâches en parallèle (défaut : 4).")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Pause entre deux appels d'une même tâche, en secondes (défaut : 0.5).")
    parser.add_argument("--limit", type=int, default=None,
                        help="S'arrêter après N leçons générées (utile pour estimer le coût).")
    parser.add_argument("--category", default=None, help="Ne traiter qu'une catégorie.")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    logger.info("Inventaire des questions…")
    pairs = collect_pairs(args.category)
    if not pairs:
        logger.error("Aucun couple (question, mauvaise réponse) trouvé. "
                     "La base de questions est-elle chargée ?")
        return 1

    # État actuel du cache : combien reste-t-il vraiment à produire ?
    session = SessionLocal()
    try:
        questions = {
            q.id: q for q in session.query(QuestionDB).filter(
                QuestionDB.id.in_({p.question_id for p in pairs})
            ).all()
        }
        todo = [
            p for p in pairs
            if p.question_id in questions and not already_cached(session, questions[p.question_id], p.option_id)
        ]
    finally:
        session.close()

    logger.info("%s explications au total, %s déjà en cache, %s à produire.",
                len(pairs), len(pairs) - len(todo), len(todo))

    if args.dry_run:
        by_category: dict = {}
        for p in todo:
            by_category[p.category] = by_category.get(p.category, 0) + 1
        for category, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
            logger.info("  %-40s %s à produire", category[:40], count)
        logger.info("Simulation : aucun appel n'a été fait, rien n'a été facturé.")
        return 0

    if not todo:
        logger.info("Tout est déjà en cache — rien à faire.")
        return 0

    if not ai_configured():
        info = diagnostics()
        logger.error("Coach IA non configuré (%s) — impossible de précharger.", info.get("reason"))
        return 1

    if args.limit is not None:
        logger.info("Limite demandée : %s leçons.", args.limit)

    tasks: "queue.Queue[Pair]" = queue.Queue()
    for pair in todo:
        tasks.put(pair)

    progress = Progress(total=len(todo))
    logger.info("Démarrage avec %s tâche(s) en parallèle. Ctrl-C pour arrêter proprement.",
                args.workers)

    threads = [
        threading.Thread(target=worker, args=(tasks, progress, args.delay, args.limit), daemon=True)
        for _ in range(max(1, args.workers))
    ]
    for t in threads:
        t.start()

    # Point d'avancement régulier : un préchargement dure longtemps, il faut
    # pouvoir vérifier d'un coup d'œil que ça avance.
    while any(t.is_alive() for t in threads):
        _stop.wait(timeout=30)
        logger.info("… %s", progress.summary())

    for t in threads:
        t.join(timeout=30)

    logger.info("Terminé — %s", progress.summary())
    if progress.failed:
        logger.warning("%s échec(s) : relance le script, il ne retraitera que ce qui manque.",
                       progress.failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
