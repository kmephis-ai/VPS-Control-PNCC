#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev/contracts/wave6-hbe-frontier-bootstrap-policy.json"
FRONTIER_ROLE = "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class BootstrapError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise BootstrapError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def loads_strict(data: bytes | str) -> Any:
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8-sig")
        return json.loads(data, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BootstrapError("JSON_INVALID:" + type(exc).__name__) from exc


def load_json(path: Path) -> Any:
    try:
        return loads_strict(path.read_bytes())
    except OSError as exc:
        raise BootstrapError("FILE_UNREADABLE:" + path.as_posix()) from exc


def git_blob_sha_bytes(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def git_blob_sha_path(path: Path) -> str:
    try:
        return git_blob_sha_bytes(path.read_bytes())
    except OSError as exc:
        raise BootstrapError("FILE_UNREADABLE:" + path.as_posix()) from exc


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "WAVE6_HBE_FRONTIER_BOOTSTRAP_DECISION",
        "decision": "BLOCKED",
        "reasons": [reason],
        "provider_mutation_performed": False,
        "frontier_mutation_performed": False,
        "merge_authority": False,
    }


def _reject_true_authority(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            lowered = key.lower()
            if (lowered.endswith("_authority") or lowered.endswith("_authority_granted")) and isinstance(child, bool) and child:
                raise BootstrapError("AUTHORITY_EXPANSION:" + child_path)
            _reject_true_authority(child, child_path)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _reject_true_authority(child, f"{path}[{idx}]")


def validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict) or policy.get("schema_version") != 1 or policy.get("role") != "WAVE6_HBE_FRONTIER_BOOTSTRAP_POLICY":
        raise BootstrapError("POLICY_IDENTITY_INVALID")
    exact = {
        "mode": "OWNER_AUTHORIZED_SINGLE_USE_FAIL_CLOSED",
        "authorized_work_unit_id": "PIPE-WU-134",
        "authorized_issue_number": 316,
        "authorized_base_sha": "7f86472c2cf66c4a5f3b64fb17ee53059cea8c60",
        "authorized_branch": "agent/PIPE-WU-134-wave6-hbe-frontier-bootstrap",
        "authorized_conflict_domain": "wave6-hbe-frontier-bootstrap-existing-authority-only",
        "frontier_path": ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json",
        "bootstrap_transition_path": ".pncc-dev/contracts/wave6-hbe-frontier-bootstrap-pipe-wu-134.json",
        "next_boundary": "EXACT_HEAD_CI_AND_EXISTING_REUSABLE_MERGE_CLOSE_AUTHORITY",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            raise BootstrapError("POLICY_FIELD_INVALID:" + key)
    for key in (
        "owner_authorized_single_use_transition",
        "same_pr_transition_required",
        "predecessor_must_match_pr_base",
        "successor_must_match_pr_head",
        "historical_reuse_forbidden",
        "automatic_none_to_active_bootstrap_forbidden",
        "future_bootstrap_requires_separate_owner_authorization",
        "successor_periodic_scheduling_authority_must_be_false",
        "successor_unattended_mutation_authority_must_be_false",
    ):
        if policy.get(key) is not True:
            raise BootstrapError("POLICY_REQUIRED_TRUE:" + key)
    predecessor = policy.get("predecessor_required")
    if predecessor != {
        "schema_version": 1,
        "role": FRONTIER_ROLE,
        "state": "NONE",
        "blob_sha": "b4cf4f19e0d89884598427ad0a6729c997e7f1fe",
    }:
        raise BootstrapError("POLICY_PREDECESSOR_INVALID")
    successor = policy.get("successor_required")
    if not isinstance(successor, dict):
        raise BootstrapError("POLICY_SUCCESSOR_INVALID")
    expected_successor = {
        "schema_version": 1,
        "role": FRONTIER_ROLE,
        "state": "ACTIVE",
        "frontier_id": "WAVE6_HBE_PIPELINE_HEALTH_DRIFT_READ_ONLY_ASSESSMENT_EXISTING_AUTHORITY_ONLY",
        "conflict_domain": "wave6-hbe-pipeline-health-drift-read-only-assessment-existing-authority-only",
        "runtime_required": False,
        "blob_sha": "c9f16baebd6ba5416e176b76fe69e32387e93786",
    }
    if successor != expected_successor:
        raise BootstrapError("POLICY_SUCCESSOR_INVALID")
    paths = policy.get("immutable_anchor_paths")
    blobs = policy.get("immutable_anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs) or not paths:
        raise BootstrapError("POLICY_ANCHOR_MAP_INVALID")
    for key, expected in blobs.items():
        if not isinstance(expected, str) or SHA40.fullmatch(expected) is None:
            raise BootstrapError("POLICY_ANCHOR_SHA_INVALID:" + key)
    _reject_true_authority(policy)


def validate_anchor_map(policy: dict[str, Any], *, root: Path = ROOT, blob_reader: Callable[[Path], str] = git_blob_sha_path) -> None:
    for key in sorted(policy["immutable_anchor_paths"]):
        rel = policy["immutable_anchor_paths"][key]
        path = root / rel
        if not path.is_file():
            raise BootstrapError("ANCHOR_MISSING:" + key)
        actual = blob_reader(path)
        if actual != policy["immutable_anchor_blobs"][key]:
            raise BootstrapError("ANCHOR_DRIFT:" + key)


def _validate_terminal_predecessor(value: Any) -> None:
    if value != {"schema_version": 1, "role": FRONTIER_ROLE, "state": "NONE"}:
        raise BootstrapError("PREDECESSOR_TERMINAL_NONE_REQUIRED")


def _validate_successor(value: Any, policy: dict[str, Any]) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("role") != FRONTIER_ROLE:
        raise BootstrapError("SUCCESSOR_IDENTITY_INVALID")
    if value.get("state") != "ACTIVE":
        raise BootstrapError("SUCCESSOR_ACTIVE_REQUIRED")
    required = policy["successor_required"]
    for key in ("frontier_id", "conflict_domain", "runtime_required"):
        if value.get(key) != required[key]:
            raise BootstrapError("SUCCESSOR_FIELD_INVALID:" + key)
    for key in ("title_template", "goal", "next_natural_boundary"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise BootstrapError("SUCCESSOR_TEXT_INVALID:" + key)
    if "{work_unit_id}" not in value["title_template"]:
        raise BootstrapError("SUCCESSOR_TITLE_TEMPLATE_INVALID")
    for key in ("scope", "forbidden_scope", "required_checks", "exit_criteria"):
        items = value.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item.strip() for item in items):
            raise BootstrapError("SUCCESSOR_LIST_INVALID:" + key)
        if len(items) != len(set(items)):
            raise BootstrapError("SUCCESSOR_LIST_DUPLICATE:" + key)
    if value.get("periodic_scheduling_authority") is not False:
        raise BootstrapError("SUCCESSOR_PERIODIC_SCHEDULING_AUTHORITY_PRESENT")
    if value.get("unattended_mutation_authority") is not False:
        raise BootstrapError("SUCCESSOR_UNATTENDED_MUTATION_AUTHORITY_PRESENT")
    _reject_true_authority(value)


def evaluate_bootstrap(transition: Any, predecessor_bytes: bytes, successor_bytes: bytes, *, work_unit_id: str, base_sha: str, branch: str, policy: dict[str, Any] | None = None, policy_bytes: bytes | None = None, check_anchors: bool = True, root: Path = ROOT, blob_reader: Callable[[Path], str] = git_blob_sha_path) -> dict[str, Any]:
    try:
        if policy is None:
            policy_bytes = POLICY_PATH.read_bytes()
            policy = loads_strict(policy_bytes)
        validate_policy(policy)
        if check_anchors:
            validate_anchor_map(policy, root=root, blob_reader=blob_reader)
        if not isinstance(transition, dict) or transition.get("schema_version") != 1 or transition.get("role") != "WAVE6_HBE_FRONTIER_BOOTSTRAP_TRANSITION":
            raise BootstrapError("TRANSITION_IDENTITY_INVALID")
        if transition.get("transition_state") != "PREPARED_FOR_OWNER_AUTHORIZED_IN_PR_BOOTSTRAP":
            raise BootstrapError("TRANSITION_STATE_INVALID")
        if work_unit_id != policy["authorized_work_unit_id"] or transition.get("work_unit_id") != work_unit_id:
            raise BootstrapError("WORK_UNIT_NOT_OWNER_AUTHORIZED")
        if base_sha != policy["authorized_base_sha"] or transition.get("base_sha") != base_sha:
            raise BootstrapError("BASE_NOT_OWNER_AUTHORIZED")
        if branch != policy["authorized_branch"] or transition.get("branch") != branch:
            raise BootstrapError("BRANCH_NOT_OWNER_AUTHORIZED")
        if transition.get("issue_number") != policy["authorized_issue_number"]:
            raise BootstrapError("ISSUE_NOT_OWNER_AUTHORIZED")
        if transition.get("conflict_domain") != policy["authorized_conflict_domain"]:
            raise BootstrapError("CONFLICT_DOMAIN_NOT_OWNER_AUTHORIZED")
        if transition.get("runtime_required") is not False:
            raise BootstrapError("TRANSITION_RUNTIME_REQUIRED")
        if transition.get("same_pr_bootstrap_required") is not True:
            raise BootstrapError("TRANSITION_SAME_PR_REQUIRED")
        if transition.get("predecessor_replay_forbidden") is not True or transition.get("future_bootstrap_reuse_forbidden") is not True:
            raise BootstrapError("TRANSITION_REPLAY_GUARD_MISSING")
        if transition.get("successor_must_be_canonical_before_merge") is not True:
            raise BootstrapError("TRANSITION_CANONICAL_SUCCESSOR_REQUIRED")
        owner = transition.get("owner_authorization")
        if owner != {
            "source": "CANONICAL_ISSUE_OWNER_AUTHORIZATION_BOUNDARY",
            "issue_number": 316,
            "exact_base_sha": "7f86472c2cf66c4a5f3b64fb17ee53059cea8c60",
            "single_use_none_to_active_transition_authorized": True,
            "product_runtime_release_tag_ruleset_security_adwf_authority_granted": False,
        }:
            raise BootstrapError("OWNER_AUTHORIZATION_BINDING_INVALID")
        if policy_bytes is None:
            policy_bytes = json.dumps(policy, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        if transition.get("policy_binding") != {
            "path": ".pncc-dev/contracts/wave6-hbe-frontier-bootstrap-policy.json",
            "blob_sha": git_blob_sha_bytes(policy_bytes),
        }:
            raise BootstrapError("POLICY_BINDING_MISMATCH")
        predecessor = loads_strict(predecessor_bytes)
        successor = loads_strict(successor_bytes)
        _validate_terminal_predecessor(predecessor)
        _validate_successor(successor, policy)
        predecessor_sha = git_blob_sha_bytes(predecessor_bytes)
        successor_sha = git_blob_sha_bytes(successor_bytes)
        if predecessor_sha != policy["predecessor_required"]["blob_sha"]:
            raise BootstrapError("PREDECESSOR_BLOB_MISMATCH")
        if successor_sha != policy["successor_required"]["blob_sha"]:
            raise BootstrapError("SUCCESSOR_BLOB_MISMATCH")
        if predecessor_sha == successor_sha:
            raise BootstrapError("FRONTIER_NOT_ADVANCED")
        if transition.get("predecessor_frontier") != {"state": "NONE", "frontier_id": "NONE", "blob_sha": predecessor_sha}:
            raise BootstrapError("TRANSITION_PREDECESSOR_BINDING_MISMATCH")
        if transition.get("successor_frontier") != {"state": "ACTIVE", "frontier_id": successor["frontier_id"], "blob_sha": successor_sha}:
            raise BootstrapError("TRANSITION_SUCCESSOR_BINDING_MISMATCH")
        expected_observed = {
            "main_sha_before_first_mutation": "7f86472c2cf66c4a5f3b64fb17ee53059cea8c60",
            "canonical_work_unit_issue_number": 316,
            "provider_state_after_lease_acquisition_sha": "c9fe6cbd12ac7e2deaf89e8107f336003279d650",
            "writer_lease_registry_blob_sha": "fe5ea76600e5d94125bc638330c43bdea16aa9ca",
            "writer_lease_generation": 44,
            "writer_lease_id": "427c7518-da33-43ae-8c64-88f714869f4f",
            "predecessor_frontier_blob_sha": predecessor_sha,
        }
        if transition.get("provider_truth_observed") != expected_observed:
            raise BootstrapError("PROVIDER_TRUTH_BINDING_INVALID")
        _reject_true_authority(transition)
        return {
            "schema_version": 1,
            "role": "WAVE6_HBE_FRONTIER_BOOTSTRAP_DECISION",
            "decision": "BOOTSTRAP_ELIGIBLE",
            "reasons": [],
            "work_unit_id": work_unit_id,
            "issue_number": transition["issue_number"],
            "base_sha": base_sha,
            "branch": branch,
            "predecessor_blob_sha": predecessor_sha,
            "successor_blob_sha": successor_sha,
            "successor_frontier_id": successor["frontier_id"],
            "provider_mutation_performed": False,
            "frontier_mutation_performed": False,
            "merge_authority": False,
            "next_boundary": policy["next_boundary"],
        }
    except (BootstrapError, OSError, KeyError, TypeError) as exc:
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
        policy_bytes = POLICY_PATH.read_bytes()
        policy = loads_strict(policy_bytes)
        result = evaluate_bootstrap(
            load_json(Path(args.transition)),
            Path(args.predecessor).read_bytes(),
            Path(args.successor).read_bytes(),
            work_unit_id=args.work_unit_id,
            base_sha=args.base_sha,
            branch=args.branch,
            policy=policy,
            policy_bytes=policy_bytes,
        )
    except (OSError, BootstrapError) as exc:
        result = _blocked(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "BOOTSTRAP_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
