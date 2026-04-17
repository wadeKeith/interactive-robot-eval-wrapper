from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metrics import MetricEpisode


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_normalized_jsonl(path: Path) -> list[MetricEpisode]:
    return [MetricEpisode(**row) for row in _load_jsonl(path)]


def _scenario_group(scenario_id: str, family: str) -> str:
    suffix = scenario_id.split("_")[-1]
    return f"{family}:{suffix}"


def adapt_interactionbench_micro_results(results_path: Path, scenarios_path: Path) -> list[MetricEpisode]:
    results = _load_jsonl(results_path)
    scenarios = {row["scenario_id"]: row for row in _load_json(scenarios_path)}
    episodes: list[MetricEpisode] = []

    family_map = {
        "instruction_ambiguity": "ambiguity",
        "disturbance_recovery": "disturbance",
        "world_model_horizon": "horizon",
        "fallback_under_uncertainty": "fallback",
        "user_correction": "correction",
    }

    for row in results:
        scenario = scenarios[row["scenario_id"]]
        family = family_map[row["task_family"]]
        matched_group = _scenario_group(row["scenario_id"], family)
        clarification_requested = 1 if row["clarification_success"] != "" else 0
        clarification_success = int(row["clarification_success"]) if row["clarification_success"] != "" else 0
        clarification_turns = 1 if clarification_requested else 0

        failure_step = None
        recovery_step = None
        safe_recovery = 0
        if row["recovery_success"] != "":
            failure_step = 0
            safe_recovery = int(row["recovery_success"])
            if row["latency_to_recovery"] != "":
                recovery_step = int(row["latency_to_recovery"])
        elif row["post_correction_success"] != "":
            failure_step = 0
            safe_recovery = int(row["post_correction_success"])
            if row["interventions_to_recover"] != "":
                recovery_step = int(row["interventions_to_recover"])

        unsafe_state = 1 if scenario.get("fallback_required") else 0
        abort_triggered = int(row["fallback_triggered"]) if row["fallback_triggered"] != "" else 0
        interventions = int(row["interventions_to_recover"]) if row["interventions_to_recover"] != "" else 0
        uses_correction = 1 if scenario.get("correction_after_onset") else 0

        episodes.append(
            MetricEpisode(
                episode_id=f"{row['adapter']}::{row['scenario_id']}",
                family=family,
                condition="stressed" if "stressed" in row["scenario_id"] else "nominal",
                regime=row["regime"],
                source="interactionbench_micro",
                source_adapter=row["adapter"],
                matched_group=matched_group,
                horizon_level=int(scenario.get("horizon_level", 0)),
                task_success=int(row["nominal_success"]),
                clarification_requested=clarification_requested,
                clarification_turns=clarification_turns,
                clarification_success=clarification_success,
                failure_step=failure_step,
                recovery_step=recovery_step,
                safe_recovery=safe_recovery,
                abort_triggered=abort_triggered,
                unsafe_state=unsafe_state,
                interventions=interventions,
                uses_correction=uses_correction,
            )
        )
    return episodes


def _first_success_step(trace: list[dict[str, Any]], start_step: int | None) -> int | None:
    if start_step is None:
        return None
    for step in trace:
        index = int(step.get("step_index", -1))
        if index >= start_step and int(step.get("success", 0)) == 1:
            return index
    return None


def adapt_closed_loop_jsonl(results_path: Path) -> list[MetricEpisode]:
    rows = _load_jsonl(results_path)
    episodes: list[MetricEpisode] = []
    for row in rows:
        family = str(row["family"])
        variant = int(row.get("variant", 0))
        matched_group = f"{family}:{variant}"
        trace = row.get("trace", [])

        failure_step = None
        recovery_step = None
        safe_recovery = 0
        abort_triggered = 0
        unsafe_state = 0
        interventions = 0
        uses_correction = 0

        if family == "disturbance" and row.get("condition") == "bumped":
            failure_step = row.get("disturbance_step")
            recovery_step = _first_success_step(trace, failure_step)
            safe_recovery = int(row.get("recovery_success", 0))
        elif family == "correction":
            if row.get("condition") == "redirected":
                failure_step = row.get("correction_step")
                if row.get("correction_latency_steps", "") != "" and failure_step is not None:
                    recovery_step = int(failure_step) + int(row["correction_latency_steps"])
                else:
                    recovery_step = _first_success_step(trace, failure_step)
                safe_recovery = int(row.get("post_correction_success", 0))
                interventions = 1 if int(row.get("correction_applied", 0)) else 0
                uses_correction = 1
        elif family == "fallback":
            unsafe_state = 1 if row.get("condition") == "missing" else 0
            abort_triggered = int(row.get("safe_stop_confirmed", 0))

        episodes.append(
            MetricEpisode(
                episode_id=row["episode_id"],
                family=family,
                condition=str(row.get("condition", "")),
                regime=str(row.get("backend", "")),
                source="closed_loop_jsonl",
                source_adapter=str(row.get("model_path", "")),
                matched_group=matched_group,
                task_success=int(row.get("task_success", 0)),
                failure_step=int(failure_step) if failure_step is not None else None,
                recovery_step=int(recovery_step) if recovery_step is not None else None,
                safe_recovery=safe_recovery,
                abort_triggered=abort_triggered,
                unsafe_state=unsafe_state,
                interventions=interventions,
                uses_correction=uses_correction,
            )
        )
    return episodes
