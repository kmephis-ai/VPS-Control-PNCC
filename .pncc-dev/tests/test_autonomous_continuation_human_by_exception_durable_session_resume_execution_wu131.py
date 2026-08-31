from __future__ import annotations
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VALIDATOR=ROOT/".pncc-dev/scripts/validate_autonomous_continuation_human_by_exception_durable_session_resume_execution_wu131.py"
EVIDENCE=ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-durable-session-resume-execution-wu131.json"

def load_validator():
    spec=importlib.util.spec_from_file_location("wu131_validator_tests",VALIDATOR)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod

V=load_validator()

class TestWU131(unittest.TestCase):
    def setUp(self):
        self.e=json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def assertBlockedValidation(self,e):
        with self.assertRaises(V.ValidationError):
            V.validate_evidence(e,check_anchors=False,replay=False)

    def test_canonical_evidence_and_hbe_replay_pass(self):
        out=V.validate_evidence(copy.deepcopy(self.e),check_anchors=True,replay=True)
        self.assertEqual(out["status"],"PASS")
        self.assertFalse(out["authority_granted"])

    def test_persisted_decision_reuse_fails(self):
        e=copy.deepcopy(self.e)
        e["handoff"]["persisted_execution_admission_reused"]=True
        self.assertBlockedValidation(e)

    def test_stale_provider_before_fails(self):
        e=copy.deepcopy(self.e)
        e["fresh_resume_truth_before_transaction"]["provider_state"]["state_branch_head_sha"]="0"*40
        self.assertBlockedValidation(e)

    def test_non_monotonic_generation_fails(self):
        e=copy.deepcopy(self.e)
        e["post_handoff_iterations"][0]["transaction_result"]["generation"]=39
        self.assertBlockedValidation(e)

    def test_provider_parent_mismatch_fails(self):
        e=copy.deepcopy(self.e)
        e["post_handoff_iterations"][0]["transaction_result"]["provider_state_parent_sha"]="0"*40
        self.assertBlockedValidation(e)

    def test_duplicate_transaction_fingerprint_fails(self):
        e=copy.deepcopy(self.e)
        fp=e["post_handoff_iterations"][0]["transaction_fingerprint"]
        e["post_handoff_iterations"][1]["transaction_fingerprint"]=fp
        e["completed_transaction_fingerprints"]=[fp,fp]
        self.assertBlockedValidation(e)

    def test_more_than_one_transaction_per_iteration_fails(self):
        e=copy.deepcopy(self.e)
        e["post_handoff_iterations"][1]["delegated_transaction_count"]=2
        self.assertBlockedValidation(e)

    def test_missing_fresh_readback_fails(self):
        e=copy.deepcopy(self.e)
        e["post_handoff_iterations"][0]["fresh_provider_readback_completed"]=False
        self.assertBlockedValidation(e)

    def test_historical_gen37_mutation_fails(self):
        e=copy.deepcopy(self.e)
        e["historical_writer_lease_observations"]["wu129_generation37_mutated"]=True
        self.assertBlockedValidation(e)

    def test_historical_reactivation_fails(self):
        e=copy.deepcopy(self.e)
        e["historical_writer_lease_observations"]["historical_lease_reactivated"]=True
        self.assertBlockedValidation(e)

    def test_1080_or_1081_mutation_fails(self):
        for key in ("reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed"):
            e=copy.deepcopy(self.e)
            e[key]=True
            self.assertBlockedValidation(e)

    def test_authority_broadening_fails(self):
        e=copy.deepcopy(self.e)
        e["authority_broadening_performed"]=True
        self.assertBlockedValidation(e)

    def test_unknown_outcome_replay_fails(self):
        e=copy.deepcopy(self.e)
        e["interrupted_checkpoint_path"]["delegated_transaction_replayed"]=True
        self.assertBlockedValidation(e)

    def test_pending_readback_replay_fails(self):
        e=copy.deepcopy(self.e)
        e["readback_pending_checkpoint_path"]["delegated_transaction_replayed"]=True
        self.assertBlockedValidation(e)

if __name__=="__main__":
    unittest.main()
