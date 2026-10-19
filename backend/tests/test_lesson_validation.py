"""
Contrat des explications d'erreur : texte propre, complet, d'une longueur
raisonnable — sinon relance (AITransientError) plutôt qu'un affichage bancal.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_client import AITransientError  # noqa: E402
from models import QuestionDB  # noqa: E402
from routes.ai_coach import clean_explanation, lesson_problem, validate_lesson  # noqa: E402

GOOD = ("En règle générale, à une intersection sans signalisation particulière, la priorité "
        "est à droite. Tu dois donc céder le passage au véhicule qui arrive de ta droite. "
        "Le véhicule venant de gauche doit, lui, te céder le passage.")


def test_valid_explanation_is_kept_word_for_word():
    lesson = validate_lesson({"explication": GOOD, "donnees_suffisantes": True})
    assert lesson == {"explication": GOOD, "donnees_suffisantes": True, "format": 2}


def test_markdown_and_preamble_are_removed_without_losing_words():
    raw = "**Explication :** La priorité est à *droite*.\n\n- Cède le passage à droite.\n- Retiens-le."
    assert clean_explanation(raw) == "La priorité est à droite. Cède le passage à droite. Retiens-le."
    fenced = "```\nLa priorité est à droite.\n```"
    assert clean_explanation(fenced) == "La priorité est à droite."


@pytest.mark.parametrize("raw", [
    None, "texte", [], {"autre": GOOD},
    {"explication": ""},
    {"explication": "Trop court."},
    {"explication": GOOD[:-1] + " et le véhicule"},       # tronquée
    {"explication": " ".join([GOOD] * 6)},                 # bien trop longue
])
def test_malformed_answers_are_rejected(raw):
    with pytest.raises(AITransientError):
        validate_lesson(raw)


def test_insufficient_data_verdict_is_accepted_when_short():
    lesson = validate_lesson({"explication": "La correction contredit l'énoncé.",
                              "donnees_suffisantes": False})
    assert lesson["donnees_suffisantes"] is False


def test_lesson_problem_detects_inconsistent_corrections():
    def q(options, text="Énoncé"):
        return QuestionDB(id="x", text=text, options=options)
    assert lesson_problem(q([{"id": "a", "text": "A", "is_correct": False}]), "a")
    assert lesson_problem(q([{"id": "a", "text": "A", "is_correct": True},
                             {"id": "b", "text": "B", "is_correct": True}]), "a")
    assert lesson_problem(q([{"id": "a", "text": "A", "is_correct": True},
                             {"id": "b", "text": "B", "is_correct": False}], text=" "), "b")
    assert lesson_problem(q([{"id": "a", "text": "A", "is_correct": True},
                             {"id": "b", "text": "B", "is_correct": False}]), "b") is None
