# app/services/team_builder.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from math import floor
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from app.services.constraints_repo import Constraints, load_constraints
from app.services.fatigue import FatigueConfig, compute_fatigue


@dataclass(frozen=True)
class TeamPlan:
    size: int
    layout: str  # e.g. "1-2-2", "2-1-2", "2-2-2", "2-2-2-2", "2-2-2-2-2"
    lead_slots: int
    team_slots: int
    wheel_slots: int


@dataclass(frozen=True)
class ScoreBreakdown:
    fatigue_sum: float
    conflict_ok: bool
    conflict_penalty: float
    pair_splits: int
    pair_penalty: float

    @property
    def total(self) -> float:
        return float(self.fatigue_sum + self.conflict_penalty + self.pair_penalty)


@dataclass(frozen=True)
class TeamSuggestion:
    plan: TeamPlan
    dogs: List[str]
    score: float
    notes: List[str]
    assignment: Dict[str, List[Optional[str]]]  # {"lead": [...], "team":[...], "wheel":[...]}
    # Extra data for UI explainability (backward-compatible defaults)
    breakdown: Optional[ScoreBreakdown] = None
    dog_details: Dict[str, Dict[str, object]] = field(default_factory=dict)


@dataclass(frozen=True)
class PoolStats:
    total: int
    lead: int
    team: int
    wheel: int
    age8p: int


def _conflicts_ok(dogs: List[str], conflicts: Set[Tuple[str, str]]) -> bool:
    s = set(dogs)
    for a in dogs:
        for b in s:
            if a != b and (a, b) in conflicts:
                return False
    return True


def _pair_penalty(dogs: List[str], pairs: Dict[str, str], keep_pairs_soft: bool) -> int:
    if not keep_pairs_soft:
        return 0
    s = set(dogs)
    missing = 0
    for d in dogs:
        mate = pairs.get(d)
        if mate and mate not in s:
            missing += 1
    # Each split counted twice if pairs map is symmetric
    return missing // 2


def _plans_for_size(size: int) -> List[TeamPlan]:
    if size == 5:
        return [
            TeamPlan(size=5, layout="1-2-2", lead_slots=1, team_slots=2, wheel_slots=2),
            TeamPlan(size=5, layout="2-1-2", lead_slots=2, team_slots=1, wheel_slots=2),
        ]
    if size == 6:
        return [TeamPlan(size=6, layout="2-2-2", lead_slots=2, team_slots=2, wheel_slots=2)]
    if size == 8:
        # Real: 4 pairs => leaders(2), center/team(4), wheels(2) but visually 2-2-2-2
        return [TeamPlan(size=8, layout="2-2-2-2", lead_slots=2, team_slots=4, wheel_slots=2)]
    if size == 10:
        # Real: 5 pairs => leaders(2), center/team(6), wheels(2) but visually 2-2-2-2-2
        return [TeamPlan(size=10, layout="2-2-2-2-2", lead_slots=2, team_slots=6, wheel_slots=2)]
    raise ValueError("Supported sizes: 5, 6, 8, 10")


def _filter_candidates(
    profiles: pd.DataFrame,
    fatigue: pd.DataFrame,
    planned_km: float,
    enforce_age_cap: bool,
    candidate_dogs: Optional[List[str]] = None,
) -> pd.DataFrame:
    df = profiles.merge(fatigue, on="dog_name", how="left").fillna(
        {"km_3d": 0.0, "km_7d": 0.0, "last_day_km": 0.0, "hard_streak": 0, "fatigue": 0.0}
    )

    if candidate_dogs is not None:
        cand_set = set(candidate_dogs)
        df = df[df["dog_name"].isin(cand_set)].copy()

    # Rule: exclude 8+ if planned km > 20
    if enforce_age_cap and planned_km > 20:
        df = df[~(df["age_years"] >= 8)].copy()

    return df


def _pick_role(df: pd.DataFrame, role_col: str, k: int, already: Set[str]) -> List[str]:
    if k <= 0:
        return []
    cand = df[(df[role_col] == 1) & (~df["dog_name"].isin(already))].copy()
    cand = cand.sort_values("fatigue", ascending=True)
    return cand["dog_name"].head(k).tolist()


def _try_add_mates(
    current: List[str],
    k: int,
    pairs: Dict[str, str],
    df: pd.DataFrame,
    already: Set[str],
) -> List[str]:
    """
    Softly try to add mates of already-picked dogs (if capacity allows).
    Doesn't force; doesn't exceed k.
    """
    if len(current) >= k:
        return current[:k]

    available = set(df["dog_name"].tolist())
    out = list(current)
    for d in list(out):
        if len(out) >= k:
            break
        mate = pairs.get(d)
        if not mate:
            continue
        if mate in out or mate in already:
            continue
        if mate not in available:
            continue
        out.append(mate)
        already.add(mate)

    return out[:k]


