# app/views/team_suggestions.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from math import floor
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st

from app.services.fatigue import FatigueConfig, compute_fatigue
from app.services.constraints_repo import load_constraints
from app.services.team_builder import (
    PoolStats,
    TeamPlan,
    TeamSuggestion,
    build_team_suggestions,
    compute_pool_stats,
    unmet_reasons,
)


@dataclass(frozen=True)
class RunPlan:
    size: int
    teams_count: int  # how many teams to build


def _auto_teams_count(available_dogs: int, size: int) -> int:
    # Maximum possible without repeats (ignores role constraints)
    if size <= 0:
        return 0
    return available_dogs // size


def _pretty_layout(layout: str) -> str:
    return layout


def _chunks(items: List[str], n: int) -> List[List[str]]:
    if n <= 0:
        return []
    out: List[List[str]] = []
    for i in range(0, len(items), n):
        out.append(items[i : i + n])
    return out


def _pill(text: str) -> None:
    st.markdown(
        f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;"
        f"border:1px solid #ddd;font-size:12px;margin-right:6px'>{text}</span>",
        unsafe_allow_html=True,
    )


def _render_dog(name: str, dog_details: Dict[str, Dict[str, object]]) -> None:
    d = dog_details.get(name, {})
    age = d.get("age_years", None)
    fatigue = d.get("fatigue", None)
    roles = d.get("roles", [])

    line = f"**{name}**"
    meta: List[str] = []
    if age is not None:
        meta.append(f"age {age}")
    if fatigue is not None:
        try:
            meta.append(f"fatigue {float(fatigue):.1f}")
        except Exception:
            meta.append("fatigue ?")
    if roles:
        meta.append("/".join([str(x) for x in roles]))

    if meta:
        line += "  ·  " + "  ·  ".join(meta)

    st.write(line)

    tags: List[str] = []
    if isinstance(age, int) and age >= 8:
        tags.append("8+")
    if roles and "lead" in roles:
        tags.append("lead")
    if roles and "team" in roles:
        tags.append("team")
    if roles and "wheel" in roles:
        tags.append("wheel")

    if tags:
        cols = st.columns(min(4, len(tags)))
        for i, t in enumerate(tags[:4]):
            with cols[i]:
                _pill(t)


def _render_pair_block(title: str, names: List[Optional[str]], dog_details: Dict[str, Dict[str, object]]) -> None:
    st.markdown(f"**{title}**")
    cleaned = [x for x in names if x is not None]
    if not cleaned:
        st.info("—")
        return

    # Show as pairs (2 per row), but keep single if odd
    pairs = _chunks(cleaned, 2)
    for p in pairs:
        if len(p) == 2:
            c1, c2 = st.columns(2)
            with c1:
                _render_dog(p[0], dog_details)
            with c2:
                _render_dog(p[1], dog_details)
        else:
            _render_dog(p[0], dog_details)


def _render_breakdown(s: TeamSuggestion) -> None:
    if s.breakdown is None:
        return

    b = s.breakdown
    with st.expander("Why this score?", expanded=False):
        st.write(f"- Fatigue sum: **{b.fatigue_sum:.1f}**")
        st.write(f"- Conflicts penalty: **{b.conflict_penalty:.1f}** ({'OK' if b.conflict_ok else 'CONFLICT'})")
        st.write(f"- Pair split penalty: **{b.pair_penalty:.1f}** (splits: {b.pair_splits})")
        st.write(f"- Total score: **{b.total:.1f}**")


def _render_one_team(i: int, s: TeamSuggestion) -> None:
    st.markdown(f"### Team #{i} — layout **{_pretty_layout(s.plan.layout)}** (score {s.score:.1f})")

    dog_details = s.dog_details or {}

    c1, c2, c3 = st.columns(3)
    with c1:
        _render_pair_block("Lead", s.assignment.get("lead", []), dog_details)
    with c2:
        _render_pair_block("Center / team", s.assignment.get("team", []), dog_details)
    with c3:
        _render_pair_block("Wheel", s.assignment.get("wheel", []), dog_details)

    _render_breakdown(s)

    if s.notes:
        # If there is a conflict, highlight it as an error
        if any("invalid" in n.lower() or "conflict" in n.lower() for n in s.notes):
            st.error(" • ".join(s.notes))
        else:
            st.caption("Notes: " + " • ".join(s.notes))

    st.caption("Dogs (flat order)")
    st.write(", ".join(s.dogs))
    st.divider()


def _pick_best_suggestion(
    *,
    day: Date,
    size: int,
    planned_km: float,
    keep_pairs_soft: bool,
    enforce_age_cap: bool,
    cfg: FatigueConfig,
    candidate_dogs: List[str],
) -> Optional[TeamSuggestion]:
    suggestions = build_team_suggestions(
        day=day,
        size=size,
        planned_km=float(planned_km),
        keep_pairs_soft=keep_pairs_soft,
        enforce_age_cap=enforce_age_cap,
        cfg=cfg,
        candidate_dogs=candidate_dogs,
    )
    if not suggestions:
        return None

    # Builder already sorts by score, but keep it explicit
    suggestions.sort(key=lambda x: x.score)
    return suggestions[0]


