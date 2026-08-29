#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev" / "contracts" / "governed-frontier-lifecycle-policy.json"
FRONTIER_ROLE = "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class FrontierLifecycleError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise FrontierLifecycleError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def loads_strict(data: bytes | str) -> Any:
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8-sig")
        return json.loads(data, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FrontierLifecycleError("JSON_INVALID:" + type(exc).__name__) from exc


def load_json(path: Path) -> Any:
    try:
        return loads_strict(path.read_bytes())
    except OSError as exc:
        raise FrontierLifecycleError("FILE_UNREADABLE:" + path.as_posix()) from exc


def git_blob_sha_bytes(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def git_blob_sha_path(path: Path) -> str:
    try:
        return git_blob_sha_bytes(path.read_bytes())
    except OSError as exc:
        raise FrontierLifecycleError("FILE_UNREADABLE:" + path.as_posix()) from exc


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "GOVERNED_FRONTIER_LIFECYCLE_DECISION",
        "decision": "BLOCKED",
        "reasons": [reason],
        "provider_mutation_performed": False,
        "frontier_mutation_performed": False,
        "merge_authority": False,
    }


def validate_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict) or policy.get("schema_version") != 1 or policy.get("role") != "GOVERNED_FRONTIER_LIFECYCLE_POLICY":
        raise FrontierLifecycleError("POLICY_IDENTITY_INVALID")
    exact = {
        "mode": "READ_ONLY_FAIL_CLOSED",
        "frontier_path": ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json",
        "transition_path_template": ".pncc-dev/contracts/governed-frontier-transition-{work_unit_id_lower}.json",
        "predecessor_state_required": "ACTIVE",
        "successor_state_policy": "ACTIVE_OR_NONE",
        "next_boundary": "PER_WORK_UNIT_TRANSITION_CONTRACT_AND_EXACT_HEAD_CI",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            raise FrontierLifecycleError("POLICY_FIELD_INVALID:" + key)
    try:
        re.compile(str(policy["applicable_branch_pattern"]))
    except (KeyError, re.error) as exc:
        raise FrontierLifecycleError("POLICY_BRANCH_PATTERN_INVALID") from exc
    required_true = (
        "same_pr_advancement_required",
        "transition_contract_changed_in_same_pr_required",
        "frontier_changed_in_same_pr_required",
        "predecessor_blob_must_match_pr_base",
        "successor_blob_must_match_pr_head",
        "successor_blob_must_differ_from_predecessor",
        "successor_frontier_id_must_differ_if_active",
        "successor_runtime_required_must_be_false_if_active",
        "completed_frontier_replay_forbidden",
        "historical_transition_reuse_forbidden",
    )
    for key in required_true:
        if policy.get(key) is not True:
            raise FrontierLifecycleError("POLICY_REQUIRED_TRUE:" + key)
    if policy.get("terminal_none_shape") != {
        "schema_version": 1,
        "role": FRONTIER_ROLE,
        "state": "NONE",
    }:
        raise FrontierLifecycleError("POLICY_TERMINAL_SHAPE_INVALID")
    if policy.get("work_unit_binding_fields") != [
        "work_unit_id", "issue_number", "conflict_domain", "base_sha", "branch"
    ]:
        raise FrontierLifecycleError("POLICY_BINDING_FIELDS_INVALID")
    paths = policy.get("immutable_materialization_anchor_paths")
    blobs = policy.get("immutable_materialization_anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs):
        raise FrontierLifecycleError("POLICY_ANCHOR_MAP_INVALID")
    false_authorities = (
        "provider_mutation_authority",
        "issue_mutation_authority",
        "branch_mutation_authority",
        "pull_request_mutation_authority",
        "writer_lease_mutation_authority",
        "merge_authority",
        "runtime_action_authority",
        "product_runtime_mutation_authority",
        "adwf_binding_mutation_authority",
        "release_tag_promotion_authority",
        "ruleset_policy_mutation_authority",
        "private_evidence_publication_authority",
        "reserve_1080_lifecycle_mutation_authority",
        "primary_1081_lifecycle_mutation_authority",
    )
    for key in false_authorities:
        if policy.get(key) is not False:
            raise FrontierLifecycleError("POLICY_AUTHORITY_PRESENT:" + key)


def validate_anchor_map(
    policy: dict[str, Any],
    *,
    root: Path = ROOT,
    blob_reader: Callable[[Path], str] = git_blob_sha_path,
) -> None:
    paths = policy["immutable_materialization_anchor_paths"]
    blobs = policy["immutable_materialization_anchor_blobs"]
    for key in sorted(paths):
        path = root / paths[key]
        if not path.is_file():
            raise FrontierLifecycleError("ANCHOR_MISSING:" + key)
        actual = blob_reader(path)
        if actual != blobs[key]:
            raise FrontierLifecycleError("ANCHOR_DRIFT:" + key)


def _validate_active_frontier(value: dict[str, Any]) -> None:
    if value.get("schema_version") != 1 or value.get("role") != FRONTIER_ROLE:
        raise FrontierLifecycleError("FRONTIER_IDENTITY_INVALID")
    if value.get("state") != "ACTIVE":
        raise FrontierLifecycleError("FRONTIER_ACTIVE_REQUIRED")
    for key in ("frontier_id", "title_template", "goal", "conflict_domain", "next_natural_boundary"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise FrontierLifecycleError("FRONTIER_FIELD_INVALID:" + key)
    if "{work_unit_id}" not in value["title_template"]:
        raise FrontierLifecycleError("FRONTIER_TITLE_TEMPLATE_INVALID")
    if value.get("runtime_required") is not False:
        raise FrontierLifecycleError("FRONTIER_RUNTIME_REQUIRED")
    for key in ("scope", "forbidden_scope", "required_checks", "exit_criteria"):
        items = value.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item.strip() for item in items):
            raise FrontierLifecycleError("FRONTIER_LIST_INVALID:" + key)
        if len(items) != len(set(items)):
            raise FrontierLifecycleError("FRONTIER_LIST_DUPLICATE:" + key)


def _validate_successor(value: dict[str, Any], policy: dict[str, Any]) -> str:
    if value.get("state") == "NONE":
        if value != policy["terminal_none_shape"]:
            raise FrontierLifecycleError("TERMINAL_NONE_SHAPE_INVALID")
        return "NONE"
    _validate_active_frontier(value)
    return "ACTIVE"


def expected_transition_path(policy: dict[str, Any], work_unit_id: str) -> str:
    return policy["transition_path_template"].format(work_unit_id_lower=work_unit_id.lower())


def evaluate_transition(
    transition: Any,
    predecessor_bytes: bytes,
    successor_bytes: bytes,
    *,
    work_unit_id: str,
    base_sha: str,
    branch: str,
    policy: dict[str, Any] | None = None,
    check_anchors: bool = True,
    root: Path = ROOT,
    blob_reader: Callable[[Path], str] = git_blob_sha_path,
) -> dict[str, Any]:
    try:
        policy = policy or load_json(POLICY_PATH)
        validate_policy(policy)
        if check_anchors:
            validate_anchor_map(policy, root=root, blob_reader=blob_reader)
        if not isinstance(transition, dict) or transition.get("schema_version") != 1 or transition.get("role") != "GOVERNED_FRONTIER_TRANSITION":
            raise FrontierLifecycleError("TRANSITION_IDENTITY_INVALID")
        if transition.get("transition_state") != "PREPARED_FOR_IN_PR_ADVANCEMENT":
            raise FrontierLifecycleError("TRANSITION_STATE_INVALID")
        if not isinstance(work_unit_id, str) or re.fullmatch(r"PIPE-WU-[0-9]+", work_unit_id) is None:
            raise FrontierLifecycleError("WORK_UNIT_ID_INVALID")
        if not isinstance(base_sha, str) or SHA40.fullmatch(base_sha) is None:
            raise FrontierLifecycleError("BASE_SHA_INVALID")
        if not isinstance(branch, str) or re.match(policy["applicable_branch_pattern"], branch) is None:
            raise FrontierLifecycleError("BRANCH_NOT_GOVERNED_WORK_UNIT")
        if transition.get("work_unit_id") != work_unit_id:
            raise FrontierLifecycleError("TRANSITION_WORK_UNIT_MISMATCH")
        if transition.get("base_sha") != base_sha:
            raise FrontierLifecycleError("TRANSITION_BASE_MISMATCH")
        if transition.get("branch") != branch:
            raise FrontierLifecycleError("TRANSITION_BRANCH_MISMATCH")
        if not isinstance(transition.get("issue_number"), int) or isinstance(transition.get("issue_number"), bool) or transition["issue_number"] < 1:
            raise FrontierLifecycleError("TRANSITION_ISSUE_NUMBER_INVALID")
        if not isinstance(transition.get("conflict_domain"), str) or not transition["conflict_domain"].strip():
            raise FrontierLifecycleError("TRANSITION_CONFLICT_DOMAIN_INVALID")
        if transition.get("runtime_required") is not False:
            raise FrontierLifecycleError("TRANSITION_RUNTIME_REQUIRED")
        if transition.get("same_pr_advancement_required") is not True:
            raise FrontierLifecycleError("TRANSITION_SAME_PR_REQUIRED")
        if transition.get("predecessor_replay_forbidden") is not True:
            raise FrontierLifecycleError("TRANSITION_REPLAY_GUARD_MISSING")
        if transition.get("successor_must_be_canonical_before_merge") is not True:
            raise FrontierLifecycleError("TRANSITION_CANONICAL_SUCCESSOR_REQUIRED")
        transition_false = (
            "provider_mutation_authority",
            "issue_mutation_authority",
            "direct_main_write_authority",
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
        for key in transition_false:
            if transition.get(key) is not False:
                raise FrontierLifecycleError("TRANSITION_AUTHORITY_PRESENT:" + key)

        predecessor = loads_strict(predecessor_bytes)
        successor = loads_strict(successor_bytes)
        if not isinstance(predecessor, dict) or not isinstance(successor, dict):
            raise FrontierLifecycleError("FRONTIER_OBJECT_REQUIRED")
        _validate_active_frontier(predecessor)
        successor_state = _validate_successor(successor, policy)

        predecessor_sha = git_blob_sha_bytes(predecessor_bytes)
        successor_sha = git_blob_sha_bytes(successor_bytes)
        pred_binding = transition.get("predecessor_frontier")
        succ_binding = transition.get("successor_frontier")
        if not isinstance(pred_binding, dict) or not isinstance(succ_binding, dict):
            raise FrontierLifecycleError("TRANSITION_FRONTIER_BINDING_INVALID")
        if pred_binding != {
            "state": "ACTIVE",
            "frontier_id": predecessor["frontier_id"],
            "blob_sha": predecessor_sha,
        }:
            raise FrontierLifecycleError("PREDECESSOR_BINDING_MISMATCH")
        expected_successor_binding = {
            "state": successor_state,
            "frontier_id": successor.get("frontier_id", "NONE") if successor_state == "ACTIVE" else "NONE",
            "blob_sha": successor_sha,
        }
        if succ_binding != expected_successor_binding:
            raise FrontierLifecycleError("SUCCESSOR_BINDING_MISMATCH")
        if predecessor_sha == successor_sha:
            raise FrontierLifecycleError("FRONTIER_NOT_ADVANCED")
        if successor_state == "ACTIVE" and predecessor["frontier_id"] == successor["frontier_id"]:
            raise FrontierLifecycleError("FRONTIER_ID_REPLAY")
        return {
            "schema_version": 1,
            "role": "GOVERNED_FRONTIER_LIFECYCLE_DECISION",
            "decision": "TERMINAL_ELIGIBLE" if successor_state == "NONE" else "ADVANCEMENT_ELIGIBLE",
            "reasons": [],
            "work_unit_id": work_unit_id,
            "issue_number": transition["issue_number"],
            "conflict_domain": transition["conflict_domain"],
            "base_sha": base_sha,
            "branch": branch,
            "predecessor_blob_sha": predecessor_sha,
            "successor_blob_sha": successor_sha,
            "successor_state": successor_state,
            "provider_mutation_performed": False,
            "frontier_mutation_performed": False,
            "merge_authority": False,
        }
    except (FrontierLifecycleError, KeyError, TypeError) as exc:
        return _blocked(str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transition", required=True)
    parser.add_argument("--predecessor", required=True)
    parser.add_argument("--successor", required=True)
    parser.add_argument("--work-unit-id", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--branch", required=True)
    args = parser.parse_args()
    try:
        transition = load_json(Path(args.transition))
        predecessor_bytes = Path(args.predecessor).read_bytes()
        successor_bytes = Path(args.successor).read_bytes()
        result = evaluate_transition(
            transition,
            predecessor_bytes,
            successor_bytes,
            work_unit_id=args.work_unit_id,
            base_sha=args.base_sha,
            branch=args.branch,
        )
    except (OSError, FrontierLifecycleError) as exc:
        result = _blocked(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] in {"ADVANCEMENT_ELIGIBLE", "TERMINAL_ELIGIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
