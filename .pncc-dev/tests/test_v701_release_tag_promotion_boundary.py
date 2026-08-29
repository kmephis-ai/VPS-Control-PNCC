#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMOTION = ROOT / '.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
VALIDATOR = ROOT / '.pncc-dev/scripts/evaluate_stable_release_tag_promotion_v701.py'
HISTORICAL = ROOT / '.pncc-dev/scripts/evaluate_stable_release_tag_promotion.py'
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'


class V701ReleaseTagPromotionBoundaryTests(unittest.TestCase):
    def run_script(self, path):
        p = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + '\n' + p.stderr)
        return p.stdout

    def test_v701_waiting_release_boundary_passes(self):
        out = self.run_script(VALIDATOR)
        self.assertIn('WAITING_OWNER_RELEASE_AUTHORIZATION', out)
        self.assertIn('RUNTIME_AUTHORITY=true', out)
        self.assertIn('PROMOTION_ELIGIBLE=false', out)
        self.assertIn('RELEASE_OR_TAG_AUTHORIZED=false', out)

    def test_historical_v700_promoted_state_still_passes(self):
        out = self.run_script(HISTORICAL)
        self.assertIn('STABLE_RELEASE_TAG_PROMOTION=PROMOTED', out)
        self.assertIn('TAG_CREATED=true', out)
        self.assertIn('RELEASE_CREATED=true', out)

    def test_v701_preparation_is_default_deny(self):
        d = json.loads(PROMOTION.read_text(encoding='utf-8-sig'))
        self.assertTrue(d['runtime_authority'])
        self.assertFalse(d['owner_release_authorization_present'])
        self.assertFalse(d['owner_release_authorization_binding_complete'])
        self.assertEqual(d['promotion_state'], 'WAITING_OWNER_RELEASE_AUTHORIZATION')
        for key in (
            'promotion_eligible','release_or_tag_authorized','tag_created','release_created',
            'release_asset_verified','stable_declared','artifact_rebuilt','artifact_substituted',
            'runtime_mutation','product_bytes_mutated','runtime_bytes_mutated',
            'private_runtime_payload_published'
        ):
            self.assertFalse(d[key], key)
        self.assertIsNone(d['release_asset_server_digest'])
        self.assertIsNone(d['target_tag_commit'])

    def test_runtime_authority_is_bound_without_release_authority_transfer(self):
        promotion = json.loads(PROMOTION.read_text(encoding='utf-8-sig'))
        grant = json.loads(GRANT.read_text(encoding='utf-8-sig'))
        self.assertEqual(grant['grant_state'], 'RUNTIME_AUTHORITY_GRANTED')
        self.assertTrue(grant['runtime_authority'])
        self.assertFalse(grant['promotion_eligible'])
        self.assertFalse(grant['release_or_tag_authorized'])
        self.assertEqual(promotion['runtime_authority_grant_contract_id'], grant['contract_id'])
        self.assertEqual(promotion['stable_artifact_sha256'], grant['stable_artifact_sha256'])
        self.assertEqual(promotion['request_id'], grant['request_id'])
        self.assertEqual(promotion['candidate_id'], grant['candidate_id'])

    def test_future_publication_namespace_is_exact_and_non_overwriting(self):
        d = json.loads(PROMOTION.read_text(encoding='utf-8-sig'))
        self.assertEqual(d['target_tag'], 'v7.0.1')
        self.assertEqual(d['target_release_name'], 'VPS Control PNCC v7.0.1')
        self.assertEqual(d['target_tag_commit_policy'], 'PREPARATION_MERGE_SHA_ONLY')
        self.assertTrue(d['target_tag_observed_absent_at_preparation'])
        self.assertTrue(d['target_release_observed_absent_at_preparation'])
        self.assertTrue(d['overwrite_existing_tag_forbidden'])
        self.assertTrue(d['overwrite_existing_release_forbidden'])
        self.assertEqual(d['owner_release_authorization_scope'], 'RELEASE_TAG_STABLE_PROMOTION_ONLY')
        self.assertEqual(
            d['next_transaction'],
            'EXPLICIT_OWNER_RELEASE_AUTHORIZATION_BOUND_TO_PREPARATION_MERGE_REQUIRED'
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
