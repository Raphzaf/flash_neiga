import json
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Local imports from backend
from backend.database import SessionLocal, engine, Base
from backend.models import TrafficSignDB


def ensure_tables():
    Base.metadata.create_all(bind=engine)


essential_fields = ["id", "nom", "image", "type"]


def map_record(rec: dict) -> TrafficSignDB:
    # Build stable unique "number"; prefix to avoid clashes with other sets
    number = f"IL-{rec.get('id')}"
    name = rec.get("nom") or ""
    category = rec.get("type") or ""
    image_url = rec.get("image") or None
    # Use name as description if no dedicated description provided
    description = name

    return TrafficSignDB(
        number=str(number),
        name=name,
        description=description,
        image_url=image_url,
        category=category,
    )


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Expected a list of objects in JSON")
        return data


def upsert_signs(db: Session, items: list):
    created = 0
    updated = 0

    for raw in items:
        # Validate minimal fields
        if not all(k in raw for k in essential_fields):
            # Skip rows missing essential keys
            continue

        number = f"IL-{raw.get('id')}"
        existing = db.query(TrafficSignDB).filter(TrafficSignDB.number == str(number)).first()

        if existing:
            # Update existing
            existing.name = raw.get("nom") or existing.name
            existing.category = raw.get("type") or existing.category
            existing.image_url = raw.get("image") or existing.image_url
            existing.description = existing.name if not existing.description else existing.description
            updated += 1
        else:
            db.add(map_record(raw))
            created += 1

    db.commit()
    return created, updated


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m backend.scripts.import_signs_from_json <path-to-json>")
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"File not found: {src}")
        sys.exit(1)

    ensure_tables()

    data = load_json(src)

    db: Session = SessionLocal()
    try:
        created, updated = upsert_signs(db, data)
        print(f"Imported signs → created: {created}, updated: {updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
