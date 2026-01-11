from __future__ import annotations

from sqlalchemy import text

from app.db import engine


def main() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dog_profile (
                    dog_id INTEGER PRIMARY KEY,
                    age_years INTEGER NOT NULL,
                    can_lead INTEGER NOT NULL DEFAULT 0,
                    can_team INTEGER NOT NULL DEFAULT 1,
                    can_wheel INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(dog_id) REFERENCES dogs(id)
                );
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dog_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dog_id_a INTEGER NOT NULL,
                    dog_id_b INTEGER NOT NULL,
                    relation_type TEXT NOT NULL CHECK (relation_type IN ('pair','conflict')),
                    FOREIGN KEY(dog_id_a) REFERENCES dogs(id),
                    FOREIGN KEY(dog_id_b) REFERENCES dogs(id)
                );
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_dog_relations
                ON dog_relations (dog_id_a, dog_id_b, relation_type);
                """
            )
        )

    print("✅ Tables created: dog_profile, dog_relations")


if __name__ == "__main__":
    main()
