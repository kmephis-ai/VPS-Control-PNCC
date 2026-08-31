#!/usr/bin/env python3
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/wave5-autonomous-continuation-control-loop.yml'
BASELINE_BLOB = '07b113b29d2e285a2b33f0fc6fdb84386e573929'

REGRESSION_STEP = """      - name: Run WU139 live no-frontier harness regression
        run: python3 -m unittest discover -s .pncc-dev/tests -p 'test_autonomous_continuation_control_loop_live_harness_wu139.py' -v

"""

NO_FRONTIER_SNAPSHOT_INSERT = """          if cont.get('decision')=='NO_FRONTIER':
              if cont.get('selected') is not None: raise SystemExit('NO_FRONTIER_SELECTED_WORK_UNIT_PRESENT')
              main_ref=get(f'https://api.github.com/repos/{repo}/git/ref/heads/main'); main=((main_ref.get('object') or {}).get('sha'))
              snap={'schema_version':1,'role':'AUTONOMOUS_CONTINUATION_CONTROL_LOOP_SNAPSHOT','repository':repo,'default_branch':'main','provider_truth_fresh':True,
                    'current_main_sha':main,'continuation_decision':cont,'execution_state':None,'ci_decision':None}
              with open(out,'w',encoding='utf-8') as f: json.dump(snap,f,sort_keys=True,indent=2); f.write('\\n')
              raise SystemExit(0)
"""

NO_FRONTIER_RESULT_INSERT = """          if loop.get('decision')=='STOP_NO_FRONTIER':
              if loop.get('delegated_authority')!='NONE_TERMINAL': raise SystemExit('NO_FRONTIER_DELEGATION_DRIFT')
              if loop.get('selected_work_unit_id') is not None or loop.get('selected_issue_number') is not None: raise SystemExit('NO_FRONTIER_SYNTHETIC_SELECTION')
              if loop.get('execution_state') is not None or loop.get('ci_decision') is not None: raise SystemExit('NO_FRONTIER_SYNTHETIC_EXECUTION_STATE')
              for field in ('provider_mutation_performed','issue_mutation_performed','branch_mutation_performed','pull_request_mutation_performed',
                            'writer_lease_mutation_performed','workflow_rerun_performed','merge_performed','runtime_action_performed','product_runtime_mutation_performed'):
                  if loop.get(field) is not False: raise SystemExit('NO_FRONTIER_MUTATION_REPORTED:'+field)
              print('LIVE_CONTROL_LOOP_DECISION='+loop['decision'])
              raise SystemExit(0)
"""

PINNED_FILES = {
    '.pncc-dev/contracts/autonomous-continuation-control-loop-policy.json': '822bcd1833ff4843b6bd176337b3ef3b742275de',
    '.pncc-dev/scripts/evaluate_autonomous_continuation_control_loop.py': '1f794892cfec466505a1a6c38b271492f9759127',
    '.pncc-dev/tests/test_autonomous_continuation_control_loop_wu108.py': '625db459bec89e89a23c7cf2c592d701d689ecb3',
    '.pncc-dev/contracts/provider-truth-continuation-policy.json': '4c6fe2895d41ed9282e9209223a5dd27b209a2fc',
    '.pncc-dev/scripts/evaluate_provider_truth_continuation.py': '33fdd78096ae09c9706e0802a94b310ba5fa4bd2',
}


def git_blob_sha_bytes(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode('utf-8') + data).hexdigest()


def git_blob_sha_text(text: str) -> str:
    return git_blob_sha_bytes(text.encode('utf-8'))


class LiveNoFrontierHarnessWU139Tests(unittest.TestCase):
    def workflow(self) -> str:
        return WORKFLOW.read_text(encoding='utf-8')

    def test_pre_wu139_workflow_reconstructs_exact_baseline_blob(self):
        text = self.workflow()
        for insertion in (REGRESSION_STEP, NO_FRONTIER_SNAPSHOT_INSERT, NO_FRONTIER_RESULT_INSERT):
            self.assertEqual(text.count(insertion), 1)
            text = text.replace(insertion, '', 1)
        self.assertEqual(git_blob_sha_text(text), BASELINE_BLOB)

    def test_no_frontier_path_has_no_synthetic_work_unit_issue_or_lease(self):
        text = self.workflow()
        self.assertIn("if cont.get('decision')=='NO_FRONTIER':", text)
        self.assertIn("'execution_state':None,'ci_decision':None", text)
        self.assertIn("if loop.get('decision')=='STOP_NO_FRONTIER':", text)
        self.assertIn("loop.get('selected_work_unit_id') is not None", text)
        self.assertIn("loop.get('selected_issue_number') is not None", text)
        self.assertIn("loop.get('execution_state') is not None", text)
        self.assertIn("loop.get('delegated_authority')!='NONE_TERMINAL'", text)
        no_frontier = text.index("if cont.get('decision')=='NO_FRONTIER':")
        hard_selected = text.index("raise SystemExit('LIVE_SELECTED_WORK_UNIT_REQUIRED')")
        self.assertLess(no_frontier, hard_selected)

    def test_wu108_evaluator_provider_truth_and_policy_anchors_are_unchanged(self):
        for rel, expected in PINNED_FILES.items():
            with self.subTest(path=rel):
                self.assertEqual(git_blob_sha_bytes((ROOT / rel).read_bytes()), expected)

    def test_workflow_permissions_and_mutation_boundary_remain_read_only(self):
        text = self.workflow().lower()
        permissions = "permissions:\n  actions: read\n  contents: read\n  issues: read\n  pull-requests: read\n"
        self.assertIn(permissions, text)
        forbidden = [
            'contents: write', 'actions: write', 'issues: write', 'pull-requests: write',
            'git push', 'gh pr merge', 'gh issue close', '--method post', '--method patch',
            '--method put', '--method delete', 'self-hosted',
        ]
        for token in forbidden:
            self.assertNotIn(token, text, token)


if __name__ == '__main__':
    unittest.main()
