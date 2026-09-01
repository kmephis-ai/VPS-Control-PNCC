#!/usr/bin/env python3
"""Read-only Provider Truth qualification for the PIPE-WU-144 redundant observer."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WU144_EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_wave6_wu137_redundant_observer_wu144.py"

SCHEMA_VERSION = 1
ROLE = "WAVE6_WU144_PROVIDER_DELIVERY_QUALIFICATION_RESULT"
OBSERVER_CRON_MINUTE = 7
OBSERVER_CADENCE_SECONDS = 3600
OBSERVER_DELIVERY_LAG_MINUTES = 45
OBSERVER_ACTIVATED_AT = datetime(2026, 9, 1, 15, 12, 58, tzinfo=timezone.utc)
FIRST_OBSERVER_NOMINAL_AT = datetime(2026, 9, 1, 16, 7, 0, tzinfo=timezone.utc)
PROVIDER_SNAPSHOT_MAX_AGE_SECONDS = 300
ROLLING_OBSERVER_OPPORTUNITIES = 6


class QualificationError(ValueError):
    """Raised when qualification input is malformed, stale, or contradictory."""


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise QualificationError(f"{field}: expected non-empty RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QualificationError(f"{field}: invalid RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise QualificationError(f"{field}: timezone is required")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_wu144_evaluator():
    spec = importlib.util.spec_from_file_location("pncc_wu144_evaluator", WU144_EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise QualificationError("wu144_evaluator: import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_runs(raw_runs: Any, observed_at: datetime, field: str) -> list[dict[str, Any]]:
    if not isinstance(raw_runs, list):
        raise QualificationError(f"{field}: expected array")

    seen_ids: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, run in enumerate(raw_runs):
        prefix = f"{field}[{index}]"
        if not isinstance(run, dict):
            raise QualificationError(f"{prefix}: expected object")
        run_id = run.get("id")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise QualificationError(f"{prefix}.id: expected positive integer")
        if run_id in seen_ids:
            raise QualificationError(f"{prefix}.id: duplicate run id {run_id}")
        seen_ids.add(run_id)
        if run.get("event") != "schedule":
            raise QualificationError(f"{prefix}.event: expected schedule")
        status = run.get("status")
        if status not in {"queued", "in_progress", "completed"}:
            raise QualificationError(f"{prefix}.status: unsupported status {status!r}")
        conclusion = run.get("conclusion")
        if status == "completed":
            if conclusion not in {
                "success", "failure", "cancelled", "timed_out", "action_required",
                "neutral", "skipped", "stale",
            }:
                raise QualificationError(f"{prefix}.conclusion: invalid terminal conclusion {conclusion!r}")
        elif conclusion is not None:
            raise QualificationError(f"{prefix}.conclusion: nonterminal run must have null conclusion")
        created_at = _parse_utc(run.get("created_at"), f"{prefix}.created_at")
        if created_at > observed_at:
            raise QualificationError(f"{prefix}.created_at: future provider timestamp")
        head_sha = run.get("head_sha")
        if head_sha is not None and (not isinstance(head_sha, str) or len(head_sha) != 40):
            raise QualificationError(f"{prefix}.head_sha: expected 40-character sha or null")
        normalized.append({
            "id": run_id,
            "event": "schedule",
            "status": status,
            "conclusion": conclusion,
            "created_at": created_at,
            "head_sha": head_sha,
        })
    normalized.sort(key=lambda item: (item["created_at"], item["id"]))
    return normalized


def _observer_opportunities(observed_at: datetime) -> tuple[list[dict[str, datetime]], dict[str, datetime] | None]:
    lag = timedelta(minutes=OBSERVER_DELIVERY_LAG_MINUTES)
    if observed_at < FIRST_OBSERVER_NOMINAL_AT:
        return [], {"nominal_at": FIRST_OBSERVER_NOMINAL_AT, "deadline_at": FIRST_OBSERVER_NOMINAL_AT + lag}

    current = observed_at.replace(minute=OBSERVER_CRON_MINUTE, second=0, microsecond=0)
    if current > observed_at:
        current -= timedelta(seconds=OBSERVER_CADENCE_SECONDS)
    if current < FIRST_OBSERVER_NOMINAL_AT:
        current = FIRST_OBSERVER_NOMINAL_AT

    immature: dict[str, datetime] | None = None
    if current + lag > observed_at:
        immature = {"nominal_at": current, "deadline_at": current + lag}
        current -= timedelta(seconds=OBSERVER_CADENCE_SECONDS)

    matured: list[dict[str, datetime]] = []
    while current >= FIRST_OBSERVER_NOMINAL_AT and len(matured) < ROLLING_OBSERVER_OPPORTUNITIES:
        matured.append({"nominal_at": current, "deadline_at": current + lag})
        current -= timedelta(seconds=OBSERVER_CADENCE_SECONDS)
    matured.reverse()
    return matured, immature


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QualificationError("input: expected object")

    observed_at = _parse_utc(payload.get("observed_at"), "observed_at")
    provider_fetched_at = _parse_utc(payload.get("provider_fetched_at"), "provider_fetched_at")
    snapshot_age = (observed_at - provider_fetched_at).total_seconds()
    if snapshot_age < 0:
        raise QualificationError("provider_fetched_at: future provider snapshot timestamp")
    if snapshot_age > PROVIDER_SNAPSHOT_MAX_AGE_SECONDS:
        raise QualificationError(
            f"provider_fetched_at: stale provider snapshot age {int(snapshot_age)}s exceeds {PROVIDER_SNAPSHOT_MAX_AGE_SECONDS}s"
        )

    observer_runs = _normalize_runs(payload.get("observer_workflow_runs"), observed_at, "observer_workflow_runs")
    wu137_runs = payload.get("wu137_workflow_runs")
    if not isinstance(wu137_runs, list):
        raise QualificationError("wu137_workflow_runs: expected array")

    matured, immature = _observer_opportunities(observed_at)
    evaluated: list[dict[str, Any]] = []
    assigned_ids: set[int] = set()
    unhealthy_ids: list[int] = []
    nonterminal_ids: list[int] = []

    for opportunity in matured:
        nominal = opportunity["nominal_at"]
        deadline = opportunity["deadline_at"]
        window_runs = [run for run in observer_runs if nominal <= run["created_at"] <= deadline]
        assigned_ids.update(run["id"] for run in window_runs)
        healthy = [run for run in window_runs if run["status"] == "completed" and run["conclusion"] == "success"]
        unhealthy = [run for run in window_runs if run["status"] == "completed" and run["conclusion"] != "success"]
        nonterminal = [run for run in window_runs if run["status"] != "completed"]
        unhealthy_ids.extend(run["id"] for run in unhealthy)
        nonterminal_ids.extend(run["id"] for run in nonterminal)
        evaluated.append({
            "nominal_at": _iso(nominal),
            "deadline_at": _iso(deadline),
            "healthy_delivered": bool(healthy),
            "healthy_run_ids": [run["id"] for run in healthy],
            "unhealthy_run_ids": [run["id"] for run in unhealthy],
            "nonterminal_run_ids": [run["id"] for run in nonterminal],
            "duplicate_healthy_run_count": max(0, len(healthy) - 1),
        })

    flags = [item["healthy_delivered"] for item in evaluated]
    consecutive_misses = 0
    for flag in reversed(flags):
        if flag:
            break
        consecutive_misses += 1

    if unhealthy_ids:
        observer_state = "OBSERVER_EXECUTION_UNHEALTHY_OBSERVED"
        recommended_action = "OWNER_REVIEW_NO_ACTIVATION"
    elif nonterminal_ids:
        observer_state = "OBSERVER_EXECUTION_NONTERMINAL_OBSERVED"
        recommended_action = "OBSERVE_UNTIL_TERMINAL_NO_CHANGE"
    elif not matured:
        observer_state = "WAITING_MATURE_OBSERVATION_WINDOW"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"
    elif flags and flags[-1]:
        observer_state = "OBSERVER_DELIVERY_HEALTHY"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"
    else:
        observer_state = "OBSERVER_DELIVERY_MISS_OBSERVED"
        recommended_action = "OWNER_REVIEW_NO_ACTIVATION"

    wu144 = _load_wu144_evaluator()
    try:
        wu137_result = wu144.evaluate({
            "observed_at": _iso(observed_at),
            "workflow_runs": wu137_runs,
        })
    except Exception as exc:  # WU144 has its own strict ProviderDataError type.
        raise QualificationError(f"wu137_provider_truth: {exc}") from exc

    ignored_observer_run_ids = [run["id"] for run in observer_runs if run["id"] not in assigned_ids]
    immature_output = None
    if immature is not None:
        immature_output = {
            "nominal_at": _iso(immature["nominal_at"]),
            "deadline_at": _iso(immature["deadline_at"]),
            "deadline_matured": False,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "observed_at": _iso(observed_at),
        "provider_fetched_at": _iso(provider_fetched_at),
        "provider_snapshot_age_seconds": int(snapshot_age),
        "provider_truth_source": "GITHUB_ACTIONS_SCHEDULE_RUN_HISTORY_READ_ONLY",
        "observer_policy": {
            "workflow": "wave6-wu137-redundant-observer-wu144",
            "activated_at": _iso(OBSERVER_ACTIVATED_AT),
            "first_nominal_at": _iso(FIRST_OBSERVER_NOMINAL_AT),
            "canonical_cron_utc": "7 * * * *",
            "canonical_cadence_seconds": OBSERVER_CADENCE_SECONDS,
            "bounded_delivery_lag_minutes": OBSERVER_DELIVERY_LAG_MINUTES,
            "provider_snapshot_max_age_seconds": PROVIDER_SNAPSHOT_MAX_AGE_SECONDS,
            "rolling_observer_opportunities": ROLLING_OBSERVER_OPPORTUNITIES,
        },
        "matured_observer_opportunities": evaluated,
        "matured_observer_opportunity_count": len(evaluated),
        "immature_observer_opportunity": immature_output,
        "observer_consecutive_misses": consecutive_misses,
        "observer_unhealthy_run_ids": sorted(set(unhealthy_ids)),
        "observer_nonterminal_run_ids": sorted(set(nonterminal_ids)),
        "ignored_observer_run_ids": ignored_observer_run_ids,
        "observer_state": observer_state,
        "wu137_delivery_observation": wu137_result,
        "state": observer_state,
        "recommended_action": recommended_action,
        "mutation_authority": False,
        "scheduler_mutation_authority": False,
        "fallback_activation_authority": False,
        "runtime_action_authority": False,
        "product_runtime_mutation_authority": False,
        "reserve_1080_lifecycle_mutation_authority": False,
        "primary_1081_lifecycle_mutation_authority": False,
    }


def _blocked_result(message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "state": "BLOCKED_PROVIDER_DATA",
        "reason": message,
        "recommended_action": "OWNER_REVIEW_NO_ACTIVATION",
        "mutation_authority": False,
        "scheduler_mutation_authority": False,
        "fallback_activation_authority": False,
        "runtime_action_authority": False,
        "product_runtime_mutation_authority": False,
        "reserve_1080_lifecycle_mutation_authority": False,
        "primary_1081_lifecycle_mutation_authority": False,
    }


def main(argv: list[str]) -> int:
    try:
        if len(argv) > 2:
            raise QualificationError("usage: evaluator [input.json]")
        if len(argv) == 2:
            payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        else:
            payload = json.load(sys.stdin)
        result = evaluate(payload)
    except (QualificationError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps(_blocked_result(str(exc)), indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
