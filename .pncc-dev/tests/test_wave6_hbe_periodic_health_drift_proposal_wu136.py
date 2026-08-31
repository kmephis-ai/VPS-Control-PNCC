from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / ".pncc-dev" / "contracts" / "wave6-hbe-periodic-health-drift-authority-proposal-wu136.json"
FRONTIER = ROOT / ".pncc-dev" / "contracts" / "wave5-next-governed-work-unit-frontier.json"
TRANSITION = ROOT / ".pncc-dev" / "contracts" / "governed-frontier-transition-pipe-wu-136.json"


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


class Wave6HbePeriodicHealthDriftProposalWu136Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        self.frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
        self.transition = json.loads(TRANSITION.read_text(encoding="utf-8"))

    def test_proposal_is_exactly_non_authorizing(self) -> None:
        p = self.proposal
        self.assertEqual(p["schema_version"], 1)
        self.assertEqual(p["role"], "WAVE6_HBE_PERIODIC_HEALTH_DRIFT_AUTHORITY_PROPOSAL")
        self.assertEqual(p["proposal_state"], "PREPARED_NON_AUTHORIZING")
        self.assertEqual(p["work_unit"]["work_unit_id"], "PIPE-WU-136")
        self.assertEqual(p["work_unit"]["issue_number"], 320)
        self.assertFalse(p["work_unit"]["runtime_required"])
        self.assertTrue(p["authority"])
        self.assertTrue(all(value is False for value in p["authority"].values()))

    def test_monitoring_shape_is_bounded_read_only(self) -> None:
        m = self.proposal["monitoring_proposal"]
        self.assertEqual(m["mode"], "READ_ONLY_PROVIDER_TRUTH_ONLY")
        self.assertEqual(m["cadence_seconds"], 3600)
        self.assertGreater(m["cadence_seconds"], m["maximum_single_run_seconds"])
        self.assertEqual(m["snapshot_freshness_max_seconds"], 300)
        self.assertEqual(m["future_clock_skew_max_seconds"], 30)
        self.assertEqual(m["overlap_policy"], "SKIP_IF_PREVIOUS_RUN_ACTIVE")
        self.assertEqual(m["required_check_contexts"], ["repo-integrity", "powershell-static", "truth-contract"])
        self.assertEqual(m["runtime_truth_source"], "NOT_APPLICABLE_NO_RUNTIME_ACTION")
        for route in m["outcome_routing"].values():
            self.assertNotIn("MUTATE", route)

    def test_activation_requires_explicit_owner_authorization(self) -> None:
        a = self.proposal["activation_boundary"]
        self.assertEqual(a["state"], "OWNER_AUTHORIZATION_REQUIRED")
        self.assertFalse(a["schedule_exists"])
        self.assertFalse(a["schedule_enabled"])
        self.assertFalse(a["periodic_execution_authorized"])
        self.assertFalse(a["unattended_mutation_authorized"])
        self.assertFalse(a["higher_autonomy_authorized"])
        self.assertFalse(a["generic_continue_instruction_is_authorization"])
        self.assertTrue(a["future_authorization_must_bind_exact_proposal_blob"])
        self.assertTrue(a["future_authorization_must_bind_fresh_main_sha"])

    def test_mandatory_invariants_are_preserved(self) -> None:
        s = self.proposal["safety_contract"]
        self.assertEqual(s["primary_1081_role"], "PRIMARY_AUTO")
        self.assertEqual(s["reserve_1080_role"], "RESERVE_MANUAL_MANUAL_ONLY")
        self.assertTrue(s["reserve_1080_lifecycle_mutation_forbidden"])
        self.assertTrue(s["primary_1081_lifecycle_mutation_forbidden"])
        self.assertEqual(s["v631_expected_sha256"], "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e")
        self.assertTrue(s["ci_runtime_equivalence_forbidden"])
        self.assertTrue(s["secrets_forbidden"])
        self.assertTrue(s["public_self_hosted_runner_forbidden"])
        self.assertTrue(s["ruleset_bypass_forbidden"])
        self.assertTrue(s["force_update_forbidden"])

    def test_frontier_is_exact_terminal_none(self) -> None:
        self.assertEqual(self.frontier, {"schema_version": 1, "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER", "state": "NONE"})
        self.assertEqual(blob_sha(FRONTIER), "73719d89c603c2607c3295c5e601b1a1cd66d928")

    def test_transition_binds_proposal_provider_and_terminal_frontier(self) -> None:
        t = self.transition
        self.assertEqual(t["work_unit_id"], "PIPE-WU-136")
        self.assertEqual(t["issue_number"], 320)
        self.assertFalse(t["runtime_required"])
        self.assertEqual(t["predecessor_frontier"]["blob_sha"], "0fcd62f95ca491d70faddc07a251baed0524f876")
        self.assertEqual(t["successor_frontier"], {"state": "NONE", "frontier_id": "NONE", "blob_sha": "73719d89c603c2607c3295c5e601b1a1cd66d928"})
        self.assertEqual(t["proposal_binding"]["blob_sha"], blob_sha(PROPOSAL))
        self.assertEqual(t["provider_truth_observed"]["provider_state_after_lease_acquisition_sha"], "5deb6c7c134ec104ff08db1a9b15a30846e712ba")
        self.assertEqual(t["provider_truth_observed"]["writer_lease_registry_blob_sha"], "9a04574ba022a6e96c4ca8247ee5b4b115dab147")
        self.assertEqual(t["provider_truth_observed"]["writer_lease_generation"], 49)
        self.assertEqual(t["provider_truth_observed"]["writer_lease_id"], "3467e349-fa84-4b99-887c-048f33634b70")
        for key, value in t.items():
            if key.endswith("_authority"):
                self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
