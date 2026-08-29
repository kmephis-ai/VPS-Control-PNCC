#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
PREP_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-bootstrap-authority-preparation.json"
TOPOLOGY_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-registry-topology.json"
CLAIM_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-claim-admission-policy.json"


class BootstrapPreparationError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BootstrapPreparationError(f"INVALID_JSON:{path.as_posix()}") from exc


def validate_preparation(prep: dict[str, Any] | None = None) -> dict[str, Any]:
    p = prep or _load(PREP_PATH)
    topology = _load(TOPOLOGY_PATH)
    claim = _load(CLAIM_PATH)
    if not isinstance(p, dict) or p.get("schema_version") != 1 or p.get("role") != "WRITER_LEASE_BOOTSTRAP_AUTHORITY_PREPARATION":
        raise BootstrapPreparationError("PREPARATION_IDENTITY_INVALID")
    exact = {
        "preparation_source_main": "723b54ada56bf1a729a82eb7c6a114dfa63b3a03",
        "topology_contract_role": "WRITER_LEASE_REGISTRY_TOPOLOGY",
        "topology_schema_version": 1,
        "claim_admission_contract_role": "WRITER_LEASE_CLAIM_ADMISSION_POLICY",
        "claim_admission_schema_version": 1,
        "writer_lease_contract_role": "WRITER_LEASE",
        "writer_lease_schema_version": 1,
        "state_branch": "pncc-provider-state",
        "registry_path": ".pncc-state/writer-lease-registry.json",
        "initial_registry_sha256": "a4d6f7946290c0a9d775b5b3d27676f09162b3085ad9d9301dc82af8a1276b11",
        "initial_registry_size": 80,
        "bootstrap_precondition": "STATE_BRANCH_MUST_BE_ABSENT_ON_FRESH_PROVIDER_READ",
        "bootstrap_create_policy": "CREATE_EXACTLY_ONCE_NO_OVERWRITE_NO_MOVE_NO_FORCE",
        "first_claim_precondition": "WU094_CLAIM_ELIGIBLE_PLUS_FRESH_PROVIDER_STATE_READ",
        "first_claim_generation": 1,
        "authorization_scope": "PROVIDER_STATE_BOOTSTRAP_AND_FIRST_WRITER_LEASE_ACQUISITION_ONLY",
        "preparation_state": "WAITING_EXPLICIT_OWNER_AUTHORIZATION",
        "next_boundary": "EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_AND_CONTRACT_BLOB_REQUIRED",
    }
    for key, expected in exact.items():
        if p.get(key) != expected:
            raise BootstrapPreparationError("PREPARATION_DRIFT:" + key)
    expected_initial='{"schema_version":1,"role":"WRITER_LEASE_REGISTRY","generation":0,"entries":[]}\n'
    if p.get("initial_registry_exact_utf8_lf") != expected_initial:
        raise BootstrapPreparationError("INITIAL_REGISTRY_BYTES_DRIFT")
    raw = expected_initial.encode("utf-8")
    if len(raw) != p["initial_registry_size"] or hashlib.sha256(raw).hexdigest() != p["initial_registry_sha256"]:
        raise BootstrapPreparationError("INITIAL_REGISTRY_DIGEST_INVALID")
    if p.get("first_claim_cas_tokens") != ["EXPECTED_REGISTRY_BLOB_SHA", "OBSERVED_STATE_BRANCH_HEAD_SHA"]:
        raise BootstrapPreparationError("CAS_TOKEN_DRIFT")
    if topology.get("state_branch") != p["state_branch"] or topology.get("registry_path") != p["registry_path"]:
        raise BootstrapPreparationError("TOPOLOGY_BINDING_MISMATCH")
    if topology.get("cas_tokens") != p["first_claim_cas_tokens"]:
        raise BootstrapPreparationError("TOPOLOGY_CAS_MISMATCH")
    if topology.get("bootstrap_authority") is not False or topology.get("registry_write_authority") is not False or topology.get("lease_acquisition_authority") is not False:
        raise BootstrapPreparationError("TOPOLOGY_ALREADY_AUTHORIZED")
    if claim.get("mode") != "READ_ONLY_ADVISORY" or claim.get("writer_lease_acquisition_authority") is not False:
        raise BootstrapPreparationError("CLAIM_ADMISSION_AUTHORITY_DRIFT")
    required_false = {
        "owner_authorization_present",
        "owner_authorization_binding_complete",
        "bootstrap_authority",
        "registry_write_authority",
        "lease_acquisition_authority",
        "lease_heartbeat_authority",
        "lease_release_authority",
        "lease_steal_authority",
        "branch_move_authority",
        "force_update_authority",
        "main_product_runtime_mutation_authority",
        "adwf_binding_mutation_authority",
        "release_tag_promotion_authority",
        "ruleset_policy_mutation_authority",
        "private_evidence_publication_authority",
        "tunnel_lifecycle_mutation_authority",
        "generic_continuation_counts_as_authorization",
    }
    if any(p.get(k) is not False for k in required_false):
        raise BootstrapPreparationError("MUTATION_AUTHORITY_PRESENT")
    required_true = {
        "owner_authorization_binding_requires_preparation_merge_sha",
        "owner_authorization_binding_requires_prepared_contract_blob_sha",
    }
    if any(p.get(k) is not True for k in required_true):
        raise BootstrapPreparationError("OWNER_BINDING_REQUIREMENT_MISSING")
    return {
        "state": "WRITER_LEASE_BOOTSTRAP_AUTHORITY_PREPARATION_PASS",
        "initial_registry_sha256": p["initial_registry_sha256"],
        "initial_registry_size": p["initial_registry_size"],
        "bootstrap_authority": False,
        "registry_write_authority": False,
        "lease_acquisition_authority": False,
        "next_boundary": p["next_boundary"],
    }


if __name__ == "__main__":
    result = validate_preparation()
    print("WRITER_LEASE_BOOTSTRAP_AUTHORITY_PREPARATION=PASS")
    print(json.dumps(result, sort_keys=True))
