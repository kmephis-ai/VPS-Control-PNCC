import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / '.pncc-dev/contracts/wave6-wu137-provider-scheduler-degradation-remediation-proposal-wu142.json'
WU137_WORKFLOW = ROOT / '.github/workflows/wave6-hbe-periodic-health-drift-wu137.yml'

EXPECTED_ANCHORS = {
    '.github/workflows/wave6-hbe-periodic-health-drift-wu137.yml': '524ff581fb1c68d25a9c4d3b3ed56cd995fa82f2',
    '.pncc-dev/contracts/wave6-hbe-periodic-health-drift-activation-wu137.json': '37e08c46e021e04f1be6b799009b6f24111c1ac3',
    '.pncc-dev/scripts/evaluate_wave6_hbe_periodic_health_drift_wu137.py': 'd478fdc13afcf81b30d59952a44cc2aad8d5d5fe',
    '.pncc-dev/tests/test_wave6_hbe_periodic_health_drift_wu137.py': 'd1e292178284663e4a5b6636d857c145aa31748e',
    '.pncc-dev/contracts/wave6-hbe-periodic-health-drift-authority-proposal-wu136.json': '7605105488aafad7400c26c13a5c8f5515d40a02',
    '.pncc-dev/contracts/wave6-wu137-provider-scheduler-delivery-qualification-wu141.json': '6414fac73150e8d4e9f004a7fa03fa19aed9c470',
}


def git_blob(path: str) -> str:
    return subprocess.check_output(
        ['git', 'hash-object', path], cwd=ROOT, text=True
    ).strip()


