#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
VALIDATOR = ROOT / '.pncc-dev/scripts/evaluate_stable_runtime_authority_owner_grant_v701.py'
HISTORICAL = ROOT / '.pncc-dev/scripts/evaluate_stable_runtime_authority_owner_grant.py'


class V701OwnerRuntimeAuthorityBoundaryTests(unittest.TestCase):
    def run_script(self, path):
        p = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + '\n' + p.stderr)
        return p.stdout

    def test_v701_waiting_boundary_passes(self):
        out = self.run_script(VALIDATOR)
        self.assertIn('WAITING_OWNER_AUTHORIZATION', out)
        self.assertIn('OWNER_AUTHORIZATION_PRESENT=false', out)
        self.assertIn('RUNTIME_AUTHORITY=false', out)

    def test_historical_v700_grant_still_passes(self):
        out = self.run_script(HISTORICAL)
        self.assertIn('RUNTIME_AUTHORITY_GRANTED', out)

    def test_v701_preparation_is_default_deny(self):
        d = json.loads(GRANT.read_text(encoding='utf-8-sig'))
        self.assertTrue(d['runtime_authority_candidate'])
        self.assertFalse(d['owner_authorization_present'])
        self.assertFalse(d['owner_authorization_binding_complete'])
        self.assertEqual(d['grant_state'], 'WAITING_OWNER_AUTHORIZATION')
        for key in (
            'runtime_authority','promotion_eligible','release_or_tag_authorized','tag_created',
            'release_created','stable_declared','artifact_rebuilt','artifact_substituted',
            'runtime_mutation','product_bytes_mutated','runtime_bytes_mutated',
            'private_runtime_payload_published'
        ):
            self.assertFalse(d[key], key)

    def test_future_authorization_scope_is_runtime_authority_only(self):
        d = json.loads(GRANT.read_text(encoding='utf-8-sig'))
        self.assertEqual(d['owner_authorization_scope'], 'RUNTIME_AUTHORITY_GRANT_ONLY')
        self.assertEqual(
            d['next_transaction'],
            'EXPLICIT_OWNER_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_REQUIRED'
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
