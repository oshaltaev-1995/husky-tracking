from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from sqlalchemy import text

from app.db import SessionLocal


@dataclass(frozen=True)
class UpsertResult:
    action: str  # "inserted" | "updated"
    dog_id: int
    date: Date
    distance_km: float
    source: str


def get_or_create_dog_id(dog_name: str) -> int:
    dog_name = dog_name.strip()
    if not dog_name:
        raise ValueError("dog_name is empty")

    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id FROM dogs WHERE name = :name"),
            {"name": dog_name},
        ).fetchone()

        if row:
            return int(row[0])

        db.execute(
            text("INSERT INTO dogs(name) VALUES (:name)"),
            {"name": dog_name},
        )
        db.commit()

        new_id = db.execute(
            text("SELECT id FROM dogs WHERE name = :name"),
            {"name": dog_name},
        ).fetchone()
        if not new_id:
            raise RuntimeError("Failed to create dog")
        return int(new_id[0])


def upsert_training(
    dog_name: str,
    day: Date,
    distance_km: float,
    source: str = "ui",
) -> UpsertResult:
    dog_id = get_or_create_dog_id(dog_name)

    with SessionLocal() as db:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM training_log
                WHERE dog_id = :dog_id AND date = :day
                """
            ),
            {"dog_id": dog_id, "day": day.isoformat()},
        ).fetchone()

        if existing:
            db.execute(
                text(
                    """
                    UPDATE training_log
                    SET distance_km = :km,
                        source = :source
                    WHERE id = :id
                    """
                ),
                {"km": float(distance_km), "source": source, "id": int(existing[0])},
            )
            db.commit()
            return UpsertResult("updated", dog_id, day, float(distance_km), source)

        db.execute(
            text(
                """
                INSERT INTO training_log(dog_id, date, distance_km, source)
                VALUES (:dog_id, :day, :km, :source)
                """
            ),
            {
                "dog_id": dog_id,
                "day": day.isoformat(),
                "km": float(distance_km),
                "source": source,
            },
        )
        db.commit()
        return UpsertResult("inserted", dog_id, day, float(distance_km), source)
