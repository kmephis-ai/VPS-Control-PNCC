#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALUATOR_PATH = ROOT / '.pncc-dev/scripts/evaluate_wave6_wu186_installer_build_request_admission.py'
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu186-installer-build-request-admission-policy.json'

spec = importlib.util.spec_from_file_location('wu186', EVALUATOR_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SOURCE_MAIN = '93a8716b395efa88070921a8622db29f5420c288'
DEFINITION_PATH = 'installer/windows/VPS-Control-PNCC.iss'
DEFINITION_BLOB = 'd30a158aef3535a9066608495b45abcf41112926'


def base_request():
    return {
        'schema_version': 1,
        'source_main_sha': SOURCE_MAIN,
        'installer_definition': {
            'path': DEFINITION_PATH,
            'git_blob_sha': DEFINITION_BLOB
        },
        'compiler_receipt_admission': {
            'schema_version': 1,
            'work_unit': 'PIPE-WU-185',
            'decision': 'ADMITTED',
            'reason_codes': ['WU184_RECEIPT_VERIFIED'],
            'authority': 'RECEIPT_CONSUMER_ADMISSION_ONLY'
        }
    }


def durable_policy():
    return json.loads(POLICY_PATH.read_text(encoding='utf-8'))


class TestWu186(unittest.TestCase):
    def test_durable_exact_identity_is_admitted(self):
        out = mod.evaluate(base_request())
        self.assertEqual(out['decision'], 'ADMITTED')
        self.assertEqual(out['reason_codes'], ['WU185_RECEIPT_ADMITTED', 'SOURCE_IDENTITY_VERIFIED', 'INSTALLER_DEFINITION_IDENTITY_VERIFIED'])

    def test_durable_policy_has_exact_materialized_definition(self):
        policy = durable_policy()
        self.assertEqual(policy['source_identity']['main_sha'], SOURCE_MAIN)
        self.assertEqual(policy['installer_definition'], {'path': DEFINITION_PATH, 'git_blob_sha': DEFINITION_BLOB})
        self.assertFalse(policy['execution_boundary']['persist_admitted_request'])
        self.assertTrue(all(value is False for value in policy['authority'].values()))

    def test_source_drift_blocks(self):
        req = base_request(); req['source_main_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_definition_path_drift_blocks(self):
        req = base_request(); req['installer_definition']['path'] = 'installer/windows/Other.iss'
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_definition_blob_drift_blocks(self):
        req = base_request(); req['installer_definition']['git_blob_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_blocked_wu185_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['decision'] = 'BLOCKED'
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_wu185_identity_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['work_unit'] = 'PIPE-WU-184'
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_wu185_authority_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['authority'] = 'BUILD'
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_wu185_reason_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['reason_codes'] = ['OTHER']
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_extra_request_authority_field_blocks(self):
        req = base_request(); req['execute'] = True
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_extra_definition_field_blocks(self):
        req = base_request(); req['installer_definition']['execute'] = True
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_extra_wu185_field_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['build'] = True
        self.assertEqual(mod.evaluate(req)['decision'], 'BLOCKED')

    def test_invalid_policy_blob_blocks(self):
        policy = copy.deepcopy(durable_policy()); policy['installer_definition']['git_blob_sha'] = 'not-a-sha'
        self.assertEqual(mod.evaluate(base_request(), policy)['decision'], 'BLOCKED')

    def test_missing_definition_anchor_blocks(self):
        policy = copy.deepcopy(durable_policy()); policy['installer_definition'] = None
        self.assertEqual(mod.evaluate(base_request(), policy)['decision'], 'BLOCKED')

    def test_non_object_request_blocks(self):
        self.assertEqual(mod.evaluate([])['decision'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
