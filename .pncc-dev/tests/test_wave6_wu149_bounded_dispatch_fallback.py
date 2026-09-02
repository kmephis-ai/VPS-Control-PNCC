import copy, importlib.util, json, unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
S=importlib.util.spec_from_file_location("f",ROOT/".pncc-dev/scripts/evaluate_wave6_wu149_bounded_dispatch_fallback.py")
f=importlib.util.module_from_spec(S); S.loader.exec_module(f)
C=json.loads((ROOT/".pncc-dev/contracts/wave6-wu149-bounded-dispatch-fallback.json").read_text())

class T(unittest.TestCase):
 def blocked(self,c):
  with self.assertRaises(f.FallbackError): f.validate_contract(c,check_anchors=False)
 def test_contract_validates(self): self.assertEqual(f.validate_contract(copy.deepcopy(C),check_anchors=False)["state"],"BOUNDED_DISPATCH_FALLBACK_ACTIVE_READ_ONLY")
 def test_write_permission_fails(self):
  c=copy.deepcopy(C); c["permissions"]["contents"]="write"; self.blocked(c)
 def test_schedule_fails(self):
  c=copy.deepcopy(C); c["trigger"]["schedule_present"]=True; self.blocked(c)
 def test_repository_dispatch_fails(self):
  c=copy.deepcopy(C); c["trigger"]["repository_dispatch_present"]=True; self.blocked(c)
 def test_external_token_fails(self):
  c=copy.deepcopy(C); c["trigger"]["external_token_present"]=True; self.blocked(c)
 def test_authority_escalation_fails(self):
  c=copy.deepcopy(C); c["authority"]["provider_mutation"]=True; self.blocked(c)
 def test_runtime_authority_fails(self):
  c=copy.deepcopy(C); c["authority"]["runtime_action"]=True; self.blocked(c)
 def test_overclaim_fails(self):
  c=copy.deepcopy(C); c["claims"]["repairs_github_schedule_delivery"]=True; self.blocked(c)
 def test_concurrency_catchup_guard_required(self):
  c=copy.deepcopy(C); c["concurrency"]["cancel_in_progress"]=False; self.blocked(c)
 def test_workflow_surface(self):
  t=(ROOT/".github/workflows/wave6-wu149-bounded-dispatch-fallback.yml").read_text().lower()
  self.assertIn("workflow_dispatch:",t); self.assertNotIn("schedule:",t); self.assertNotIn("repository_dispatch",t)
  for p in ("contents: read","issues: read","pull-requests: read","actions: read","checks: read"): self.assertIn(p,t)
  for bad in ("contents: write","issues: write","actions: write","self-hosted","git push","--method post","--method patch","127.0.0.1:1080","127.0.0.1:1081"): self.assertNotIn(bad,t)
  self.assertIn("cancel-in-progress: true",t)
 def test_no_new_authority(self): self.assertTrue(all(v is False for v in C["authority"].values()))

if __name__=="__main__": unittest.main()
