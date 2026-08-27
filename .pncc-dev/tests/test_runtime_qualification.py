from __future__ import annotations
import copy, importlib.util, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; MODPATH=ROOT/'.pncc-dev/scripts/evaluate_runtime_qualification.py'
spec=importlib.util.spec_from_file_location('rq',MODPATH); MOD=importlib.util.module_from_spec(spec); sys.modules[spec.name]=MOD; spec.loader.exec_module(MOD)
POL=json.loads((ROOT/'.pncc-dev/contracts/runtime-qualification-policy.json').read_text()); REQ=json.loads((ROOT/'.pncc-dev/requests/runtime-qualification-rc14.39.json').read_text())
def result(kind='PASS', failure=None):
    checks=[]
    for i,s in enumerate(POL['required_scopes']):
        r=kind if i==0 else 'PASS'; fc=failure if i==0 and r!='PASS' else None
        checks.append({'scope':s,'result':r,'exit_code':0 if r=='PASS' else 10,'failure_class':fc,'evidence_refs':[f'private://e/{s.lower()}']})
    q='RUNTIME_VERIFIED' if kind=='PASS' else ('BLOCKED' if kind=='BLOCKED' else 'FAILED')
    return {'schema_version':1,'contract_id':POL['result_contract_id'],'request_id':REQ['request_id'],'candidate':copy.deepcopy(REQ['candidate']),
      'producer':{'source_plane':'PRIVATE_RUNTIME','agent_id':'PNCC-WINDOWS-AGENT','runtime_agent_version':'1.0.0','validation_lab_version':'1.0.0'},
      'environment':{'windows_version':'10.0.19045','powershell_version':'5.1.19041.6456'},'checks':checks,
      'evidence_bundle':{'sha256':'a'*64,'private_location_ref':'private://pncc/evidence/abc','sanitation_state':'PRIVATE'},
      'qualification_state':q,'failure_classification':None if kind=='PASS' else failure,'runtime_authority':kind=='PASS','promotion_eligible':False}
class Tests(unittest.TestCase):
 def test_current_request_exact_and_waiting(self):
  MOD.validate_request(REQ,POL); o=MOD.evaluate(ROOT,ROOT/'.pncc-dev/requests/runtime-qualification-rc14.39.json'); self.assertEqual('WAITING_RUNTIME_EVIDENCE',o['state']); self.assertFalse(o['runtime_authority'])
 def test_candidate_substitution_fails(self):
  q=copy.deepcopy(REQ); q['candidate']['artifact_sha256']='b'*64
  with self.assertRaises(MOD.ContractError): MOD.validate_request(q,POL)
 def test_scope_omission_fails(self):
  q=copy.deepcopy(REQ); q['required_scopes']=q['required_scopes'][:-1]
  with self.assertRaises(MOD.ContractError): MOD.validate_request(q,POL)
 def test_invariant_weakening_fails(self):
  q=copy.deepcopy(REQ); q['expected_invariants']['plaintext_pw_allowed']=True
  with self.assertRaises(MOD.ContractError): MOD.validate_request(q,POL)
 def test_full_private_pass_can_be_runtime_verified_but_not_promoted(self):
  r=result(); self.assertEqual('RUNTIME_VERIFIED',MOD.validate_result(REQ,r,POL)); self.assertTrue(r['runtime_authority']); self.assertFalse(r['promotion_eligible'])
 def test_hosted_source_plane_cannot_verify(self):
  r=result(); r['producer']['source_plane']='GITHUB_HOSTED'
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_missing_result_scope_fails(self):
  r=result(); r['checks'].pop()
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_blocked_environment_is_not_product_defect(self):
  r=result('BLOCKED','ENVIRONMENT_OR_BASELINE_BLOCKER'); self.assertEqual('BLOCKED',MOD.validate_result(REQ,r,POL)); self.assertFalse(r['runtime_authority'])
 def test_product_failure_is_failed_not_blocked(self):
  r=result('FAIL','PRODUCT_DEFECT'); self.assertEqual('FAILED',MOD.validate_result(REQ,r,POL))
 def test_nonpass_zero_exit_fails(self):
  r=result('BLOCKED','ENVIRONMENT_OR_BASELINE_BLOCKER'); r['checks'][0]['exit_code']=0
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_pass_with_failure_class_fails(self):
  r=result(); r['checks'][0]['failure_class']='PRODUCT_DEFECT'
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_evidence_must_remain_private(self):
  r=result(); r['evidence_bundle']['sanitation_state']='SANITIZED_PUBLIC'
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_runtime_verified_requires_all_pass(self):
  r=result('BLOCKED','ENVIRONMENT_OR_BASELINE_BLOCKER'); r['qualification_state']='RUNTIME_VERIFIED'; r['runtime_authority']=True
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
 def test_promotion_true_always_fails(self):
  r=result(); r['promotion_eligible']=True
  with self.assertRaises(MOD.ContractError): MOD.validate_result(REQ,r,POL)
if __name__=='__main__': unittest.main(verbosity=2)
