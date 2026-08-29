import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('lease_lifecycle',ROOT/'.pncc-dev/scripts/evaluate_writer_lease_lifecycle.py')
mod=importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

LEASE={
 'schema_version':1,'role':'WRITER_LEASE','lease_id':'3bf7a003-1e8e-4ab2-910d-0c1d4aba9b03',
 'work_unit_id':'PIPE-WU-096','conflict_domain':'wave5-writer-lease-bootstrap-authority-preparation',
 'holder':'chatgpt-wave5-writer','base_sha':'755343fa254ca17e93c0ec85631de22e37ce830e',
 'branch':'pncc-provider-state','state':'ACTIVE','generation':1,
 'acquired_at':'2026-08-29T17:54:21Z','heartbeat_at':'2026-08-29T17:54:21Z','expires_at':'2026-08-29T18:54:21Z'
}


def call(action='HEARTBEAT',now='2026-08-29T18:10:00Z',fresh=True,authority=False,lease=None,**overrides):
    args=dict(holder='chatgpt-wave5-writer',work_unit_id='PIPE-WU-096',conflict_domain='wave5-writer-lease-bootstrap-authority-preparation',base_sha='755343fa254ca17e93c0ec85631de22e37ce830e',branch='pncc-provider-state')
    args.update(overrides)
    return mod.evaluate_lifecycle(LEASE if lease is None else lease,action=action,now_iso=now,fresh_provider_truth=fresh,explicit_autonomous_authority=authority,**args)


class LifecycleTests(unittest.TestCase):
    def test_heartbeat_eligible(self):
        self.assertEqual(call()['decision'],'HEARTBEAT_ELIGIBLE')
    def test_release_eligible(self):
        self.assertEqual(call(action='RELEASE')['decision'],'RELEASE_ELIGIBLE')
    def test_natural_expiry_is_read_only(self):
        r=call(now='2026-08-29T18:54:21Z')
        self.assertEqual(r['decision'],'NATURALLY_EXPIRED')
        self.assertFalse(r['provider_mutation_performed'])
    def test_holder_mismatch_blocks(self):
        self.assertEqual(call(holder='other')['decision'],'BLOCKED')
    def test_base_mismatch_blocks(self):
        self.assertEqual(call(base_sha='0'*40)['decision'],'BLOCKED')
    def test_branch_mismatch_blocks(self):
        self.assertEqual(call(branch='agent/other')['decision'],'BLOCKED')
    def test_stale_provider_truth_blocks(self):
        self.assertEqual(call(fresh=False)['decision'],'BLOCKED')
    def test_autonomous_execution_without_authority_blocks(self):
        r=call(action='AUTONOMOUS_EXECUTION',authority=False)
        self.assertEqual(r['decision'],'BLOCKED')
        self.assertIn('EXPLICIT_AUTONOMOUS_AUTHORITY_REQUIRED',r['reasons'])
    def test_design_policy_still_blocks_even_if_external_flag_true(self):
        r=call(action='AUTONOMOUS_EXECUTION',authority=True)
        self.assertEqual(r['decision'],'BLOCKED')
        self.assertFalse(r['autonomous_execution_admitted'])
    def test_released_lease_blocks(self):
        x=dict(LEASE);x['state']='RELEASED'
        self.assertEqual(call(lease=x)['decision'],'BLOCKED')

if __name__=='__main__':
    unittest.main()
