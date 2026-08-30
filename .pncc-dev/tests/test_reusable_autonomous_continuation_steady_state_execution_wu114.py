import copy, importlib.util, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/".pncc-dev/scripts/validate_reusable_autonomous_continuation_steady_state_execution_wu114.py"
EVIDENCE=ROOT/".pncc-dev/contracts/reusable-autonomous-continuation-steady-state-execution-wu114.json"
spec=importlib.util.spec_from_file_location("wu114_validator",MOD); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
BASE=json.loads(EVIDENCE.read_text())

class WU114SteadyStateExecutionTests(unittest.TestCase):
    def ok(self,e):
        r=m.validate(e,check_anchors=False); self.assertEqual(r["state"],"PASS"); self.assertEqual(r["iterations_validated"],2)
    def blocked(self,e):
        with self.assertRaises(m.ValidationError): m.validate(e,check_anchors=False)
    def test_canonical_evidence_passes_and_replays_both_iterations(self): self.ok(copy.deepcopy(BASE))
    def test_missing_first_readback_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][0]["fresh_provider_readback_completed"]=False; self.blocked(e)
    def test_second_iteration_without_previous_readback_binding_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["previous_iteration_fresh_provider_readback_completed"]=False; self.blocked(e)
    def test_stale_control_or_admission_reuse_blocks(self):
        for field in ("control_loop_reused_from_prior_iteration","execution_admission_reused_from_prior_iteration"):
            e=copy.deepcopy(BASE); e["iterations"][1][field]=True; self.blocked(e)
    def test_more_than_one_transaction_in_iteration_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["delegated_transaction_count"]=2; self.blocked(e)
    def test_authority_or_target_substitution_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["delegated_authority_identity"]="EXISTING_REUSABLE_AUTONOMOUS_MERGE_CLOSE_AUTHORITY"; self.blocked(e)
        e=copy.deepcopy(BASE); e["iterations"][1]["target_action"]="EXACT_BOUNDED_PULL_REQUEST_CREATE_PATH"; self.blocked(e)
    def test_provider_state_chain_gap_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["provider_state_before"]["registry_blob_sha"]="a"*40; self.blocked(e)
    def test_branch_not_created_from_exact_base_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["transaction_result"]["branch_head_sha"]="b"*40; self.blocked(e)
    def test_branch_compare_not_identical_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"][1]["branch_state_after"]["compare_status"]="ahead"; e["iterations"][1]["branch_state_after"]["ahead_by"]=1; self.blocked(e)
    def test_forbidden_mutation_or_authority_broadening_blocks(self):
        for field in m.FORBIDDEN_TRUE:
            e=copy.deepcopy(BASE); e[field]=True; self.blocked(e)
    def test_main_drift_blocks(self):
        e=copy.deepcopy(BASE); e["main_sha_after_iterations"]="c"*40; self.blocked(e)
    def test_iteration_reordering_blocks(self):
        e=copy.deepcopy(BASE); e["iterations"].reverse(); self.blocked(e)
    def test_anchor_map_matches_canonical_repository(self):
        for name,(rel,expected) in m.ANCHORS.items(): self.assertEqual(m.blob(ROOT/rel),expected,name)

if __name__=="__main__": unittest.main()
