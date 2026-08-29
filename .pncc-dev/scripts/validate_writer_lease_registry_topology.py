#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".pncc-dev" / "contracts" / "writer-lease-registry-topology.json"
SPEC = importlib.util.spec_from_file_location("pncc_state", ROOT / ".pncc-dev" / "scripts" / "validate_state.py")
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)


class RegistryTopologyError(ValueError):
    pass


def load_policy() -> dict[str, Any]:
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryTopologyError("POLICY_JSON_INVALID") from exc
    validate_policy(value)
    return value


def validate_policy(p: dict[str, Any]) -> None:
    if not isinstance(p, dict) or p.get("schema_version") != 1 or p.get("role") != "WRITER_LEASE_REGISTRY_TOPOLOGY":
        raise RegistryTopologyError("POLICY_IDENTITY_INVALID")
    exact = {
        "provider": "GITHUB",
        "state_branch": "pncc-provider-state",
        "registry_path": ".pncc-state/writer-lease-registry.json",
        "registry_contract_role": "WRITER_LEASE_REGISTRY",
        "registry_schema_version": 1,
        "lease_contract_role": "WRITER_LEASE",
        "lease_schema_version": 1,
        "truth_plane": "PROVIDER_VISIBLE_DEVELOPMENT_CONTROL_PLANE",
        "generation_policy": "STRICTLY_MONOTONIC_PER_CONFLICT_DOMAIN",
        "next_boundary": "SEPARATE_PROVIDER_STATE_BOOTSTRAP_AND_LEASE_ACQUISITION_AUTHORITY_PREPARATION",
    }
    for key, expected in exact.items():
        if p.get(key) != expected:
            raise RegistryTopologyError("POLICY_DRIFT:" + key)
    true_fields = {
        "main_branch_registry_forbidden", "issue_comment_registry_forbidden", "issue_label_registry_forbidden",
        "cas_required", "blind_create_after_observation_forbidden", "blind_overwrite_forbidden",
        "force_ref_update_forbidden", "last_write_wins_forbidden", "silent_lease_steal_forbidden",
        "fresh_provider_read_before_claim_required", "historical_reactivation_forbidden",
    }
    if any(p.get(k) is not True for k in true_fields):
        raise RegistryTopologyError("POLICY_FAIL_CLOSED_GUARD_MISSING")
    if p.get("cas_tokens") != ["EXPECTED_REGISTRY_BLOB_SHA", "OBSERVED_STATE_BRANCH_HEAD_SHA"]:
        raise RegistryTopologyError("POLICY_CAS_TOKEN_DRIFT")
    if p.get("max_unexpired_active_per_conflict_domain") != 1:
        raise RegistryTopologyError("POLICY_ACTIVE_LIMIT_DRIFT")
    false_fields = {
        "bootstrap_authority", "registry_write_authority", "lease_acquisition_authority",
        "lease_heartbeat_authority", "lease_release_authority", "lease_steal_authority",
    }
    if any(p.get(k) is not False for k in false_fields):
        raise RegistryTopologyError("POLICY_AUTHORITY_PRESENT")


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RegistryTopologyError("NOW_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RegistryTopologyError("NOW_TIMEZONE_REQUIRED")
    return parsed


def validate_registry_snapshot(registry: Any, *, now_iso: str) -> dict[str, Any]:
    policy = load_policy()
    if not isinstance(registry, dict) or set(registry) != {"schema_version", "role", "generation", "entries"}:
        raise RegistryTopologyError("REGISTRY_SHAPE_INVALID")
    if registry["schema_version"] != policy["registry_schema_version"] or registry["role"] != policy["registry_contract_role"]:
        raise RegistryTopologyError("REGISTRY_IDENTITY_INVALID")
    if not isinstance(registry["generation"], int) or isinstance(registry["generation"], bool) or registry["generation"] < 0:
        raise RegistryTopologyError("REGISTRY_GENERATION_INVALID")
    if not isinstance(registry["entries"], list):
        raise RegistryTopologyError("REGISTRY_ENTRIES_LIST_REQUIRED")
    now = _timestamp(now_iso)
    lease_ids: set[str] = set()
    generations: dict[str, set[int]] = {}
    active_by_domain: dict[str, int] = {}
    max_generation: dict[str, int] = {}
    for raw in registry["entries"]:
        try:
            lease = state.validate_writer_lease(raw)
        except state.ContractError as exc:
            raise RegistryTopologyError("REGISTRY_LEASE_INVALID:" + str(exc)) from exc
        if lease["lease_id"] in lease_ids:
            raise RegistryTopologyError("REGISTRY_DUPLICATE_LEASE_ID")
        lease_ids.add(lease["lease_id"])
        domain = lease["conflict_domain"]
        generations.setdefault(domain, set())
        if lease["generation"] in generations[domain]:
            raise RegistryTopologyError("REGISTRY_DUPLICATE_DOMAIN_GENERATION")
        generations[domain].add(lease["generation"])
        max_generation[domain] = max(max_generation.get(domain, 0), lease["generation"])
        expires = datetime.fromisoformat(lease["expires_at"].replace("Z", "+00:00"))
        if lease["state"] == "ACTIVE" and expires > now:
            active_by_domain[domain] = active_by_domain.get(domain, 0) + 1
            if active_by_domain[domain] > policy["max_unexpired_active_per_conflict_domain"]:
                raise RegistryTopologyError("REGISTRY_MULTIPLE_ACTIVE_CONFLICT_DOMAIN")
    return {
        "state": "WRITER_LEASE_REGISTRY_TOPOLOGY_VALID",
        "entry_count": len(registry["entries"]),
        "active_conflict_domain_count": len(active_by_domain),
        "max_generation_by_conflict_domain": max_generation,
        "bootstrap_authority": False,
        "registry_write_authority": False,
        "lease_acquisition_authority": False,
    }


if __name__ == "__main__":
    load_policy()
    print("WRITER_LEASE_REGISTRY_TOPOLOGY=PASS")
