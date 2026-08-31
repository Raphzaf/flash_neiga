"""
Tests de la mémoire partagée du prof IA (`ai_cache` + routes du coach).

Ce que l'on vérifie, dans l'ordre des promesses faites au produit :

1. Deux élèves qui se trompent sur la même question ne coûtent qu'UN appel,
   qu'ils soient là à la même seconde ou à un an d'écart.
2. Une reformulation (accents, casse, ponctuation) tombe sur la même entrée.
3. Rien de personnel n'entre jamais dans un cache partagé.
4. Le prof reste utile même quand le modèle est totalement injoignable.

Aucun appel réseau : la couche modèle est remplacée par des doubles.
"""
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import ai_cache  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import AIAnswerCacheDB, QuestionDB, UserDB, User  # noqa: E402
from auth import (  # noqa: E402
    get_current_user, get_current_user_optional, require_admin, require_subscription,
)
import routes.ai_coach as ai_coach  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_ai_cache.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ELEVE_A = User(id="eleve-a", email="a@test.fr")
ELEVE_B = User(id="eleve-b", email="b@test.fr")

client = TestClient(app)

# Utilisateur courant, changé en cours de test pour simuler un second élève.
_current = {"user": ELEVE_A}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_current_user():
    return _current["user"]


FAKE_LESSON = {
    "explication": "Le panneau impose de céder le passage.",
    "regle": "En Israël, un triangle pointe en bas signifie « cédez le passage ».",
    "erreurs_a_eviter": ["Confondre avec le stop"],
}


def _opts():
    return [
        {"id": "a", "text": "Céder le passage", "is_correct": True},
        {"id": "b", "text": "Passer en premier", "is_correct": False},
    ]


@pytest.fixture(scope="function")
def db(monkeypatch):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_current_user_optional] = override_current_user
    app.dependency_overrides[require_subscription] = override_current_user
    app.dependency_overrides[require_admin] = override_current_user
    _current["user"] = ELEVE_A

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="eleve-a", email="a@test.fr", hashed_password="x"))
    session.add(UserDB(id="eleve-b", email="b@test.fr", hashed_password="x"))
    session.add(QuestionDB(
        id="q1", text="Que signifie ce panneau triangulaire ?", category="Panneaux",
        options=_opts(), explanation="Le triangle pointe en bas : cédez le passage.",
    ))
    session.commit()

    monkeypatch.setattr(ai_coach, "ai_configured", lambda: True)

    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


# ===== Normalisation et clés =====
@pytest.mark.parametrize("a, b", [
    ("C'est quoi la distance de sécurité ?", "cest quoi la distance de securite"),
    ("  DISTANCE   d'arrêt  ", "distance darret"),
    ("Priorité à droite !!!", "priorite a droite"),
])
def test_normalisation_rapproche_les_reformulations(a, b):
    assert ai_cache.normalize_text(a) == ai_cache.normalize_text(b)


def test_normalisation_distingue_les_sens_differents():
    assert ai_cache.normalize_text("distance de sécurité") != ai_cache.normalize_text("distance d'arrêt")


def test_cle_sans_collision_entre_composants():
    """('ab','c') et ('a','bc') ne doivent pas produire la même clé."""
    assert ai_cache.make_key("lesson", ["ab", "c"]) != ai_cache.make_key("lesson", ["a", "bc"])


def test_cle_change_avec_la_version_de_prompt():
    """Changer les consignes pédagogiques périme le contenu déjà produit."""
    assert ai_cache.make_key("chat", ["x"], version="v1") != ai_cache.make_key("chat", ["x"], version="v2")


def test_cle_stable_dans_le_temps():
    """Même demande, même clé : c'est ce qui permet la réutilisation à un an."""
    assert ai_cache.make_key("chat", ["Quelle est la vitesse en ville ?"]) == \
           ai_cache.make_key("chat", ["quelle est la vitesse en ville"])


# ===== Confidentialité =====
@pytest.mark.parametrize("question", [
    "Je m'appelle David, est-ce que je suis prêt ?",
    "Mon numéro est le 054 123 4567, rappelez-moi",
    "Mon email est eleve@exemple.fr",
    "ok",  # trop court pour être discriminant
    "x" * 500,  # trop long : demande unique, pas un cas général
])
def test_questions_personnelles_jamais_mises_en_cache(question):
    assert ai_cache.is_cacheable_question(question) is False


