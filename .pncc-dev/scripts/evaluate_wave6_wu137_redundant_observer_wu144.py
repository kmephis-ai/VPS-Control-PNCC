#!/usr/bin/env python3
"""Read-only evaluator for PIPE-WU-144 WU137 scheduler-delivery observation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ROLE = "WAVE6_WU137_GITHUB_NATIVE_REDUNDANT_OBSERVER_RESULT"
CANONICAL_CRON_MINUTE = 17
CADENCE_SECONDS = 3600
BOUNDED_DELIVERY_LAG_MINUTES = 45
ROLLING_WINDOW_OPPORTUNITIES = 6
STABLE_CONSECUTIVE_OPPORTUNITIES = 4
REVIEW_CONSECUTIVE_MISSES = 3
ROLLING_DELIVERED_RATIO_THRESHOLD = 0.5
OBSERVATION_START = datetime(2026, 8, 31, 22, 17, tzinfo=timezone.utc)


class ProviderDataError(ValueError):
    """Raised when Provider Truth is malformed or contradictory."""


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProviderDataError(f"{field}: expected non-empty RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderDataError(f"{field}: invalid RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ProviderDataError(f"{field}: timezone is required")
    parsed = parsed.astimezone(timezone.utc)
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _matured_opportunities(observed_at: datetime) -> list[dict[str, datetime]]:
    current = observed_at.replace(minute=CANONICAL_CRON_MINUTE, second=0, microsecond=0)
    lag = timedelta(minutes=BOUNDED_DELIVERY_LAG_MINUTES)
    if current + lag > observed_at:
        current -= timedelta(seconds=CADENCE_SECONDS)

    opportunities: list[dict[str, datetime]] = []
    cursor = current
    while cursor >= OBSERVATION_START and len(opportunities) < ROLLING_WINDOW_OPPORTUNITIES:
        opportunities.append({"nominal_at": cursor, "deadline_at": cursor + lag})
        cursor -= timedelta(seconds=CADENCE_SECONDS)
    opportunities.reverse()
    return opportunities


def _normalize_runs(payload: dict[str, Any], observed_at: datetime) -> list[dict[str, Any]]:
    raw_runs = payload.get("workflow_runs")
    if not isinstance(raw_runs, list):
        raise ProviderDataError("workflow_runs: expected array")

    seen_ids: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, run in enumerate(raw_runs):
        if not isinstance(run, dict):
            raise ProviderDataError(f"workflow_runs[{index}]: expected object")

        run_id = run.get("id")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise ProviderDataError(f"workflow_runs[{index}].id: expected positive integer")
        if run_id in seen_ids:
            raise ProviderDataError(f"workflow_runs[{index}].id: duplicate run id {run_id}")
        seen_ids.add(run_id)

        if run.get("event") != "schedule":
            raise ProviderDataError(f"workflow_runs[{index}].event: expected schedule")

        status = run.get("status")
        if status not in {"queued", "in_progress", "completed"}:
            raise ProviderDataError(f"workflow_runs[{index}].status: unsupported status {status!r}")

        conclusion = run.get("conclusion")
        if status == "completed":
            if conclusion not in {
                "success",
                "failure",
                "cancelled",
                "timed_out",
                "action_required",
                "neutral",
                "skipped",
                "stale",
            }:
                raise ProviderDataError(
                    f"workflow_runs[{index}].conclusion: invalid terminal conclusion {conclusion!r}"
                )
        elif conclusion is not None:
            raise ProviderDataError(
                f"workflow_runs[{index}].conclusion: nonterminal run must have null conclusion"
            )

        created_at = _parse_utc(run.get("created_at"), f"workflow_runs[{index}].created_at")
        if created_at > observed_at:
            raise ProviderDataError(f"workflow_runs[{index}].created_at: future provider timestamp")

        normalized.append(
            {
                "id": run_id,
                "event": "schedule",
                "status": status,
                "conclusion": conclusion,
                "created_at": created_at,
                "head_sha": run.get("head_sha"),
            }
        )

    normalized.sort(key=lambda item: (item["created_at"], item["id"]))
    return normalized


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProviderDataError("input: expected object")

    observed_at = _parse_utc(payload.get("observed_at"), "observed_at")
    runs = _normalize_runs(payload, observed_at)
    opportunities = _matured_opportunities(observed_at)

    evaluated: list[dict[str, Any]] = []
    all_window_run_ids: set[int] = set()
    unhealthy_ids: list[int] = []
    nonterminal_ids: list[int] = []

    for opportunity in opportunities:
        nominal = opportunity["nominal_at"]
        deadline = opportunity["deadline_at"]
        window_runs = [
            run for run in runs if nominal <= run["created_at"] <= deadline
        ]
        for run in window_runs:
            all_window_run_ids.add(run["id"])

        healthy_runs = [
            run for run in window_runs
            if run["status"] == "completed" and run["conclusion"] == "success"
        ]
        unhealthy_runs = [
            run for run in window_runs
            if run["status"] == "completed" and run["conclusion"] != "success"
        ]
        nonterminal_runs = [
            run for run in window_runs if run["status"] != "completed"
        ]
        unhealthy_ids.extend(run["id"] for run in unhealthy_runs)
        nonterminal_ids.extend(run["id"] for run in nonterminal_runs)

        evaluated.append(
            {
                "nominal_at": _iso(nominal),
                "deadline_at": _iso(deadline),
                "healthy_delivered": bool(healthy_runs),
                "healthy_run_ids": [run["id"] for run in healthy_runs],
                "unhealthy_run_ids": [run["id"] for run in unhealthy_runs],
                "nonterminal_run_ids": [run["id"] for run in nonterminal_runs],
                "duplicate_healthy_run_count": max(0, len(healthy_runs) - 1),
            }
        )

    healthy_flags = [item["healthy_delivered"] for item in evaluated]
    healthy_count = sum(1 for flag in healthy_flags if flag)
    denominator = len(evaluated)
    ratio = (healthy_count / denominator) if denominator else None

    consecutive_misses = 0
    for flag in reversed(healthy_flags):
        if flag:
            break
        consecutive_misses += 1

    consecutive_healthy = 0
    for flag in reversed(healthy_flags):
        if not flag:
            break
        consecutive_healthy += 1

    rolling_ratio_trigger = (
        denominator == ROLLING_WINDOW_OPPORTUNITIES
        and ratio is not None
        and ratio < ROLLING_DELIVERED_RATIO_THRESHOLD
    )
    consecutive_miss_trigger = consecutive_misses >= REVIEW_CONSECUTIVE_MISSES
    stable = consecutive_healthy >= STABLE_CONSECUTIVE_OPPORTUNITIES

    if unhealthy_ids:
        state = "WU137_EXECUTION_UNHEALTHY_OBSERVED"
        recommended_action = "OWNER_REVIEW_NO_ACTIVATION"
    elif nonterminal_ids:
        state = "WU137_EXECUTION_NONTERMINAL_OBSERVED"
        recommended_action = "OWNER_REVIEW_NO_ACTIVATION"
    elif stable:
        state = "STABLE_DELIVERY_OBSERVED"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"
    elif consecutive_miss_trigger or rolling_ratio_trigger:
        state = "REMEDIATION_REVIEW_ELIGIBLE"
        recommended_action = "OWNER_REVIEW_NO_ACTIVATION"
    elif healthy_count >= 2:
        state = "RECOVERED_INTERMITTENT"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"
    elif healthy_count == 1:
        state = "RECOVERED_SINGLE"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"
    else:
        state = "NO_MATURED_HEALTHY_DELIVERY_OBSERVED"
        recommended_action = "OBSERVE_ONLY_NO_CHANGE"

    ignored_run_ids = [
        run["id"] for run in runs if run["id"] not in all_window_run_ids
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "observed_at": _iso(observed_at),
        "provider_truth_source": "GITHUB_ACTIONS_WU137_SCHEDULE_RUN_HISTORY_ONLY",
        "policy": {
            "canonical_cron_utc": "17 * * * *",
            "canonical_cadence_seconds": CADENCE_SECONDS,
            "bounded_delivery_lag_minutes": BOUNDED_DELIVERY_LAG_MINUTES,
            "rolling_window_opportunities": ROLLING_WINDOW_OPPORTUNITIES,
            "stable_consecutive_opportunities": STABLE_CONSECUTIVE_OPPORTUNITIES,
            "review_consecutive_misses": REVIEW_CONSECUTIVE_MISSES,
            "rolling_delivered_ratio_threshold": ROLLING_DELIVERED_RATIO_THRESHOLD,
            "observation_start_at": _iso(OBSERVATION_START),
        },
        "opportunities": evaluated,
        "healthy_delivered_opportunities": healthy_count,
        "matured_opportunity_count": denominator,
        "rolling_delivered_ratio": ratio,
        "consecutive_misses": consecutive_misses,
        "consecutive_healthy": consecutive_healthy,
        "rolling_ratio_trigger": rolling_ratio_trigger,
        "consecutive_miss_trigger": consecutive_miss_trigger,
        "unhealthy_run_ids": sorted(set(unhealthy_ids)),
        "nonterminal_run_ids": sorted(set(nonterminal_ids)),
        "ignored_run_ids": ignored_run_ids,
        "state": state,
        "recommended_action": recommended_action,
        "mutation_authority": False,
        "fallback_activation_authority": False,
        "wu137_mutation_authority": False,
        "external_scheduler_or_dispatch_authority": False,
    }


def _blocked_result(message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "state": "BLOCKED_PROVIDER_DATA",
        "reason": message,
        "recommended_action": "OWNER_REVIEW_NO_ACTIVATION",
        "mutation_authority": False,
        "fallback_activation_authority": False,
        "wu137_mutation_authority": False,
        "external_scheduler_or_dispatch_authority": False,
    }


def main(argv: list[str]) -> int:
    try:
        if len(argv) > 2:
            raise ProviderDataError("usage: evaluator [input.json]")
        if len(argv) == 2:
            payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        else:
            payload = json.load(sys.stdin)
        result = evaluate(payload)
    except (ProviderDataError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps(_blocked_result(str(exc)), indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
