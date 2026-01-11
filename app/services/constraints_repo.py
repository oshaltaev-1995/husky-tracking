from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple

import pandas as pd
from sqlalchemy import text

from app.db import engine


@dataclass(frozen=True)
class Constraints:
    profiles: pd.DataFrame  # dog_name, age_years, can_lead, can_team, can_wheel
    pairs: Dict[str, str]  # dog -> pair_mate
    conflicts: Set[Tuple[str, str]]  # (a,b) directed for easy lookup


def load_constraints() -> Constraints:
    # profiles
    q_profiles = """
    SELECT d.name AS dog_name,
           p.age_years,
           p.can_lead,
           p.can_team,
           p.can_wheel
    FROM dog_profile p
    JOIN dogs d ON d.id = p.dog_id
    """
    profiles = pd.read_sql(text(q_profiles), engine)

    # relations
    q_rel = """
    SELECT d1.name AS a, d2.name AS b, r.relation_type AS rel
    FROM dog_relations r
    JOIN dogs d1 ON d1.id = r.dog_id_a
    JOIN dogs d2 ON d2.id = r.dog_id_b
    """
    rel = pd.read_sql(text(q_rel), engine)

    pairs: Dict[str, str] = {}
    conflicts: Set[Tuple[str, str]] = set()

    for _, row in rel.iterrows():
        a = str(row["a"])
        b = str(row["b"])
        r = str(row["rel"])
        if r == "pair":
            # store bidirectional
            pairs[a] = b
        elif r == "conflict":
            conflicts.add((a, b))

    return Constraints(profiles=profiles, pairs=pairs, conflicts=conflicts)
