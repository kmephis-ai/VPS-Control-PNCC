#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/evaluate_wave6_wu197_installer_compiler_acquisition_authorization_readiness.py'
POLICY = ROOT / '.pncc-dev/contracts/wave6-wu197-installer-compiler-acquisition-authorization-readiness.json'

spec = importlib.util.spec_from_file_location('wu197', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def exact_candidate():
    p = json.loads(POLICY.read_text(encoding='utf-8'))
    return {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-197',
        'owner_authorization_state': 'NOT_GRANTED',
        'acquisition_authorized': False,
        'one_time_only': True,
        'runner_class': 'GITHUB_HOSTED',
        'destination_class': 'EPHEMERAL_WORKSPACE_ONLY',
        'target': copy.deepcopy(p['upstream_target'])
    }


class TestWu197(unittest.TestCase):
    def test_exact_candidate_is_ready_but_not_authorized(self):
        out = mod.evaluate(exact_candidate())
        self.assertEqual(out['decision'], 'READY_FOR_OWNER_GRANT')
        self.assertFalse(out['acquisition_authorized'])
        self.assertEqual(out['authority'], 'AUTHORIZATION_READINESS_ONLY')

    def test_self_grant_blocks(self):
        c = exact_candidate(); c['owner_authorization_state'] = 'GRANTED'; c['acquisition_authorized'] = True
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_self_hosted_runner_blocks(self):
        c = exact_candidate(); c['runner_class'] = 'SELF_HOSTED'
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_reusable_acquisition_blocks(self):
        c = exact_candidate(); c['one_time_only'] = False
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_persistent_destination_blocks(self):
        c = exact_candidate(); c['destination_class'] = 'PERSISTENT_CACHE'
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_asset_id_drift_blocks(self):
        c = exact_candidate(); c['target']['asset_id'] += 1
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_hash_drift_blocks(self):
        c = exact_candidate(); c['target']['sha256'] = '0' * 64
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_mutable_tag_drift_blocks(self):
        c = exact_candidate(); c['target']['tag'] = 'latest'
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_extra_authority_field_blocks(self):
        c = exact_candidate(); c['force'] = True
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_target_extra_field_blocks(self):
        c = exact_candidate(); c['target']['url'] = 'https://example.invalid/latest.exe'
        self.assertEqual(mod.evaluate(c)['decision'], 'BLOCKED')

    def test_policy_authority_expansion_blocks(self):
        p = json.loads(POLICY.read_text(encoding='utf-8')); p['authority']['network_acquisition'] = True
        self.assertEqual(mod.evaluate(exact_candidate(), p)['decision'], 'BLOCKED')

    def test_policy_execution_expansion_blocks(self):
        p = json.loads(POLICY.read_text(encoding='utf-8')); p['future_execution_boundary']['execute_allowed'] = True
        self.assertEqual(mod.evaluate(exact_candidate(), p)['decision'], 'BLOCKED')

    def test_non_object_blocks(self):
        self.assertEqual(mod.evaluate([])['decision'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
