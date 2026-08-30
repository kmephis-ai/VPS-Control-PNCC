#!/usr/bin/env python3
"""Read-only provider-truth selector/planner continuation integration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import argparse
import hashlib
import importlib.util
import json
import os
import re

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev/contracts/provider-truth-continuation-policy.json"
SELECTOR_PATH = ROOT / ".pncc-dev/scripts/select_provider_work_unit.py"
PLANNER_PATH = ROOT / ".pncc-dev/scripts/plan_governed_work_unit_materialization.py"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class ContinuationError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContinuationError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContinuationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ContinuationError("MODULE_IMPORT_FAILED:" + path.as_posix())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob_sha_path(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


FALSE_AUTHORITIES = (
    "provider_mutation_authority",
    "issue_create_authority",
    "issue_update_authority",
    "issue_close_authority",
    "branch_mutation_authority",
    "pull_request_mutation_authority",
    "writer_lease_mutation_authority",
    "merge_authority",
    "runtime_action_authority",
    "product_runtime_mutation_authority",
    "adwf_binding_mutation_authority",
    "adwf_repository_mutation_authority",
    "release_tag_promotion_authority",
    "ruleset_policy_mutation_authority",
    "private_evidence_publication_authority",
    "reserve_1080_lifecycle_mutation_authority",
    "primary_1081_lifecycle_mutation_authority",
)


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_version") != 1 or policy.get("role") != "PROVIDER_TRUTH_CONTINUATION_POLICY":
        raise ContinuationError("POLICY_IDENTITY_INVALID")
    exact = {
        "mode": "READ_ONLY_FAIL_CLOSED",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "selector_guard_policy": "ALLOW_ONLY_EXACT_RECONCILED_PROOF_PIN_DRIFT",
        "allowed_selector_guard_error": "WAVE5_ADWF_PIN_DRIFT",
        "selected_work_unit_policy": "EXACTLY_ONE_EXECUTABLE_CONTINUE_WITHOUT_MATERIALIZATION",
        "no_work_policy": "PLAN_ONLY_MATERIALIZATION_THROUGH_EXISTING_PLANNER",
        "waiting_runtime_policy": "WAIT_WITHOUT_MUTATION",
        "blocked_policy": "BLOCK_FAIL_CLOSED",
        "issue_history_policy": "COMPLETE_HISTORY_REQUIRED_FOR_CONTINUATION_EVALUATION",
        "required_mutation_authority": "NONE_BINDING_IS_PROOF_ONLY",
        "next_boundary": "EXACT_HEAD_CI_INSPECTION_CLASSIFICATION_RECOVERY_INTEGRATION",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            raise ContinuationError("POLICY_FIELD_INVALID:" + key)
    if policy.get("provider_truth_fresh_required") is not True:
        raise ContinuationError("POLICY_PROVIDER_TRUTH_FRESH_REQUIRED")
    if policy.get("decisions") != [
        "CONTINUE_SELECTED_WORK_UNIT",
        "PLAN_MATERIALIZATION",
        "WAITING_RUNTIME",
        "NO_FRONTIER",
        "BLOCKED",
    ]:
        raise ContinuationError("POLICY_DECISIONS_INVALID")
    paths = policy.get("anchor_paths")
    blobs = policy.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs):
        raise ContinuationError("POLICY_ANCHOR_MAP_INVALID")
    for key in FALSE_AUTHORITIES:
        if policy.get(key) is not False:
            raise ContinuationError("POLICY_AUTHORITY_PRESENT:" + key)


def validate_anchor_map(
    policy: dict[str, Any],
    *,
    root: Path = ROOT,
    blob_reader: Callable[[Path], str] = git_blob_sha_path,
) -> None:
    for key in sorted(policy["anchor_paths"]):
        path = root / policy["anchor_paths"][key]
        if not path.is_file():
            raise ContinuationError("ANCHOR_MISSING:" + key)
        actual = blob_reader(path)
        if actual != policy["anchor_blobs"][key]:
            raise ContinuationError("ANCHOR_DRIFT:" + key)


def validate_selector_guard(selector, policy: dict[str, Any], *, root: Path = ROOT) -> str:
    readiness = load_json(root / ".adwf-consumer/wave5-readiness.json")
    binding = load_json(root / ".adwf-consumer/external-binding.json")
    expected_legacy = policy["legacy_selector_expected_adwf_sha"]
    reconciled = policy["reconciled_adwf_sha"]
    if getattr(selector, "EXPECTED_ADWF_SHA", None) != expected_legacy:
        raise ContinuationError("SELECTOR_EXPECTED_ADWF_DRIFT")
    if readiness.get("framework", {}).get("source_sha") != reconciled:
        raise ContinuationError("READINESS_RECONCILED_ADWF_DRIFT")
    if binding.get("framework", {}).get("source_sha") != reconciled:
        raise ContinuationError("BINDING_RECONCILED_ADWF_DRIFT")
    if binding.get("binding_sha256") != policy["reconciled_binding_sha256"]:
        raise ContinuationError("BINDING_DIGEST_DRIFT")
    if binding.get("mutation_authority") != policy["required_mutation_authority"]:
        raise ContinuationError("BINDING_AUTHORITY_DRIFT")
    consumer = readiness.get("consumer", {})
    framework = readiness.get("framework", {})
    if consumer.get("mutation_authority") != policy["required_mutation_authority"]:
        raise ContinuationError("READINESS_AUTHORITY_DRIFT")
    if consumer.get("managed_surface_adopted") is not False:
        raise ContinuationError("READINESS_MANAGED_SURFACE_ADOPTED")
    if framework.get("provider_ops_consumer_authority_granted") is not False:
        raise ContinuationError("READINESS_PROVIDER_AUTHORITY_PRESENT")
    try:
        selector.validate_readiness_guard(root)
    except selector.SelectionError as exc:
        reason = str(exc)
        if reason != policy["allowed_selector_guard_error"]:
            raise ContinuationError("SELECTOR_GUARD_UNEXPECTED:" + reason) from exc
        return "PROVEN_RECONCILED_PIN_DRIFT"
    return "PASS"


def _blocked(reason: str, *, guard_state: str | None = None, selector_result: Any = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "PROVIDER_TRUTH_CONTINUATION_DECISION",
        "state": "READ_ONLY_CONTINUATION_BLOCKED",
        "decision": "BLOCKED",
        "reasons": [reason],
        "selector_guard_state": guard_state,
        "selector_result": selector_result,
        "selected": None,
        "materialization_plan": None,
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
        "writer_lease_mutation_performed": False,
        "merge_performed": False,
        "runtime_action_performed": False,
    }


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("number", issue.get("issue_number"))
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContinuationError("PROVIDER_ISSUE_NUMBER_INVALID")
    return value


def validate_provider_inventory(open_issues: list[Any], issue_history: list[Any]) -> None:
    if not isinstance(open_issues, list) or not isinstance(issue_history, list):
        raise ContinuationError("PROVIDER_ISSUE_LIST_REQUIRED")
    history: dict[int, dict[str, Any]] = {}
    for raw in issue_history:
        if not isinstance(raw, dict):
            raise ContinuationError("PROVIDER_ISSUE_OBJECT_REQUIRED")
        number = _issue_number(raw)
        if number in history:
            raise ContinuationError("PROVIDER_ISSUE_HISTORY_DUPLICATE")
        state = str(raw.get("state", "")).lower()
        if state not in {"open", "closed"}:
            raise ContinuationError("PROVIDER_ISSUE_HISTORY_STATE_INVALID")
        history[number] = raw
    seen_open: set[int] = set()
    for raw in open_issues:
        if not isinstance(raw, dict):
            raise ContinuationError("PROVIDER_OPEN_ISSUE_OBJECT_REQUIRED")
        number = _issue_number(raw)
        if number in seen_open:
            raise ContinuationError("PROVIDER_OPEN_ISSUE_DUPLICATE")
        seen_open.add(number)
        if str(raw.get("state", "")).lower() != "open":
            raise ContinuationError("PROVIDER_OPEN_ISSUE_STATE_INVALID")
        recorded = history.get(number)
        if recorded is None or str(recorded.get("state", "")).lower() != "open":
            raise ContinuationError("PROVIDER_HISTORY_MISSING_OPEN_ISSUE")
        for key in ("title", "body"):
            if (recorded.get(key) or "") != (raw.get(key) or ""):
                raise ContinuationError("PROVIDER_HISTORY_OPEN_ISSUE_MISMATCH:" + key)
        if bool(recorded.get("pull_request")) != bool(raw.get("pull_request")):
            raise ContinuationError("PROVIDER_HISTORY_OPEN_ISSUE_MISMATCH:pull_request")


def evaluate_continuation(
    *,
    open_issues: list[Any],
    issue_history: list[Any],
    repository: str,
    default_branch: str,
    default_head_sha: str,
    observed_at: str,
    provider_truth_fresh: bool,
    issue_history_complete: bool,
    policy: dict[str, Any] | None = None,
    selector_module=None,
    planner_module=None,
    root: Path = ROOT,
    check_anchors: bool = True,
    guard_checker=None,
) -> dict[str, Any]:
    guard_state: str | None = None
    selector_result: Any = None
    try:
        policy = policy or load_json(POLICY_PATH)
        validate_policy(policy)
        if check_anchors:
            validate_anchor_map(policy, root=root)
        if repository != policy["repository"] or default_branch != policy["default_branch"]:
            raise ContinuationError("PROVIDER_IDENTITY_MISMATCH")
        if SHA40.fullmatch(str(default_head_sha)) is None:
            raise ContinuationError("DEFAULT_HEAD_SHA_INVALID")
        if provider_truth_fresh is not True:
            raise ContinuationError("PROVIDER_TRUTH_NOT_FRESH")
        if issue_history_complete is not True:
            raise ContinuationError("ISSUE_HISTORY_INCOMPLETE")
        if not isinstance(observed_at, str) or not observed_at.strip():
            raise ContinuationError("OBSERVED_AT_REQUIRED")
        validate_provider_inventory(open_issues, issue_history)
        selector_module = selector_module or load_module("pncc_provider_selector", SELECTOR_PATH)
        planner_module = planner_module or load_module("pncc_materialization_planner", PLANNER_PATH)
        guard_checker = guard_checker or validate_selector_guard
        guard_state = guard_checker(selector_module, policy, root=root)
        if guard_state not in {"PASS", "PROVEN_RECONCILED_PIN_DRIFT"}:
            raise ContinuationError("SELECTOR_GUARD_STATE_INVALID")
        try:
            selector_result = selector_module.select_from_provider_issues(
                open_issues,
                repository=repository,
                default_branch=default_branch,
                default_head_sha=default_head_sha,
                observed_at=observed_at,
            )
        except Exception as exc:
            raise ContinuationError("SELECTOR_CLASSIFICATION_FAILED:" + str(exc)) from exc
        if selector_result.get("schema_version") != 2 or selector_result.get("state") != "READ_ONLY_PROVIDER_TRUTH_SELECTION_PASS":
            raise ContinuationError("SELECTOR_RESULT_IDENTITY_INVALID")
        if selector_result.get("provider_mutation_performed") is not False:
            raise ContinuationError("SELECTOR_MUTATION_REPORTED")
        disposition = selector_result.get("orchestration_disposition")
        if disposition == "EXECUTABLE":
            if selector_result.get("decision") != "SELECTED" or selector_result.get("executable_count") != 1:
                raise ContinuationError("EXECUTABLE_SELECTION_NOT_EXACTLY_ONE")
            selected = selector_result.get("selected")
            if not isinstance(selected, dict) or selected.get("classification") != "EXECUTABLE_READ_ONLY_SELECTION":
                raise ContinuationError("SELECTED_WORK_UNIT_INVALID")
            return {
                "schema_version": 1,
                "role": "PROVIDER_TRUTH_CONTINUATION_DECISION",
                "state": "READ_ONLY_CONTINUATION_PASS",
                "decision": "CONTINUE_SELECTED_WORK_UNIT",
                "reasons": [],
                "selector_guard_state": guard_state,
                "selector_result": selector_result,
                "selected": selected,
                "materialization_plan": None,
                "provider_mutation_performed": False,
                "issue_mutation_performed": False,
                "writer_lease_mutation_performed": False,
                "merge_performed": False,
                "runtime_action_performed": False,
                "next_boundary": "EXISTING_REUSABLE_WRITER_LEASE_AND_BOUNDED_BRANCH_AUTHORITY",
            }
        if disposition == "WAITING_RUNTIME":
            return {
                "schema_version": 1,
                "role": "PROVIDER_TRUTH_CONTINUATION_DECISION",
                "state": "READ_ONLY_CONTINUATION_WAITING_RUNTIME",
                "decision": "WAITING_RUNTIME",
                "reasons": [],
                "selector_guard_state": guard_state,
                "selector_result": selector_result,
                "selected": None,
                "materialization_plan": None,
                "provider_mutation_performed": False,
                "issue_mutation_performed": False,
                "writer_lease_mutation_performed": False,
                "merge_performed": False,
                "runtime_action_performed": False,
                "next_boundary": "WAIT_FOR_PRIVATE_RUNTIME_EVIDENCE",
            }
        if disposition == "BLOCKED":
            return _blocked("SELECTOR_DISPOSITION_BLOCKED", guard_state=guard_state, selector_result=selector_result)
        if disposition != "NO_WORK" or selector_result.get("decision") != "NO_EXECUTABLE_WORK_UNIT":
            raise ContinuationError("SELECTOR_DISPOSITION_INVALID")
        snapshot = {
            "schema_version": 1,
            "role": "GOVERNED_WORK_UNIT_MATERIALIZATION_SNAPSHOT",
            "repository": repository,
            "default_branch": default_branch,
            "default_head_sha": default_head_sha,
            "provider_truth_fresh": True,
            "issue_history_complete": True,
            "selector_disposition": "NO_WORK",
            "observed_at": observed_at,
            "issues": issue_history,
        }
        plan = planner_module.plan_materialization(snapshot)
        if plan.get("provider_mutation_performed") is not False or plan.get("issue_mutation_performed") is not False:
            raise ContinuationError("PLANNER_MUTATION_REPORTED")
        if plan.get("decision") == "MATERIALIZATION_ELIGIBLE":
            return {
                "schema_version": 1,
                "role": "PROVIDER_TRUTH_CONTINUATION_DECISION",
                "state": "READ_ONLY_CONTINUATION_PASS",
                "decision": "PLAN_MATERIALIZATION",
                "reasons": [],
                "selector_guard_state": guard_state,
                "selector_result": selector_result,
                "selected": None,
                "materialization_plan": plan,
                "provider_mutation_performed": False,
                "issue_mutation_performed": False,
                "writer_lease_mutation_performed": False,
                "merge_performed": False,
                "runtime_action_performed": False,
                "next_boundary": "EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY",
            }
        if plan.get("decision") == "NO_FRONTIER":
            return {
                "schema_version": 1,
                "role": "PROVIDER_TRUTH_CONTINUATION_DECISION",
                "state": "READ_ONLY_CONTINUATION_NO_FRONTIER",
                "decision": "NO_FRONTIER",
                "reasons": [],
                "selector_guard_state": guard_state,
                "selector_result": selector_result,
                "selected": None,
                "materialization_plan": plan,
                "provider_mutation_performed": False,
                "issue_mutation_performed": False,
                "writer_lease_mutation_performed": False,
                "merge_performed": False,
                "runtime_action_performed": False,
                "next_boundary": None,
            }
        return _blocked(
            "MATERIALIZATION_PLANNER_BLOCKED:" + "|".join(plan.get("reasons") or ["UNKNOWN"]),
            guard_state=guard_state,
            selector_result=selector_result,
        )
    except (ContinuationError, KeyError, TypeError, OSError) as exc:
        return _blocked(str(exc), guard_state=guard_state, selector_result=selector_result)


def fetch_complete_issue_history(selector, repository: str, token: str | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    url: str | None = f"https://api.github.com/repos/{repository}/issues?state=all&per_page=100&sort=created&direction=asc"
    pages = 0
    while url:
        pages += 1
        if pages > 20:
            raise ContinuationError("GITHUB_ISSUE_HISTORY_PAGINATION_LIMIT")
        page, headers = selector._github_get_json(url, token)
        if not isinstance(page, list):
            raise ContinuationError("GITHUB_ISSUE_HISTORY_RESPONSE_INVALID")
        issues.extend(page)
        url = selector._next_link(headers.get("link"))
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", required=True)
    ap.add_argument("--default-branch", default="main")
    ap.add_argument("--live-github", action="store_true")
    ap.add_argument("--open-issues-json")
    ap.add_argument("--issue-history-json")
    ap.add_argument("--default-head-sha")
    ap.add_argument("--observed-at")
    ap.add_argument("--output")
    args = ap.parse_args()
    selector = load_module("pncc_provider_selector", SELECTOR_PATH)
    if args.live_github:
        head, open_issues = selector.fetch_live_provider_truth(
            args.repository, args.default_branch, os.environ.get("GITHUB_TOKEN")
        )
        issue_history = fetch_complete_issue_history(selector, args.repository, os.environ.get("GITHUB_TOKEN"))
    else:
        if not args.open_issues_json or not args.issue_history_json or not args.default_head_sha:
            raise ContinuationError("OFFLINE_PROVIDER_INPUT_REQUIRED")
        open_issues = load_json(Path(args.open_issues_json))
        issue_history = load_json(Path(args.issue_history_json))
        head = args.default_head_sha
    observed_at = args.observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = evaluate_continuation(
        open_issues=open_issues,
        issue_history=issue_history,
        repository=args.repository,
        default_branch=args.default_branch,
        default_head_sha=head,
        observed_at=observed_at,
        provider_truth_fresh=True,
        issue_history_complete=True,
        selector_module=selector,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
