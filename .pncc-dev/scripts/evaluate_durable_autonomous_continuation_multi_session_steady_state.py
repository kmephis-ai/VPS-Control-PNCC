#!/usr/bin/env python3
"""PLAN_ONLY fail-closed evaluator for PNCC durable multi-session continuation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-policy.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SESSION_ID = re.compile(r"^PNCC-SESSION-[A-Za-z0-9._-]+$")
CHECKPOINT_ID = re.compile(r"^PNCC-CONTINUATION-CHECKPOINT-[A-Za-z0-9._-]+$")
WU_ID = re.compile(r"^PIPE-WU-[0-9]+$")
FALSE_AUTH = (
    "provider_mutation_authority", "issue_create_authority", "issue_update_authority", "issue_close_authority",
    "branch_mutation_authority", "pull_request_mutation_authority", "writer_lease_mutation_authority",
    "workflow_rerun_authority", "merge_authority", "runtime_action_authority", "product_runtime_mutation_authority",
    "adwf_binding_mutation_authority", "adwf_repository_mutation_authority", "release_tag_promotion_authority",
    "ruleset_policy_mutation_authority", "private_evidence_publication_authority", "force_ref_update_authority",
    "silent_lease_steal_authority", "reserve_1080_lifecycle_mutation_authority", "primary_1081_lifecycle_mutation_authority",
)
RECORD_FALSE = (
    "checkpoint_is_mutation_authority", "checkpoint_cas_tokens_reusable", "checkpoint_ci_success_reusable",
    "checkpoint_admission_reusable", "checkpoint_merge_eligibility_reusable", "checkpoint_writer_lease_ownership_reusable",
    "contains_private_runtime_payload", "contains_credentials", "contains_host_identifiers", "contains_secret_transport_data",
)
PERSISTED_DECISION_KEYS = {
    "control_loop_decision", "execution_admission_decision", "ci_decision", "merge_eligibility_decision"
}


class MultiSessionError(ValueError):
    pass


def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise MultiSessionError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MultiSessionError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _sha(value: Any, name: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or SHA40.fullmatch(value) is None:
        raise MultiSessionError("SHA_INVALID:" + name)
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise MultiSessionError("BOOLEAN_REQUIRED:" + name)
    return value


def _positive_int(value: Any, name: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MultiSessionError("INTEGER_INVALID:" + name)
    return value


def _exact_keys(obj: Any, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise MultiSessionError(name + "_OBJECT_REQUIRED")
    if set(obj) != keys:
        missing = sorted(keys - set(obj))
        extra = sorted(set(obj) - keys)
        raise MultiSessionError(f"{name}_KEYSET_INVALID:missing={','.join(missing)}:extra={','.join(extra)}")
    return obj


def validate_policy(policy: dict[str, Any]) -> None:
    exact = {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_STEADY_STATE_POLICY",
        "mode": "PLAN_ONLY_MULTI_SESSION_FAIL_CLOSED",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "session_role": "DURABLE_AUTONOMOUS_CONTINUATION_SESSION",
        "handoff_record_role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_HANDOFF_RECORD",
        "snapshot_role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
        "decision_role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_DECISION",
        "retention_payload_policy": "IDENTITIES_AND_PUBLIC_SAFE_PROVIDER_REFERENCES_ONLY",
        "next_boundary": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_STEADY_STATE_EXECUTION",
    }
    for key, expected in exact.items():
        if policy.get(key) != expected:
            raise MultiSessionError("POLICY_FIELD_INVALID:" + key)
    true_fields = (
        "fresh_provider_truth_required_at_every_session_start", "fresh_current_main_required_at_every_session_start",
        "fresh_selected_work_unit_required_at_every_session_start", "fresh_provider_state_required_at_every_session_start",
        "fresh_branch_pr_ci_truth_required_when_applicable", "fresh_wu108_recomputation_required_before_every_session_mutation",
        "fresh_wu109_recomputation_required_before_every_session_mutation", "one_delegated_provider_transaction_per_iteration",
        "mandatory_provider_readback_after_every_delegated_transaction", "next_iteration_requires_previous_readback",
        "checkpoint_refresh_requires_clean_iteration_boundary", "checkpoint_refresh_requires_fresh_provider_readback",
        "checkpoint_refresh_is_hint_only", "checkpoint_refresh_never_grants_mutation_authority",
        "prior_checkpoint_is_immutable_history", "prior_checkpoint_authority_reuse_forbidden",
        "prior_control_loop_decision_reuse_forbidden", "prior_execution_admission_reuse_forbidden",
        "prior_ci_success_reuse_forbidden", "prior_registry_cas_reuse_forbidden", "prior_merge_eligibility_reuse_forbidden",
        "prior_writer_lease_ownership_reuse_forbidden", "provider_truth_supersedes_all_persisted_session_state",
        "interrupted_session_requires_provider_reconciliation_before_mutation",
        "readback_pending_session_requires_provider_readback_before_mutation", "unknown_transaction_outcome_replay_forbidden",
        "classified_failure_requires_separate_authority", "session_target_inheritance_forbidden",
        "session_sequence_must_increase_by_one", "checkpoint_identity_must_change_on_refresh", "public_safety_required",
    )
    for key in true_fields:
        if policy.get(key) is not True:
            raise MultiSessionError("POLICY_REQUIRED_TRUE:" + key)
    if policy.get("maximum_retained_historical_checkpoint_identities") != 8:
        raise MultiSessionError("POLICY_RETENTION_INVALID")
    if set(policy.get("session_start_decisions", [])) != {
        "START_FRESH_RECOMPUTE", "RECONCILE_INTERRUPTED_SESSION", "WAIT_FOR_PROVIDER_READBACK",
        "SEPARATE_AUTHORITY_REQUIRED", "BLOCKED"
    }:
        raise MultiSessionError("POLICY_SESSION_DECISIONS_INVALID")
    if set(policy.get("iteration_decisions", [])) != {
        "ADMIT_FRESH_ITERATION", "REQUIRE_PROVIDER_READBACK", "CLEAN_HANDOFF_READY",
        "SEPARATE_AUTHORITY_REQUIRED", "BLOCKED"
    }:
        raise MultiSessionError("POLICY_ITERATION_DECISIONS_INVALID")
    if policy.get("handoff_classes") != [
        "CLEAN_ITERATION_BOUNDARY", "TRANSACTION_OUTCOME_UNKNOWN", "PROVIDER_READBACK_PENDING"
    ]:
        raise MultiSessionError("POLICY_HANDOFF_CLASSES_INVALID")
    paths = policy.get("anchor_paths")
    blobs = policy.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict) or set(paths) != set(blobs):
        raise MultiSessionError("POLICY_ANCHOR_MAP_INVALID")
    for key in FALSE_AUTH:
        if policy.get(key) is not False:
            raise MultiSessionError("POLICY_AUTHORITY_PRESENT:" + key)


def validate_anchors(policy: dict[str, Any], root: Path = ROOT) -> None:
    for name, rel in sorted(policy["anchor_paths"].items()):
        path = root / rel
        if not path.is_file():
            raise MultiSessionError("ANCHOR_MISSING:" + name)
        actual = blob_sha(path)
        if actual != policy["anchor_blobs"][name]:
            raise MultiSessionError(f"ANCHOR_DRIFT:{name}:{actual}")


def validate_selected_work_unit(obj: Any, name: str) -> dict[str, Any] | None:
    if obj is None:
        return None
    keys = {"work_unit_id", "issue_number", "base_sha", "runtime_required", "provider_open"}
    value = _exact_keys(obj, keys, name)
    if not isinstance(value["work_unit_id"], str) or WU_ID.fullmatch(value["work_unit_id"]) is None:
        raise MultiSessionError(name + "_WORK_UNIT_ID_INVALID")
    _positive_int(value["issue_number"], name + "_ISSUE", 1)
    _sha(value["base_sha"], name + "_BASE")
    _bool(value["runtime_required"], name + "_RUNTIME_REQUIRED")
    _bool(value["provider_open"], name + "_PROVIDER_OPEN")
    return value


def validate_provider_state(obj: Any, name: str) -> dict[str, Any]:
    value = _exact_keys(obj, {"state_branch_head_sha", "registry_blob_sha", "registry_generation"}, name)
    _sha(value["state_branch_head_sha"], name + "_HEAD")
    _sha(value["registry_blob_sha"], name + "_BLOB")
    _positive_int(value["registry_generation"], name + "_GENERATION", 0)
    return value


def validate_execution_state(obj: Any, name: str) -> dict[str, Any]:
    keys = {
        "lease_state", "lease_id", "branch_name", "branch_head_sha", "pull_request_state", "pull_request_number",
        "ci_state", "ci_head_sha"
    }
    value = _exact_keys(obj, keys, name)
    if value["lease_state"] not in {"NONE", "ACTIVE", "RELEASED", "EXPIRED", "UNKNOWN"}:
        raise MultiSessionError(name + "_LEASE_STATE_INVALID")
    if value["lease_id"] is not None and (not isinstance(value["lease_id"], str) or not value["lease_id"]):
        raise MultiSessionError(name + "_LEASE_ID_INVALID")
    if value["branch_name"] is not None and (not isinstance(value["branch_name"], str) or not value["branch_name"]):
        raise MultiSessionError(name + "_BRANCH_NAME_INVALID")
    _sha(value["branch_head_sha"], name + "_BRANCH_HEAD", nullable=True)
    if value["pull_request_state"] not in {"NONE", "OPEN", "MERGED", "CLOSED", "UNKNOWN"}:
        raise MultiSessionError(name + "_PR_STATE_INVALID")
    if value["pull_request_number"] is not None:
        _positive_int(value["pull_request_number"], name + "_PR_NUMBER", 1)
    if value["ci_state"] not in {"NONE", "SUCCESS", "PENDING", "FAILED", "AMBIGUOUS", "UNKNOWN"}:
        raise MultiSessionError(name + "_CI_STATE_INVALID")
    _sha(value["ci_head_sha"], name + "_CI_HEAD", nullable=True)
    return value


def validate_handoff_record(record: Any, policy: dict[str, Any], name: str = "HANDOFF") -> dict[str, Any]:
    keys = {
        "schema_version", "role", "record_state", "session_sequence", "session_id", "checkpoint_id", "checkpoint_blob_sha",
        "previous_checkpoint_id", "retained_historical_checkpoint_ids", "handoff_class", "recorded_main_sha", "selected_work_unit",
        "provider_state", "execution_state", "last_completed_iteration", "provider_readback_completed", "persisted_decisions",
        "checkpoint_is_mutation_authority", "checkpoint_cas_tokens_reusable", "checkpoint_ci_success_reusable",
        "checkpoint_admission_reusable", "checkpoint_merge_eligibility_reusable", "checkpoint_writer_lease_ownership_reusable",
        "contains_private_runtime_payload", "contains_credentials", "contains_host_identifiers", "contains_secret_transport_data"
    }
    value = _exact_keys(record, keys, name)
    if value["schema_version"] != 1 or value["role"] != policy["handoff_record_role"] or value["record_state"] != "PERSISTED_HINT_ONLY":
        raise MultiSessionError(name + "_IDENTITY_INVALID")
    _positive_int(value["session_sequence"], name + "_SESSION_SEQUENCE", 1)
    if not isinstance(value["session_id"], str) or SESSION_ID.fullmatch(value["session_id"]) is None:
        raise MultiSessionError(name + "_SESSION_ID_INVALID")
    if not isinstance(value["checkpoint_id"], str) or CHECKPOINT_ID.fullmatch(value["checkpoint_id"]) is None:
        raise MultiSessionError(name + "_CHECKPOINT_ID_INVALID")
    _sha(value["checkpoint_blob_sha"], name + "_CHECKPOINT_BLOB")
    previous = value["previous_checkpoint_id"]
    if previous is not None and (not isinstance(previous, str) or CHECKPOINT_ID.fullmatch(previous) is None):
        raise MultiSessionError(name + "_PREVIOUS_CHECKPOINT_INVALID")
    history = value["retained_historical_checkpoint_ids"]
    if not isinstance(history, list) or len(history) > policy["maximum_retained_historical_checkpoint_identities"] or len(history) != len(set(history)):
        raise MultiSessionError(name + "_HISTORY_INVALID")
    for checkpoint in history:
        if not isinstance(checkpoint, str) or CHECKPOINT_ID.fullmatch(checkpoint) is None:
            raise MultiSessionError(name + "_HISTORY_ID_INVALID")
    if value["checkpoint_id"] in history:
        raise MultiSessionError(name + "_CURRENT_CHECKPOINT_IN_HISTORY")
    if value["handoff_class"] not in policy["handoff_classes"]:
        raise MultiSessionError(name + "_HANDOFF_CLASS_INVALID")
    _sha(value["recorded_main_sha"], name + "_MAIN")
    validate_selected_work_unit(value["selected_work_unit"], name + "_SELECTED")
    validate_provider_state(value["provider_state"], name + "_PROVIDER")
    validate_execution_state(value["execution_state"], name + "_EXECUTION")
    _positive_int(value["last_completed_iteration"], name + "_ITERATION", 0)
    _bool(value["provider_readback_completed"], name + "_READBACK")
    persisted = _exact_keys(value["persisted_decisions"], PERSISTED_DECISION_KEYS, name + "_PERSISTED")
    for key, persisted_value in persisted.items():
        if persisted_value is not None and (not isinstance(persisted_value, str) or not persisted_value or len(persisted_value) > 128):
            raise MultiSessionError(name + "_PERSISTED_DECISION_INVALID:" + key)
    for key in RECORD_FALSE:
        if value[key] is not False:
            raise MultiSessionError(name + "_FORBIDDEN_FLAG:" + key)
    if value["handoff_class"] == "CLEAN_ITERATION_BOUNDARY" and value["provider_readback_completed"] is not True:
        raise MultiSessionError(name + "_CLEAN_WITHOUT_READBACK")
    return value


def _discarded(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    return sorted(key for key, value in record["persisted_decisions"].items() if value is not None)


def _output(policy: dict[str, Any], phase: str, decision: str, *, prior: dict[str, Any] | None = None,
            reasons: list[str] | None = None, reconciliation: bool = False, readback: bool = False,
            checkpoint_refresh_allowed: bool = False) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": policy["decision_role"],
        "state": "MULTI_SESSION_PLAN_ONLY_PASS" if decision not in {"BLOCKED"} else "MULTI_SESSION_BLOCKED",
        "phase": phase,
        "decision": decision,
        "reasons": reasons or [],
        "discarded_prior_persisted_decisions": _discarded(prior),
        "fresh_wu108_recomputation_required_before_mutation": decision in {"START_FRESH_RECOMPUTE", "ADMIT_FRESH_ITERATION", "CLEAN_HANDOFF_READY"},
        "fresh_wu109_recomputation_required_before_mutation": decision in {"START_FRESH_RECOMPUTE", "ADMIT_FRESH_ITERATION", "CLEAN_HANDOFF_READY"},
        "provider_reconciliation_required": reconciliation,
        "provider_readback_required": readback,
        "checkpoint_refresh_allowed": checkpoint_refresh_allowed,
        "prior_checkpoint_authority_used": False,
        "prior_control_loop_reused": False,
        "prior_execution_admission_reused": False,
        "prior_ci_reused": False,
        "prior_cas_reused": False,
        "prior_merge_eligibility_reused": False,
        "prior_writer_lease_ownership_reused": False,
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
        "branch_mutation_performed": False,
        "pull_request_mutation_performed": False,
        "writer_lease_mutation_performed": False,
        "workflow_rerun_performed": False,
        "merge_performed": False,
        "runtime_action_performed": False,
        "product_runtime_mutation_performed": False,
        "next_boundary": policy["next_boundary"],
    }


def _validate_snapshot_identity(snapshot: Any, policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1 or snapshot.get("role") != policy["snapshot_role"]:
        raise MultiSessionError("SNAPSHOT_IDENTITY_INVALID")
    if snapshot.get("repository") != policy["repository"] or snapshot.get("default_branch") != policy["default_branch"]:
        raise MultiSessionError("SNAPSHOT_PROVIDER_IDENTITY_INVALID")
    return snapshot


def evaluate(snapshot: dict[str, Any], *, policy: dict[str, Any] | None = None, root: Path = ROOT,
             check_anchors: bool = True) -> dict[str, Any]:
    p = policy or load_json(POLICY_PATH)
    prior: dict[str, Any] | None = None
    try:
        validate_policy(p)
        if check_anchors:
            validate_anchors(p, root)
        s = _validate_snapshot_identity(snapshot, p)
        phase = s.get("phase")
        if phase not in {"SESSION_START", "ITERATION", "HANDOFF_REFRESH"}:
            raise MultiSessionError("PHASE_INVALID")
        if s.get("classified_failure_detected") is True:
            return _output(p, phase, "SEPARATE_AUTHORITY_REQUIRED", reasons=["CLASSIFIED_FAILURE_REQUIRES_SEPARATE_AUTHORITY"])
        if s.get("classified_failure_detected") is not False:
            raise MultiSessionError("CLASSIFIED_FAILURE_FLAG_INVALID")

        if phase == "SESSION_START":
            if s.get("provider_truth_fresh") is not True:
                raise MultiSessionError("SESSION_PROVIDER_TRUTH_NOT_FRESH")
            if s.get("contradictory_provider_truth") is not False:
                raise MultiSessionError("SESSION_PROVIDER_TRUTH_CONTRADICTORY")
            _sha(s.get("current_main_sha"), "SESSION_CURRENT_MAIN")
            selected = validate_selected_work_unit(s.get("selected_work_unit"), "SESSION_SELECTED")
            validate_provider_state(s.get("provider_state"), "SESSION_PROVIDER")
            if s.get("branch_pr_ci_truth_fresh") is not True:
                raise MultiSessionError("SESSION_BRANCH_PR_CI_NOT_FRESH")
            sequence = _positive_int(s.get("session_sequence"), "SESSION_SEQUENCE", 1)
            session_id = s.get("session_id")
            if not isinstance(session_id, str) or SESSION_ID.fullmatch(session_id) is None:
                raise MultiSessionError("SESSION_ID_INVALID")
            prior_raw = s.get("prior_handoff")
            if prior_raw is None:
                if sequence != 1:
                    raise MultiSessionError("BOOTSTRAP_SESSION_SEQUENCE_INVALID")
                return _output(p, phase, "START_FRESH_RECOMPUTE")
            prior = validate_handoff_record(prior_raw, p, "PRIOR_HANDOFF")
            if sequence != prior["session_sequence"] + 1:
                raise MultiSessionError("SESSION_SEQUENCE_NOT_MONOTONIC")
            if session_id == prior["session_id"]:
                raise MultiSessionError("SESSION_ID_REUSED")
            handoff_class = prior["handoff_class"]
            if handoff_class == "TRANSACTION_OUTCOME_UNKNOWN":
                return _output(p, phase, "RECONCILE_INTERRUPTED_SESSION", prior=prior,
                               reasons=["UNKNOWN_TRANSACTION_OUTCOME_REQUIRES_PROVIDER_RECONCILIATION"], reconciliation=True)
            if handoff_class == "PROVIDER_READBACK_PENDING":
                return _output(p, phase, "WAIT_FOR_PROVIDER_READBACK", prior=prior,
                               reasons=["PRIOR_PROVIDER_READBACK_PENDING"], reconciliation=True, readback=True)
            if handoff_class != "CLEAN_ITERATION_BOUNDARY":
                raise MultiSessionError("PRIOR_HANDOFF_CLASS_UNHANDLED")
            if selected is None or selected.get("provider_open") is not True:
                raise MultiSessionError("SESSION_FRESH_OPEN_WORK_UNIT_REQUIRED")
            return _output(p, phase, "START_FRESH_RECOMPUTE", prior=prior)

        if phase == "ITERATION":
            if s.get("provider_truth_fresh") is not True:
                raise MultiSessionError("ITERATION_PROVIDER_TRUTH_NOT_FRESH")
            _positive_int(s.get("session_sequence"), "ITERATION_SESSION_SEQUENCE", 1)
            _positive_int(s.get("iteration_sequence"), "ITERATION_SEQUENCE", 1)
            if s.get("control_loop_fresh_for_iteration") is not True:
                raise MultiSessionError("ITERATION_CONTROL_NOT_FRESH")
            if s.get("execution_admission_fresh_for_iteration") is not True:
                raise MultiSessionError("ITERATION_ADMISSION_NOT_FRESH")
            if s.get("control_loop_reused_from_prior_session") is not False:
                raise MultiSessionError("ITERATION_CONTROL_REUSED")
            if s.get("execution_admission_reused_from_prior_session") is not False:
                raise MultiSessionError("ITERATION_ADMISSION_REUSED")
            if s.get("registry_cas_reused_from_prior_session") is not False:
                raise MultiSessionError("ITERATION_CAS_REUSED")
            if s.get("previous_iteration_provider_readback_completed") is not True and s.get("iteration_sequence") != 1:
                raise MultiSessionError("PREVIOUS_ITERATION_READBACK_REQUIRED")
            transaction = s.get("delegated_transaction")
            if not isinstance(transaction, dict):
                raise MultiSessionError("ITERATION_TRANSACTION_REQUIRED")
            count = _positive_int(transaction.get("delegated_transaction_count"), "TRANSACTION_COUNT", 0)
            performed = _bool(transaction.get("provider_mutation_performed"), "TRANSACTION_PERFORMED")
            readback = _bool(transaction.get("fresh_provider_readback_completed"), "TRANSACTION_READBACK")
            if count > 1:
                raise MultiSessionError("BATCHED_TRANSACTION_FORBIDDEN")
            if not performed:
                if count != 0 or readback:
                    raise MultiSessionError("UNPERFORMED_TRANSACTION_STATE_INVALID")
                return _output(p, phase, "ADMIT_FRESH_ITERATION")
            if count != 1:
                raise MultiSessionError("PERFORMED_TRANSACTION_COUNT_INVALID")
            if not readback:
                return _output(p, phase, "REQUIRE_PROVIDER_READBACK", readback=True)
            return _output(p, phase, "CLEAN_HANDOFF_READY", checkpoint_refresh_allowed=True)

        if s.get("provider_truth_fresh") is not True:
            raise MultiSessionError("REFRESH_PROVIDER_TRUTH_NOT_FRESH")
        if s.get("fresh_provider_readback_completed") is not True:
            raise MultiSessionError("REFRESH_PROVIDER_READBACK_REQUIRED")
        prior = validate_handoff_record(s.get("prior_handoff"), p, "REFRESH_PRIOR")
        new = validate_handoff_record(s.get("new_handoff"), p, "REFRESH_NEW")
        if prior["handoff_class"] != "CLEAN_ITERATION_BOUNDARY" or new["handoff_class"] != "CLEAN_ITERATION_BOUNDARY":
            raise MultiSessionError("REFRESH_REQUIRES_CLEAN_BOUNDARIES")
        if new["session_sequence"] != prior["session_sequence"] + 1:
            raise MultiSessionError("REFRESH_SESSION_SEQUENCE_INVALID")
        if new["checkpoint_id"] == prior["checkpoint_id"] or new["checkpoint_blob_sha"] == prior["checkpoint_blob_sha"]:
            raise MultiSessionError("REFRESH_CHECKPOINT_IDENTITY_NOT_ADVANCED")
        if new["previous_checkpoint_id"] != prior["checkpoint_id"]:
            raise MultiSessionError("REFRESH_PREVIOUS_CHECKPOINT_BINDING_INVALID")
        if prior["checkpoint_id"] not in new["retained_historical_checkpoint_ids"]:
            raise MultiSessionError("REFRESH_PRIOR_CHECKPOINT_NOT_RETAINED")
        if new["recorded_main_sha"] != s.get("current_main_sha"):
            raise MultiSessionError("REFRESH_MAIN_BINDING_INVALID")
        if new["selected_work_unit"] != s.get("selected_work_unit"):
            raise MultiSessionError("REFRESH_SELECTED_WORK_UNIT_BINDING_INVALID")
        if new["provider_state"] != s.get("provider_state"):
            raise MultiSessionError("REFRESH_PROVIDER_STATE_BINDING_INVALID")
        if new["execution_state"] != s.get("execution_state"):
            raise MultiSessionError("REFRESH_EXECUTION_STATE_BINDING_INVALID")
        return _output(p, phase, "CLEAN_HANDOFF_READY", prior=prior, checkpoint_refresh_allowed=True)
    except (KeyError, TypeError) as exc:
        raise MultiSessionError("SNAPSHOT_STRUCTURE_INVALID:" + type(exc).__name__) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--no-anchor-check", action="store_true")
    args = parser.parse_args()
    try:
        result = evaluate(load_json(args.snapshot), check_anchors=not args.no_anchor_check)
    except MultiSessionError as exc:
        print(json.dumps({
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_DECISION",
            "state": "MULTI_SESSION_BLOCKED",
            "decision": "BLOCKED",
            "reason": str(exc),
        }, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