class WU142ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads(PROPOSAL.read_text(encoding='utf-8'))
        cls.workflow = WU137_WORKFLOW.read_text(encoding='utf-8')
        cls.workflow_lower = cls.workflow.lower()

    def test_identity_and_authority_are_exact_and_proposal_only(self):
        p = self.proposal
        self.assertEqual(p['schema_version'], 1)
        self.assertEqual(p['role'], 'WAVE6_WU137_PROVIDER_SCHEDULER_DEGRADATION_REMEDIATION_PROPOSAL')
        self.assertEqual(p['work_unit_id'], 'PIPE-WU-142')
        self.assertEqual(p['issue_number'], 329)
        self.assertEqual(p['authorized_base_sha'], 'f8576dab46d08d7610fab7651979046e9e3fe839')
        self.assertEqual(p['proposal_state'], 'OWNER_AUTHORIZED_PROPOSAL_ONLY')
        self.assertFalse(p['runtime_required'])
        self.assertFalse(p['activation_authority'])
        self.assertEqual(p['current_recommendation'], 'OBSERVE_ONLY_NO_CHANGE')
        self.assertTrue(p['classification']['separate_owner_authorization_required'])
        self.assertEqual(p['classification']['fallback_activation_state'], 'NO_FALLBACK_ACTIVATION_AUTHORIZED')

    def test_recovered_schedule_runs_are_exact_and_healthy(self):
        runs = self.proposal['provider_recovery_evidence']['recovered_schedule_runs']
        self.assertEqual([r['run_id'] for r in runs], [33448268711, 33460267213])
        self.assertEqual([r['job_id'] for r in runs], [99672132901, 99708757357])
        self.assertEqual([r['created_at'] for r in runs], ['2026-08-31T22:53:15Z', '2026-09-01T01:50:20Z'])
        for r in runs:
            self.assertEqual(r['event'], 'schedule')
            self.assertEqual(r['head_sha'], 'f8576dab46d08d7610fab7651979046e9e3fe839')
            self.assertEqual(r['conclusion'], 'success')
            self.assertEqual(r['health_outcome'], 'HEALTHY')
        classification = self.proposal['classification']
        self.assertEqual(classification['workflow_execution_health'], 'DELIVERY_HEALTHY_WHEN_DELIVERED')
        self.assertEqual(classification['provider_event_delivery_health'], 'INTERMITTENT_PROVIDER_SCHEDULER_DELIVERY')
        self.assertFalse(classification['repository_configuration_defect_proven'])
        self.assertFalse(classification['provider_scheduler_permanent_failure_proven'])

    def test_predecessor_and_wu137_anchors_are_byte_exact(self):
        self.assertEqual(self.proposal['immutable_anchor_blobs'], EXPECTED_ANCHORS)
        for path, expected in EXPECTED_ANCHORS.items():
            self.assertEqual(git_blob(path), expected, path)

    def test_wu137_schedule_and_read_only_semantics_are_unchanged(self):
        text = self.workflow
        low = self.workflow_lower
        self.assertIn("cron: '17 * * * *'", text)
        self.assertIn('periodic-health-drift:', text)
        self.assertIn("if: github.event_name == 'schedule'", text)
        self.assertIn('contents: read', text)
        self.assertIn('issues: read', text)
        self.assertIn('pull-requests: read', text)
        self.assertIn('actions: read', text)
        self.assertIn('checks: read', text)
        forbidden = [
            'workflow_' + 'dispatch:', 'repository_' + 'dispatch:',
            'contents:' + ' write', 'issues:' + ' write', 'pull-requests:' + ' write',
            'actions:' + ' write', 'checks:' + ' write', 'self-' + 'hosted',
        ]
        for token in forbidden:
            self.assertNotIn(token, low, token)

    def test_review_threshold_can_only_escalate_to_owner(self):
        policy = self.proposal['delivery_assessment_policy_proposal']
        self.assertEqual(policy['provider_truth_source'], 'GITHUB_ACTIONS_SCHEDULE_RUN_HISTORY_ONLY')
        self.assertEqual(policy['canonical_cadence_seconds'], 3600)
        self.assertEqual(policy['bounded_delivery_lag_minutes'], 45)
        self.assertEqual(policy['review_eligible_effect'], 'OWNER_ESCALATION_ONLY_NO_ACTIVATION')
        self.assertTrue(policy['fresh_provider_truth_required_for_every_decision'])
        self.assertFalse(policy['automatic_fallback_activation'])
        self.assertFalse(policy['automatic_trigger_or_permission_mutation'])
        states = policy['states']
        self.assertIn('RECOVERED_SINGLE', states)
        self.assertIn('RECOVERED_INTERMITTENT', states)
        self.assertIn('STABLE_DELIVERY_OBSERVED', states)
        self.assertIn('REMEDIATION_REVIEW_ELIGIBLE', states)

    def test_candidate_remediations_do_not_activate(self):
        rows = {x['id']: x for x in self.proposal['candidate_remediation_classes']}
        self.assertEqual(rows['OBSERVE_ONLY_NO_CHANGE']['activation_state'], 'CURRENT_RECOMMENDATION')
        self.assertEqual(rows['GITHUB_NATIVE_REDUNDANT_OBSERVER_SEPARATE_WORKFLOW']['activation_state'], 'PROPOSAL_ONLY_DISABLED')
        self.assertEqual(rows['EXTERNAL_SCHEDULER_OR_DISPATCH']['activation_state'], 'FORBIDDEN_IN_PIPE_WU_142')
        self.assertIn('SEPARATE_OWNER_AUTHORIZATION_REQUIRED', rows['GITHUB_NATIVE_REDUNDANT_OBSERVER_SEPARATE_WORKFLOW']['authority_delta'])
        self.assertIn('SEPARATE_OWNER_AUTHORIZATION_REQUIRED', rows['EXTERNAL_SCHEDULER_OR_DISPATCH']['authority_delta'])

    def test_forbidden_scope_is_fail_closed(self):
        forbidden = self.proposal['forbidden_mutations']
        self.assertTrue(forbidden)
        self.assertTrue(all(forbidden.values()))
        report = self.proposal['mutation_report']
        self.assertTrue(report)
        self.assertTrue(all(value is False for value in report.values()))
        self.assertEqual(
            self.proposal['next_boundary'],
            'PROPOSAL_ONLY_MERGE_THEN_SEPARATE_OWNER_DECISION_IF_ACTIVATION_IS_STILL_JUSTIFIED',
        )

    def test_provider_documentation_is_background_only(self):
        background = self.proposal['official_provider_semantics_background']
        self.assertEqual(background['source'], 'GitHub Actions documentation')
        self.assertEqual(
            background['decision_authority'],
            'BACKGROUND_ONLY_NOT_A_SUBSTITUTE_FOR_REPOSITORY_PROVIDER_TRUTH',
        )
        self.assertEqual(len(background['facts']), 2)


if __name__ == '__main__':
    unittest.main()
