#!/usr/bin/env python3
"""Fail-closed replay validator for PIPE-WU-118 multi-session execution evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-execution-wu118.json"
POLICY_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-steady-state-policy.json"
EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_durable_autonomous_continuation_multi_session_steady_state.py"
SESSION1_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-handoff-record-wu117.json"
SESSION2_CHECKPOINT_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-session-checkpoint-wu118.json"
SESSION2_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-multi-session-handoff-record-wu118.json"

EXPECTED = {
    "evidence": "33c887d92e4f7e2fde384f5946a3240142a6bd4a",
    "policy": "1c1107d0d8ef446b0e07848b2fbf1dd30dea07bd",
    "evaluator": "58b8d1e73a7436be754b75d111c9695bccd3e888",
    "session1": "bb1e1ef834184a4dddfdcdb239d7bd2dc75d187d",
    "session2_checkpoint": "b458e310ce54a86e9be0ecc7e1fda4e9530d6e92",
    "session2": "19fa9c3d93f007651574be484b1fb2963164efcd",
    "control_policy": "822bcd1833ff4843b6bd176337b3ef3b742275de",
    "admission_policy": "406d78da6250c452bfc7706b57dc51a18ca48977",
    "writer_grant": "717e1f9081915f40fad2e0620c64245a650ca235",
}
ANCHORS = {
    "evidence": EVIDENCE_PATH,
    "policy": POLICY_PATH,
    "evaluator": EVALUATOR_PATH,
    "session1": SESSION1_PATH,
    "session2_checkpoint": SESSION2_CHECKPOINT_PATH,
    "session2": SESSION2_PATH,
    "control_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json",
    "admission_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json",
    "writer_grant": ROOT / ".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json",
}


class ValidationError(ValueError):
    pass


def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValidationError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValidationError("MODULE_LOAD_FAILED:" + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_true(value: Any, name: str) -> None:
    if value is not True:
        raise ValidationError("REQUIRED_TRUE:" + name)


def require_false(value: Any, name: str) -> None:
    if value is not False:
        raise ValidationError("REQUIRED_FALSE:" + name)


def require_equal(actual: Any, expected: Any, name: str) -> None:
    if actual != expected:
        raise ValidationError(f"MISMATCH:{name}:actual={actual!r}:expected={expected!r}")


def validate_anchors(evidence: dict[str, Any]) -> None:
    for name, path in ANCHORS.items():
        if not path.is_file():
            raise ValidationError("ANCHOR_MISSING:" + name)
        actual = blob_sha(path)
        if actual != EXPECTED[name]:
            raise ValidationError(f"ANCHOR_DRIFT:{name}:{actual}")
    fields = {
        "multi_session_policy_blob_sha": EXPECTED["policy"],
        "multi_session_evaluator_blob_sha": EXPECTED["evaluator"],
        "session_1_handoff_blob_sha": EXPECTED["session1"],
        "session_2_checkpoint_blob_sha": EXPECTED["session2_checkpoint"],
        "session_2_handoff_blob_sha": EXPECTED["session2"],
        "control_loop_policy_blob_sha": EXPECTED["control_policy"],
        "execution_admission_policy_blob_sha": EXPECTED["admission_policy"],
        "delegated_authority_grant_blob_sha": EXPECTED["writer_grant"],
    }
    for field, expected in fields.items():
        require_equal(evidence.get(field), expected, "evidence." + field)


def _session_start_snapshot(evidence: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    start = evidence["session_2_start"]
    pstate = start["provider_state_before_transaction"]
    return {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
        "phase": "SESSION_START",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "classified_failure_detected": False,
        "provider_truth_fresh": start["provider_truth_fresh"],
        "contradictory_provider_truth": False,
        "current_main_sha": start["current_main_sha"],
        "selected_work_unit": copy.deepcopy(start["selected_work_unit"]),
        "provider_state": {
            "state_branch_head_sha": pstate["state_branch_head_sha"],
            "registry_blob_sha": pstate["registry_blob_sha"],
            "registry_generation": pstate["registry_generation"],
        },
        "branch_pr_ci_truth_fresh": start["branch_pr_ci_truth_fresh"],
        "session_sequence": start["session_sequence"],
        "session_id": start["session_id"],
        "prior_handoff": copy.deepcopy(prior),
    }


def replay_session_start(evidence: dict[str, Any], evaluator: Any, policy: dict[str, Any], session1: dict[str, Any]) -> None:
    snapshot = _session_start_snapshot(evidence, session1)
    result = evaluator.evaluate(snapshot, policy=policy, check_anchors=True)
    require_equal(result.get("decision"), "START_FRESH_RECOMPUTE", "session_start.decision")
    require_false(result.get("prior_checkpoint_authority_used"), "session_start.prior_checkpoint_authority_used")
    require_false(result.get("prior_control_loop_reused"), "session_start.prior_control_loop_reused")
    require_false(result.get("prior_execution_admission_reused"), "session_start.prior_execution_admission_reused")
    require_false(result.get("prior_ci_reused"), "session_start.prior_ci_reused")
    require_false(result.get("prior_cas_reused"), "session_start.prior_cas_reused")
    require_false(result.get("prior_merge_eligibility_reused"), "session_start.prior_merge_reused")
    require_false(result.get("prior_writer_lease_ownership_reused"), "session_start.prior_lease_reused")
    require_true(result.get("fresh_wu108_recomputation_required_before_mutation"), "session_start.wu108")
    require_true(result.get("fresh_wu109_recomputation_required_before_mutation"), "session_start.wu109")
    require_equal(
        set(result.get("discarded_prior_persisted_decisions", [])),
        {"control_loop_decision", "execution_admission_decision"},
        "session_start.discarded_decisions",
    )

    interrupted = copy.deepcopy(session1)
    interrupted["handoff_class"] = "TRANSACTION_OUTCOME_UNKNOWN"
    interrupted_snapshot = _session_start_snapshot(evidence, interrupted)
    interrupted_result = evaluator.evaluate(interrupted_snapshot, policy=policy, check_anchors=True)
    require_equal(interrupted_result.get("decision"), "RECONCILE_INTERRUPTED_SESSION", "interrupted.decision")
    require_true(interrupted_result.get("provider_reconciliation_required"), "interrupted.reconciliation")
    require_false(interrupted_result.get("prior_checkpoint_authority_used"), "interrupted.prior_authority")

    pending = copy.deepcopy(session1)
    pending["handoff_class"] = "PROVIDER_READBACK_PENDING"
    pending["provider_readback_completed"] = False
    pending_snapshot = _session_start_snapshot(evidence, pending)
    pending_result = evaluator.evaluate(pending_snapshot, policy=policy, check_anchors=True)
    require_equal(pending_result.get("decision"), "WAIT_FOR_PROVIDER_READBACK", "pending.decision")
    require_true(pending_result.get("provider_reconciliation_required"), "pending.reconciliation")
    require_true(pending_result.get("provider_readback_required"), "pending.readback")
    require_false(pending_result.get("prior_checkpoint_authority_used"), "pending.prior_authority")


def replay_iterations(evidence: dict[str, Any], evaluator: Any, policy: dict[str, Any]) -> None:
    iterations = evidence.get("session_2_iterations")
    if not isinstance(iterations, list) or len(iterations) != 2:
        raise ValidationError("SESSION2_ITERATION_COUNT_INVALID")
    for item in iterations:
        sequence = item["iteration_sequence"]
        snapshot = {
            "schema_version": 1,
            "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
            "phase": "ITERATION",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "classified_failure_detected": False,
            "provider_truth_fresh": item["provider_truth_fresh"],
            "session_sequence": 2,
            "iteration_sequence": sequence,
            "control_loop_fresh_for_iteration": item["control_loop_fresh_for_iteration"],
            "execution_admission_fresh_for_iteration": item["execution_admission_fresh_for_iteration"],
            "control_loop_reused_from_prior_session": item["control_loop_reused_from_prior_session"],
            "execution_admission_reused_from_prior_session": item["execution_admission_reused_from_prior_session"],
            "registry_cas_reused_from_prior_session": item["registry_cas_reused_from_prior_session"],
            "previous_iteration_provider_readback_completed": item["previous_iteration_provider_readback_completed"],
            "delegated_transaction": {
                "delegated_transaction_count": item["delegated_transaction_count"],
                "provider_mutation_performed": item["transaction_result"]["provider_mutation_performed"],
                "fresh_provider_readback_completed": item["fresh_provider_readback_completed"],
            },
        }
        result = evaluator.evaluate(snapshot, policy=policy, check_anchors=True)
        require_equal(result.get("decision"), "CLEAN_HANDOFF_READY", f"iteration{sequence}.decision")
        require_true(result.get("checkpoint_refresh_allowed"), f"iteration{sequence}.refresh_allowed")
        require_false(result.get("prior_checkpoint_authority_used"), f"iteration{sequence}.prior_authority")

        pending = copy.deepcopy(snapshot)
        pending["delegated_transaction"]["fresh_provider_readback_completed"] = False
        pending_result = evaluator.evaluate(pending, policy=policy, check_anchors=True)
        require_equal(pending_result.get("decision"), "REQUIRE_PROVIDER_READBACK", f"iteration{sequence}.pending_decision")
        require_true(pending_result.get("provider_readback_required"), f"iteration{sequence}.pending_readback")


def replay_refresh(evidence: dict[str, Any], evaluator: Any, policy: dict[str, Any], session1: dict[str, Any], session2: dict[str, Any]) -> None:
    refresh = evidence["session_2_handoff_refresh"]
    selected = evidence["session_2_start"]["selected_work_unit"]
    provider = session2["provider_state"]
    execution = session2["execution_state"]
    snapshot = {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_SNAPSHOT",
        "phase": "HANDOFF_REFRESH",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "classified_failure_detected": False,
        "provider_truth_fresh": refresh["provider_truth_fresh"],
        "fresh_provider_readback_completed": refresh["fresh_provider_readback_completed"],
        "prior_handoff": copy.deepcopy(session1),
        "new_handoff": copy.deepcopy(session2),
        "current_main_sha": evidence["session_2_start"]["current_main_sha"],
        "selected_work_unit": copy.deepcopy(selected),
        "provider_state": copy.deepcopy(provider),
        "execution_state": copy.deepcopy(execution),
    }
    result = evaluator.evaluate(snapshot, policy=policy, check_anchors=True)
    require_equal(result.get("decision"), "CLEAN_HANDOFF_READY", "refresh.decision")
    require_true(result.get("checkpoint_refresh_allowed"), "refresh.allowed")
    require_false(result.get("prior_checkpoint_authority_used"), "refresh.prior_authority")


def validate_evidence(evidence: dict[str, Any], *, check_anchors: bool = True, replay: bool = True) -> dict[str, Any]:
    exact = {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_STEADY_STATE_EXECUTION_EVIDENCE",
        "evidence_state": "RECORDED",
        "work_unit_id": "PIPE-WU-118",
        "issue_number": 284,
        "base_main_sha": "395ed526d845ea7bb084467fe20237b3c5edf92e",
        "frontier_id": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_STEADY_STATE_EXECUTION",
        "predecessor_frontier_blob_sha": "8d200456847139a9490df81c2797940b614eabbd",
        "branch": "agent/PIPE-WU-118-durable-autonomous-continuation-multi-session-steady-state-execution",
        "next_boundary": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_ASSESSMENT",
    }
    for field, expected in exact.items():
        require_equal(evidence.get(field), expected, field)
    if check_anchors:
        validate_anchors(evidence)

    require_equal(evidence.get("independent_session_count"), 2, "independent_session_count")
    for flag in (
        "session_sequence_monotonic", "session_ids_distinct", "checkpoint_ids_distinct",
        "provider_drift_between_sessions_detected", "fresh_provider_truth_superseded_prior_checkpoint",
        "fresh_control_loop_and_admission_per_iteration", "all_delegated_transactions_followed_by_fresh_readback",
        "checkpoint_history_bounded_and_public_safe",
    ):
        require_true(evidence.get(flag), flag)
    for flag in (
        "stale_prior_session_authority_reuse_performed", "batch_provider_mutation_performed",
        "product_runtime_mutation_performed", "runtime_action_performed", "adwf_binding_or_repository_mutation_performed",
        "release_tag_promotion_performed", "ruleset_policy_mutation_performed", "private_evidence_publication_performed",
        "reserve_1080_lifecycle_mutation_performed", "primary_1081_lifecycle_mutation_performed", "authority_broadening_performed",
    ):
        require_false(evidence.get(flag), flag)

    session1_summary = evidence.get("session_1")
    session2_start = evidence.get("session_2_start")
    if not isinstance(session1_summary, dict) or not isinstance(session2_start, dict):
        raise ValidationError("SESSION_SUMMARIES_REQUIRED")
    require_equal(session1_summary.get("session_sequence"), 1, "session1.sequence")
    require_equal(session2_start.get("session_sequence"), 2, "session2.sequence")
    if session1_summary.get("session_id") == session2_start.get("session_id"):
        raise ValidationError("SESSION_ID_REUSED")
    if session1_summary.get("checkpoint_id") == evidence["session_2_handoff_refresh"].get("new_checkpoint_id"):
        raise ValidationError("CHECKPOINT_ID_REUSED")
    require_false(session1_summary.get("checkpoint_is_mutation_authority"), "session1.checkpoint_authority")
    require_true(session1_summary.get("provider_readback_completed"), "session1.readback")

    require_true(session2_start.get("provider_truth_fresh"), "session2.provider_truth_fresh")
    require_true(session2_start.get("branch_pr_ci_truth_fresh"), "session2.branch_pr_ci_fresh")
    require_equal(session2_start.get("decision"), "START_FRESH_RECOMPUTE", "session2.decision")
    require_true(session2_start.get("fresh_wu108_recomputation_required_before_mutation"), "session2.wu108")
    require_true(session2_start.get("fresh_wu109_recomputation_required_before_mutation"), "session2.wu109")
    for flag in (
        "prior_checkpoint_authority_used", "prior_control_loop_reused", "prior_execution_admission_reused",
        "prior_ci_reused", "prior_cas_reused", "prior_merge_eligibility_reused", "prior_writer_lease_ownership_reused",
    ):
        require_false(session2_start.get(flag), "session2." + flag)
    require_equal(
        set(session2_start.get("discarded_prior_persisted_decisions", [])),
        {"control_loop_decision", "execution_admission_decision"},
        "session2.discarded_prior_decisions",
    )

    before = session2_start["provider_state_before_transaction"]
    require_equal(before.get("registry_generation"), 25, "provider_before.generation")
    require_equal(before.get("wu117_lease_state"), "RELEASED", "provider_before.wu117_state")
    require_false(before.get("wu118_lease_present"), "provider_before.wu118_present")
    iterations = evidence.get("session_2_iterations")
    if not isinstance(iterations, list) or len(iterations) != 2:
        raise ValidationError("SESSION2_ITERATION_COUNT_INVALID")
    expected_kinds = ["WRITER_LEASE_ACQUISITION", "BOUNDED_BRANCH_CREATE"]
    for index, item in enumerate(iterations):
        require_equal(item.get("iteration_sequence"), index + 1, f"iteration{index+1}.sequence")
        require_equal(item.get("transaction_kind"), expected_kinds[index], f"iteration{index+1}.kind")
        require_equal(item.get("delegated_transaction_count"), 1, f"iteration{index+1}.count")
        require_true(item.get("provider_truth_fresh"), f"iteration{index+1}.provider_fresh")
        require_true(item.get("control_loop_fresh_for_iteration"), f"iteration{index+1}.control_fresh")
        require_true(item.get("execution_admission_fresh_for_iteration"), f"iteration{index+1}.admission_fresh")
        require_false(item.get("control_loop_reused_from_prior_session"), f"iteration{index+1}.control_reused")
        require_false(item.get("execution_admission_reused_from_prior_session"), f"iteration{index+1}.admission_reused")
        require_false(item.get("registry_cas_reused_from_prior_session"), f"iteration{index+1}.cas_reused")
        require_true(item.get("fresh_provider_readback_completed"), f"iteration{index+1}.readback")
        require_true(item.get("readback_matches_expected_transaction"), f"iteration{index+1}.readback_match")
        require_true(item.get("transaction_result", {}).get("provider_mutation_performed"), f"iteration{index+1}.mutation_evidence")
    require_false(iterations[0].get("previous_iteration_provider_readback_completed"), "iteration1.previous_readback")
    require_true(iterations[1].get("previous_iteration_provider_readback_completed"), "iteration2.previous_readback")
    require_equal(iterations[0]["provider_state_before"].get("registry_generation"), 25, "iteration1.before_generation")
    require_equal(iterations[0]["provider_state_after"].get("registry_generation"), 26, "iteration1.after_generation")
    require_equal(iterations[1]["provider_state_before"].get("registry_generation"), 26, "iteration2.before_generation")
    require_equal(iterations[1]["provider_state_after"].get("registry_generation"), 26, "iteration2.after_generation")
    require_equal(iterations[1]["branch_state_after"].get("compare_status"), "identical", "iteration2.compare")
    require_equal(iterations[1]["branch_state_after"].get("ahead_by"), 0, "iteration2.ahead")
    require_equal(iterations[1]["branch_state_after"].get("behind_by"), 0, "iteration2.behind")

    refresh = evidence.get("session_2_handoff_refresh")
    if not isinstance(refresh, dict):
        raise ValidationError("HANDOFF_REFRESH_REQUIRED")
    require_true(refresh.get("provider_truth_fresh"), "refresh.provider_fresh")
    require_true(refresh.get("fresh_provider_readback_completed"), "refresh.readback")
    require_equal(refresh.get("decision"), "CLEAN_HANDOFF_READY", "refresh.decision")
    require_true(refresh.get("checkpoint_refresh_allowed"), "refresh.allowed")
    require_false(refresh.get("prior_checkpoint_content_mutated"), "refresh.prior_content_mutated")
    require_false(refresh.get("prior_checkpoint_authority_used"), "refresh.prior_authority")
    require_equal(refresh.get("prior_checkpoint_id"), "PNCC-CONTINUATION-CHECKPOINT-WU117-CLEAN-A1", "refresh.prior_checkpoint")
    require_equal(refresh.get("new_checkpoint_id"), "PNCC-CONTINUATION-CHECKPOINT-WU118-CLEAN-A2", "refresh.new_checkpoint")

    paths = evidence.get("reconciliation_paths")
    if not isinstance(paths, dict):
        raise ValidationError("RECONCILIATION_PATHS_REQUIRED")
    interrupted = paths.get("interrupted", {})
    pending = paths.get("readback_pending", {})
    require_equal(interrupted.get("expected_decision"), "RECONCILE_INTERRUPTED_SESSION", "interrupted.expected")
    require_true(interrupted.get("provider_reconciliation_required"), "interrupted.reconciliation")
    require_false(interrupted.get("delegated_transaction_replayed"), "interrupted.replayed")
    require_false(interrupted.get("new_mutation_before_reconciliation"), "interrupted.mutation_before_reconcile")
    require_equal(pending.get("expected_decision"), "WAIT_FOR_PROVIDER_READBACK", "pending.expected")
    require_true(pending.get("provider_readback_required"), "pending.readback")
    require_false(pending.get("delegated_transaction_replayed"), "pending.replayed")
    require_false(pending.get("new_mutation_before_readback"), "pending.mutation_before_readback")

    if replay:
        evaluator = load_module(EVALUATOR_PATH, "wu118_multi_session_replay")
        policy = load_json(POLICY_PATH)
        evaluator.validate_policy(policy)
        evaluator.validate_anchors(policy)
        session1 = load_json(SESSION1_PATH)
        session2 = load_json(SESSION2_PATH)
        evaluator.validate_handoff_record(session1, policy, "SESSION1")
        evaluator.validate_handoff_record(session2, policy, "SESSION2")
        replay_session_start(evidence, evaluator, policy, session1)
        replay_iterations(evidence, evaluator, policy)
        replay_refresh(evidence, evaluator, policy, session1, session2)

    return {
        "schema_version": 1,
        "role": "WU118_MULTI_SESSION_EXECUTION_VALIDATION_RESULT",
        "state": "PASS",
        "work_unit_id": "PIPE-WU-118",
        "independent_session_count": 2,
        "session_start_replayed": replay,
        "iterations_replayed": replay,
        "handoff_refresh_replayed": replay,
        "reconciliation_paths_replayed": replay,
        "authority_broadening_performed": False,
        "product_runtime_mutation_performed": False,
        "next_boundary": "AUTONOMOUS_CONTINUATION_HUMAN_BY_EXCEPTION_READINESS_ASSESSMENT",
    }


def main() -> int:
    try:
        result = validate_evidence(load_json(EVIDENCE_PATH), check_anchors=True, replay=True)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema_version": 1,
            "role": "WU118_MULTI_SESSION_EXECUTION_VALIDATION_RESULT",
            "state": "BLOCKED",
            "reason": f"{type(exc).__name__}:{exc}",
        }, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
