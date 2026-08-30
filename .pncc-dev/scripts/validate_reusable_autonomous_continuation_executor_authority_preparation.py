#!/usr/bin/env python3
"""Fail-closed validator for WU-110 reusable autonomous continuation executor preparation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev/contracts/reusable-autonomous-continuation-executor-authority-preparation.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

EXPECTED_ANCHORS = {
    "admission_policy": (".pncc-dev/contracts/autonomous-continuation-execution-admission-policy.json", "406d78da6250c452bfc7706b57dc51a18ca48977"),
    "admission_evaluator": (".pncc-dev/scripts/evaluate_autonomous_continuation_execution_admission.py", "cde13515632717b81cef77876e53e9ceef0c46bf"),
    "control_loop_policy": (".pncc-dev/contracts/autonomous-continuation-control-loop-policy.json", "822bcd1833ff4843b6bd176337b3ef3b742275de"),
    "control_loop_evaluator": (".pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py", "1f794892cfec466505a1a6c38b271492f9759127"),
    "reusable_materialization_grant": (".pncc-dev/contracts/reusable-canonical-work-unit-materialization-authorized.json", "39db0554b86932b1beb4bb7250d040c06f9371ea"),
    "reusable_writer_lease_grant": (".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json", "717e1f9081915f40fad2e0620c64245a650ca235"),
    "reusable_merge_close_grant": (".pncc-dev/contracts/reusable-autonomous-merge-close-authorized.json", "baa503d63eaa437545ddcf0a045cf864d1ef36e6"),
    "merge_close_executor_integration": (".pncc-dev/contracts/reusable-merge-close-executor-integration.json", "220668dc1089aaa123085724db005f3eae9971c8"),
}

FALSE_AUTHORITY_FIELDS = (
    "reusable_authority_granted",
    "reusable_autonomous_continuation_executor_authority",
    "provider_mutation_authority",
    "issue_create_authority",
    "issue_update_authority",
    "issue_close_authority",
    "branch_mutation_authority",
    "pull_request_mutation_authority",
    "writer_lease_mutation_authority",
    "workflow_rerun_authority",
    "merge_authority",
    "runtime_action_authority",
    "product_runtime_mutation_authority",
    "adwf_binding_mutation_authority",
    "adwf_repository_mutation_authority",
    "release_tag_promotion_authority",
    "ruleset_policy_mutation_authority",
    "private_evidence_publication_authority",
    "force_ref_update_authority",
    "silent_lease_steal_authority",
    "reserve_1080_lifecycle_mutation_authority",
    "primary_1081_lifecycle_mutation_authority",
)

TRUE_GATE_FIELDS = (
    "explicit_owner_authorization_required",
    "future_owner_receipt_must_bind_preparation_contract_blob_sha",
    "future_owner_receipt_must_bind_preparation_merge_main_sha",
    "future_grant_requires_exact_owner_receipt",
    "future_grant_requires_exact_preparation_contract",
    "future_grant_requires_explicit_owner_authorization",
    "per_transaction_provider_truth_fresh_required",
    "per_transaction_exact_current_main_binding_required",
    "per_transaction_execution_admission_pass_required",
    "per_transaction_admission_delegated_authority_must_match_existing_canonical_grant",
    "per_transaction_target_action_must_be_exact_and_supported",
    "per_transaction_revalidate_delegated_authority_anchors_required",
    "per_transaction_no_inferred_or_fallback_authority",
    "per_transaction_wait_stop_blocked_no_mutation",
    "per_transaction_separate_authority_required_no_mutation",
    "per_transaction_writer_lease_fresh_cas_required_when_delegated",
    "per_transaction_pinned_expected_head_merge_required_when_delegated",
    "per_transaction_post_merge_close_readback_required_when_delegated",
)


class PreparationError(ValueError):
    pass


def _strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PreparationError("DUPLICATE_KEY:" + key)
        out[key] = value
    return out


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreparationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def validate(contract: dict, root: Path = ROOT) -> None:
    if contract.get("schema_version") != 1:
        raise PreparationError("SCHEMA_VERSION_INVALID")
    if contract.get("role") != "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_AUTHORITY_PREPARATION":
        raise PreparationError("ROLE_INVALID")
    if contract.get("preparation_state") != "WAITING_EXPLICIT_OWNER_AUTHORIZATION":
        raise PreparationError("PREPARATION_STATE_INVALID")
    if contract.get("future_scope") != "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY":
        raise PreparationError("FUTURE_SCOPE_INVALID")
    if contract.get("preparation_base_main_sha") != "435d856c0747a91e1208d904e22bed820b12a224":
        raise PreparationError("PREPARATION_BASE_INVALID")
    if contract.get("generic_continuation_text_is_owner_authorization") is not False:
        raise PreparationError("GENERIC_CONTINUATION_MUST_NOT_AUTHORIZE")
    if contract.get("owner_authorization_present") is not False:
        raise PreparationError("OWNER_AUTHORIZATION_MUST_BE_ABSENT")
    if contract.get("owner_authorization_binding_complete") is not False:
        raise PreparationError("OWNER_BINDING_MUST_BE_INCOMPLETE")
    if contract.get("future_owner_authorization_receipt_path") != ".pncc-dev/attestations/reusable-autonomous-continuation-executor-owner-authorization-wu111.json":
        raise PreparationError("OWNER_RECEIPT_PATH_INVALID")
    if contract.get("future_authorized_grant_path") != ".pncc-dev/contracts/reusable-autonomous-continuation-executor-authorized.json":
        raise PreparationError("FUTURE_GRANT_PATH_INVALID")
    if contract.get("future_owner_receipt_must_bind_authorization_scope") != "REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_ONLY":
        raise PreparationError("OWNER_SCOPE_BINDING_INVALID")

    for field in TRUE_GATE_FIELDS:
        if contract.get(field) is not True:
            raise PreparationError("REQUIRED_GATE_FALSE:" + field)
    for field in FALSE_AUTHORITY_FIELDS:
        if contract.get(field) is not False:
            raise PreparationError("AUTHORITY_PRESENT:" + field)

    paths = contract.get("anchor_paths")
    blobs = contract.get("anchor_blobs")
    if not isinstance(paths, dict) or not isinstance(blobs, dict):
        raise PreparationError("ANCHOR_MAP_MISSING")
    if set(paths) != set(EXPECTED_ANCHORS) or set(blobs) != set(EXPECTED_ANCHORS):
        raise PreparationError("ANCHOR_KEYSET_INVALID")
    for key, (expected_path, expected_blob) in sorted(EXPECTED_ANCHORS.items()):
        if paths.get(key) != expected_path or blobs.get(key) != expected_blob:
            raise PreparationError("ANCHOR_DECLARATION_DRIFT:" + key)
        if SHA40.fullmatch(expected_blob) is None:
            raise PreparationError("ANCHOR_SHA_INVALID:" + key)
        path = root / expected_path
        if not path.is_file():
            raise PreparationError("ANCHOR_MISSING:" + key)
        if blob_sha(path) != expected_blob:
            raise PreparationError("ANCHOR_CONTENT_DRIFT:" + key)

    expected_delegation = {
        "ADMIT_EXISTING_MATERIALIZATION_AUTHORITY": "EXISTING_REUSABLE_CANONICAL_WORK_UNIT_MATERIALIZATION_AUTHORITY",
        "ADMIT_EXISTING_WRITER_LEASE_AUTHORITY": "EXISTING_REUSABLE_WRITER_LEASE_BOUNDED_BRANCH_AUTHORITY",
        "ADMIT_EXISTING_MERGE_CLOSE_AUTHORITY": "EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY",
        "WAIT_ONLY": "NO_MUTATION",
        "STOP_ONLY": "NO_MUTATION",
        "SEPARATE_AUTHORITY_REQUIRED": "NO_MUTATION_AND_SEPARATE_EXPLICIT_AUTHORITY_REQUIRED",
        "BLOCKED": "NO_MUTATION_FAIL_CLOSED",
    }
    if contract.get("delegation_policy") != expected_delegation:
        raise PreparationError("DELEGATION_POLICY_INVALID")
    if contract.get("interruption_behavior") != "STOP_OR_WAIT_FAIL_CLOSED_AND_REEVALUATE_FRESH_PROVIDER_TRUTH":
        raise PreparationError("INTERRUPTION_BEHAVIOR_INVALID")
    if contract.get("classified_failure_behavior") != "SEPARATE_AUTHORITY_REQUIRED_NO_GUESSED_RECOVERY":
        raise PreparationError("CLASSIFIED_FAILURE_BEHAVIOR_INVALID")
    if contract.get("unknown_or_contradictory_behavior") != "BLOCK_FAIL_CLOSED":
        raise PreparationError("UNKNOWN_BEHAVIOR_INVALID")
    if contract.get("anchor_drift_behavior") != "BLOCK_FAIL_CLOSED" or contract.get("revocation_behavior") != "BLOCK_FAIL_CLOSED":
        raise PreparationError("DRIFT_REVOCATION_BEHAVIOR_INVALID")
    if contract.get("next_boundary") != "EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_MAIN_AND_CONTRACT_BLOB":
        raise PreparationError("NEXT_BOUNDARY_INVALID")


def main() -> int:
    contract = load_json(CONTRACT)
    validate(contract)
    print("REUSABLE_AUTONOMOUS_CONTINUATION_EXECUTOR_PREPARATION=PASS")
    print("OWNER_AUTHORIZATION_PRESENT=false")
    print("REUSABLE_EXECUTOR_AUTHORITY=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