def compute_pool_stats(
    profiles: pd.DataFrame,
    fatigue: pd.DataFrame,
    planned_km: float,
    enforce_age_cap: bool,
    candidate_dogs: Optional[List[str]] = None,
) -> PoolStats:
    """
    Computes pool stats after applying the same filters as in team building.
    """
    df = _filter_candidates(
        profiles=profiles,
        fatigue=fatigue,
        planned_km=planned_km,
        enforce_age_cap=enforce_age_cap,
        candidate_dogs=candidate_dogs,
    )

    total = int(df["dog_name"].nunique())
    lead = int((df["can_lead"] == 1).sum()) if "can_lead" in df.columns else 0
    team = int((df["can_team"] == 1).sum()) if "can_team" in df.columns else 0
    wheel = int((df["can_wheel"] == 1).sum()) if "can_wheel" in df.columns else 0
    age8p = int((df["age_years"] >= 8).sum()) if "age_years" in df.columns else 0

    return PoolStats(total=total, lead=lead, team=team, wheel=wheel, age8p=age8p)


def theoretical_max_teams(pool: PoolStats, plans: List[TeamPlan]) -> int:
    """
    Upper bound ignoring conflicts/pairs: how many teams could exist by counts only.
    We take the best (max) over allowed plans for the size.
    """
    best = 0
    for p in plans:
        if p.size <= 0:
            continue
        caps = [
            floor(pool.total / p.size) if p.size else 0,
            floor(pool.lead / p.lead_slots) if p.lead_slots else 10**9,
            floor(pool.wheel / p.wheel_slots) if p.wheel_slots else 10**9,
            floor(pool.team / p.team_slots) if p.team_slots else 10**9,
        ]
        best = max(best, int(min(caps)))
    return best


def unmet_reasons(
    pool: PoolStats,
    plans: List[TeamPlan],
    requested_teams: int,
) -> List[str]:
    """
    Human-friendly reasons for failing to reach requested teams.
    This is a necessary-not-sufficient diagnosis (ignores conflicts/pairs).
    """
    if requested_teams <= 0:
        return []

    max_possible = theoretical_max_teams(pool, plans)
    if max_possible >= requested_teams:
        # Likely blocked by conflicts/pairs or "greedy" selection effects.
        return [
            "Counts look sufficient, but constraints (conflicts) or pair-keeping may block valid combinations.",
            "Try disabling 'Keep kennel pairs' or expanding the date range (for better fatigue history), or adjust team size.",
        ]

    # Otherwise, show concrete shortages using the best plan for the pool (the plan that gives max teams).
    best_plan = None
    best_cap = -1
    for p in plans:
        caps = [
            floor(pool.total / p.size) if p.size else 0,
            floor(pool.lead / p.lead_slots) if p.lead_slots else 10**9,
            floor(pool.wheel / p.wheel_slots) if p.wheel_slots else 10**9,
            floor(pool.team / p.team_slots) if p.team_slots else 10**9,
        ]
        cap = int(min(caps))
        if cap > best_cap:
            best_cap = cap
            best_plan = p

    if best_plan is None:
        return ["No valid plan found for this team size."]

    need_total = best_plan.size * requested_teams
    need_lead = best_plan.lead_slots * requested_teams
    need_team = best_plan.team_slots * requested_teams
    need_wheel = best_plan.wheel_slots * requested_teams

    out: List[str] = [
        f"Requested {requested_teams} teams, but the theoretical maximum is {max_possible} "
        f"(best layout {best_plan.layout})."
    ]

    if pool.total < need_total:
        out.append(f"Not enough dogs: need {need_total}, available {pool.total}.")
    if pool.lead < need_lead:
        out.append(f"Not enough leaders: need {need_lead}, available {pool.lead}.")
    if pool.team < need_team:
        out.append(f"Not enough center/team dogs: need {need_team}, available {pool.team}.")
    if pool.wheel < need_wheel:
        out.append(f"Not enough wheels: need {need_wheel}, available {pool.wheel}.")

    return out


