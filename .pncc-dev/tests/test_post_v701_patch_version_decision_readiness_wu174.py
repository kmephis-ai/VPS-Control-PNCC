import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / '.pncc-dev' / 'contracts' / 'post-v701-patch-version-decision-readiness-wu174.json'


class PostV701PatchVersionDecisionReadinessWU174Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding='utf-8'))

    def test_identity_and_recommendation_are_exact(self):
        c = self.contract
        self.assertEqual(c['schema_version'], 1)
        self.assertEqual(c['role'], 'PNCC_POST_V7_0_1_PATCH_VERSION_DECISION_READINESS')
        self.assertEqual(c['work_unit_id'], 'PIPE-WU-174')
        self.assertEqual(c['issue_number'], 397)
        self.assertEqual(c['authorized_base_sha'], '0681dbb5adac996ea0072460a30e4c00c87d5721')
        self.assertEqual(c['stable_version'], '7.0.1')
        self.assertEqual(c['lineage_class'], 'PATCH')
        self.assertEqual(c['recommended_next_version'], '7.0.2')
        self.assertEqual(c['decision_state'], 'READY_FOR_SEPARATE_OWNER_VERSION_ACTIVATION_DECISION')

    def test_readiness_does_not_activate_or_grant_mutation_authority(self):
        a = self.contract['activation']
        self.assertFalse(a['performed'])
        self.assertTrue(a['separate_explicit_owner_authorization_required'])
        for key, value in a.items():
            if key in ('performed', 'separate_explicit_owner_authorization_required'):
                continue
            self.assertFalse(value, key)

    def test_stable_and_network_invariants_remain_fail_closed(self):
        inv = self.contract['invariants']
        self.assertTrue(inv['stable_7_0_1_identity_immutable'])
        self.assertTrue(inv['reserve_manual_1080_lifecycle_immutable'])
        self.assertTrue(inv['primary_auto_1081_contract_preserved'])
        self.assertTrue(inv['v6_3_1_immutable'])
        self.assertTrue(inv['ci_verified_is_not_runtime_verified'])

    def test_future_activation_requires_fresh_governed_transaction(self):
        requirements = self.contract['future_activation_requirements']
        joined = '\n'.join(requirements).lower()
        for token in ('fresh exact main', 'fresh writer lease', 'explicit owner authorization', 'exact-head ci'):
            self.assertIn(token, joined)
        self.assertIn('7.0.2', joined)


if __name__ == '__main__':
    unittest.main()