@pytest.mark.parametrize("question", [
    "Quelle est la vitesse maximale en ville ?",
    "C'est quoi la distance de sécurité sur autoroute ?",
])
def test_questions_generiques_mises_en_cache(question):
    assert ai_cache.is_cacheable_question(question) is True


# ===== Lecture / écriture =====
def test_store_puis_lookup_et_comptage_des_reutilisations(db):
    key = ai_cache.make_key("chat", ["une question"])
    ai_cache.store(db, key, "chat", {"reply": "une réponse"}, prompt_preview="une question")

    assert ai_cache.lookup(db, key) == {"reply": "une réponse"}
    assert ai_cache.lookup(db, key) == {"reply": "une réponse"}

    entry = db.query(AIAnswerCacheDB).filter(AIAnswerCacheDB.cache_key == key).first()
    assert entry.hit_count == 2  # deux appels API économisés


def test_lookup_absent_renvoie_none(db):
    assert ai_cache.lookup(db, ai_cache.make_key("chat", ["jamais posée"])) is None


def test_entree_corrompue_est_purgee_au_lieu_de_planter(db):
    key = "0" * 64
    db.add(AIAnswerCacheDB(cache_key=key, kind="chat", payload_json="{ceci n'est pas du json"))
    db.commit()

    assert ai_cache.lookup(db, key) is None
    assert db.query(AIAnswerCacheDB).filter(AIAnswerCacheDB.cache_key == key).first() is None


def test_double_ecriture_concurrente_ne_leve_pas(db):
    key = ai_cache.make_key("chat", ["doublon"])
    ai_cache.store(db, key, "chat", {"reply": "1"})
    ai_cache.store(db, key, "chat", {"reply": "2"})  # viole l'unicité : absorbé
    assert ai_cache.lookup(db, key) == {"reply": "1"}


def test_invalidation_par_sujet(db):
    for i in range(3):
        ai_cache.store(db, ai_cache.make_key("lesson", ["q1", str(i)]), "lesson",
                       {"explication": str(i)}, subject_id="q1")
    ai_cache.store(db, ai_cache.make_key("lesson", ["q2", "a"]), "lesson",
                   {"explication": "autre"}, subject_id="q2")

    assert ai_cache.invalidate_subject(db, "q1") == 3
    assert db.query(AIAnswerCacheDB).count() == 1


# ===== La promesse produit : un appel payé, réutilisé indéfiniment =====
def test_deux_eleves_une_seule_generation(db, monkeypatch):
    """L'élève B, arrivé après, reçoit la leçon de l'élève A sans appel IA."""
    calls = {"n": 0}

    def fake_call(**kwargs):
        calls["n"] += 1
        return dict(FAKE_LESSON)

    monkeypatch.setattr(ai_coach, "call_structured", fake_call)

    body = {"question_id": "q1", "selected_option_id": "b"}

    r1 = client.post("/api/ai-coach/lesson", json=body)
    assert r1.status_code == 200
    assert r1.json()["source"] == "ai"
    assert r1.json()["explication"] == FAKE_LESSON["explication"]

    _current["user"] = ELEVE_B  # un autre élève, plus tard
    r2 = client.post("/api/ai-coach/lesson", json=body)
    assert r2.status_code == 200
    assert r2.json()["source"] == "cache"
    assert r2.json()["explication"] == FAKE_LESSON["explication"]

    assert calls["n"] == 1  # un seul appel facturé pour les deux élèves


def test_lecon_resservie_meme_si_le_modele_est_tombe_entre_temps(db, monkeypatch):
    """« Une semaine, un mois, un an après » : le cache ne dépend pas de l'IA."""
    monkeypatch.setattr(ai_coach, "call_structured", lambda **kw: dict(FAKE_LESSON))
    body = {"question_id": "q1", "selected_option_id": "b"}
    assert client.post("/api/ai-coach/lesson", json=body).json()["source"] == "ai"

    # Plus tard : le fournisseur n'est même plus configuré.
    monkeypatch.setattr(ai_coach, "ai_configured", lambda: False)
    _current["user"] = ELEVE_B
    r = client.post("/api/ai-coach/lesson", json=body)
    assert r.status_code == 200
    assert r.json()["source"] == "cache"
    assert r.json()["explication"] == FAKE_LESSON["explication"]


