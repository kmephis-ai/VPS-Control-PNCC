#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
AUTH = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-authorization-v7.0.1.json'
VALIDATOR = ROOT / '.pncc-dev/scripts/evaluate_stable_runtime_authority_owner_grant_v701.py'
HISTORICAL = ROOT / '.pncc-dev/scripts/evaluate_stable_runtime_authority_owner_grant.py'


class V701OwnerRuntimeAuthorityBoundaryTests(unittest.TestCase):
    def run_script(self, path):
        p = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + '\n' + p.stderr)
        return p.stdout

    def test_v701_exact_owner_grant_passes(self):
        out = self.run_script(VALIDATOR)
        self.assertIn('RUNTIME_AUTHORITY_GRANTED', out)
        self.assertIn('OWNER_AUTHORIZATION_PRESENT=true', out)
        self.assertIn('OWNER_AUTHORIZATION_BINDING_COMPLETE=true', out)
        self.assertIn('RUNTIME_AUTHORITY=true', out)
        self.assertIn('PROMOTION_ELIGIBLE=false', out)
        self.assertIn('RELEASE_OR_TAG_AUTHORIZED=false', out)

    def test_historical_v700_grant_still_passes(self):
        out = self.run_script(HISTORICAL)
        self.assertIn('RUNTIME_AUTHORITY_GRANTED', out)

    def test_authorization_receipt_is_exactly_bound(self):
        d = json.loads(AUTH.read_text(encoding='utf-8-sig'))
        self.assertEqual(d['contract_id'], 'PNCC_STABLE_RUNTIME_AUTHORITY_OWNER_AUTHORIZATION_V1')
        self.assertEqual(d['authorized_preparation_main'], 'c0b6c2dcbf74c7978ec5e668c06762c677b5d078')
        self.assertEqual(d['authorized_prepared_grant_contract_blob_sha'], '087bb42e2e21bfa68c25abe921f19944072d3dc4')
        self.assertEqual(d['stable_artifact_sha256'], '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72')
        self.assertEqual(d['stable_artifact_size_bytes'], 701893)
        self.assertEqual(d['request_id'], 'PNCC-RQ-V7.0.1-D58023321360')
        self.assertEqual(d['candidate_id'], 'PNCC-V7.0.1-D58023321360')
        self.assertEqual(d['owner_authorization_scope'], 'RUNTIME_AUTHORITY_GRANT_ONLY')
        self.assertTrue(d['owner_authorization_present'])
        self.assertTrue(d['owner_authorization_binding_complete'])
        self.assertTrue(d['runtime_authority_grant_authorized'])

    def test_authorization_exclusions_remain_false(self):
        d = json.loads(AUTH.read_text(encoding='utf-8-sig'))
        for key in (
            'promotion_eligible_authorized','release_or_tag_authorized','tag_creation_authorized',
            'release_creation_authorized','stable_declaration_authorized','artifact_rebuild_authorized',
            'artifact_substitution_authorized','product_bytes_mutation_authorized',
            'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
            'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
        ):
            self.assertFalse(d[key], key)

    def test_grant_is_runtime_authority_only(self):
        d = json.loads(GRANT.read_text(encoding='utf-8-sig'))
        self.assertTrue(d['runtime_authority_candidate'])
        self.assertTrue(d['owner_authorization_present'])
        self.assertTrue(d['owner_authorization_binding_complete'])
        self.assertEqual(d['owner_authorization_scope'], 'RUNTIME_AUTHORITY_GRANT_ONLY')
        self.assertEqual(d['grant_state'], 'RUNTIME_AUTHORITY_GRANTED')
        self.assertTrue(d['runtime_authority'])
        for key in (
            'promotion_eligible','release_or_tag_authorized','tag_created','release_created',
            'stable_declared','artifact_rebuilt','artifact_substituted','runtime_mutation',
            'product_bytes_mutated','runtime_bytes_mutated','private_runtime_payload_published'
        ):
            self.assertFalse(d[key], key)
        self.assertEqual(d['next_transaction'], 'SEPARATE_EXPLICIT_OWNER_AUTHORIZED_RELEASE_PROMOTION')


if __name__ == '__main__':
    unittest.main(verbosity=2)
