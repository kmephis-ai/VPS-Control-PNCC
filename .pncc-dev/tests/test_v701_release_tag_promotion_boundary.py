#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMOTION = ROOT / '.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
AUTH = ROOT / '.pncc-dev/attestations/stable-release-tag-owner-authorization-v7.0.1.json'
VALIDATOR = ROOT / '.pncc-dev/scripts/evaluate_stable_release_tag_promotion_v701.py'
HISTORICAL = ROOT / '.pncc-dev/scripts/evaluate_stable_release_tag_promotion.py'
GRANT = ROOT / '.pncc-dev/attestations/stable-runtime-authority-owner-grant-v7.0.1.json'
REQUEST = ROOT / '.pncc-dev/requests/runtime-qualification-v7.0.1.json'


class V701ReleaseTagPromotionBoundaryTests(unittest.TestCase):
    def run_script(self, path):
        p = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + '\n' + p.stderr)
        return p.stdout

    def test_v701_authorized_pending_boundary_passes(self):
        out = self.run_script(VALIDATOR)
        self.assertIn('AUTHORIZED_PENDING_EXECUTION', out)
        self.assertIn('RUNTIME_AUTHORITY=true', out)
        self.assertIn('PROMOTION_ELIGIBLE=true', out)
        self.assertIn('RELEASE_OR_TAG_AUTHORIZED=true', out)
        self.assertIn('TAG_CREATED=false', out)
        self.assertIn('RELEASE_CREATED=false', out)
        self.assertIn('STABLE_DECLARED=false', out)

    def test_historical_v700_promoted_state_still_passes(self):
        out = self.run_script(HISTORICAL)
        self.assertIn('STABLE_RELEASE_TAG_PROMOTION=PROMOTED', out)
        self.assertIn('TAG_CREATED=true', out)
        self.assertIn('RELEASE_CREATED=true', out)

    def test_exact_owner_authorization_is_bound_to_preparation(self):
        a = json.loads(AUTH.read_text(encoding='utf-8-sig'))
        self.assertEqual(a['contract_id'], 'PNCC_STABLE_RELEASE_TAG_OWNER_AUTHORIZATION_V1')
        self.assertEqual(a['authorized_preparation_main'], '41e8c9c8bed2cc37423c33750d0748c49ff941b7')
        self.assertEqual(a['authorized_prepared_promotion_contract_blob_sha'], 'f20891555e6db3a0b5bb57488bac5e8ccf36eb71')
        self.assertEqual(a['owner_release_authorization_scope'], 'RELEASE_TAG_STABLE_PROMOTION_ONLY')
        self.assertTrue(a['owner_release_authorization_present'])
        self.assertTrue(a['owner_release_authorization_binding_complete'])
        for key in (
            'promotion_eligibility_authorized','tag_creation_authorized','release_creation_authorized',
            'release_asset_upload_authorized','release_asset_server_digest_verification_required',
            'stable_declaration_authorized','overwrite_existing_tag_forbidden','move_existing_tag_forbidden',
            'overwrite_existing_release_forbidden'
        ):
            self.assertTrue(a[key], key)
        for key in (
            'artifact_rebuild_authorized','artifact_substitution_authorized','product_bytes_mutation_authorized',
            'runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized',
            'reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized'
        ):
            self.assertFalse(a[key], key)

    def test_authorized_state_has_no_publication_side_effect_yet(self):
        d = json.loads(PROMOTION.read_text(encoding='utf-8-sig'))
        self.assertTrue(d['runtime_authority'])
        self.assertTrue(d['owner_release_authorization_present'])
        self.assertTrue(d['owner_release_authorization_binding_complete'])
        self.assertEqual(d['promotion_state'], 'AUTHORIZED_PENDING_EXECUTION')
        self.assertTrue(d['promotion_eligible'])
        self.assertTrue(d['release_or_tag_authorized'])
        self.assertEqual(d['target_tag_commit'], '41e8c9c8bed2cc37423c33750d0748c49ff941b7')
        for key in (
            'tag_created','release_created','release_asset_verified','stable_declared',
            'artifact_rebuilt','artifact_substituted','runtime_mutation','product_bytes_mutated',
            'runtime_bytes_mutated','private_runtime_payload_published'
        ):
            self.assertFalse(d[key], key)
        self.assertIsNone(d['release_asset_server_digest'])
        self.assertEqual(d['next_transaction'], 'CREATE_EXACT_TAG_AND_RELEASE_NO_OVERWRITE')

    def test_runtime_authority_grant_remains_independently_bounded(self):
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

    def test_provider_artifact_and_product_identity_are_exact(self):
        a = json.loads(AUTH.read_text(encoding='utf-8-sig'))
        r = json.loads(REQUEST.read_text(encoding='utf-8-sig'))
        c = r['candidate']
        self.assertEqual(a['provider_artifact_id'], 9711822972)
        self.assertEqual(a['provider_artifact_digest'], 'sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5')
        self.assertEqual(a['provider_build_run_id'], 33242642394)
        self.assertEqual(a['provider_artifact_id'], c['provider_artifact_id'])
        self.assertEqual(a['provider_artifact_digest'], 'sha256:' + c['provider_artifact_digest'])
        self.assertEqual(a['provider_build_run_id'], c['provider_build_run_id'])
        self.assertEqual(a['stable_artifact_filename'], c['artifact_filename'])
        self.assertEqual(a['stable_artifact_sha256'], c['artifact_sha256'])
        self.assertEqual(a['stable_artifact_size_bytes'], c['artifact_size_bytes'])

    def test_future_publication_namespace_is_exact_and_non_overwriting(self):
        d = json.loads(PROMOTION.read_text(encoding='utf-8-sig'))
        a = json.loads(AUTH.read_text(encoding='utf-8-sig'))
        self.assertEqual(d['target_tag'], 'v7.0.1')
        self.assertEqual(d['target_release_name'], 'VPS Control PNCC v7.0.1')
        self.assertEqual(d['target_tag_commit_policy'], 'PREPARATION_MERGE_SHA_ONLY')
        self.assertEqual(d['target_tag_commit'], a['target_tag_commit'])
        self.assertTrue(d['target_tag_observed_absent_at_preparation'])
        self.assertTrue(d['target_release_observed_absent_at_preparation'])
        self.assertTrue(d['overwrite_existing_tag_forbidden'])
        self.assertTrue(d['overwrite_existing_release_forbidden'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
