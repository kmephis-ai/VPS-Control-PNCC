#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ROLE = "WAVE6_CROSS_WORKFLOW_SCHEDULER_DELIVERY_CORRELATION_RESULT"
EXPECTED_MAIN = "9d5f3cc3bc0482e0d953f786551eb1321cd951d6"
WU137_PATH = ".github/workflows/wave6-hbe-periodic-health-drift-wu137.yml"
WU144_PATH = ".github/workflows/wave6-wu137-redundant-observer-wu144.yml"
WU137_CRON_MINUTE = 17
WU144_CRON_MINUTE = 7
FIRST_WU144_NOMINAL = "2026-09-01T16:07:00Z"
FIRST_WU144_DEADLINE = "2026-09-01T16:52:00Z"
SECOND_WU144_NOMINAL = "2026-09-01T17:07:00Z"
SECOND_WU144_DEADLINE = "2026-09-01T17:52:00Z"
WU142_CLASSIFICATION = "INTERMITTENT_PROVIDER_SCHEDULER_DELIVERY"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

class ProviderDataError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ProviderDataError(f"DUPLICATE_KEY:{k}")
        out[k] = v
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, ProviderDataError) as exc:
        if isinstance(exc, ProviderDataError):
            raise
        raise ProviderDataError(f"INVALID_JSON:{type(exc).__name__}") from exc


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProviderDataError(f"TIMESTAMP_REQUIRED:{field}")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderDataError(f"TIMESTAMP_INVALID:{field}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ProviderDataError(f"TIMESTAMP_TIMEZONE_REQUIRED:{field}")
    return dt.astimezone(timezone.utc)


def _validate_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA40.fullmatch(value) is None:
        raise ProviderDataError(f"SHA40_REQUIRED:{field}")
    return value


def _validate_workflow(raw: Any, *, key: str, expected_path: str, expected_cron_minute: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProviderDataError(f"WORKFLOW_OBJECT_REQUIRED:{key}")
    required = {"name", "path", "cron_minute", "registered_on_default_branch", "runs"}
    if set(raw) != required:
        raise ProviderDataError(f"WORKFLOW_SHAPE_INVALID:{key}")
    if not isinstance(raw["name"], str) or not raw["name"]:
        raise ProviderDataError(f"WORKFLOW_NAME_INVALID:{key}")
    if raw["path"] != expected_path:
        raise ProviderDataError(f"WORKFLOW_PATH_MISMATCH:{key}")
    if raw["cron_minute"] != expected_cron_minute:
        raise ProviderDataError(f"WORKFLOW_CRON_MISMATCH:{key}")
    if raw["registered_on_default_branch"] is not True:
        raise ProviderDataError(f"WORKFLOW_NOT_DEFAULT_BRANCH_REGISTERED:{key}")
    if not isinstance(raw["runs"], list):
        raise ProviderDataError(f"WORKFLOW_RUNS_LIST_REQUIRED:{key}")
    return raw


def _normalize_runs(runs: list[Any], *, key: str, observed_at: datetime) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(runs):
        if not isinstance(raw, dict):
            raise ProviderDataError(f"RUN_OBJECT_REQUIRED:{key}:{i}")
        required = {"id", "event", "status", "conclusion", "created_at", "head_sha"}
        if set(raw) != required:
            raise ProviderDataError(f"RUN_SHAPE_INVALID:{key}:{i}")
        rid = raw["id"]
        if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0:
            raise ProviderDataError(f"RUN_ID_INVALID:{key}:{i}")
        if rid in seen:
            raise ProviderDataError(f"RUN_ID_DUPLICATE:{key}:{rid}")
        seen.add(rid)
        if raw["event"] != "schedule":
            raise ProviderDataError(f"RUN_EVENT_INVALID:{key}:{rid}")
        if raw["status"] not in {"queued", "in_progress", "completed"}:
            raise ProviderDataError(f"RUN_STATUS_INVALID:{key}:{rid}")
        if raw["status"] == "completed":
            if raw["conclusion"] not in {"success", "failure", "cancelled", "timed_out", "action_required", "neutral", "skipped", "stale"}:
                raise ProviderDataError(f"RUN_CONCLUSION_INVALID:{key}:{rid}")
        elif raw["conclusion"] is not None:
            raise ProviderDataError(f"RUN_NONTERMINAL_CONCLUSION_INVALID:{key}:{rid}")
        created = parse_time(raw["created_at"], f"{key}.runs[{i}].created_at")
        if created > observed_at:
            raise ProviderDataError(f"RUN_FUTURE_TIMESTAMP:{key}:{rid}")
        sha = _validate_sha(raw["head_sha"], f"{key}.runs[{i}].head_sha")
        out.append({**raw, "created_dt": created, "head_sha": sha})
    out.sort(key=lambda r: (r["created_dt"], r["id"]))
    return out


def evaluate(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProviderDataError("INPUT_OBJECT_REQUIRED")
    required = {"observed_at", "main_sha", "wu142_classification", "wu137", "wu144"}
    if set(payload) != required:
        raise ProviderDataError("INPUT_SHAPE_INVALID")
    observed = parse_time(payload["observed_at"], "observed_at")
    main_sha = _validate_sha(payload["main_sha"], "main_sha")
    if main_sha != EXPECTED_MAIN:
        raise ProviderDataError("MAIN_SHA_DRIFT")
    if payload["wu142_classification"] != WU142_CLASSIFICATION:
        raise ProviderDataError("WU142_CLASSIFICATION_DRIFT")

    wu137 = _validate_workflow(payload["wu137"], key="wu137", expected_path=WU137_PATH, expected_cron_minute=WU137_CRON_MINUTE)
    wu144 = _validate_workflow(payload["wu144"], key="wu144", expected_path=WU144_PATH, expected_cron_minute=WU144_CRON_MINUTE)
    if wu137["path"] == wu144["path"] or wu137["name"] == wu144["name"]:
        raise ProviderDataError("WORKFLOW_INDEPENDENCE_NOT_PROVEN")

    r137 = _normalize_runs(wu137["runs"], key="wu137", observed_at=observed)
    r144 = _normalize_runs(wu144["runs"], key="wu144", observed_at=observed)
    nominal = parse_time(FIRST_WU144_NOMINAL, "first_nominal")
    deadline = parse_time(FIRST_WU144_DEADLINE, "first_deadline")
    if observed < deadline:
        state = "WAITING_MATURE_OBSERVATION_WINDOW"
        correlated = False
        recommendation = "OBSERVE_ONLY_NO_CHANGE"
    else:
        within = [x for x in r144 if nominal <= x["created_dt"] <= deadline]
        if within:
            raise ProviderDataError("WU144_FIRST_MATURED_MISS_CONTRADICTED")
        healthy137 = [x for x in r137 if x["status"] == "completed" and x["conclusion"] == "success"]
        unhealthy137 = [x for x in r137 if x["status"] == "completed" and x["conclusion"] != "success"]
        nonterminal137 = [x for x in r137 if x["status"] != "completed"]
        if unhealthy137:
            state = "WU137_EXECUTION_UNHEALTHY_OBSERVED"
            correlated = False
            recommendation = "OWNER_REVIEW_NO_ACTIVATION"
        elif nonterminal137:
            state = "WU137_EXECUTION_NONTERMINAL_OBSERVED"
            correlated = False
            recommendation = "OWNER_REVIEW_NO_ACTIVATION"
        elif not healthy137:
            state = "INSUFFICIENT_WU137_DELIVERY_EVIDENCE"
            correlated = False
            recommendation = "OBSERVE_ONLY_NO_CHANGE"
        else:
            state = "CROSS_WORKFLOW_SCHEDULE_DELIVERY_DEGRADATION_CORRELATED"
            correlated = True
            recommendation = "OWNER_REVIEW_NO_ACTIVATION"

    second_nominal = parse_time(SECOND_WU144_NOMINAL, "second_nominal")
    second_deadline = parse_time(SECOND_WU144_DEADLINE, "second_deadline")
    second_window_ids = [x["id"] for x in r144 if second_nominal <= x["created_dt"] <= second_deadline]
    late144 = [x["id"] for x in r144 if x["created_dt"] > deadline]
    healthy137_ids = [x["id"] for x in r137 if x["status"] == "completed" and x["conclusion"] == "success"]
    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "observed_at": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": state,
        "correlation": {
            "repository_local_cross_workflow_correlation": correlated,
            "distinct_workflow_paths_proven": True,
            "distinct_cron_minutes_proven": True,
            "wu144_first_matured_delivery_miss_proven": observed >= deadline and not any(nominal <= x["created_dt"] <= deadline for x in r144),
            "wu144_second_matured_delivery_miss_proven": observed >= second_deadline and not second_window_ids,
            "wu137_delivery_healthy_when_delivered": bool(healthy137_ids),
            "provider_root_cause_proven": False,
            "global_github_outage_proven": False,
        },
        "evidence": {
            "wu137_healthy_schedule_run_ids": healthy137_ids,
            "wu144_first_nominal_at": FIRST_WU144_NOMINAL,
            "wu144_first_deadline_at": FIRST_WU144_DEADLINE,
            "wu144_second_nominal_at": SECOND_WU144_NOMINAL,
            "wu144_second_deadline_at": SECOND_WU144_DEADLINE,
            "wu144_second_window_run_ids": second_window_ids,
            "wu144_late_run_ids_after_first_deadline": late144,
            "wu142_predecessor_classification": WU142_CLASSIFICATION,
        },
        "recommended_action": recommendation,
        "authority": {
            "mutation_authority": False,
            "scheduler_mutation_authority": False,
            "fallback_activation_authority": False,
            "workflow_dispatch_authority": False,
            "repository_dispatch_authority": False,
            "external_scheduler_or_webhook_authority": False,
            "runtime_action_authority": False,
            "product_runtime_mutation_authority": False,
            "ruleset_mutation_authority": False,
            "release_tag_promotion_authority": False,
            "reserve_1080_lifecycle_mutation_authority": False,
            "primary_1081_lifecycle_mutation_authority": False,
            "v631_mutation_authority": False,
            "force_or_bypass_authority": False,
        },
        "next_boundary": "OWNER_REVIEW_NO_ACTIVATION" if recommendation == "OWNER_REVIEW_NO_ACTIVATION" else "FRESH_PROVIDER_TRUTH_REOBSERVATION",
    }


def blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "state": "BLOCKED_PROVIDER_DATA",
        "reason": reason,
        "recommended_action": "OWNER_REVIEW_NO_ACTIVATION",
        "authority": {
            "mutation_authority": False,
            "scheduler_mutation_authority": False,
            "fallback_activation_authority": False,
            "workflow_dispatch_authority": False,
            "repository_dispatch_authority": False,
            "external_scheduler_or_webhook_authority": False,
            "runtime_action_authority": False,
            "product_runtime_mutation_authority": False,
            "reserve_1080_lifecycle_mutation_authority": False,
            "primary_1081_lifecycle_mutation_authority": False,
            "v631_mutation_authority": False,
            "force_or_bypass_authority": False,
        },
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input")
    args = p.parse_args(argv[1:])
    try:
        result = evaluate(load_json(Path(args.input)))
    except ProviderDataError as exc:
        print(json.dumps(blocked(str(exc)), indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
