#!/usr/bin/env python3
import json, pathlib, subprocess, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
PROMOTION=ROOT/'.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json'
PUBLICATION=ROOT/'.pncc-dev/attestations/stable-release-tag-publication-v7.0.1.json'
AUTH=ROOT/'.pncc-dev/attestations/stable-release-tag-owner-authorization-v7.0.1.json'
VALIDATOR=ROOT/'.pncc-dev/scripts/evaluate_stable_release_tag_promotion_v701.py'
HISTORICAL=ROOT/'.pncc-dev/scripts/evaluate_stable_release_tag_promotion.py'
class T(unittest.TestCase):
 def runv(self,p):
  r=subprocess.run([sys.executable,str(p)],cwd=ROOT,text=True,capture_output=True);self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr);return r.stdout
 def test_v701_promoted(self):
  o=self.runv(VALIDATOR);self.assertIn('V701_RELEASE_TAG_PROMOTION=PROMOTED',o);self.assertIn('STABLE_DECLARED=true',o);self.assertIn('RELEASE_ASSET_VERIFIED=true',o)
 def test_v700_still_promoted(self):
  self.assertIn('STABLE_RELEASE_TAG_PROMOTION=PROMOTED',self.runv(HISTORICAL))
 def test_publication_receipt_exact(self):
  r=json.loads(PUBLICATION.read_text(encoding='utf-8-sig'));self.assertEqual(r['release_id'],379032537);self.assertEqual(r['release_asset_id'],535416506);self.assertEqual(r['target_tag_commit'],'41e8c9c8bed2cc37423c33750d0748c49ff941b7');self.assertEqual(r['release_asset_server_digest'],'sha256:22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72');self.assertEqual(r['independent_download_sha256'],'22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72');self.assertFalse(r['release_draft']);self.assertFalse(r['release_prerelease'])
 def test_stable_truth_exact(self):
  d=json.loads(PROMOTION.read_text(encoding='utf-8-sig'));self.assertEqual(d['promotion_state'],'PROMOTED');self.assertTrue(d['runtime_authority']);self.assertTrue(d['promotion_eligible']);self.assertTrue(d['release_or_tag_authorized']);self.assertTrue(d['tag_created']);self.assertTrue(d['release_created']);self.assertTrue(d['release_asset_verified']);self.assertTrue(d['stable_declared']);self.assertEqual(d['next_transaction'],'POST_STABLE_CLOSEOUT');self.assertFalse(d['artifact_rebuilt']);self.assertFalse(d['artifact_substituted']);self.assertFalse(d['runtime_mutation']);self.assertFalse(d['private_runtime_payload_published'])
 def test_authorization_remains_bound(self):
  a=json.loads(AUTH.read_text(encoding='utf-8-sig'));self.assertEqual(a['authorized_preparation_main'],'41e8c9c8bed2cc37423c33750d0748c49ff941b7');self.assertEqual(a['authorized_prepared_promotion_contract_blob_sha'],'f20891555e6db3a0b5bb57488bac5e8ccf36eb71');self.assertEqual(a['owner_release_authorization_scope'],'RELEASE_TAG_STABLE_PROMOTION_ONLY')
if __name__=='__main__':unittest.main(verbosity=2)
