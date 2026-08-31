#!/usr/bin/env python3
import copy, importlib.util, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EVAL=ROOT/".pncc-dev/scripts/validate_autonomous_continuation_human_by_exception_steady_state_execution_wu129.py"
spec=importlib.util.spec_from_file_location("wu129_validate",EVAL)
mod=importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(mod)

class WU129SteadyStateExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=mod.load(ROOT/".pncc-dev/contracts/autonomous-continuation-human-by-exception-steady-state-execution-wu129.json")

    def ok(self,value):
        self.assertEqual(mod.validate(value,check_anchors=False)["state"],"PASS")

    def blocked(self,value):
        with self.assertRaises(mod.ValidationError):
            mod.validate(value,check_anchors=False)

    def test_canonical_evidence_passes(self):
        self.ok(copy.deepcopy(self.evidence))

    def test_second_iteration_requires_first_readback(self):
        x=copy.deepcopy(self.evidence); x["iterations"][1]["previous_iteration_fresh_provider_readback_completed"]=False
        self.blocked(x)

    def test_cross_iteration_provider_chain_cannot_drift(self):
        x=copy.deepcopy(self.evidence); x["iterations"][1]["provider_state_before"]["registry_blob_sha"]="0"*40
        self.blocked(x)

    def test_transaction_count_cannot_exceed_one(self):
        x=copy.deepcopy(self.evidence); x["iterations"][0]["delegated_transaction_count"]=2
        self.blocked(x)

    def test_branch_must_start_at_exact_base(self):
        x=copy.deepcopy(self.evidence); x["iterations"][1]["transaction_result"]["branch_head_sha"]="1"*40
        self.blocked(x)

    def test_expired_generation_37_must_remain_historical_active(self):
        x=copy.deepcopy(self.evidence); x["session_interruption_recovery"]["original_lease"]["recorded_state_preserved"]="RELEASED"
        self.blocked(x)

    def test_expired_generation_37_cannot_be_marked_mutated(self):
        x=copy.deepcopy(self.evidence); x["session_interruption_recovery"]["original_lease"]["historical_entry_mutated"]=True
        self.blocked(x)

    def test_recovery_must_use_new_monotonic_generation(self):
        x=copy.deepcopy(self.evidence); x["session_interruption_recovery"]["fresh_claim"]["registry_generation_after"]=37
        self.blocked(x)

    def test_recovery_is_not_a_third_required_iteration(self):
        x=copy.deepcopy(self.evidence); x["session_interruption_recovery"]["recovery_counted_as_required_iteration"]=True
        self.blocked(x)

    def test_silent_lease_steal_cannot_be_asserted(self):
        x=copy.deepcopy(self.evidence); x["session_interruption_recovery"]["fresh_claim"]["silent_lease_steal_performed"]=True
        self.blocked(x)

    def test_authority_cannot_be_granted_by_execution_evidence(self):
        x=copy.deepcopy(self.evidence); x["authority_granted"]=True
        self.blocked(x)

    def test_product_runtime_and_1080_1081_remain_untouched(self):
        for key in ("product_runtime_mutation_performed","reserve_1080_lifecycle_mutation_performed","primary_1081_lifecycle_mutation_performed"):
            x=copy.deepcopy(self.evidence); x[key]=True
            self.blocked(x)

if __name__=="__main__":
    unittest.main()
