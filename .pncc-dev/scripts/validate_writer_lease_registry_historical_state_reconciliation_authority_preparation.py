#!/usr/bin/env python3
"""Fail-closed validator for PIPE-WU-121 historical Writer Lease reconciliation preparation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / ".pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-authority-preparation-wu121.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

EXPECTED_BASE = "4bf295f43f46850b0a74341066b9d3719d862353"
EXPECTED_BRANCH = "agent/PIPE-WU-121-writer-lease-registry-historical-state-reconciliation"
EXPECTED_PROVIDER_HEAD = "c1212a395366dff49b8fcaaf627797cad33a12c1"
EXPECTED_REGISTRY_BLOB = "10342c16ed3aff3c8c8f0b94e3a80500d48e0403"
EXPECTED_CURRENT_LEASE = "08e426fc-4bc5-40e6-a408-da4d7d06e97b"
EXPECTED_REFERENCE_TIME = "2026-08-30T16:14:00Z"
EXPECTED_SCOPE = "EXACT_FOUR_STALE_WRITER_LEASE_STATE_FIELDS_ACTIVE_TO_RELEASED_ONLY"

EXPECTED_HISTORICAL = (
    ("3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03", "PIPE-WU-096", 1),
    ("ee8b93cb-c629-4f69-82c6-25793fd10d8f", "PIPE-WU-105", 10),
    ("38a86545-e9b7-47eb-9b6e-3c9974bbd020", "PIPE-WU-105", 11),
    ("9c2dcb40-26dc-4dce-aa4f-c1be79a66983", "PIPE-WU-108", 15),
)
EXPECTED_HISTORICAL_IDS = {x[0] for x in EXPECTED_HISTORICAL}

EXPECTED_ANCHORS = {
    "wu119_assessment": (".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-assessment-wu119.json", "ad147299e65cec74f3fc5ef0365376f50f1485aa"),
    "wu120_decision": (".pncc-dev/contracts/autonomous-continuation-human-by-exception-readiness-decision-wu120.json", "a014f81efa52671bf3f637f7a16dc6332a70091b"),
    "writer_lease_registry_topology": (".pncc-dev/contracts/writer-lease-registry-topology.json", "2b9dec3f2b28aadb80ac8edbb09bdc9d453115a1"),
    "writer_lease_lifecycle_policy": (".pncc-dev/contracts/writer-lease-lifecycle-autonomous-execution-policy.json", "942492b4ffe2c2a8c4369b15b617ad9f7f795643"),
    "reusable_writer_lease_grant": (".pncc-dev/contracts/reusable-writer-lease-bounded-branch-authorized.json", "717e1f9081915f40fad2e0620c64245a650ca235"),
    "provider_truth_policy": (".pncc-dev/contracts/provider-truth-continuation-policy.json", "4c6fe2895d41ed9282e9209223a5dd27b209a2fc"),
    "governed_frontier_lifecycle_policy": (".pncc-dev/contracts/governed-frontier-lifecycle-policy.json", "a9d04f0c8611f29cb1cd1929719dbec6f7434c52"),
}

FALSE_AUTHORITY_FIELDS = (
    "historical_reconciliation_authority_granted",
    "provider_mutation_authority",
    "writer_lease_historical_mutation_authority",
    "writer_lease_current_lifecycle_authority",
    "issue_mutation_authority",
    "branch_mutation_authority",
    "pull_request_mutation_authority",
    "workflow_rerun_authority",
    "merge_authority",
    "direct_main_write_authority",
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
    "higher_autonomy_authority",
)

TRUE_PREPARATION_FIELDS = (
    "explicit_owner_authorization_required",
    "future_owner_receipt_must_bind_preparation_contract_blob_sha",
    "future_owner_receipt_must_bind_preparation_merge_main_sha",
    "future_grant_requires_exact_owner_receipt",
    "future_grant_requires_exact_preparation_contract",
    "future_grant_requires_explicit_owner_authorization",
)

TRUE_RECONCILIATION_SEMANTICS = (
    "exact_state_field_only_mutation_required",
    "active_to_released_only",
    "registry_generation_must_remain_unchanged_during_historical_reconciliation",
    "entry_order_must_remain_unchanged",
    "entry_count_must_remain_unchanged",
    "lease_identity_must_remain_unchanged",
    "work_unit_binding_must_remain_unchanged",
    "conflict_domain_must_remain_unchanged",
    "holder_must_remain_unchanged",
    "base_sha_must_remain_unchanged",
    "branch_must_remain_unchanged",
    "lease_generation_must_remain_unchanged",
    "acquired_at_must_remain_unchanged",
    "heartbeat_at_must_remain_unchanged",
    "expires_at_must_remain_unchanged",
    "unrelated_entries_must_remain_semantically_identical",
    "current_writer_entry_must_not_be_modified_by_historical_reconciliation",
    "historical_reactivation_forbidden",
    "partial_or_superset_reconciliation_forbidden",
    "unknown_provider_outcome_replay_forbidden",
    "fresh_provider_read_before_authorized_execution_required",
    "registry_cas_required",
    "post_transaction_provider_readback_required",
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


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreparationError(f"INVALID_JSON:{path.as_posix()}:{type(exc).__name__}") from exc


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PreparationError("TIMESTAMP_INVALID:" + repr(value))
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise PreparationError("TIMESTAMP_INVALID:" + value) from exc


def _by_lease_id(entries: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in entries:
        lease_id = entry.get("lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise PreparationError("LEASE_ID_INVALID")
        if lease_id in out:
            raise PreparationError("DUPLICATE_LEASE_ID:" + lease_id)
        out[lease_id] = entry
    return out


def _validate_anchor_content(contract: dict, root: Path) -> None:
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


def _validate_semantic_anchors(root: Path) -> None:
    wu119 = load_json(root / EXPECTED_ANCHORS["wu119_assessment"][0])
    stale119 = wu119.get("stale_active_history")
    if not isinstance(stale119, list):
        raise PreparationError("WU119_STALE_SET_MISSING")
    ids119 = {x.get("lease_id") for x in stale119}
    if ids119 != EXPECTED_HISTORICAL_IDS:
        raise PreparationError("WU119_STALE_SET_DRIFT")
    for row in stale119:
        if row.get("state") != "ACTIVE" or row.get("current_ownership_eligible") is not False or row.get("remediation") != "SEPARATE_AUTHORITY_REQUIRED":
            raise PreparationError("WU119_STALE_SEMANTICS_DRIFT")

    wu120 = load_json(root / EXPECTED_ANCHORS["wu120_decision"][0])
    decision = wu120.get("stale_history_decision")
    if not isinstance(decision, dict):
        raise PreparationError("WU120_STALE_DECISION_MISSING")
    if set(decision.get("lease_ids", [])) != EXPECTED_HISTORICAL_IDS or decision.get("count") != 4:
        raise PreparationError("WU120_STALE_SET_DRIFT")
    if decision.get("classification") != "SEPARATE_AUTHORITY_REQUIRED":
        raise PreparationError("WU120_CLASSIFICATION_DRIFT")
    if decision.get("historical_state_mutation_performed_in_wu120") is not False:
        raise PreparationError("WU120_FALSE_MUTATION_CLAIM_DRIFT")
    if wu120.get("higher_autonomy_authorized") is not False or wu120.get("authority_granted") is not False:
        raise PreparationError("WU120_AUTHORITY_DRIFT")


def validate_contract(contract: dict, root: Path = ROOT, check_anchor_content: bool = True) -> None:
    if contract.get("schema_version") != 1:
        raise PreparationError("SCHEMA_VERSION_INVALID")
    if contract.get("role") != "WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION_AUTHORITY_PREPARATION":
        raise PreparationError("ROLE_INVALID")
    if contract.get("preparation_state") != "WAITING_EXPLICIT_OWNER_AUTHORIZATION":
        raise PreparationError("PREPARATION_STATE_INVALID")
    if contract.get("future_scope") != EXPECTED_SCOPE:
        raise PreparationError("FUTURE_SCOPE_INVALID")
    if contract.get("preparation_base_main_sha") != EXPECTED_BASE:
        raise PreparationError("PREPARATION_BASE_INVALID")
    if contract.get("preparation_reference_time") != EXPECTED_REFERENCE_TIME:
        raise PreparationError("REFERENCE_TIME_INVALID")
    if contract.get("work_unit_id") != "PIPE-WU-121" or contract.get("issue_number") != 290:
        raise PreparationError("WORK_UNIT_BINDING_INVALID")
    if contract.get("branch") != EXPECTED_BRANCH or contract.get("runtime_required") is not False:
        raise PreparationError("BRANCH_OR_RUNTIME_BINDING_INVALID")
    if contract.get("generic_continuation_text_is_owner_authorization") is not False:
        raise PreparationError("GENERIC_CONTINUATION_MUST_NOT_AUTHORIZE")
    if contract.get("owner_authorization_present") is not False or contract.get("owner_authorization_binding_complete") is not False:
        raise PreparationError("OWNER_AUTHORIZATION_MUST_BE_ABSENT")
    if contract.get("historical_state_mutation_performed_in_preparation") is not False:
        raise PreparationError("PREPARATION_MUST_NOT_CLAIM_MUTATION")
    if contract.get("future_owner_authorization_receipt_path") != ".pncc-dev/attestations/writer-lease-registry-historical-state-reconciliation-owner-authorization.json":
        raise PreparationError("OWNER_RECEIPT_PATH_INVALID")
    if contract.get("future_authorized_grant_path") != ".pncc-dev/contracts/writer-lease-registry-historical-state-reconciliation-authorized.json":
        raise PreparationError("AUTHORIZED_GRANT_PATH_INVALID")
    if contract.get("future_owner_receipt_must_bind_authorization_scope") != EXPECTED_SCOPE:
        raise PreparationError("OWNER_SCOPE_BINDING_INVALID")

    for field in TRUE_PREPARATION_FIELDS:
        if contract.get(field) is not True:
            raise PreparationError("REQUIRED_PREPARATION_GATE_FALSE:" + field)
    for field in FALSE_AUTHORITY_FIELDS:
        if contract.get(field) is not False:
            raise PreparationError("AUTHORITY_PRESENT:" + field)

    provider = contract.get("provider_snapshot")
    if not isinstance(provider, dict):
        raise PreparationError("PROVIDER_SNAPSHOT_MISSING")
    expected_provider = {
        "state_branch": "pncc-provider-state",
        "state_branch_head_sha": EXPECTED_PROVIDER_HEAD,
        "registry_path": ".pncc-state/writer-lease-registry.json",
        "registry_blob_sha": EXPECTED_REGISTRY_BLOB,
        "registry_generation": 29,
    }
    if provider != expected_provider:
        raise PreparationError("PROVIDER_SNAPSHOT_DRIFT")

    current = contract.get("current_writer")
    expected_current = {
        "lease_id": EXPECTED_CURRENT_LEASE,
        "work_unit_id": "PIPE-WU-121",
        "generation": 29,
        "base_sha": EXPECTED_BASE,
        "branch": EXPECTED_BRANCH,
        "state": "ACTIVE",
        "current_ownership_eligible": True,
    }
    if current != expected_current:
        raise PreparationError("CURRENT_WRITER_DECLARATION_DRIFT")

    predecessor = contract.get("predecessor_frontier")
    if predecessor != {
        "path": ".pncc-dev/contracts/wave5-next-governed-work-unit-frontier.json",
        "blob_sha": "a6bb097dcc210c7cd64154565808c16015c74b86",
        "frontier_id": "WRITER_LEASE_REGISTRY_HISTORICAL_STATE_RECONCILIATION",
    }:
        raise PreparationError("PREDECESSOR_FRONTIER_DRIFT")

    historical = contract.get("exact_historical_set")
    if not isinstance(historical, list) or len(historical) != 4:
        raise PreparationError("HISTORICAL_SET_INVALID")
    expected_rows = [
        {"lease_id": lease_id, "work_unit_id": wu, "generation": gen, "expected_pre_state": "ACTIVE", "authorized_post_state": "RELEASED"}
        for lease_id, wu, gen in EXPECTED_HISTORICAL
    ]
    if historical != expected_rows:
        raise PreparationError("HISTORICAL_SET_DRIFT")

    semantics = contract.get("reconciliation_semantics")
    if not isinstance(semantics, dict):
        raise PreparationError("RECONCILIATION_SEMANTICS_MISSING")
    if semantics.get("historical_entries_are_current_ownership_eligible") is not False:
        raise PreparationError("HISTORICAL_OWNERSHIP_MUST_BE_FALSE")
    for field in TRUE_RECONCILIATION_SEMANTICS:
        if semantics.get(field) is not True:
            raise PreparationError("RECONCILIATION_GATE_FALSE:" + field)

    if contract.get("next_boundary") != "EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_WU121_PREPARATION_MERGE_MAIN_AND_CONTRACT_BLOB":
        raise PreparationError("NEXT_BOUNDARY_INVALID")

    if check_anchor_content:
        _validate_anchor_content(contract, root)
        _validate_semantic_anchors(root)


def validate_observed_registry(contract: dict, registry: dict) -> None:
    if registry.get("schema_version") != 1 or registry.get("role") != "WRITER_LEASE_REGISTRY":
        raise PreparationError("REGISTRY_IDENTITY_INVALID")
    if registry.get("generation") != 29:
        raise PreparationError("REGISTRY_GENERATION_INVALID")
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise PreparationError("REGISTRY_ENTRIES_INVALID")
    by_id = _by_lease_id(entries)

    current = by_id.get(EXPECTED_CURRENT_LEASE)
    if current is None:
        raise PreparationError("CURRENT_WRITER_MISSING")
    for key, value in {
        "work_unit_id": "PIPE-WU-121",
        "generation": 29,
        "base_sha": EXPECTED_BASE,
        "branch": EXPECTED_BRANCH,
        "state": "ACTIVE",
    }.items():
        if current.get(key) != value:
            raise PreparationError("CURRENT_WRITER_REGISTRY_DRIFT:" + key)

    reference = parse_ts(contract["preparation_reference_time"])
    if parse_ts(current.get("expires_at")) <= reference:
        raise PreparationError("CURRENT_WRITER_EXPIRED_AT_REFERENCE")

    for lease_id, work_unit_id, generation in EXPECTED_HISTORICAL:
        row = by_id.get(lease_id)
        if row is None:
            raise PreparationError("STALE_ENTRY_MISSING:" + lease_id)
        if row.get("work_unit_id") != work_unit_id or row.get("generation") != generation:
            raise PreparationError("STALE_ENTRY_IDENTITY_DRIFT:" + lease_id)
        if row.get("state") != "ACTIVE":
            raise PreparationError("STALE_ENTRY_PRESTATE_DRIFT:" + lease_id)
        if parse_ts(row.get("expires_at")) > reference:
            raise PreparationError("STALE_ENTRY_NOT_EXPIRED:" + lease_id)

    expired_active = {
        row["lease_id"]
        for row in entries
        if row.get("state") == "ACTIVE" and parse_ts(row.get("expires_at")) <= reference
    }
    if expired_active != EXPECTED_HISTORICAL_IDS:
        raise PreparationError("EXPIRED_ACTIVE_SET_DRIFT")


def build_expected_reconciled_registry(before: dict) -> dict:
    """Return a pure in-memory candidate with only the exact four state fields changed."""
    after = copy.deepcopy(before)
    by_id = _by_lease_id(after["entries"])
    for lease_id in EXPECTED_HISTORICAL_IDS:
        by_id[lease_id]["state"] = "RELEASED"
    return after


def validate_authorized_candidate_shape(before: dict, after: dict) -> None:
    """Validate the only mutation shape a future separately authorized transaction may perform."""
    if before.get("schema_version") != after.get("schema_version") or before.get("role") != after.get("role"):
        raise PreparationError("CANDIDATE_REGISTRY_IDENTITY_DRIFT")
    if before.get("generation") != after.get("generation"):
        raise PreparationError("CANDIDATE_REGISTRY_GENERATION_CHANGED")
    before_entries = before.get("entries")
    after_entries = after.get("entries")
    if not isinstance(before_entries, list) or not isinstance(after_entries, list) or len(before_entries) != len(after_entries):
        raise PreparationError("CANDIDATE_ENTRY_COUNT_CHANGED")
    if [x.get("lease_id") for x in before_entries] != [x.get("lease_id") for x in after_entries]:
        raise PreparationError("CANDIDATE_ENTRY_ORDER_OR_ID_CHANGED")

    changed = set()
    for left, right in zip(before_entries, after_entries):
        lease_id = left.get("lease_id")
        if lease_id in EXPECTED_HISTORICAL_IDS:
            expected = copy.deepcopy(left)
            if left.get("state") != "ACTIVE":
                raise PreparationError("CANDIDATE_PRESTATE_NOT_ACTIVE:" + str(lease_id))
            expected["state"] = "RELEASED"
            if right != expected:
                raise PreparationError("CANDIDATE_STALE_ENTRY_COLLATERAL_DRIFT:" + str(lease_id))
            changed.add(lease_id)
        elif right != left:
            raise PreparationError("CANDIDATE_UNRELATED_ENTRY_CHANGED:" + str(lease_id))
    if changed != EXPECTED_HISTORICAL_IDS:
        raise PreparationError("CANDIDATE_PARTIAL_OR_SUPERSET_CHANGE")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    contract = load_json(CONTRACT_PATH)
    registry = load_json(args.registry)
    validate_contract(contract)
    validate_observed_registry(contract, registry)
    candidate = build_expected_reconciled_registry(registry)
    validate_authorized_candidate_shape(registry, candidate)
    print("WU121_HISTORICAL_RECONCILIATION_PREPARATION=PASS")
    print("OWNER_AUTHORIZATION_PRESENT=false")
    print("HISTORICAL_RECONCILIATION_AUTHORITY=false")
    print("HISTORICAL_STATE_MUTATION_PERFORMED=false")
    print("EXACT_STALE_SET_COUNT=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
