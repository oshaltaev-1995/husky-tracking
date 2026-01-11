from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text

from app.db import SessionLocal


@dataclass(frozen=True)
class DogInfo:
    name: str
    age: int
    can_lead: bool
    can_team: bool
    can_wheel: bool


def _get_dog_id(db, name: str) -> int:
    row = db.execute(text("SELECT id FROM dogs WHERE name = :name"), {"name": name}).fetchone()
    if not row:
        raise RuntimeError(f"Dog not found in DB: {name}. Import Excel first.")
    return int(row[0])


def _upsert_profile(db, dog_id: int, info: DogInfo) -> None:
    # SQLite has no native boolean -> use 0/1
    exists = db.execute(text("SELECT dog_id FROM dog_profile WHERE dog_id = :id"), {"id": dog_id}).fetchone()
    payload = {
        "dog_id": dog_id,
        "age_years": info.age,
        "can_lead": 1 if info.can_lead else 0,
        "can_team": 1 if info.can_team else 0,
        "can_wheel": 1 if info.can_wheel else 0,
    }
    if exists:
        db.execute(
            text(
                """
                UPDATE dog_profile
                SET age_years=:age_years,
                    can_lead=:can_lead,
                    can_team=:can_team,
                    can_wheel=:can_wheel
                WHERE dog_id=:dog_id
                """
            ),
            payload,
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO dog_profile(dog_id, age_years, can_lead, can_team, can_wheel)
                VALUES (:dog_id, :age_years, :can_lead, :can_team, :can_wheel)
                """
            ),
            payload,
        )


def _add_relation_bidir(db, a_id: int, b_id: int, rel: str) -> None:
    # Insert both directions, ignore duplicates via try/except
    for x, y in [(a_id, b_id), (b_id, a_id)]:
        try:
            db.execute(
                text(
                    """
                    INSERT INTO dog_relations(dog_id_a, dog_id_b, relation_type)
                    VALUES (:a, :b, :rel)
                    """
                ),
                {"a": x, "b": y, "rel": rel},
            )
        except Exception:
            # likely UNIQUE constraint (already exists)
            pass


def main() -> None:
    # --- Profiles from your message
    dogs: list[DogInfo] = [
        DogInfo("Irbis", 2, True, True, False),
        DogInfo("Taiga", 2, True, True, False),

        DogInfo("Rikki", 7, False, True, False),
        DogInfo("Joha", 7, False, True, False),

        DogInfo("Lennon", 7, False, True, True),
        DogInfo("Blix", 7, False, True, True),

        DogInfo("Talvi", 10, False, True, False),
        DogInfo("Lumi", 10, False, True, False),

        DogInfo("Tesla", 3, True, True, True),
        DogInfo("Lara", 3, True, True, True),

        DogInfo("Jukki", 11, False, True, False),
        DogInfo("Vita", 11, False, True, False),

        DogInfo("Efir", 8, False, False, True),
        DogInfo("Sparki", 8, False, False, True),

        DogInfo("Vesta", 7, True, False, False),
        DogInfo("Lisa", 7, True, False, False),

        DogInfo("Prince", 6, False, True, True),
        DogInfo("Rover", 6, False, True, True),

        DogInfo("Landa", 6, True, False, False),
        DogInfo("Koni", 6, True, False, False),

        DogInfo("Monti", 6, True, True, True),
        DogInfo("Python", 6, True, True, True),

        DogInfo("Misha", 3, False, False, True),
        DogInfo("Graph", 3, False, False, True),

        DogInfo("Ilon", 3, False, True, True),
        DogInfo("Knox", 3, False, True, True),

        DogInfo("Kurt", 9, False, True, False),
        DogInfo("Marfa", 9, False, True, False),

        DogInfo("Whisky", 7, False, True, True),
        DogInfo("Ray", 7, False, True, True),
    ]

    # kennel pairs (also add as relation_type="pair")
    pair_names = [
        ("Irbis", "Taiga"),
        ("Rikki", "Joha"),
        ("Lennon", "Blix"),
        ("Talvi", "Lumi"),
        ("Tesla", "Lara"),
        ("Jukki", "Vita"),
        ("Efir", "Sparki"),
        ("Vesta", "Lisa"),
        ("Prince", "Rover"),
        ("Landa", "Koni"),
        ("Monti", "Python"),
        ("Misha", "Graph"),
        ("Ilon", "Knox"),
        ("Kurt", "Marfa"),
        ("Whisky", "Ray"),
    ]

    # conflicts (bidirectional)
    conflicts = [
        ("Vesta", "Jukki"),
        ("Vesta", "Vita"),
        ("Lisa", "Jukki"),
        ("Lisa", "Vita"),

        ("Misha", "Prince"),
        ("Misha", "Rover"),

        ("Rikki", "Marfa"),

        ("Koni", "Vesta"),
        ("Koni", "Lisa"),
        ("Landa", "Vesta"),
        ("Landa", "Lisa"),
    ]

    with SessionLocal() as db:
        # profiles
        for info in dogs:
            dog_id = _get_dog_id(db, info.name)
            _upsert_profile(db, dog_id, info)

        # relations
        for a, b in pair_names:
            a_id = _get_dog_id(db, a)
            b_id = _get_dog_id(db, b)
            _add_relation_bidir(db, a_id, b_id, "pair")

        for a, b in conflicts:
            a_id = _get_dog_id(db, a)
            b_id = _get_dog_id(db, b)
            _add_relation_bidir(db, a_id, b_id, "conflict")

        db.commit()

    print("✅ Seed done: dog_profile + dog_relations")


if __name__ == "__main__":
    main()
