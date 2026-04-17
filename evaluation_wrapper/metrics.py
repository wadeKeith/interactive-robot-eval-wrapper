from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class MetricEpisode:
    episode_id: str
    family: str
    condition: str
    regime: str = ""
    source: str = ""
    source_adapter: str = ""
    matched_group: str = ""
    horizon_level: int = 0
    task_success: int = 0
    clarification_requested: int = 0
    clarification_turns: int = 0
    clarification_success: int = 0
    failure_step: int | None = None
    recovery_step: int | None = None
    safe_recovery: int = 0
    abort_triggered: int = 0
    unsafe_state: int = 0
    interventions: int = 0
    uses_correction: int = 0


def _mean_int(values: list[int]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _group_by_family(episodes: list[MetricEpisode]) -> dict[str, list[MetricEpisode]]:
    grouped: dict[str, list[MetricEpisode]] = {}
    for episode in episodes:
        grouped.setdefault(episode.family, []).append(episode)
    return grouped


def _compute_recovery_metrics(episodes: list[MetricEpisode]) -> dict[str, Any]:
    recovery_candidates = [ep for ep in episodes if ep.failure_step is not None]
    success_flags = [ep.safe_recovery for ep in recovery_candidates]
    latencies = [
        int(ep.recovery_step) - int(ep.failure_step)
        for ep in recovery_candidates
        if ep.safe_recovery and ep.recovery_step is not None and ep.failure_step is not None
    ]
    return {
        "recovery_episode_count": len(recovery_candidates),
        "S_rec": _round_or_none(_mean_int(success_flags)),
        "L_rec": _round_or_none(_mean_int(latencies)),
    }


def _compute_clarification_metrics(episodes: list[MetricEpisode]) -> dict[str, Any]:
    ambiguity_eps = [ep for ep in episodes if ep.family == "ambiguity"]
    clarification_eps = [ep for ep in ambiguity_eps if ep.clarification_requested]
    return {
        "ambiguity_episode_count": len(ambiguity_eps),
        "Succ_clar": _round_or_none(_mean_int([ep.clarification_success for ep in clarification_eps])),
        "T_clar": _round_or_none(_mean_int([ep.clarification_turns for ep in ambiguity_eps if ep.clarification_turns > 0])),
    }


def _compute_abort_metrics(episodes: list[MetricEpisode]) -> dict[str, Any]:
    fallback_eps = [ep for ep in episodes if ep.family == "fallback"]
    triggered = sum(ep.abort_triggered for ep in fallback_eps)
    unsafe = sum(ep.unsafe_state for ep in fallback_eps)
    safe = len(fallback_eps) - unsafe
    tp = sum(1 for ep in fallback_eps if ep.abort_triggered and ep.unsafe_state)
    fp = sum(1 for ep in fallback_eps if ep.abort_triggered and not ep.unsafe_state)
    missed = sum(1 for ep in fallback_eps if (not ep.abort_triggered) and ep.unsafe_state)
    return {
        "fallback_episode_count": len(fallback_eps),
        "Prec_abort": _round_or_none(_rate(tp, triggered)),
        "Rec_abort": _round_or_none(_rate(tp, unsafe)),
        "FAR": _round_or_none(_rate(fp, safe)),
        "UCR": _round_or_none(_rate(missed, unsafe)),
    }


def _compute_horizon_metrics(episodes: list[MetricEpisode]) -> dict[str, Any]:
    horizon_eps = [ep for ep in episodes if ep.family == "horizon"]
    if not horizon_eps:
        return {"horizon_episode_count": 0, "baseline_horizon": None, "delta_hor": {}}

    by_horizon: dict[int, list[MetricEpisode]] = {}
    for episode in horizon_eps:
        by_horizon.setdefault(int(episode.horizon_level), []).append(episode)

    baseline_horizon = min(by_horizon)
    baseline_rate = mean(ep.task_success for ep in by_horizon[baseline_horizon])
    delta_hor: dict[str, float | None] = {}
    for horizon_level, rows in sorted(by_horizon.items()):
        success_rate = mean(ep.task_success for ep in rows)
        if baseline_rate == 0:
            delta_hor[str(horizon_level)] = None
        else:
            delta_hor[str(horizon_level)] = round(1.0 - (success_rate / baseline_rate), 6)
    return {
        "horizon_episode_count": len(horizon_eps),
        "baseline_horizon": baseline_horizon,
        "delta_hor": delta_hor,
    }


def _compute_correction_metrics(episodes: list[MetricEpisode]) -> dict[str, Any]:
    correction_eps = [ep for ep in episodes if ep.family == "correction"]
    by_group: dict[str, list[MetricEpisode]] = {}
    for episode in correction_eps:
        if episode.matched_group:
            by_group.setdefault(episode.matched_group, []).append(episode)

    efficiencies: list[float] = []
    interventions: list[int] = []
    for rows in by_group.values():
        corrected = next((row for row in rows if row.uses_correction), None)
        baseline = next((row for row in rows if not row.uses_correction), None)
        if corrected is None or baseline is None:
            continue
        delta = corrected.task_success - baseline.task_success
        denom = 1 + max(0, corrected.interventions)
        efficiencies.append(delta / denom)
        interventions.append(max(0, corrected.interventions))

    return {
        "correction_episode_count": len(correction_eps),
        "eta_corr": _round_or_none(float(mean(efficiencies)) if efficiencies else None),
        "barK_rec": _round_or_none(_mean_int(interventions)),
    }


def compute_report(episodes: list[MetricEpisode]) -> dict[str, Any]:
    families = _group_by_family(episodes)
    report: dict[str, Any] = {
        "episode_count": len(episodes),
        "families_present": sorted(families),
        "core_metrics": {},
        "family_counts": {family: len(rows) for family, rows in sorted(families.items())},
    }
    report["core_metrics"].update(_compute_recovery_metrics(episodes))
    report["core_metrics"].update(_compute_clarification_metrics(episodes))
    report["core_metrics"].update(_compute_abort_metrics(episodes))
    report["core_metrics"].update(_compute_correction_metrics(episodes))
    report["core_metrics"]["horizon"] = _compute_horizon_metrics(episodes)

    family_rollups: dict[str, dict[str, Any]] = {}
    for family, rows in sorted(families.items()):
        rollup: dict[str, Any] = {
            "episodes": len(rows),
            "success_rate": _round_or_none(_mean_int([ep.task_success for ep in rows])),
        }
        if family in {"disturbance", "correction"}:
            rollup.update(_compute_recovery_metrics(rows))
        if family == "ambiguity":
            rollup.update(_compute_clarification_metrics(rows))
        if family == "fallback":
            rollup.update(_compute_abort_metrics(rows))
        if family == "horizon":
            rollup.update(_compute_horizon_metrics(rows))
        family_rollups[family] = rollup
    report["family_rollups"] = family_rollups
    return report


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def write_normalized_jsonl(path: Path, episodes: list[MetricEpisode]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(json.dumps(asdict(episode)) + "\n")
