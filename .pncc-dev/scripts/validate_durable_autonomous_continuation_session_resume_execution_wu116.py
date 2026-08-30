#!/usr/bin/env python3
"""Validate and replay PIPE-WU-116 durable continuation session-resume execution evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-session-resume-execution-wu116.json"
CHECKPOINT_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-session-checkpoint-wu115.json"
RESUME_POLICY_PATH = ROOT / ".pncc-dev/contracts/durable-autonomous-continuation-session-resume-policy.json"
RESUME_EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_durable_autonomous_continuation_session_resume.py"
STEADY_POLICY_PATH = ROOT / ".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-policy.json"
STEADY_EVALUATOR_PATH = ROOT / ".pncc-dev/scripts/evaluate_reusable_autonomous_continuation_steady_state.py"

EXPECTED = {
    "checkpoint": "aa7b7e7cf2fa9657bb3897d47055971466975965",
    "resume_policy": "4305cd65c2ed7eaf67a6a6df24d3b4bb4d612446",
    "resume_evaluator": "f55d7d4de713e75f13a726292f61dad035c0a2a7",
    "steady_policy": "6957f09565a66e7b7f7206a640157aac4491bfa8",
    "steady_evaluator": "66af19669dbd7efff1aa3709d263c590fcec5108",
    "control_policy": "822bcd1833ff4843b6bd176337b3ef3b742275de",
    "control_evaluator": "1f794892cfec466505a1a6c38b271492f9759127",
    "admission_policy": "406d78da6250c452bfc7706b57dc51a18ca48977",
    "admission_evaluator": "cde13515632717b81cef77876e53e9ceef0c46bf",
    "writer_grant": "717e1f9081915f40fad2e0620c64245a650ca235",
}
ANCHORS = {
    "checkpoint": CHECKPOINT_PATH,
    "resume_policy": RESUME_POLICY_PATH,
    "resume_evaluator": RESUME_EVALUATOR_PATH,
    "steady_policy": STEADY_POLICY_PATH,
    "steady_evaluator": STEADY_EVALUATOR_PATH,
    "control_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json",
    "control_evaluator": ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py",
    "admission_policy": ROOT / ".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json",
    "admission_evaluator": ROOT / ".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py",
    "writer_grant": ROOT / ".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json",
}

class ValidationError(ValueError):
    pass


def _strict(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValidationError(f"DUPLICATE_KEY:{key}")
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
        raise ValidationError(f"MODULE_LOAD_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_true(value: Any, name: str) -> None:
    if value is not True:
        raise ValidationError(f"REQUIRED_TRUE:{name}")


def assert_false(value: Any, name: str) -> None:
    if value is not False:
        raise ValidationError(f"REQUIRED_FALSE:{name}")


def validate_anchors(e: dict[str, Any]) -> None:
    for name, path in ANCHORS.items():
        if not path.is_file():
            raise ValidationError(f"ANCHOR_MISSING:{name}")
        actual = blob_sha(path)
        if actual != EXPECTED[name]:
            raise ValidationError(f"ANCHOR_DRIFT:{name}:{actual}")
    evidence_fields = {
        "checkpoint_blob_sha": EXPECTED["checkpoint"],
        "resume_policy_blob_sha": EXPECTED["resume_policy"],
        "resume_evaluator_blob_sha": EXPECTED["resume_evaluator"],
        "steady_state_policy_blob_sha": EXPECTED["steady_policy"],
        "steady_state_evaluator_blob_sha": EXPECTED["steady_evaluator"],
        "control_loop_policy_blob_sha": EXPECTED["control_policy"],
        "control_loop_evaluator_blob_sha": EXPECTED["control_evaluator"],
        "execution_admission_policy_blob_sha": EXPECTED["admission_policy"],
        "execution_admission_evaluator_blob_sha": EXPECTED["admission_evaluator"],
        "delegated_authority_grant_blob_sha": EXPECTED["writer_grant"],
    }
    for field, expected in evidence_fields.items():
        if e.get(field) != expected:
            raise ValidationError(f"EVIDENCE_ANCHOR_MISMATCH:{field}")


def _plan_flags() -> dict[str, bool]:
    return {
        "provider_mutation_performed": False,
        "issue_mutation_performed": False,
        "branch_mutation_performed": False,
        "pull_request_mutation_performed": False,
        "writer_lease_mutation_performed": False,
        "workflow_rerun_performed": False,
        "merge_performed": False,
        "runtime_action_performed": False,
        "product_runtime_mutation_performed": False,
    }


def _control(decision: str) -> dict[str, Any]:
    out = {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_CONTROL_LOOP_DECISION",
        "state": "PLAN_ONLY_CONTROL_LOOP_PASS",
        "decision": decision,
    }
    out.update(_plan_flags())
    return out


def _admission(control_decision: str, target: str) -> dict[str, Any]:
    out = {
        "schema_version": 1,
        "role": "AUTONOMOUS_CONTINUATION_EXECUTION_ADMISSION_DECISION",
        "state": "PLAN_ONLY_ADMISSION_PASS",
        "decision": "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY",
        "control_loop_decision": control_decision,
        "delegated_authority": "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY",
        "target_action": target,
    }
    out.update(_plan_flags())
    return out


def replay_resume(e: dict[str, Any]) -> None:
    resume = load_module(RESUME_EVALUATOR_PATH, "wu116_resume_replay")
    policy = load_json(RESUME_POLICY_PATH)
    checkpoint = load_json(CHECKPOINT_PATH)
    fresh = e["fresh_resume_truth_before_transaction"]
    selected = fresh["selected_work_unit"]
    provider = fresh["provider_state"]
    execution = {
        "lease": {"state": "NONE", "lease_id": None, "generation": None, "branch": None},
        "branch": {"present": False, "name": None, "head_sha": None},
        "pull_request": {"state": "NONE", "number": None, "base_sha": None, "head_sha": None, "merge_commit_sha": None},
        "ci": {"state": "NONE", "head_sha": None},
    }
    snapshot = {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_SNAPSHOT",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "default_branch": "main",
        "provider_truth_fresh": True,
        "contradictory_provider_truth": False,
        "current_main_sha": fresh["current_main_sha"],
        "selected_work_unit": selected,
        "provider_state": {
            "state_branch_present": True,
            "state_branch_head_sha": provider["state_branch_head_sha"],
            "registry_blob_sha": provider["registry_blob_sha"],
            "registry_generation": provider["registry_generation"],
        },
        "execution_state": execution,
        "classified_failure_detected": False,
        "fresh_provider_readback_completed": True,
        "checkpoint": checkpoint,
    }
    result = resume.evaluate(snapshot, policy=policy)
    if result.get("decision") != "RECOMPUTE_FRESH_CONTINUATION":
        raise ValidationError(f"RESUME_REPLAY_DECISION:{result}")
    if result.get("checkpoint_authority_used") is not False:
        raise ValidationError("CHECKPOINT_AUTHORITY_REPLAYED")
    if set(result.get("discarded_persisted_decisions", [])) != {"control_loop_decision", "execution_admission_decision"}:
        raise ValidationError("PERSISTED_DECISIONS_NOT_DISCARDED")

    interrupted = copy.deepcopy(checkpoint)
    interrupted["transaction_boundary"] = "TRANSACTION_OUTCOME_UNKNOWN"
    interrupted_snapshot = copy.deepcopy(snapshot)
    interrupted_snapshot["checkpoint"] = interrupted
    interrupted_result = resume.evaluate(interrupted_snapshot, policy=policy)
    if interrupted_result.get("decision") != "RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH":
        raise ValidationError(f"INTERRUPTED_REPLAY_DECISION:{interrupted_result}")
    if interrupted_result.get("provider_reconciliation_required") is not True:
        raise ValidationError("INTERRUPTED_RECONCILIATION_NOT_REQUIRED")

    pending = copy.deepcopy(checkpoint)
    pending["transaction_boundary"] = "PROVIDER_READBACK_PENDING"
    pending_snapshot = copy.deepcopy(snapshot)
    pending_snapshot["checkpoint"] = pending
    pending_snapshot["fresh_provider_readback_completed"] = False
    pending_result = resume.evaluate(pending_snapshot, policy=policy)
    if pending_result.get("decision") != "WAIT_FOR_FRESH_PROVIDER_READBACK":
        raise ValidationError(f"PENDING_REPLAY_DECISION:{pending_result}")


def replay_iterations(e: dict[str, Any]) -> None:
    steady = load_module(STEADY_EVALUATOR_PATH, "wu116_steady_replay")
    policy = load_json(STEADY_POLICY_PATH)
    iterations = e["post_handoff_iterations"]
    for item in iterations:
        seq = item["iteration_sequence"]
        transaction = {
            "state": "PERFORMED_READBACK_COMPLETE",
            "delegated_transaction_count": item["delegated_transaction_count"],
            "delegated_authority_identity": item["delegated_authority_identity"],
            "target_action": item["target_action"],
            "provider_mutation_performed": item["transaction_result"]["provider_mutation_performed"],
            "fresh_provider_readback_completed": item["fresh_provider_readback_completed"],
            "provider_state_after": {
                "fresh": True,
                "identity": item["provider_state_after"]["state_branch_head_sha"] + ":" + item["provider_state_after"]["registry_blob_sha"],
            },
        }
        snapshot = {
            "schema_version": 1,
            "role": "REUSABLE_AUTONOMOUS_CONTINUATION_STEADY_STATE_SNAPSHOT",
            "repository": "kmephis-ai/VPS-Control-PNCC",
            "default_branch": "main",
            "provider_truth_fresh": item["provider_truth_fresh"],
            "current_main_sha": e["base_main_sha"],
            "iteration_sequence": seq,
            "control_loop_fresh_for_iteration": item["control_loop_fresh_for_iteration"],
            "execution_admission_fresh_for_iteration": item["execution_admission_fresh_for_iteration"],
            "control_loop_reused_from_prior_iteration": item["control_loop_reused_from_prior_session"],
            "execution_admission_reused_from_prior_iteration": item["execution_admission_reused_from_prior_session"],
            "previous_iteration_fresh_provider_readback_completed": item["previous_iteration_fresh_provider_readback_completed"],
            "interrupted": False,
            "stale_state": False,
            "contradiction_detected": False,
            "anchor_drift_detected": False,
            "revocation_detected": False,
            "classified_failure_detected": False,
            "control_loop_decision": _control(item["control_loop_decision"]),
            "execution_admission_decision": _admission(item["control_loop_decision"], item["target_action"]),
            "delegated_transaction": transaction,
        }
        result = steady.evaluate(snapshot, policy=policy)
        if result.get("decision") != "ITERATION_COMPLETE_NEXT_FRESH_ITERATION_ALLOWED":
            raise ValidationError(f"STEADY_REPLAY_FAILED:{seq}:{result}")
        if result.get("delegated_transaction_count") != 1:
            raise ValidationError(f"STEADY_TRANSACTION_COUNT:{seq}")


def validate_evidence(e: dict[str, Any], *, check_anchors: bool = True, replay: bool = True) -> dict[str, Any]:
    exact = {
        "schema_version": 1,
        "role": "DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_EXECUTION_EVIDENCE",
        "evidence_state": "RECORDED",
        "work_unit_id": "PIPE-WU-116",
        "issue_number": 280,
        "base_main_sha": "a16e831591ab89e7175ab80cc313bc1da3f2d6c4",
        "frontier_id": "DURABLE_AUTONOMOUS_CONTINUATION_SESSION_RESUME_EXECUTION",
        "predecessor_frontier_blob_sha": "61fd1e5c450652874b5ff19c7370771bca88d0e5",
        "branch": "agent/PIPE-WU-116-durable-autonomous-continuation-session-resume-execution",
        "next_boundary": "DURABLE_AUTONOMOUS_CONTINUATION_MULTI_SESSION_STEADY_STATE",
    }
    for field, expected in exact.items():
        if e.get(field) != expected:
            raise ValidationError(f"IDENTITY_MISMATCH:{field}")
    if check_anchors:
        validate_anchors(e)

    handoff = e.get("handoff")
    if not isinstance(handoff, dict):
        raise ValidationError("HANDOFF_REQUIRED")
    for flag in (
        "checkpoint_is_mutation_authority",
        "persisted_control_loop_reused",
        "persisted_execution_admission_reused",
        "persisted_ci_success_reused",
        "persisted_registry_cas_reused",
        "persisted_merge_eligibility_reused",
    ):
        assert_false(handoff.get(flag), "handoff." + flag)
    if handoff.get("checkpoint_transaction_boundary") != "CLEAN_ITERATION_BOUNDARY":
        raise ValidationError("HANDOFF_BOUNDARY_INVALID")

    fresh = e.get("fresh_resume_truth_before_transaction")
    if not isinstance(fresh, dict):
        raise ValidationError("FRESH_RESUME_TRUTH_REQUIRED")
    assert_true(fresh.get("provider_truth_fresh"), "fresh.provider_truth_fresh")
    assert_true(fresh.get("fresh_wu108_recomputation_required"), "fresh.wu108")
    assert_true(fresh.get("fresh_wu109_recomputation_required_before_mutation"), "fresh.wu109")
    assert_false(fresh.get("checkpoint_authority_used"), "fresh.checkpoint_authority_used")
    if fresh.get("resume_decision") != "RECOMPUTE_FRESH_CONTINUATION":
        raise ValidationError("FRESH_RESUME_DECISION_INVALID")
    if fresh.get("current_main_sha") == handoff.get("checkpoint_recorded_main_sha"):
        raise ValidationError("CHECKPOINT_MAIN_DRIFT_NOT_PROVEN")
    if fresh["selected_work_unit"].get("work_unit_id") == handoff.get("checkpoint_selected_work_unit_id"):
        raise ValidationError("CHECKPOINT_WORK_UNIT_DRIFT_NOT_PROVEN")
    required_drift = {"current_main", "selected_work_unit", "provider_state", "writer_lease", "branch"}
    if set(fresh.get("checkpoint_drift_fields", [])) != required_drift:
        raise ValidationError("CHECKPOINT_DRIFT_FIELDS_INVALID")

    iterations = e.get("post_handoff_iterations")
    if not isinstance(iterations, list) or len(iterations) != 2:
        raise ValidationError("EXACT_TWO_POST_HANDOFF_ITERATIONS_REQUIRED")
    if [x.get("iteration_sequence") for x in iterations] != [1, 2]:
        raise ValidationError("ITERATION_SEQUENCE_INVALID")
    expected_decisions = ["PLAN_EXISTING_WRITER_LEASE_ACQUISITION", "PLAN_EXISTING_BOUNDED_BRANCH_CREATE"]
    expected_kinds = ["WRITER_LEASE_ACQUISITION", "BOUNDED_BRANCH_CREATE"]
    for idx, item in enumerate(iterations):
        for flag in ("provider_truth_fresh", "control_loop_fresh_for_iteration", "execution_admission_fresh_for_iteration", "fresh_provider_readback_completed", "readback_matches_expected_transaction"):
            assert_true(item.get(flag), f"iteration{idx+1}.{flag}")
        assert_false(item.get("control_loop_reused_from_prior_session"), f"iteration{idx+1}.control_reuse")
        assert_false(item.get("execution_admission_reused_from_prior_session"), f"iteration{idx+1}.admission_reuse")
        if item.get("delegated_transaction_count") != 1:
            raise ValidationError(f"ITERATION_TRANSACTION_COUNT:{idx+1}")
        if item.get("control_loop_decision") != expected_decisions[idx]:
            raise ValidationError(f"ITERATION_CONTROL_DECISION:{idx+1}")
        if item.get("execution_admission_decision") != "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY":
            raise ValidationError(f"ITERATION_ADMISSION_DECISION:{idx+1}")
        if item.get("delegated_authority_identity") != "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY":
            raise ValidationError(f"ITERATION_AUTHORITY:{idx+1}")
        if item.get("transaction_kind") != expected_kinds[idx]:
            raise ValidationError(f"ITERATION_KIND:{idx+1}")
        assert_true(item["transaction_result"].get("provider_mutation_performed"), f"iteration{idx+1}.provider_mutation")
    assert_false(iterations[0].get("previous_iteration_fresh_provider_readback_completed"), "iteration1.previous_readback")
    assert_true(iterations[1].get("previous_iteration_fresh_provider_readback_completed"), "iteration2.previous_readback")
    if iterations[0]["provider_state_after"] != iterations[1]["provider_state_before"]:
        raise ValidationError("CROSS_ITERATION_PROVIDER_CHAIN_MISMATCH")
    if iterations[0]["provider_state_before"]["registry_generation"] != 23 or iterations[0]["provider_state_after"]["registry_generation"] != 24:
        raise ValidationError("REGISTRY_GENERATION_ADVANCE_INVALID")
    if iterations[1]["branch_state_after"].get("compare_status") != "identical" or iterations[1]["branch_state_after"].get("ahead_by") != 0 or iterations[1]["branch_state_after"].get("behind_by") != 0:
        raise ValidationError("BOUNDED_BRANCH_READBACK_INVALID")

    interrupted = e.get("interrupted_checkpoint_path", {})
    pending = e.get("readback_pending_checkpoint_path", {})
    if interrupted.get("expected_resume_decision") != "RECONCILE_INTERRUPTED_TRANSACTION_FROM_PROVIDER_TRUTH":
        raise ValidationError("INTERRUPTED_EXPECTED_DECISION_INVALID")
    if pending.get("expected_resume_decision") != "WAIT_FOR_FRESH_PROVIDER_READBACK":
        raise ValidationError("PENDING_EXPECTED_DECISION_INVALID")
    for obj, prefix in ((interrupted, "interrupted"), (pending, "pending")):
        assert_true(obj.get("provider_reconciliation_required"), prefix + ".reconciliation")
        assert_false(obj.get("delegated_transaction_replayed"), prefix + ".replay")
    assert_false(interrupted.get("mutation_performed_before_reconciliation"), "interrupted.mutation")
    assert_false(pending.get("mutation_performed_before_readback"), "pending.mutation")

    for flag in (
        "checkpoint_provider_drift_detected",
        "fresh_provider_truth_superseded_checkpoint",
        "fresh_control_loop_and_admission_per_iteration",
        "main_unchanged_during_post_handoff_iterations",
    ):
        assert_true(e.get(flag), flag)
    for flag in (
        "stale_control_loop_or_admission_reuse_performed",
        "stale_ci_or_cas_reuse_performed",
        "batch_provider_mutation_performed",
        "inferred_or_fallback_authority_used",
        "checkpoint_is_mutation_authority",
        "product_runtime_mutation_performed",
        "runtime_action_performed",
        "adwf_binding_or_repository_mutation_performed",
        "release_tag_promotion_performed",
        "ruleset_policy_mutation_performed",
        "private_evidence_publication_performed",
        "reserve_1080_lifecycle_mutation_performed",
        "primary_1081_lifecycle_mutation_performed",
        "authority_broadening_performed",
    ):
        assert_false(e.get(flag), flag)
    if e.get("main_sha_after_iterations") != e.get("base_main_sha"):
        raise ValidationError("MAIN_DRIFT_DURING_ITERATIONS")

    if replay:
        replay_resume(e)
        replay_iterations(e)
    return {
        "schema_version": 1,
        "role": "WU116_DURABLE_RESUME_EXECUTION_VALIDATION",
        "state": "PASS",
        "work_unit_id": "PIPE-WU-116",
        "post_handoff_iterations_validated": 2,
        "checkpoint_provider_drift_proven": True,
        "next_boundary": e["next_boundary"],
    }


def main() -> int:
    evidence = load_json(EVIDENCE_PATH)
    try:
        result = validate_evidence(evidence)
    except ValidationError as exc:
        print(json.dumps({"schema_version": 1, "role": "WU116_DURABLE_RESUME_EXECUTION_VALIDATION", "state": "BLOCKED", "reason": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