def render_team_suggestions(dff: pd.DataFrame) -> None:
    st.subheader("Team suggestions")
    st.caption(
        "Demo: generate multiple teams using workload (fatigue) + roles + conflicts + kennel pairs (soft). "
        "Dogs are not reused between teams."
    )

    # Defaults from Red Flags sliders if user already interacted there
    hard_day = float(st.session_state.get("rf_hard_day", 18))
    hard_streak = int(st.session_state.get("rf_streak", 3))
    cfg = FatigueConfig(hard_day_threshold_km=hard_day, hard_streak_days=hard_streak)

    # Available dogs in current filter range (dff)
    all_dogs = sorted(dff["dog_name"].unique().tolist())
    available_raw = len(all_dogs)

    # UI row 1
    r1c1, r1c2, r1c3, r1c4 = st.columns([1, 1, 1, 1])
    with r1c1:
        size = st.selectbox("Team size", options=[5, 6, 8, 10], index=1, key="ts_size")
    with r1c2:
        planned_km = st.slider("Planned km today", 0, 60, 20, 1, key="ts_planned_km")
    with r1c3:
        keep_pairs = st.checkbox("Keep kennel pairs (soft)", value=True, key="ts_keep_pairs")
    with r1c4:
        age_rule = st.checkbox("Age rule: 8+ excluded if planned km > 20", value=True, key="ts_age_rule")

    # Planned run date
    max_date = dff["date"].max().date() if not dff.empty else Date.today()
    day = st.date_input("Planned run date", value=max_date, key="ts_day")

    st.divider()

    # Compute pool stats using the same filters as builder (important!)
    # We compute fatigue here too, so pool diagnostics match the day+cfg.
    cons = load_constraints()
    fatigue = compute_fatigue(day=day, cfg=cfg)
    pool = compute_pool_stats(
        profiles=cons.profiles,
        fatigue=fatigue,
        planned_km=float(planned_km),
        enforce_age_cap=age_rule,
        candidate_dogs=all_dogs,
    )

    st.markdown("### Pool diagnostics")
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Total", pool.total)
    p2.metric("Lead", pool.lead)
    p3.metric("Center/Team", pool.team)
    p4.metric("Wheel", pool.wheel)
    p5.metric("Age 8+", pool.age8p)

    auto_cnt_simple = _auto_teams_count(available_dogs=pool.total, size=size)
    if auto_cnt_simple <= 0:
        st.warning("Not enough dogs in the current filter for this team size (after filters).")
        return

    h1, h2, h3 = st.columns(3)
    with h1:
        st.metric("Dogs in current filter (raw)", available_raw)
    with h2:
        st.metric("Team size", size)
    with h3:
        st.metric("Auto teams (simple)", auto_cnt_simple)

    m1, m2 = st.columns([1, 2])
    with m1:
        mode = st.radio("How many teams?", options=["Auto", "Manual"], horizontal=True, key="ts_mode")
    with m2:
        if mode == "Auto":
            teams_count = auto_cnt_simple
            st.info(f"Auto: will try to generate **{teams_count}** team(s) (using up to {teams_count * size} dogs).")
        else:
            teams_count = st.number_input(
                "Teams to generate",
                min_value=1,
                max_value=max(1, auto_cnt_simple),
                value=min(3, auto_cnt_simple),
                step=1,
                key="ts_manual_cnt",
            )
            st.info(f"Manual: will try to generate **{teams_count}** team(s).")

    st.divider()

    # Generate button
    if not st.button("Generate teams", key="ts_generate"):
        st.caption("Tip: set the top date range so workload history includes at least the last 7 days.")
        return

    remaining: Set[str] = set(all_dogs)
    built: List[TeamSuggestion] = []
    failed_rounds = 0

    for _ in range(int(teams_count)):
        if len(remaining) < size:
            break

        best = _pick_best_suggestion(
            day=day,
            size=size,
            planned_km=float(planned_km),
            keep_pairs_soft=keep_pairs,
            enforce_age_cap=age_rule,
            cfg=cfg,
            candidate_dogs=sorted(list(remaining)),
        )

        if best is None:
            failed_rounds += 1
            # If stuck due to pair preference, try relaxing it once
            if keep_pairs and failed_rounds <= 1:
                best = _pick_best_suggestion(
                    day=day,
                    size=size,
                    planned_km=float(planned_km),
                    keep_pairs_soft=False,
                    enforce_age_cap=age_rule,
                    cfg=cfg,
                    candidate_dogs=sorted(list(remaining)),
                )

        if best is None:
            break

        built.append(best)
        remaining -= set(best.dogs)

    if not built:
        st.error("No teams could be generated. Try another size, expand date range, or disable constraints.")
        return

    used = len(all_dogs) - len(remaining)
    st.success(f"✅ Generated {len(built)} team(s). Used {used}/{len(all_dogs)} dogs.")

    # If user requested more than we generated, explain why (pool-level diagnosis)
    if len(built) < int(teams_count):
        plans = []
        # Import locally to avoid circulars; builder already knows plans, but we use them here for reasons.
        # For size=5 there are multiple layouts, and we want to consider all of them.
        from app.services.team_builder import _plans_for_size  # noqa: WPS433 (local import by design)

        plans = _plans_for_size(int(size))
        reasons = unmet_reasons(pool=pool, plans=plans, requested_teams=int(teams_count))
        st.warning(f"Could not build {teams_count} team(s). Built {len(built)}.")
        for r in reasons:
            st.write(f"- {r}")

    # Render teams
    for idx, team in enumerate(built, start=1):
        _render_one_team(idx, team)

    # Remaining dogs
    if remaining:
        st.subheader("Unused dogs (remaining)")
        st.write(", ".join(sorted(list(remaining))))
    else:
        st.caption("All dogs were assigned to teams.")