def build_team_suggestions(
    day: Date,
    size: int,
    planned_km: float,
    keep_pairs_soft: bool = True,
    enforce_age_cap: bool = True,
    cfg: FatigueConfig | None = None,
    candidate_dogs: Optional[List[str]] = None,
) -> List[TeamSuggestion]:
    """
    candidate_dogs: limit selection to this subset (used by daily schedule builder to avoid repeats).
    """
    cfg = cfg or FatigueConfig()
    cons: Constraints = load_constraints()
    fatigue = compute_fatigue(day=day, cfg=cfg)

    df = _filter_candidates(
        profiles=cons.profiles,
        fatigue=fatigue,
        planned_km=planned_km,
        enforce_age_cap=enforce_age_cap,
        candidate_dogs=candidate_dogs,
    )

    conflicts = cons.conflicts
    pairs = cons.pairs

    suggestions: List[TeamSuggestion] = []
    plans = _plans_for_size(size)

    # Pre-sorted "freshest" for fill
    df_fresh = df.sort_values("fatigue", ascending=True).copy()

    # Dog details map for UI (fatigue/age/roles)
    details: Dict[str, Dict[str, object]] = {}
    if not df.empty:
        for _, row in df.iterrows():
            name = str(row["dog_name"])
            roles: List[str] = []
            if int(row.get("can_lead", 0)) == 1:
                roles.append("lead")
            if int(row.get("can_team", 0)) == 1:
                roles.append("team")
            if int(row.get("can_wheel", 0)) == 1:
                roles.append("wheel")
            details[name] = {
                "fatigue": float(row.get("fatigue", 0.0)),
                "age_years": int(row.get("age_years")) if pd.notna(row.get("age_years")) else None,
                "roles": roles,
            }

    for plan in plans:
        notes: List[str] = []

        # Pick by roles (freshest first), no conflicts considered yet
        already: Set[str] = set()

        wheels = _pick_role(df, "can_wheel", plan.wheel_slots, already=already)
        already.update(wheels)

        leads = _pick_role(df, "can_lead", plan.lead_slots, already=already)
        already.update(leads)

        teams = _pick_role(df, "can_team", plan.team_slots, already=already)
        already.update(teams)

        # Not enough role candidates -> skip plan
        if len(wheels) < plan.wheel_slots or len(leads) < plan.lead_slots or len(teams) < plan.team_slots:
            notes.append("Not enough candidates for required roles.")
            continue

        # Keep kennel pairs (soft) within each role group if possible
        if keep_pairs_soft:
            # Try to keep mates in same role group, without exceeding slot size,
            # but also not stealing dogs already used by other role groups.
            wheels_already = set(wheels)
            wheels2 = _try_add_mates(wheels, plan.wheel_slots, pairs, df, already=wheels_already)

            # Recompute global already (avoid duplicates between groups)
            already2 = set(wheels2)

            leads2 = _pick_role(df, "can_lead", plan.lead_slots, already=already2)
            already2.update(leads2)
            leads2 = _try_add_mates(leads2, plan.lead_slots, pairs, df, already=already2)

            already2 = set(wheels2) | set(leads2)
            teams2 = _pick_role(df, "can_team", plan.team_slots, already=already2)
            already2.update(teams2)
            teams2 = _try_add_mates(teams2, plan.team_slots, pairs, df, already=already2)

            wheels, leads, teams = wheels2, leads2, teams2

        # Compose final list in role order (lead, team, wheel) for UI
        ordered: List[str] = []
        for group in (leads, teams, wheels):
            for d in group:
                if d not in ordered:
                    ordered.append(d)

        # Ensure exact size by filling with freshest remaining (any role) if needed
        if len(ordered) < plan.size:
            remaining = df_fresh[~df_fresh["dog_name"].isin(set(ordered))]
            fill = remaining["dog_name"].head(plan.size - len(ordered)).tolist()
            ordered.extend(fill)

        ordered = ordered[: plan.size]

        # Notes & penalties
        conflict_ok = _conflicts_ok(ordered, conflicts)
        if not conflict_ok:
            notes.append("Conflicts detected; this team is invalid by constraints.")

        pair_splits = _pair_penalty(ordered, pairs, keep_pairs_soft)
        if keep_pairs_soft and pair_splits > 0:
            notes.append(f"Pairs split: {pair_splits}")

        if enforce_age_cap and planned_km > 20:
            notes.append("Age rule enabled: 8+ excluded when planned km > 20.")

        # Scoring
        sub = df[df["dog_name"].isin(ordered)].set_index("dog_name")
        fatigue_sum = float(sub["fatigue"].sum()) if not sub.empty else 99999.0

        conflict_penalty = 5000.0 if not conflict_ok else 0.0  # make invalids sink
        pair_penalty = 80.0 * float(pair_splits)                # soft preference only

        breakdown = ScoreBreakdown(
            fatigue_sum=float(fatigue_sum),
            conflict_ok=bool(conflict_ok),
            conflict_penalty=float(conflict_penalty),
            pair_splits=int(pair_splits),
            pair_penalty=float(pair_penalty),
        )

        score = breakdown.total

        def pad(role_list: List[str], slots: int) -> List[Optional[str]]:
            out: List[Optional[str]] = role_list[:slots]
            while len(out) < slots:
                out.append(None)
            return out

        assignment = {
            "lead": pad(leads, plan.lead_slots),
            "team": pad(teams, plan.team_slots),
            "wheel": pad(wheels, plan.wheel_slots),
        }

        suggestions.append(
            TeamSuggestion(
                plan=plan,
                dogs=ordered,
                score=float(score),
                notes=notes,
                assignment=assignment,
                breakdown=breakdown,
                dog_details=details,
            )
        )

    suggestions.sort(key=lambda x: x.score)
    return suggestions[:5]
