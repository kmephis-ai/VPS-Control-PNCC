#!/usr/bin/env python3
"""Deterministic PLAN_ONLY governed PNCC Work Unit materialization planner."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev/contracts/governed-work-unit-materialization-policy.json"
FRONTIER_PATH = ROOT / ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json"
SELECTOR_PATH = ROOT / ".pncc-dev/scripts/select_provider_work_unit.py"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class MaterializationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def load_selector():
    spec = importlib.util.spec_from_file_location("pncc_provider_selector", SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise MaterializationError("SELECTOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blocked(*reasons: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_PLAN",
        "decision": "BLOCKED",
        "reasons": list(reasons),
        "proposal": None,
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
    }


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schema_version") != 1 or policy.get("role") != "GOVERNED_WORK_UNIT_MATERIALIZATION_POLICY":
        errors.append("POLICY_IDENTITY_INVALID")
    if policy.get("mode") != "PLAN_ONLY_DEFAULT_DENY":
        errors.append("POLICY_MODE_INVALID")
    exact = {
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "work_unit_prefix": "PIPE-WU-",
        "required_selector_disposition": "NO_WORK",
        "required_marker_state": "READY",
        "open_canonical_work_unit_policy": "BLOCK_ANY_OPEN_CANONICAL_WORK_UNIT",
        "malformed_marker_policy": "BLOCK_FAIL_CLOSED",
        "next_id_policy": "MAX_HISTORICAL_PIPE_WU_SUFFIX_PLUS_ONE",
        "frontier_state_policy": "ACTIVE_OR_NONE",
        "anchor_drift_behavior": "BLOCK_FAIL_CLOSED",
        "next_boundary_if_eligible": "SEPARATE_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY_PREPARATION",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            errors.append(f"POLICY_FIELD_INVALID:{key}")
    for key in (
        "runtime_required_must_be_false",
        "provider_truth_fresh_required",
        "complete_issue_history_required",
        "proposal_must_be_deterministic",
    ):
        if policy.get(key) is not True:
            errors.append(f"POLICY_REQUIRED_TRUE:{key}")
    for key in (
        "issue_create_authority",
        "issue_update_authority",
        "issue_close_authority",
        "branch_mutation_authority",
        "provider_state_mutation_authority",
        "writer_lease_mutation_authority",
        "autonomous_merge_authority",
        "runtime_action_authority",
        "product_runtime_mutation_authority",
        "adwf_binding_mutation_authority",
        "release_tag_promotion_authority",
        "ruleset_policy_administration_authority",
        "private_evidence_publication_authority",
        "reserve_1080_lifecycle_mutation_authority",
        "primary_1081_lifecycle_mutation_authority",
    ):
        if policy.get(key) is not False:
            errors.append(f"POLICY_FORBIDDEN_AUTHORITY:{key}")
    paths = policy.get("anchor_paths")
    blobs = policy.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs):
        errors.append("POLICY_ANCHOR_MAP_INVALID")
    return errors


def validate_anchor_map(policy: dict[str, Any], blob_reader=git_blob_sha) -> list[str]:
    errors: list[str] = []
    paths = policy.get("anchor_paths")
    blobs = policy.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs):
        return ["POLICY_ANCHOR_MAP_INVALID"]
    for key in sorted(paths):
        rel = paths[key]
        expected = blobs[key]
        if not isinstance(rel, str) or not isinstance(expected, str):
            errors.append(f"ANCHOR_INVALID:{key}")
            continue
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"ANCHOR_MISSING:{key}")
            continue
        actual = blob_reader(path)
        if actual != expected:
            errors.append(f"ANCHOR_DRIFT:{key}:{expected}:{actual}")
    return errors


def validate_frontier(frontier: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if frontier.get("schema_version") != 1 or frontier.get("role") != "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER":
        errors.append("FRONTIER_IDENTITY_INVALID")
        return errors
    state = frontier.get("state")
    if state not in {"ACTIVE", "NONE"}:
        errors.append("FRONTIER_STATE_INVALID")
        return errors
    if state == "NONE":
        return errors
    required_text = ("frontier_id", "title_template", "goal", "conflict_domain", "next_natural_boundary")
    for key in required_text:
        if not isinstance(frontier.get(key), str) or not frontier[key].strip():
            errors.append(f"FRONTIER_FIELD_INVALID:{key}")
    if "{work_unit_id}" not in str(frontier.get("title_template", "")):
        errors.append("FRONTIER_TITLE_TEMPLATE_MISSING_WORK_UNIT_ID")
    if frontier.get("runtime_required") is not False:
        errors.append("FRONTIER_RUNTIME_MUST_BE_FALSE")
    for key in ("scope", "forbidden_scope", "required_checks", "exit_criteria"):
        value = frontier.get(key)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(f"FRONTIER_LIST_INVALID:{key}")
        elif len(set(value)) != len(value):
            errors.append(f"FRONTIER_LIST_DUPLICATE:{key}")
    return errors


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("number", issue.get("issue_number"))
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise MaterializationError("PROVIDER_ISSUE_NUMBER_INVALID")
    return value


def _issue_is_open(issue: dict[str, Any]) -> bool:
    state = str(issue.get("state", "")).lower()
    if state not in {"open", "closed"}:
        raise MaterializationError("PROVIDER_ISSUE_STATE_INVALID")
    return state == "open"


def _render_issue_body(work_unit_id: str, base_sha: str, frontier: dict[str, Any]) -> str:
    marker = (
        f"<!-- PNCC-WORK-UNIT schema=1 id={work_unit_id} state=READY "
        f"conflict_domain={frontier['conflict_domain']} base={base_sha} runtime_required=false -->"
    )
    sections = [
        marker,
        "",
        "## Goal",
        "",
        frontier["goal"],
        "",
        "## Scope",
        "",
        *[f"- {item}" for item in frontier["scope"]],
        "",
        "## Forbidden scope",
        "",
        *[f"- {item}" for item in frontier["forbidden_scope"]],
        "",
        "## Required evidence",
        "",
        *[f"- {item}" for item in frontier["exit_criteria"]],
        "",
        "## Next natural boundary",
        "",
        f"`{frontier['next_natural_boundary']}`",
        "",
        "This intake was deterministically proposed by the canonical PLAN_ONLY materialization planner. "
        "The proposal itself grants no Issue-write, branch, lease, merge, runtime, release/tag, ruleset or product authority.",
    ]
    return "\n".join(sections) + "\n"


def plan_materialization(
    snapshot: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    frontier: dict[str, Any] | None = None,
    selector_module=None,
    blob_reader=git_blob_sha,
) -> dict[str, Any]:
    policy = policy or load_json(POLICY_PATH)
    frontier = frontier or load_json(FRONTIER_PATH)
    errors = validate_policy(policy) + validate_anchor_map(policy, blob_reader=blob_reader) + validate_frontier(frontier)
    if errors:
        return _blocked(*errors)

    if frontier.get("state") == "NONE":
        return {
            "schema_version": 1,
            "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_PLAN",
            "decision": "NO_FRONTIER",
            "reasons": [],
            "proposal": None,
            "provider_mutation_performed": False,
            "issue_mutation_performed": False,
        }

    if not isinstance(snapshot, dict):
        return _blocked("PROVIDER_SNAPSHOT_OBJECT_REQUIRED")
    if snapshot.get("schema_version") != 1 or snapshot.get("role") != "GOVERNED_WORK_UNIT_MATERIALIZATION_SNAPSHOT":
        return _blocked("PROVIDER_SNAPSHOT_IDENTITY_INVALID")
    if snapshot.get("repository") != policy["repository"]:
        return _blocked("PROVIDER_REPOSITORY_MISMATCH")
    if snapshot.get("default_branch") != policy["default_branch"]:
        return _blocked("DEFAULT_BRANCH_MISMATCH")
    head = snapshot.get("default_head_sha")
    if not isinstance(head, str) or SHA40.fullmatch(head) is None:
        return _blocked("DEFAULT_HEAD_SHA_INVALID")
    if snapshot.get("provider_truth_fresh") is not True:
        return _blocked("PROVIDER_TRUTH_NOT_FRESH")
    if snapshot.get("issue_history_complete") is not True:
        return _blocked("ISSUE_HISTORY_INCOMPLETE")
    if snapshot.get("selector_disposition") != policy["required_selector_disposition"]:
        return _blocked("SELECTOR_DISPOSITION_NOT_NO_WORK")
    if not isinstance(snapshot.get("observed_at"), str) or not snapshot["observed_at"].strip():
        return _blocked("OBSERVED_AT_REQUIRED")
    issues = snapshot.get("issues")
    if not isinstance(issues, list):
        return _blocked("PROVIDER_ISSUES_LIST_REQUIRED")

    selector_module = selector_module or load_selector()
    historical_suffixes: list[int] = []
    canonical_records: list[dict[str, Any]] = []
    malformed: list[str] = []
    prefix_re = re.compile(r"^" + re.escape(policy["work_unit_prefix"]) + r"([0-9]+)$")

    for issue in issues:
        if not isinstance(issue, dict):
            return _blocked("PROVIDER_ISSUE_OBJECT_REQUIRED")
        try:
            number = _issue_number(issue)
            is_open = _issue_is_open(issue)
        except MaterializationError as exc:
            return _blocked(str(exc))
        if issue.get("pull_request") is not None:
            continue
        body = issue.get("body") or ""
        if not isinstance(body, str):
            return _blocked(f"ISSUE_BODY_TEXT_REQUIRED:{number}")
        if "PNCC-WORK-UNIT" not in body.upper():
            continue
        try:
            marker = selector_module.parse_issue_intake_marker(body)
        except Exception as exc:
            malformed.append(f"ISSUE_{number}:{type(exc).__name__}:{exc}")
            continue
        if marker is None:
            malformed.append(f"ISSUE_{number}:CANONICAL_MARKER_NOT_PARSED")
            continue
        record = {"issue_number": number, "provider_open": is_open, **marker}
        canonical_records.append(record)
        match = prefix_re.fullmatch(marker["work_unit_id"])
        if match:
            historical_suffixes.append(int(match.group(1)))

    if malformed:
        return _blocked("MALFORMED_CANONICAL_MARKER:" + "|".join(sorted(malformed)))
    open_canonical = sorted(r["issue_number"] for r in canonical_records if r["provider_open"])
    if open_canonical:
        return _blocked("OPEN_CANONICAL_WORK_UNIT_PRESENT:" + ",".join(str(x) for x in open_canonical))
    if not historical_suffixes:
        return _blocked("NO_HISTORICAL_PIPE_WORK_UNIT_ID")
    next_suffix = max(historical_suffixes) + 1
    work_unit_id = f"{policy['work_unit_prefix']}{next_suffix:03d}"
    if any(r["work_unit_id"] == work_unit_id for r in canonical_records):
        return _blocked("PROPOSED_WORK_UNIT_ID_ALREADY_EXISTS")

    title = frontier["title_template"].format(work_unit_id=work_unit_id)
    body = _render_issue_body(work_unit_id, head, frontier)
    marker = selector_module.parse_issue_intake_marker(body)
    if marker is None:
        return _blocked("GENERATED_MARKER_NOT_PARSEABLE")
    if marker["work_unit_id"] != work_unit_id or marker["base_sha"] != head:
        return _blocked("GENERATED_MARKER_IDENTITY_MISMATCH")
    if marker["state"] != policy["required_marker_state"] or marker["runtime_required"] is not False:
        return _blocked("GENERATED_MARKER_POLICY_MISMATCH")
    if marker["conflict_domain"] != frontier["conflict_domain"]:
        return _blocked("GENERATED_MARKER_CONFLICT_DOMAIN_MISMATCH")

    return {
        "schema_version": 1,
        "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_PLAN",
        "decision": "MATERIALIZATION_ELIGIBLE",
        "reasons": [],
        "proposal": {
            "work_unit_id": work_unit_id,
            "title": title,
            "body": body,
            "marker": marker,
            "base_sha": head,
            "conflict_domain": frontier["conflict_domain"],
            "runtime_required": False,
            "frontier_id": frontier["frontier_id"],
            "required_checks": frontier["required_checks"],
            "next_natural_boundary": frontier["next_natural_boundary"],
        },
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
        "next_boundary": policy["next_boundary_if_eligible"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--policy", default=str(POLICY_PATH))
    parser.add_argument("--frontier", default=str(FRONTIER_PATH))
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = plan_materialization(
            load_json(Path(args.snapshot)),
            policy=load_json(Path(args.policy)),
            frontier=load_json(Path(args.frontier)),
        )
    except MaterializationError as exc:
        result = _blocked(str(exc))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 2 if result["decision"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
