# app/views/team_suggestions.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Dict, List, Optional, Set

import pandas as pd
import streamlit as st

from app.services.fatigue import FatigueConfig, compute_fatigue
from app.services.constraints_repo import load_constraints
from app.services.team_builder import (
    TeamSuggestion,
    build_team_suggestions,
    compute_pool_stats,
    unmet_reasons,
)


# =========================================================
# Helpers
# =========================================================

@dataclass(frozen=True)
class RunPlan:
    size: int
    teams_count: int


def _auto_teams_count(available_dogs: int, size: int) -> int:
    if size <= 0:
        return 0
    return available_dogs // size


def _pretty_layout(layout: str) -> str:
    return layout


# =========================================================
# CSS for top-down team schematic
# IMPORTANT: must be injected on EVERY rerun (Streamlit rebuilds DOM)
# =========================================================

def _inject_schematic_css() -> None:
    st.markdown(
        """
<style>
.ts-wrap {
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 14px;
  padding: 10px 12px 8px 12px;
  background: rgba(255,255,255,0.02);
  max-width: 620px;
  margin: 0 auto;
}

.ts-zone-title {
  font-size: 11px;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  opacity: 0.70;
  margin: 8px 0 4px 0;
}

.ts-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 4px 0;
}

.ts-conn {
  width: 140px;
  height: 2px;
  background: rgba(255,255,255,0.18);
  border-radius: 999px;
  flex: 0 0 140px;
}

.ts-dog {
  min-width: 86px;
  max-width: 180px;
  padding: 7px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(0,0,0,0.15);
  font-weight: 600;
  font-size: 13px;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ts-single {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 4px 0;
}

.ts-divider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 8px 0 4px 0;
}
</style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# Schematic rendering
# =========================================================

def _pair_rows(names: List[Optional[str]]) -> List[List[str]]:
    cleaned = [x for x in names if x]
    rows: List[List[str]] = []
    i = 0
    while i < len(cleaned):
        if i + 1 < len(cleaned):
            rows.append([cleaned[i], cleaned[i + 1]])
            i += 2
        else:
            rows.append([cleaned[i]])
            i += 1
    return rows


def _render_zone(title: str, names: List[Optional[str]]) -> str:
    rows = _pair_rows(names)
    if not rows:
        return f"<div class='ts-zone-title'>{title}</div><div style='opacity:0.6;'>—</div>"

    html: List[str] = [f"<div class='ts-zone-title'>{title}</div>"]
    for r in rows:
        if len(r) == 2:
            a, b = r
            html.append(
                "<div class='ts-row'>"
                f"<div class='ts-dog'>{a}</div>"
                "<div class='ts-conn'></div>"
                f"<div class='ts-dog'>{b}</div>"
                "</div>"
            )
        else:
            a = r[0]
            html.append(
                "<div class='ts-single'>"
                f"<div class='ts-dog'>{a}</div>"
                "</div>"
            )
    return "\n".join(html)


def _render_team_schematic(assignment: Dict[str, List[Optional[str]]]) -> None:
    _inject_schematic_css()

    lead_html = _render_zone("Lead", assignment.get("lead", []))
    team_html = _render_zone("Team", assignment.get("team", []))
    wheel_html = _render_zone("Wheel", assignment.get("wheel", []))

    st.markdown(
        f"""
<div class="ts-wrap">
  {lead_html}
  <div class="ts-divider"></div>
  {team_html}
  <div class="ts-divider"></div>
  {wheel_html}
</div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# Explainability
# =========================================================

def _render_breakdown(s: TeamSuggestion) -> None:
    if s.breakdown is None:
        return

    b = s.breakdown
    with st.expander("Why this score?", expanded=False):
        st.write(f"- Fatigue sum: **{b.fatigue_sum:.1f}**")
        st.write(f"- Conflicts penalty: **{b.conflict_penalty:.1f}**")
        st.write(f"- Pair split penalty: **{b.pair_penalty:.1f}** (splits: {b.pair_splits})")
        st.write(f"- Total score: **{b.total:.1f}**")


def _render_one_team(i: int, s: TeamSuggestion) -> None:
    st.markdown(
        f"### Team #{i} — layout **{_pretty_layout(s.plan.layout)}** "
        f"(score {s.score:.1f})"
    )

    _render_team_schematic(s.assignment)

    _render_breakdown(s)

    if s.notes:
        if any("invalid" in n.lower() or "conflict" in n.lower() for n in s.notes):
            st.error(" • ".join(s.notes))
        else:
            st.caption("Notes: " + " • ".join(s.notes))

    st.caption("Dogs (flat order)")
    st.write(", ".join(s.dogs))
    st.divider()


# =========================================================
# Selection logic
# =========================================================

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

    suggestions.sort(key=lambda x: x.score)
    return suggestions[0]


# =========================================================
# Main view
# =========================================================

def render_team_suggestions(dff: pd.DataFrame) -> None:
    st.subheader("Team suggestions")
    st.caption(
        "Demo: generate multiple teams using workload (fatigue) + roles + conflicts "
        "+ kennel pairs (soft). Dogs are not reused between teams."
    )

    hard_day = float(st.session_state.get("rf_hard_day", 18))
    hard_streak = int(st.session_state.get("rf_streak", 3))
    cfg = FatigueConfig(
        hard_day_threshold_km=hard_day,
        hard_streak_days=hard_streak,
    )

    all_dogs = sorted(dff["dog_name"].unique().tolist())
    available_raw = len(all_dogs)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        size = st.selectbox("Team size", [5, 6, 8, 10], index=1)
    with c2:
        planned_km = st.slider("Planned km today", 0, 60, 20, 1)
    with c3:
        keep_pairs = st.checkbox("Keep kennel pairs (soft)", True)
    with c4:
        age_rule = st.checkbox("Age rule: 8+ excluded if planned km > 20", True)

    max_date = dff["date"].max().date() if not dff.empty else Date.today()
    day = st.date_input("Planned run date", value=max_date)

    st.divider()

    cons = load_constraints()
    fatigue = compute_fatigue(day=day, cfg=cfg)
    pool = compute_pool_stats(
        profiles=cons.profiles,
        fatigue=fatigue,
        planned_km=float(planned_km),
        enforce_age_cap=age_rule,
        candidate_dogs=all_dogs,
    )

    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Total", pool.total)
    p2.metric("Lead", pool.lead)
    p3.metric("Center/Team", pool.team)
    p4.metric("Wheel", pool.wheel)
    p5.metric("Age 8+", pool.age8p)

    auto_cnt = _auto_teams_count(pool.total, size)
    if auto_cnt <= 0:
        st.warning("Not enough dogs for this team size.")
        return

    mode = st.radio("How many teams?", ["Auto", "Manual"], horizontal=True)
    if mode == "Auto":
        teams_count = auto_cnt
        st.info(f"Auto: will try to generate **{teams_count}** team(s).")
    else:
        teams_count = st.number_input(
            "Teams to generate",
            min_value=1,
            max_value=auto_cnt,
            value=min(3, auto_cnt),
            step=1,
        )

    st.divider()

    if not st.button("Generate teams"):
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

        if best is None and keep_pairs and failed_rounds < 1:
            failed_rounds += 1
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
        st.error("No teams could be generated.")
        return

    st.success(f"Generated {len(built)} team(s).")

    if len(built) < teams_count:
        from app.services.team_builder import _plans_for_size
        reasons = unmet_reasons(
            pool=pool,
            plans=_plans_for_size(size),
            requested_teams=int(teams_count),
        )
        st.warning("Could not build all requested teams.")
        for r in reasons:
            st.write(f"- {r}")

    for i, team in enumerate(built, start=1):
        _render_one_team(i, team)

    if remaining:
        st.subheader("Unused dogs")
        st.write(", ".join(sorted(remaining)))
