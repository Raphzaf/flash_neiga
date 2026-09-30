"""
Cours fournis avec le site (course_seed.py) : chargés une seule fois, et
jamais recréés après une suppression ou une modification dans le CMS.
"""
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import course_seed  # noqa: E402
from database import Base  # noqa: E402
from models import CourseDB  # noqa: E402

engine = create_engine("sqlite:///./test_course_seed.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

FRONT_PUBLIC = backend_path.parent / "frontend" / "public"


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _bundled():
    path = course_seed.DATA_DIR / course_seed.BUNDLED_COURSES[0][0]
    return json.loads(path.read_text(encoding="utf-8"))


def test_bundled_courses_are_loaded(db):
    courses = _bundled()
    assert course_seed.seed_bundled_courses(db) == len(courses)
    titles = [c.title for c in db.query(CourseDB).order_by(CourseDB.order)]
    assert titles == [c["title"] for c in courses]


def test_seeding_runs_only_once(db):
    course_seed.seed_bundled_courses(db)
    assert course_seed.seed_bundled_courses(db) == 0
    assert db.query(CourseDB).count() == len(_bundled())


def test_deleted_course_is_not_recreated(db):
    course_seed.seed_bundled_courses(db)
    first = db.query(CourseDB).order_by(CourseDB.order).first()
    db.delete(first)
    db.commit()
    course_seed.seed_bundled_courses(db)
    assert db.query(CourseDB).filter(CourseDB.title == first.title).count() == 0


def test_existing_course_with_same_title_is_kept(db):
    title = _bundled()[0]["title"]
    db.add(CourseDB(title=title, content="<p>Version de l'auto-école</p>"))
    db.commit()
    course_seed.seed_bundled_courses(db)
    same = db.query(CourseDB).filter(CourseDB.title == title).all()
    assert len(same) == 1 and same[0].content == "<p>Version de l'auto-école</p>"


def test_every_course_image_is_shipped():
    """Chaque image citée par un cours existe dans le front."""
    import re

    for course in _bundled():
        urls = set(re.findall(r'src="(/course-media/[^"]+)"', course["content"]))
        if course.get("image_url"):
            urls.add(course["image_url"])
        for url in urls:
            assert (FRONT_PUBLIC / url.lstrip("/")).exists(), url
