import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/evaluate_autonomous_merge_issue_close_eligibility.py'
POLICY = ROOT / '.pncc-dev/contracts/autonomous-merge-issue-close-eligibility-policy.json'
spec = importlib.util.spec_from_file_location('wu099_eval', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

MUTATION_AUTHORITY_FIELDS = [
    'autonomous_merge_authority',
    'autonomous_issue_close_authority',
    'direct_main_write_authority',
    'provider_state_write_authority',
    'lease_acquisition_authority',
    'heartbeat_authority',
    'release_authority',
    'runtime_action_authority',
    'product_runtime_mutation_authority',
    'adwf_binding_mutation_authority',
    'promotion_release_tag_authority',
    'ruleset_policy_mutation_authority',
    'private_evidence_publication_authority',
    'reserve_1080_lifecycle_mutation_authority',
    'primary_1081_lifecycle_mutation_authority',
]


def good_snapshot():
    return {
        'provider_truth_fresh': True,
        'selected_work_unit': True,
        'work_unit_active': True,
        'runtime_not_required': True,
        'current_main_matches_work_unit_base': True,
        'pr_base_matches_current_main': True,
        'pr_head_matches_selected_head': True,
        'pr_open': True,
        'pr_mergeable': True,
        'current_head_full_ci_success': True,
        'no_pending_checks': True,
        'bounded_execution_receipt_valid': True,
        'released_writer_lease_exact': True,
        'provider_state_release_head_exact': True,
        'registry_release_blob_exact': True,
        'provider_state_unchanged_since_release': True,
        'head_unchanged_since_ci': True,
        'no_protected_surface_violation': True,
        'explicit_merge_authority': True,
        'merge_completed': False,
        'actual_merge_sha_readback': False,
        'current_main_equals_actual_merge_sha': False,
        'exact_work_unit_issue': False,
        'explicit_issue_close_authority': False,
    }


class Wu099EligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding='utf-8'))

    def test_policy_remains_read_only_and_has_no_mutation_authority(self):
        self.assertEqual(self.policy['mode'], 'READ_ONLY_ADVISORY')
        self.assertTrue(self.policy['merge_requires_explicit_authority'])
        self.assertTrue(self.policy['close_requires_explicit_authority'])
        self.assertTrue(all(self.policy[k] is False for k in MUTATION_AUTHORITY_FIELDS))

    def test_exact_good_premerge_snapshot_is_merge_eligible(self):
        self.assertEqual(mod.evaluate(good_snapshot(), self.policy)['decision'], 'MERGE_ELIGIBLE')

    def test_missing_explicit_merge_authority_blocks(self):
        s = good_snapshot(); s['explicit_merge_authority'] = False
        r = mod.evaluate(s, self.policy)
        self.assertEqual(r['decision'], 'BLOCKED')
        self.assertIn('explicit_merge_authority must be true', r['reasons'])

    def test_stale_provider_truth_blocks(self):
        s = good_snapshot(); s['provider_truth_fresh'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_head_drift_after_ci_blocks(self):
        s = good_snapshot(); s['head_unchanged_since_ci'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_pending_checks_block(self):
        s = good_snapshot(); s['no_pending_checks'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_active_or_unreleased_lease_blocks(self):
        s = good_snapshot(); s['released_writer_lease_exact'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_provider_state_drift_after_release_blocks(self):
        s = good_snapshot(); s['provider_state_unchanged_since_release'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_protected_surface_violation_blocks(self):
        s = good_snapshot(); s['no_protected_surface_violation'] = False
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_postmerge_without_readback_blocks_close(self):
        s = good_snapshot(); s['merge_completed'] = True; s['explicit_issue_close_authority'] = True
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')

    def test_exact_postmerge_readback_is_close_eligible(self):
        s = good_snapshot()
        s.update({
            'merge_completed': True,
            'actual_merge_sha_readback': True,
            'current_main_equals_actual_merge_sha': True,
            'exact_work_unit_issue': True,
            'explicit_issue_close_authority': True,
        })
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'CLOSE_ELIGIBLE')

    def test_close_never_inferred_from_merge_alone(self):
        s = good_snapshot()
        s.update({
            'merge_completed': True,
            'actual_merge_sha_readback': True,
            'current_main_equals_actual_merge_sha': True,
            'exact_work_unit_issue': True,
            'explicit_issue_close_authority': False,
        })
        self.assertEqual(mod.evaluate(s, self.policy)['decision'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
