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


def base_request():
    return {
        'schema_version': 1,
        'source_main_sha': '52e635d81f3d76485ffdff9bce774fc7a9a1f7ff',
        'installer_definition': {
            'path': 'installer/PNCC.iss',
            'git_blob_sha': '1' * 40
        },
        'compiler_receipt_admission': {
            'schema_version': 1,
            'work_unit': 'PIPE-WU-185',
            'decision': 'ADMITTED',
            'reason_codes': ['WU184_RECEIPT_VERIFIED'],
            'authority': 'RECEIPT_CONSUMER_ADMISSION_ONLY'
        }
    }


def synthetic_policy():
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    policy['installer_definition'] = {
        'path': 'installer/PNCC.iss',
        'git_blob_sha': '1' * 40
    }
    return policy


class TestWu186(unittest.TestCase):
    def test_durable_default_policy_is_blocked(self):
        out = mod.evaluate(base_request())
        self.assertEqual(out['decision'], 'BLOCKED')
        self.assertEqual(out['reason_codes'], ['INSTALLER_DEFINITION_NOT_AUTHORIZED'])

    def test_synthetic_in_memory_identity_can_be_admitted(self):
        out = mod.evaluate(base_request(), synthetic_policy())
        self.assertEqual(out['decision'], 'ADMITTED')

    def test_source_drift_blocks(self):
        req = base_request(); req['source_main_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_definition_path_drift_blocks(self):
        req = base_request(); req['installer_definition']['path'] = 'installer/Other.iss'
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_definition_blob_drift_blocks(self):
        req = base_request(); req['installer_definition']['git_blob_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_blocked_wu185_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['decision'] = 'BLOCKED'
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_wu185_identity_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['work_unit'] = 'PIPE-WU-184'
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_wu185_authority_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['authority'] = 'BUILD'
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_wu185_reason_drift_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['reason_codes'] = ['OTHER']
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_extra_request_authority_field_blocks(self):
        req = base_request(); req['execute'] = True
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_extra_definition_field_blocks(self):
        req = base_request(); req['installer_definition']['execute'] = True
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_extra_wu185_field_blocks(self):
        req = base_request(); req['compiler_receipt_admission']['build'] = True
        self.assertEqual(mod.evaluate(req, synthetic_policy())['decision'], 'BLOCKED')

    def test_invalid_policy_blob_blocks(self):
        policy = synthetic_policy(); policy['installer_definition']['git_blob_sha'] = 'not-a-sha'
        self.assertEqual(mod.evaluate(base_request(), policy)['decision'], 'BLOCKED')

    def test_missing_definition_anchor_blocks(self):
        policy = synthetic_policy(); policy['installer_definition'] = None
        self.assertEqual(mod.evaluate(base_request(), policy)['decision'], 'BLOCKED')

    def test_non_object_request_blocks(self):
        self.assertEqual(mod.evaluate([], synthetic_policy())['decision'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
