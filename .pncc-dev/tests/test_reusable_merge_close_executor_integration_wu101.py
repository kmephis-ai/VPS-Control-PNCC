from pathlib import Path
import copy
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / '.pncc-dev/scripts'
sys.path.insert(0, str(SCRIPTS))
import execute_reusable_merge_close as ex


class FakeRunner:
    def __init__(self, merge_sha='b' * 40, issue_number=244):
        self.calls = []
        self.merge_sha = merge_sha
        self.issue_number = issue_number

    def __call__(self, cmd, text=True, capture_output=True):
        self.calls.append(list(cmd))
        if '--method' in cmd and 'PUT' in cmd:
            payload = {'merged': True, 'sha': self.merge_sha}
        elif cmd[-1].endswith('/branches/main'):
            payload = {'commit': {'sha': self.merge_sha}}
        elif '--method' in cmd and 'PATCH' in cmd:
            payload = {'state': 'closed', 'number': self.issue_number}
        elif cmd[-1].endswith(f'/issues/{self.issue_number}'):
            payload = {'state': 'closed', 'number': self.issue_number}
        else:
            return subprocess.CompletedProcess(cmd, 1, '', 'unexpected command')
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), '')


def merge_snapshot():
    return {
        'requested_pr_number': 246,
        'selected_pr_number': 246,
        'requested_issue_number': 244,
        'selected_issue_number': 244,
        'selected_pr_head_sha': 'a' * 40,
        'current_main_branch': 'main',
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
        'merge_completed': False,
    }


class ExecutorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.contract = ex.load_json(ex.CONTRACT_PATH)
        self.grant = ex.load_json(ROOT / self.contract['authorized_grant_path'])
        self.receipt = ex.load_json(ROOT / self.contract['owner_authorization_receipt_path'])
        self.prep = ex.load_json(ROOT / self.contract['preparation_contract_path'])
        self.policy = ex.load_json(ROOT / self.contract['eligibility_policy_path'])

    def build(self, snapshot, **kwargs):
        return ex.build_plan(
            snapshot,
            contract=kwargs.get('contract', self.contract),
            grant=kwargs.get('grant', self.grant),
            receipt=kwargs.get('receipt', self.receipt),
            preparation=kwargs.get('preparation', self.prep),
            policy=kwargs.get('policy', self.policy),
        )

    def test_canonical_anchor_map_is_exact(self):
        self.assertEqual(ex.validate_anchor_map(self.contract), [])

    def test_merge_plan_derives_authority_only_from_grant(self):
        snap = merge_snapshot()
        snap['explicit_merge_authority'] = False
        snap['explicit_issue_close_authority'] = False
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'MERGE_ELIGIBLE')
        self.assertEqual(plan['action']['type'], 'PINNED_EXPECTED_HEAD_PR_MERGE')
        self.assertEqual(plan['action']['expected_head_sha'], 'a' * 40)

    def test_grant_drift_blocks_fail_closed(self):
        grant = copy.deepcopy(self.grant)
        grant['reusable_autonomous_merge_authority'] = False
        plan = self.build(merge_snapshot(), grant=grant)
        self.assertEqual(plan['decision'], 'BLOCKED')
        self.assertTrue(any('reusable_autonomous_merge_authority' in r for r in plan['reasons']))

    def test_anchor_drift_blocks_fail_closed(self):
        contract = copy.deepcopy(self.contract)
        contract['eligibility_policy_blob_sha'] = '0' * 40
        plan = self.build(merge_snapshot(), contract=contract)
        self.assertEqual(plan['decision'], 'BLOCKED')
        self.assertTrue(any('anchor drift' in r for r in plan['reasons']))

    def test_unrelated_pr_substitution_is_blocked(self):
        snap = merge_snapshot()
        snap['requested_pr_number'] = 999
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'BLOCKED')
        self.assertIn('requested PR is not exact selected PR', plan['reasons'])

    def test_unrelated_issue_substitution_is_blocked(self):
        snap = merge_snapshot()
        snap['requested_issue_number'] = 999
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'BLOCKED')
        self.assertIn('requested Issue is not exact selected Work Unit Issue', plan['reasons'])

    def test_pending_ci_blocks(self):
        snap = merge_snapshot()
        snap['no_pending_checks'] = False
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'BLOCKED')

    def test_provider_state_drift_blocks(self):
        snap = merge_snapshot()
        snap['provider_state_unchanged_since_release'] = False
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'BLOCKED')

    def test_protected_surface_violation_blocks(self):
        snap = merge_snapshot()
        snap['no_protected_surface_violation'] = False
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'BLOCKED')

    def test_close_plan_after_merge_readback(self):
        snap = merge_snapshot()
        snap.update({
            'merge_completed': True,
            'actual_merge_sha_readback': True,
            'current_main_equals_actual_merge_sha': True,
            'exact_work_unit_issue': True,
            'actual_merge_sha': 'b' * 40,
        })
        plan = self.build(snap)
        self.assertEqual(plan['decision'], 'CLOSE_ELIGIBLE')
        self.assertEqual(plan['action']['type'], 'EXACT_SELECTED_WORK_UNIT_ISSUE_CLOSE')
        self.assertEqual(plan['action']['issue_number'], 244)

    def test_execute_requires_exact_confirmation_token(self):
        plan = self.build(merge_snapshot())
        with self.assertRaises(RuntimeError):
            ex.execute_plan(plan, 'kmephis-ai/VPS-Control-PNCC', 'WRONG', runner=FakeRunner())

    def test_merge_execute_builds_only_pinned_endpoint_and_readback(self):
        plan = self.build(merge_snapshot())
        runner = FakeRunner()
        result = ex.execute_plan(plan, 'kmephis-ai/VPS-Control-PNCC', 'EXECUTE_REUSABLE_MERGE_CLOSE_ONLY', runner=runner)
        self.assertTrue(result['executed'])
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(runner.calls[0][:4], ['gh', 'api', '--method', 'PUT'])
        self.assertIn('repos/kmephis-ai/VPS-Control-PNCC/pulls/246/merge', runner.calls[0])
        self.assertIn('sha=' + 'a' * 40, runner.calls[0])
        self.assertEqual(runner.calls[1], ['gh', 'api', 'repos/kmephis-ai/VPS-Control-PNCC/branches/main'])

    def test_close_execute_targets_only_exact_selected_issue(self):
        snap = merge_snapshot()
        snap.update({
            'merge_completed': True,
            'actual_merge_sha_readback': True,
            'current_main_equals_actual_merge_sha': True,
            'exact_work_unit_issue': True,
            'actual_merge_sha': 'b' * 40,
        })
        plan = self.build(snap)
        runner = FakeRunner(issue_number=244)
        result = ex.execute_plan(plan, 'kmephis-ai/VPS-Control-PNCC', 'EXECUTE_REUSABLE_MERGE_CLOSE_ONLY', runner=runner)
        self.assertTrue(result['executed'])
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(runner.calls[0][:4], ['gh', 'api', '--method', 'PATCH'])
        self.assertIn('repos/kmephis-ai/VPS-Control-PNCC/issues/244', runner.calls[0])
        self.assertEqual(runner.calls[1], ['gh', 'api', 'repos/kmephis-ai/VPS-Control-PNCC/issues/244'])


if __name__ == '__main__':
    unittest.main()
