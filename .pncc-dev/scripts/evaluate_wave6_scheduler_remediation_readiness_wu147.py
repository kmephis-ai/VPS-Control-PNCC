#!/usr/bin/env python3
"""Fail-closed evaluator for PIPE-WU-147 scheduler remediation readiness.

This evaluator grants no activation authority. It only proves that the durable
owner-decision packet remains zero-authority, evidence-bounded and rollback-ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

EXPECTED_ROLE = "WAVE6_SCHEDULER_REMEDIATION_OWNER_DECISION_READINESS"
EXPECTED_WORK_UNIT = "PIPE-WU-147"
EXPECTED_ISSUE = 342
EXPECTED_BASE = "b8980da9879619f8c28bc844969a3955b4d6e368"
EXPECTED_BRANCH = "agent/PIPE-WU-147-scheduler-remediation-readiness-leased"
EXPECTED_PREDECESSOR_CLASSIFICATION = "CROSS_WORKFLOW_SCHEDULE_DELIVERY_DEGRADATION_CORRELATED"
EXPECTED_TERMINAL = "READY_FOR_OWNER_DECISION"

REQUIRED_DECISIONS = {
    "DEFER_OBSERVE_ONLY",
    "GITHUB_NATIVE_REDUNDANT_SCHEDULE_OBSERVATION",
    "BOUNDED_DISPATCH_FALLBACK_CLASS",
}
REQUIRED_ABORTS = {
    "FRESH_PROVIDER_TRUTH_UNAVAILABLE",
    "AUTHORIZED_BASE_DRIFT",
    "SCOPE_OR_DIFF_DRIFT",
    "AUTHORITY_REQUIREMENT_AMBIGUOUS",
    "CREDENTIAL_STORAGE_OR_LOGGING_SAFETY_UNPROVEN",
    "ROLLBACK_PATH_UNPROVEN",
    "RULESET_OR_SECURITY_WEAKENING_REQUIRED",
    "PRODUCT_OR_RUNTIME_MUTATION_REQUIRED",
    "GLOBAL_OUTAGE_OR_PROVIDER_ROOT_CAUSE_WOULD_HAVE_TO_BE_ASSUMED",
}
REQUIRED_ROLLBACK = {
    "RESTORE_EXACT_PRE_ACTIVATION_REPOSITORY_CONFIGURATION",
    "DISABLE_OR_REMOVE_ONLY_THE_NEWLY_AUTHORIZED_FALLBACK_PATH",
    "REVOKE_NEWLY_INTRODUCED_EXTERNAL_CREDENTIAL_IF_ANY",
    "VERIFY_POST_ROLLBACK_PROVIDER_AND_REPOSITORY_STATE",
    "PRESERVE_WU137_AND_WU144_PREDECESSOR_EVIDENCE",
}
REQUIRED_PREREQUISITES = {
    "EXPLICIT_OWNER_AUTHORIZATION_NAMING_EXACT_ACTIVATION_CLASS",
    "NEW_BOUNDED_WORK_UNIT_FROM_FRESH_EXACT_MAIN",
    "FRESH_GITHUB_ACTIONS_PROVIDER_TRUTH_READBACK",
    "LEAST_AUTHORITY_AND_CREDENTIAL_THREAT_MODEL_IF_DISPATCH_OR_EXTERNAL_MECHANISM_IS_PROPOSED",
    "NO_SECRET_VALUE_IN_REPOSITORY_ISSUE_PR_CI_LOG_OR_EVIDENCE",
    "EXACT_ALLOWED_AND_FORBIDDEN_MUTATION_SCOPE",
    "MACHINE_VERIFIABLE_PRE_ACTIVATION_BASE_AND_DIFF",
    "BOUNDED_BLAST_RADIUS",
    "EXPLICIT_ABORT_CONDITIONS",
    "EXPLICIT_ROLLBACK_PROCEDURE_AND_POST_ROLLBACK_READBACK",
    "GITHUB_HOSTED_ONLY_NO_SELF_HOSTED_RUNNER",
    "NO_PRODUCT_RUNTIME_1080_1081_OR_V631_MUTATION",
}


def _git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("utf-8") + payload).hexdigest()


def _require_subset(errors: List[str], actual: Iterable[str], required: set[str], label: str) -> None:
    actual_set = set(actual)
    missing = sorted(required - actual_set)
    if missing:
        errors.append(f"{label}_missing:{','.join(missing)}")


def evaluate_contract(contract: Dict[str, Any], repo_root: Optional[Path] = None) -> Dict[str, Any]:
    errors: List[str] = []

    exact = {
        "role": EXPECTED_ROLE,
        "work_unit_id": EXPECTED_WORK_UNIT,
        "issue_number": EXPECTED_ISSUE,
        "authorized_base_sha": EXPECTED_BASE,
        "authorized_branch": EXPECTED_BRANCH,
    }
    for key, expected in exact.items():
        if contract.get(key) != expected:
            errors.append(f"identity_mismatch:{key}")

    if contract.get("runtime_required") is not False:
        errors.append("runtime_required_must_be_false")

    predecessor = contract.get("predecessor_evidence") or {}
    if predecessor.get("classification") != EXPECTED_PREDECESSOR_CLASSIFICATION:
        errors.append("predecessor_classification_mismatch")
    if predecessor.get("repository_local_cross_workflow_correlation") is not True:
        errors.append("repository_local_correlation_must_be_true")
    for key in ("global_github_outage_proven", "provider_root_cause_proven", "repository_configuration_defect_proven"):
        if predecessor.get(key) is not False:
            errors.append(f"evidence_overclaim:{key}")

    freshness = contract.get("freshness_boundary") or {}
    if freshness.get("fresh_provider_truth_observed_in_wu147") is not False:
        errors.append("wu147_must_not_claim_fresh_provider_truth")
    if freshness.get("stale_predecessor_evidence_may_authorize_activation") is not False:
        errors.append("stale_evidence_cannot_authorize_activation")
    if freshness.get("fresh_provider_truth_required_before_every_activation_decision") is not True:
        errors.append("fresh_provider_truth_gate_missing")
    if freshness.get("activation_must_abort_if_fresh_readback_unavailable") is not True:
        errors.append("fresh_readback_abort_gate_missing")
    if freshness.get("required_source") != "GITHUB_ACTIONS_SCHEDULE_RUN_HISTORY":
        errors.append("provider_truth_source_mismatch")

    decisions_raw = contract.get("decision_matrix")
    decisions: List[Dict[str, Any]] = []
    decision_ids: List[str] = []
    if not isinstance(decisions_raw, list):
        errors.append("decision_matrix_must_be_list")
    else:
        for index, decision in enumerate(decisions_raw):
            if not isinstance(decision, dict):
                errors.append(f"decision_matrix_entry_must_be_object:{index}")
                continue
            decision_id = decision.get("id")
            if not isinstance(decision_id, str) or not decision_id:
                errors.append(f"decision_matrix_id_invalid:{index}")
                continue
            decisions.append(decision)
            decision_ids.append(decision_id)

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for decision_id in decision_ids:
        if decision_id in seen_ids:
            duplicate_ids.add(decision_id)
        seen_ids.add(decision_id)
    for decision_id in sorted(duplicate_ids):
        errors.append(f"decision_matrix_duplicate_id:{decision_id}")

    by_id = {d["id"]: d for d in decisions}
    if set(by_id) != REQUIRED_DECISIONS:
        errors.append("decision_matrix_ids_mismatch")
    if any(d.get("selected") is not False for d in by_id.values()):
        errors.append("candidate_must_not_be_selected")

    defer = by_id.get("DEFER_OBSERVE_ONLY", {})
    if defer.get("authority_delta") != "NONE":
        errors.append("defer_must_require_zero_authority")

    redundant = by_id.get("GITHUB_NATIVE_REDUNDANT_SCHEDULE_OBSERVATION", {})
    if redundant.get("sufficient_as_reliability_remediation") is not False:
        errors.append("native_redundancy_must_not_be_overclaimed")

    fallback = by_id.get("BOUNDED_DISPATCH_FALLBACK_CLASS", {})
    if fallback.get("authority_delta") != "SEPARATE_EXACT_OWNER_AUTHORIZATION_REQUIRED":
        errors.append("fallback_owner_authorization_requirement_missing")
    for key in (
        "allowed_mechanism_is_preselected",
        "external_secret_or_token_authorized",
        "workflow_dispatch_authorized",
        "repository_dispatch_authorized",
        "external_scheduler_authorized",
    ):
        if fallback.get(key) is not False:
            errors.append(f"premature_fallback_authority:{key}")
    if fallback.get("rollback_requirement") != "MANDATORY_BEFORE_ACTIVATION":
        errors.append("fallback_rollback_requirement_missing")

    authority = contract.get("authority") or {}
    if not authority:
        errors.append("authority_map_missing")
    else:
        for key, value in authority.items():
            if value is not False:
                errors.append(f"authority_escalation:{key}")

    decision_state = contract.get("decision_state") or {}
    if decision_state.get("terminal_if_valid") != EXPECTED_TERMINAL:
        errors.append("terminal_state_mismatch")
    if decision_state.get("selected_candidate") is not None:
        errors.append("selected_candidate_must_be_null")
    for key in ("activation_performed", "provider_state_mutated"):
        if decision_state.get(key) is not False:
            errors.append(f"premature_activation:{key}")
    if decision_state.get("separate_owner_authorization_required") is not True:
        errors.append("separate_owner_authorization_required")
    if decision_state.get("reusable_authority_allowed") is not False:
        errors.append("reusable_authority_forbidden")
    if decision_state.get("recommended_default_without_new_authority") != "DEFER_OBSERVE_ONLY":
        errors.append("safe_default_mismatch")

    _require_subset(errors, contract.get("activation_prerequisites") or [], REQUIRED_PREREQUISITES, "activation_prerequisites")
    _require_subset(errors, contract.get("mandatory_abort_conditions") or [], REQUIRED_ABORTS, "abort_conditions")
    _require_subset(errors, contract.get("mandatory_rollback_requirements") or [], REQUIRED_ROLLBACK, "rollback_requirements")

    expected_boundary = "MERGED_READY_FOR_OWNER_DECISION_THEN_STOP_BEFORE_ANY_PROVIDER_OR_SCHEDULER_ACTIVATION"
    if contract.get("next_boundary") != expected_boundary:
        errors.append("next_boundary_mismatch")

    anchors = contract.get("immutable_anchor_blobs") or {}
    if not anchors:
        errors.append("immutable_anchor_blobs_missing")
    if repo_root is not None:
        for rel, expected_sha in anchors.items():
            path = repo_root / rel
            if not path.is_file():
                errors.append(f"anchor_missing:{rel}")
                continue
            actual_sha = _git_blob_sha(path)
            if actual_sha != expected_sha:
                errors.append(f"anchor_drift:{rel}")

    return {
        "work_unit_id": EXPECTED_WORK_UNIT,
        "verdict": EXPECTED_TERMINAL if not errors else "FAIL_CLOSED",
        "activation_authorized": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        default=".pncc-dev/contracts/wave6-scheduler-remediation-owner-decision-readiness-wu147.json",
    )
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    contract_path = Path(args.contract)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    result = evaluate_contract(contract, Path(args.repo_root))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == EXPECTED_TERMINAL else 2


if __name__ == "__main__":
    raise SystemExit(main())
