import copy
import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("x",ROOT/".pncc-dev/scripts/writer_lease_cas_executor_wu149.py")
x=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(x)

WU={"work_unit_id":"PIPE-WU-149","conflict_domain":"wave6-test","base_sha":"a"*40,"branch":"agent/PIPE-WU-149-test","runtime_required":False}
NOW=datetime(2026,9,2,16,0,0,tzinfo=timezone.utc)
REQ={"action":"ACQUIRE","request_id":"11111111-1111-4111-8111-111111111111","lease_id":"22222222-2222-4222-8222-222222222222","expected_state_head":"b"*40,"expected_registry_blob":"c"*40}
def reg(entries=None,g=62):
    return {"schema_version":1,"role":"WRITER_LEASE_REGISTRY","generation":g,"entries":entries or []}
def lease(**kw):
    d={"schema_version":1,"role":"WRITER_LEASE","lease_id":"33333333-3333-4333-8333-333333333333","work_unit_id":"OLD","conflict_domain":"old","holder":"chatgpt-wave5-writer","base_sha":"d"*40,"branch":"agent/old","state":"RELEASED","generation":1,"acquired_at":"2026-09-01T00:00:00Z","heartbeat_at":"2026-09-01T00:00:00Z","expires_at":"2026-09-01T01:00:00Z"}
    d.update(kw); return d

class T(unittest.TestCase):
    def test_parse_exact_markers(self):
        body='<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-149 state=READY conflict_domain=wave6-test base='+('a'*40)+' runtime_required=false branch=agent/PIPE-WU-149-test -->\n<!-- PNCC-LEASE-CAS-REQUEST schema=1 action=ACQUIRE request_id=11111111-1111-4111-8111-111111111111 lease_id=22222222-2222-4222-8222-222222222222 expected_state_head='+('b'*40)+' expected_registry_blob='+('c'*40)+' -->'
        self.assertEqual(x.parse_work_unit(body)["work_unit_id"],"PIPE-WU-149")
        self.assertEqual(x.parse_request(body)["action"],"ACQUIRE")
    def test_duplicate_request_fails(self):
        b='<!-- PNCC-LEASE-CAS-REQUEST schema=1 action=ACQUIRE request_id=11111111-1111-4111-8111-111111111111 lease_id=22222222-2222-4222-8222-222222222222 expected_state_head='+('b'*40)+' expected_registry_blob='+('c'*40)+' -->'
        with self.assertRaises(x.ExecutorError): x.parse_request(b+b)
    def test_runtime_required_fails(self):
        b='<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-149 state=READY conflict_domain=x base='+('a'*40)+' runtime_required=true branch=agent/x -->'
        with self.assertRaises(x.ExecutorError): x.parse_work_unit(b)
    def test_main_branch_fails(self):
        b='<!-- PNCC-WORK-UNIT schema=1 id=PIPE-WU-149 state=READY conflict_domain=x base='+('a'*40)+' runtime_required=false branch=main -->'
        with self.assertRaises(x.ExecutorError): x.parse_work_unit(b)
    def test_acquire_monotonic_preserves_history(self):
        old=lease()
        out=x.build_acquire_registry(reg([old]),WU,REQ,NOW)
        self.assertEqual(out["generation"],63); self.assertEqual(out["entries"][0],old)
        self.assertEqual(out["entries"][-1]["generation"],63)
        self.assertEqual(out["entries"][-1]["state"],"ACTIVE")
    def test_duplicate_lease_id_fails(self):
        r=reg([lease(lease_id=REQ["lease_id"])])
        with self.assertRaises(x.ExecutorError): x.build_acquire_registry(r,WU,REQ,NOW)
    def test_active_same_domain_blocks(self):
        r=reg([lease(state="ACTIVE",conflict_domain="wave6-test",expires_at="2026-09-02T17:00:00Z")])
        with self.assertRaises(x.ExecutorError): x.build_acquire_registry(r,WU,REQ,NOW)
    def test_expired_active_is_historical(self):
        old=lease(state="ACTIVE",conflict_domain="wave6-test",expires_at="2026-09-02T15:00:00Z")
        out=x.build_acquire_registry(reg([old]),WU,REQ,NOW)
        self.assertEqual(out["entries"][0],old)
    def test_release_only_state_changes(self):
        active=lease(lease_id=REQ["lease_id"],work_unit_id=WU["work_unit_id"],conflict_domain=WU["conflict_domain"],base_sha=WU["base_sha"],branch=WU["branch"],state="ACTIVE",expires_at="2026-09-02T17:00:00Z")
        rr=dict(REQ); rr["action"]="RELEASE"
        out=x.build_release_registry(reg([active],g=63),WU,rr,NOW)
        expected=copy.deepcopy(active); expected["state"]="RELEASED"
        self.assertEqual(out["entries"][0],expected); self.assertEqual(out["generation"],63)
    def test_release_expired_fails(self):
        active=lease(lease_id=REQ["lease_id"],work_unit_id=WU["work_unit_id"],conflict_domain=WU["conflict_domain"],base_sha=WU["base_sha"],branch=WU["branch"],state="ACTIVE",expires_at="2026-09-02T15:00:00Z")
        rr=dict(REQ); rr["action"]="RELEASE"
        with self.assertRaises(x.ExecutorError): x.build_release_registry(reg([active],g=63),WU,rr,NOW)
    def test_release_foreign_binding_fails(self):
        active=lease(lease_id=REQ["lease_id"],work_unit_id="OTHER",state="ACTIVE",expires_at="2026-09-02T17:00:00Z")
        rr=dict(REQ); rr["action"]="RELEASE"
        with self.assertRaises(x.ExecutorError): x.build_release_registry(reg([active],g=63),WU,rr,NOW)
    def test_request_unknown_attr_fails(self):
        b='<!-- PNCC-LEASE-CAS-REQUEST schema=1 action=ACQUIRE request_id=11111111-1111-4111-8111-111111111111 lease_id=22222222-2222-4222-8222-222222222222 expected_state_head='+('b'*40)+' expected_registry_blob='+('c'*40)+' force=true -->'
        with self.assertRaises(x.ExecutorError): x.parse_request(b)
    def test_contract_has_no_new_authority(self):
        c=json.loads((ROOT/".pncc-dev/contracts/wave6-wu149-writer-lease-cas-executor.json").read_text())
        self.assertTrue(all(v is False for v in c["authority"].values()))
        self.assertFalse(c["cas"]["force_ref_update"])
    def test_workflow_surface(self):
        t=(ROOT/".github/workflows/wave6-wu149-writer-lease-cas-executor.yml").read_text().lower()
        self.assertIn("issues:",t); self.assertIn("types: [edited]",t)
        self.assertIn("contents: write",t)
        self.assertNotIn("self-hosted",t); self.assertNotIn("repository_dispatch",t)
        self.assertNotIn("schedule:",t); self.assertNotIn("workflow_dispatch:",t)
        self.assertNotIn("force: true",t); self.assertNotIn("git push",t)
        self.assertNotIn("127.0.0.1:1080",t); self.assertNotIn("127.0.0.1:1081",t)
    def test_script_has_force_false_and_readback(self):
        t=(ROOT/".pncc-dev/scripts/writer_lease_cas_executor_wu149.py").read_text()
        self.assertIn('"force":False',t); self.assertIn("POSTWRITE_READBACK_MISMATCH",t)
        self.assertNotIn('"force":True',t)

if __name__=="__main__": unittest.main()
