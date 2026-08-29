#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_registry",
    ROOT / ".pncc-dev" / "scripts" / "validate_writer_lease_registry_topology.py",
)
registry = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(registry)
NOW = "2030-01-01T00:30:00Z"
HEAD = "a" * 40


def lease(lease_id, domain, generation, *, state="ACTIVE", expires="2030-01-01T01:00:00Z"):
    return {
        "schema_version": 1,
        "role": "WRITER_LEASE",
        "lease_id": lease_id,
        "work_unit_id": f"PIPE-WU-{90 + generation}",
        "conflict_domain": domain,
        "holder": "writer",
        "base_sha": HEAD,
        "branch": f"agent/example-{generation}",
        "state": state,
        "generation": generation,
        "acquired_at": "2030-01-01T00:00:00Z",
        "heartbeat_at": "2030-01-01T00:10:00Z",
        "expires_at": expires,
    }


def snapshot(entries):
    return {"schema_version": 1, "role": "WRITER_LEASE_REGISTRY", "generation": len(entries), "entries": entries}


class RegistryTopologyTests(unittest.TestCase):
    def test_policy_is_default_deny_and_cas_bound(self):
        p=registry.load_policy()
        self.assertEqual(p["state_branch"], "pncc-provider-state")
        self.assertEqual(p["registry_path"], ".pncc-state/writer-lease-registry.json")
        self.assertEqual(p["cas_tokens"], ["EXPECTED_REGISTRY_BLOB_SHA", "OBSERVED_STATE_BRANCH_HEAD_SHA"])
        self.assertTrue(p["force_ref_update_forbidden"])
        self.assertTrue(p["blind_overwrite_forbidden"])
        self.assertFalse(p["bootstrap_authority"])
        self.assertFalse(p["registry_write_authority"])
        self.assertFalse(p["lease_acquisition_authority"])

    def test_empty_registry_is_valid_without_granting_authority(self):
        result=registry.validate_registry_snapshot(snapshot([]), now_iso=NOW)
        self.assertEqual(result["state"], "WRITER_LEASE_REGISTRY_TOPOLOGY_VALID")
        self.assertFalse(result["registry_write_authority"])
        self.assertFalse(result["lease_acquisition_authority"])

    def test_one_active_per_domain_is_valid(self):
        a=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "domain-a", 1)
        b=lease("b7d08baf-5a9d-41f8-9b42-b2e0611f38f5", "domain-b", 1)
        result=registry.validate_registry_snapshot(snapshot([a,b]), now_iso=NOW)
        self.assertEqual(result["active_conflict_domain_count"], 2)

    def test_two_unexpired_active_same_domain_block(self):
        a=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "same", 1)
        b=lease("b7d08baf-5a9d-41f8-9b42-b2e0611f38f5", "same", 2)
        with self.assertRaisesRegex(registry.RegistryTopologyError, "REGISTRY_MULTIPLE_ACTIVE_CONFLICT_DOMAIN"):
            registry.validate_registry_snapshot(snapshot([a,b]), now_iso=NOW)

    def test_expired_active_history_does_not_count_as_live(self):
        old=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "same", 1, expires="2030-01-01T00:20:00Z")
        current=lease("b7d08baf-5a9d-41f8-9b42-b2e0611f38f5", "same", 2)
        result=registry.validate_registry_snapshot(snapshot([old,current]), now_iso=NOW)
        self.assertEqual(result["active_conflict_domain_count"], 1)
        self.assertEqual(result["max_generation_by_conflict_domain"]["same"], 2)

    def test_duplicate_domain_generation_blocks(self):
        a=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "same", 1, state="RELEASED")
        b=lease("b7d08baf-5a9d-41f8-9b42-b2e0611f38f5", "same", 1, state="EXPIRED")
        with self.assertRaisesRegex(registry.RegistryTopologyError, "REGISTRY_DUPLICATE_DOMAIN_GENERATION"):
            registry.validate_registry_snapshot(snapshot([a,b]), now_iso=NOW)

    def test_duplicate_lease_identity_blocks(self):
        a=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "a", 1, state="RELEASED")
        b=lease("70c397e8-8c1d-4939-8dc8-59aec23bdf60", "b", 1, state="EXPIRED")
        with self.assertRaisesRegex(registry.RegistryTopologyError, "REGISTRY_DUPLICATE_LEASE_ID"):
            registry.validate_registry_snapshot(snapshot([a,b]), now_iso=NOW)

    def test_existing_writer_lease_contract_still_validates_entries(self):
        example=json.loads((ROOT / ".pncc-dev/examples/writer-lease.valid.json").read_text(encoding="utf-8"))
        registry.state.validate_writer_lease(example)


if __name__ == "__main__":
    unittest.main()