def test_peek_ne_genere_jamais_et_signale_l_absence(db, monkeypatch):
    def refuse(**kwargs):
        raise AssertionError("/lesson/peek ne doit jamais appeler le modèle")

    monkeypatch.setattr(ai_coach, "call_structured", refuse)
    body = {"question_id": "q1", "selected_option_id": "b"}

    r = client.post("/api/ai-coach/lesson/peek", json=body)
    assert r.status_code == 200
    assert r.json() == {"available": False}

    # Une fois la leçon produite, le peek la sert (c'est le préchargement du front).
    monkeypatch.setattr(ai_coach, "call_structured", lambda **kw: dict(FAKE_LESSON))
    client.post("/api/ai-coach/lesson", json=body)

    monkeypatch.setattr(ai_coach, "call_structured", refuse)
    r = client.post("/api/ai-coach/lesson/peek", json=body)
    assert r.json()["available"] is True
    assert r.json()["lesson"]["explication"] == FAKE_LESSON["explication"]


def test_lecon_invalidee_quand_l_enonce_change(db, monkeypatch):
    """Corriger une question ne doit pas laisser resservir l'ancienne leçon."""
    calls = {"n": 0}

    def fake_call(**kwargs):
        calls["n"] += 1
        return {**FAKE_LESSON, "explication": f"version {calls['n']}"}

    monkeypatch.setattr(ai_coach, "call_structured", fake_call)
    body = {"question_id": "q1", "selected_option_id": "b"}

    assert client.post("/api/ai-coach/lesson", json=body).json()["explication"] == "version 1"

    question = db.query(QuestionDB).filter(QuestionDB.id == "q1").first()
    question.text = "Énoncé corrigé : que signifie ce panneau ?"
    db.commit()
    # L'ancienne table `ai_lessons` ignore l'énoncé : on la purge comme le ferait
    # l'admin via /cache/invalidate.
    client.post("/api/ai-coach/cache/invalidate", json={"question_id": "q1"})

    assert client.post("/api/ai-coach/lesson", json=body).json()["explication"] == "version 2"


# ===== Rafale : un seul appel pour N élèves simultanés =====
def test_single_flight_un_seul_appel_en_rafale(db, monkeypatch):
    calls = {"n": 0}
    lock = threading.Lock()

    def slow_call(**kwargs):
        with lock:
            calls["n"] += 1
        time.sleep(0.15)  # le temps que les autres threads arrivent au verrou
        return dict(FAKE_LESSON)

    monkeypatch.setattr(ai_coach, "call_structured", slow_call)

    question = db.query(QuestionDB).filter(QuestionDB.id == "q1").first()
    results = []
    errors = []

    def worker():
        session = TestingSessionLocal()
        try:
            results.append(ai_coach.get_or_create_lesson(session, question, "b"))
        except Exception as exc:  # pragma: no cover - remonté par l'assertion
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors
    assert len(results) == 8
    assert all(r["explication"] == FAKE_LESSON["explication"] for r in results)
    assert calls["n"] == 1  # huit élèves, un seul appel payé


# ===== Chat =====
def test_question_libre_identique_servie_depuis_le_cache(db, monkeypatch):
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return "En ville, la vitesse est limitée à 50 km/h."

    monkeypatch.setattr(ai_coach, "call_chat", fake_chat)

    r1 = client.post("/api/ai-coach/chat", json={
        "messages": [{"role": "user", "content": "Quelle est la vitesse maximale en ville ?"}],
    })
    assert r1.status_code == 200
    assert r1.json()["source"] == "ai"

    # Un autre élève, une reformulation : même entrée de cache.
    _current["user"] = ELEVE_B
    r2 = client.post("/api/ai-coach/chat", json={
        "messages": [{"role": "user", "content": "quelle est la vitesse maximale en ville"}],
    })
    assert r2.status_code == 200
    assert r2.json()["source"] == "cache"
    assert r2.json()["reply"] == r1.json()["reply"]

    assert calls["n"] == 1


