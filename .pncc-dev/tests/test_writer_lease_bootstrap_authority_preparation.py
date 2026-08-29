#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import copy
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_bootstrap_prep",
    ROOT / ".pncc-dev" / "scripts" / "validate_writer_lease_bootstrap_authority_preparation.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def base_prep():
    return json.loads((ROOT / ".pncc-dev/contracts/writer-lease-bootstrap-authority-preparation.json").read_text(encoding="utf-8"))


class BootstrapAuthorityPreparationTests(unittest.TestCase):
    def test_canonical_preparation_passes_default_deny(self):
        result = mod.validate_preparation(base_prep())
        self.assertEqual(result["state"], "WRITER_LEASE_BOOTSTRAP_AUTHORITY_PREPARATION_PASS")
        self.assertFalse(result["bootstrap_authority"])
        self.assertFalse(result["registry_write_authority"])
        self.assertFalse(result["lease_acquisition_authority"])

    def test_initial_registry_exact_digest_is_bound(self):
        p = base_prep()
        self.assertEqual(p["initial_registry_size"], 80)
        self.assertEqual(p["initial_registry_sha256"], "a4d6f7946290c0a9d775b5b3d27676f09162b3085ad9d9301dc82af8a1276b11")
        bad = copy.deepcopy(p)
        bad["initial_registry_exact_utf8_lf"] = bad["initial_registry_exact_utf8_lf"].rstrip("\n")
        with self.assertRaises(mod.BootstrapPreparationError):
            mod.validate_preparation(bad)

    def test_generic_continuation_never_authorizes(self):
        p = base_prep()
        self.assertFalse(p["generic_continuation_counts_as_authorization"])
        bad = copy.deepcopy(p)
        bad["generic_continuation_counts_as_authorization"] = True
        with self.assertRaises(mod.BootstrapPreparationError):
            mod.validate_preparation(bad)

    def test_owner_authorization_cannot_be_pre_materialized(self):
        for field in ("owner_authorization_present", "owner_authorization_binding_complete"):
            bad = base_prep()
            bad[field] = True
            with self.assertRaises(mod.BootstrapPreparationError):
                mod.validate_preparation(bad)

    def test_mutation_authority_cannot_be_pre_materialized(self):
        fields = [
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
        ]
        for field in fields:
            bad = base_prep()
            bad[field] = True
            with self.subTest(field=field), self.assertRaises(mod.BootstrapPreparationError):
                mod.validate_preparation(bad)

    def test_exact_future_target_and_cas_tokens_are_pinned(self):
        p = base_prep()
        self.assertEqual(p["state_branch"], "pncc-provider-state")
        self.assertEqual(p["registry_path"], ".pncc-state/writer-lease-registry.json")
        self.assertEqual(p["first_claim_cas_tokens"], ["EXPECTED_REGISTRY_BLOB_SHA", "OBSERVED_STATE_BRANCH_HEAD_SHA"])
        self.assertEqual(p["first_claim_generation"], 1)

    def test_exact_owner_binding_is_required_after_preparation_merge(self):
        p = base_prep()
        self.assertTrue(p["owner_authorization_binding_requires_preparation_merge_sha"])
        self.assertTrue(p["owner_authorization_binding_requires_prepared_contract_blob_sha"])
        self.assertEqual(p["preparation_state"], "WAITING_EXPLICIT_OWNER_AUTHORIZATION")

    def test_source_main_drift_blocks(self):
        bad = base_prep()
        bad["preparation_source_main"] = "0" * 40
        with self.assertRaises(mod.BootstrapPreparationError):
            mod.validate_preparation(bad)


if __name__ == "__main__":
    unittest.main()
