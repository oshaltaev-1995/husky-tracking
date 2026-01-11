from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DogView:
    name: str
    age: Optional[int] = None
    fatigue: Optional[float] = None
    role: Optional[str] = None  # "lead" | "center" | "wheel" (optional)
    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamView:
    layout: str  # e.g. "2-2-2", "1-2-2"
    lead: Tuple[DogView, ...]
    center: Tuple[DogView, ...]
    wheel: Tuple[DogView, ...]


@dataclass(frozen=True)
class ScoreItem:
    label: str
    penalty: float
    details: Optional[str] = None


@dataclass(frozen=True)
class ScoreBreakdown:
    fatigue_sum: float
    items: Tuple[ScoreItem, ...]  # conflicts, pair splits, age penalties, etc.

    @property
    def extra_penalties_sum(self) -> float:
        return sum(x.penalty for x in self.items)

    @property
    def total(self) -> float:
        return float(self.fatigue_sum + self.extra_penalties_sum)


@dataclass(frozen=True)
class PoolStats:
    total: int
    lead: int
    center: int
    wheel: int
    age8p: int


def compute_pool_stats(dogs: List[dict]) -> PoolStats:
    """
    dogs: list of dicts with at least:
      - name
      - roles: set/list of roles OR role flags
      - age (optional)
    """
    total = len(dogs)
    lead = center = wheel = age8p = 0

    for d in dogs:
        roles = d.get("roles")
        if roles is None:
            # allow single role string too
            roles = [d.get("role")] if d.get("role") else []
        roles_set = set(roles)

        if "lead" in roles_set:
            lead += 1
        if "center" in roles_set:
            center += 1
        if "wheel" in roles_set:
            wheel += 1

        age = d.get("age")
        if age is not None and age >= 8:
            age8p += 1

    return PoolStats(total=total, lead=lead, center=center, wheel=wheel, age8p=age8p)


def unmet_reasons_for_request(
    pool: PoolStats,
    layout: str,
    requested_teams: int,
) -> List[str]:
    """
    Fast diagnostic "why N teams couldn't be built".
    This does NOT account for conflicts and tricky rules — only theoretical minimum.
    """
    # layout like "2-2-2" => needs:
    parts = [int(x) for x in layout.split("-")]
    dogs_per_team = sum(parts)

    # Heuristic role requirements per layout segment:
    # - Lead segment = first number
    # - Wheel segment = last number
    # - Center segment = middle sum
    need_lead = parts[0] * requested_teams
    need_wheel = parts[-1] * requested_teams
    need_total = dogs_per_team * requested_teams

    reasons: List[str] = []
    if pool.total < need_total:
        reasons.append(f"Running out of dogs: required {need_total}, available {pool.total}.")
    if pool.lead < need_lead:
        reasons.append(f"Running out of leaders: required {need_lead}, available {pool.lead}.")
    if pool.wheel < need_wheel:
        reasons.append(f"Running out of wheels: required {need_wheel}, available {pool.wheel}.")

    return reasons


def chunk_by_layout(dogs: List[DogView], layout: str) -> TeamView:
    """
    Turns the list of dogs into lead/center/wheel according to layout.
    Order of dogs matches the logic of their placement.
    """
    parts = [int(x) for x in layout.split("-")]
    idx = 0
    lead = tuple(dogs[idx: idx + parts[0]])
    idx += parts[0]
    center_count = sum(parts[1:-1]) if len(parts) > 2 else 0
    center = tuple(dogs[idx: idx + center_count])
    idx += center_count
    wheel = tuple(dogs[idx: idx + parts[-1]])
    return TeamView(layout=layout, lead=lead, center=center, wheel=wheel)
