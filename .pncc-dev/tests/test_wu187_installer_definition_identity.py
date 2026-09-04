#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / '.pncc-dev/scripts/evaluate_wave6_wu187_installer_definition_identity.py'
POLICY = ROOT / '.pncc-dev/contracts/wave6-wu187-installer-definition-identity-policy.json'
spec = importlib.util.spec_from_file_location('wu187', EVALUATOR)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def synthetic_policy():
    p = json.loads(POLICY.read_text(encoding='utf-8'))
    p['installer_definition_identity'] = {'path': 'installer/PNCC.iss', 'git_blob_sha': '1' * 40}
    return p


def proposal():
    p = synthetic_policy()
    return {'schema_version': 1, 'source_main_sha': p['source_identity']['main_sha'],
            'installer_definition_identity': copy.deepcopy(p['installer_definition_identity']),
            'semantics': copy.deepcopy(p['required_semantics'])}


class TestWu187(unittest.TestCase):
    def test_durable_policy_blocks_unbound_identity(self):
        out = mod.evaluate(proposal())
        self.assertEqual(out['decision'], 'BLOCKED')
        self.assertEqual(out['reason_codes'], ['INSTALLER_DEFINITION_IDENTITY_NOT_AUTHORIZED'])

    def test_synthetic_identity_admits_in_memory_only(self):
        self.assertEqual(mod.evaluate(proposal(), synthetic_policy())['decision'], 'ADMITTED')

    def test_source_drift_blocks(self):
        q = proposal(); q['source_main_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_path_drift_blocks(self):
        q = proposal(); q['installer_definition_identity']['path'] = 'installer/Other.iss'
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_blob_drift_blocks(self):
        q = proposal(); q['installer_definition_identity']['git_blob_sha'] = '2' * 40
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_non_iss_path_blocks(self):
        q = proposal(); q['installer_definition_identity']['path'] = 'installer/PNCC.txt'
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_bad_blob_shape_blocks(self):
        q = proposal(); q['installer_definition_identity']['git_blob_sha'] = 'bad'
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_reserve_1080_lifecycle_expansion_blocks(self):
        q = proposal(); q['semantics']['reserve_1080_automated_lifecycle'] = True
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_primary_1081_authority_expansion_blocks(self):
        q = proposal(); q['semantics']['primary_1081_authority_expansion'] = True
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_v631_drift_blocks(self):
        q = proposal(); q['semantics']['v631_sha256'] = '0' * 64
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_secret_embedding_blocks(self):
        q = proposal(); q['semantics']['embed_secrets_or_passwords'] = True
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_plaintext_putty_pw_blocks(self):
        q = proposal(); q['semantics']['putty_plaintext_pw'] = True
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_hostkey_weakening_blocks(self):
        q = proposal(); q['semantics']['host_key_verification_fail_closed'] = False
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_ps51_regression_blocks(self):
        q = proposal(); q['semantics']['powershell_51_compatible'] = False
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')

    def test_extra_authority_field_blocks(self):
        q = proposal(); q['execute'] = True
        self.assertEqual(mod.evaluate(q, synthetic_policy())['decision'], 'BLOCKED')


if __name__ == '__main__': unittest.main()