def test_conversation_en_cours_jamais_mise_en_cache(db, monkeypatch):
    """Une réponse qui dépend de l'historique est propre à un élève."""
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return f"réponse {calls['n']}"

    monkeypatch.setattr(ai_coach, "call_chat", fake_chat)

    history = [
        {"role": "user", "content": "Quelle est la vitesse maximale en ville ?"},
        {"role": "assistant", "content": "50 km/h."},
        {"role": "user", "content": "Et sur autoroute alors ?"},
    ]
    client.post("/api/ai-coach/chat", json={"messages": history})
    client.post("/api/ai-coach/chat", json={"messages": history})

    assert calls["n"] == 2  # deux appels : rien n'a été partagé
    assert db.query(AIAnswerCacheDB).filter(AIAnswerCacheDB.kind == "chat").count() == 0


def test_question_personnelle_jamais_mise_en_cache_par_la_route(db, monkeypatch):
    monkeypatch.setattr(ai_coach, "call_chat", lambda **kw: "Bonjour David !")
    client.post("/api/ai-coach/chat", json={
        "messages": [{"role": "user", "content": "Je m'appelle David, mon examen est demain, un conseil ?"}],
    })
    assert db.query(AIAnswerCacheDB).filter(AIAnswerCacheDB.kind == "chat").count() == 0


# ===== Statistiques =====
def test_statistiques_du_cache(db, monkeypatch):
    monkeypatch.setattr(ai_coach, "call_structured", lambda **kw: dict(FAKE_LESSON))
    body = {"question_id": "q1", "selected_option_id": "b"}
    client.post("/api/ai-coach/lesson", json=body)
    client.post("/api/ai-coach/lesson", json=body)
    client.post("/api/ai-coach/lesson", json=body)

    stats = client.get("/api/ai-coach/cache-stats").json()
    assert stats["available"] is True
    assert stats["entries"] == 1
    assert stats["api_calls_saved"] == 2  # 3 demandes, 1 seule payée
    assert stats["by_kind"]["lesson"]["entries"] == 1


def test_single_flight_libere_les_verrous(db):
    """La table de verrous ne doit pas grossir : sinon fuite mémoire lente."""
    for i in range(50):
        with ai_cache.single_flight(f"cle-{i}"):
            pass
    assert ai_cache._locks == {}
    assert ai_cache._lock_waiters == {}


def test_single_flight_ne_bloque_pas_indefiniment(monkeypatch):
    """Un producteur bloqué ne doit jamais immobiliser les autres requêtes."""
    monkeypatch.setattr(ai_cache, "LOCK_WAIT_SECONDS", 0.05)
    key = "cle-bloquee"
    holder_in = threading.Event()
    release = threading.Event()

    def holder():
        with ai_cache.single_flight(key):
            holder_in.set()
            release.wait(timeout=5)

    t = threading.Thread(target=holder)
    t.start()
    assert holder_in.wait(timeout=5)

    started = time.monotonic()
    with ai_cache.single_flight(key):  # ne doit pas attendre le premier thread
        pass
    waited = time.monotonic() - started

    release.set()
    t.join(timeout=5)
    assert waited < 2.0


def test_reponse_de_chat_vide_en_cache_traitee_comme_absente(db, monkeypatch):
    """Une entrée sans texte utile ne doit jamais donner une bulle vide à l'élève."""
    calls = {"n": 0}

    def fake_chat(**kwargs):
        calls["n"] += 1
        return "En ville : 50 km/h."

    monkeypatch.setattr(ai_coach, "call_chat", fake_chat)
    question = "Quelle est la vitesse maximale en ville ?"

    # On empoisonne le cache avec une entrée vide.
    ai_cache.store(db, ai_cache.make_key("chat", [question, ""]), "chat", {"reply": "   "})

    r = client.post("/api/ai-coach/chat", json={"messages": [{"role": "user", "content": question}]})
    assert r.status_code == 200
    assert r.json()["reply"] == "En ville : 50 km/h."
    assert calls["n"] == 1  # on a bien régénéré plutôt que servir du vide
