import importlib.util
import json
import pathlib
import unittest
from unittest import mock

P = pathlib.Path('.pncc-dev/scripts/wu180_exact_head_dispatch_bridge.py')
spec = importlib.util.spec_from_file_location('wu180', P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DispatchBridgeTests(unittest.TestCase):
    def request(self):
        return {
            'schema_version': 1,
            'action': 'DISPATCH',
            'work_unit': 'PIPE-WU-180',
            'target_branch': m.TARGET_BRANCH,
            'target_sha': 'a' * 40,
            'workflows': list(m.WORKFLOWS),
        }

    def marker(self, obj):
        return '<!-- PNCC-EXACT-HEAD-CI-DISPATCH-REQUEST ' + json.dumps(obj, separators=(',', ':')) + ' -->'

    def test_exact_request_parses(self):
        self.assertEqual(m.parse_request(self.marker(self.request()))['target_sha'], 'a' * 40)

    def test_closed_schema_rejects_extra_field(self):
        obj = self.request(); obj['force'] = False
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_main_rejected(self):
        obj = self.request(); obj['target_branch'] = 'main'
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_other_branch_rejected(self):
        obj = self.request(); obj['target_branch'] = 'agent/other'
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_invalid_sha_rejected(self):
        obj = self.request(); obj['target_sha'] = 'abc'
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_workflow_subset_rejected(self):
        obj = self.request(); obj['workflows'] = obj['workflows'][:-1]
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_workflow_reorder_rejected(self):
        obj = self.request(); obj['workflows'] = list(reversed(obj['workflows']))
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(obj))

    def test_duplicate_marker_rejected(self):
        marker = self.marker(self.request())
        with self.assertRaises(m.Blocked): m.parse_request(marker + '\n' + marker)

    def test_ref_path_is_read_endpoint(self):
        path = m.ref_path(m.TARGET_BRANCH)
        self.assertIn('/git/ref/heads/', path)
        self.assertNotIn('/git/refs/heads/', path)

    def test_dispatch_one_does_one_get_then_post(self):
        calls = []
        def fake_api(path, token, method='GET', payload=None):
            calls.append((path, method, payload))
            if method == 'GET':
                return {'object': {'sha': 'a' * 40}}
            return None
        with mock.patch.object(m, 'api', side_effect=fake_api):
            m.dispatch_one('t', m.WORKFLOWS[0], m.TARGET_BRANCH, 'a' * 40)
        self.assertEqual(calls[0][1], 'GET')
        self.assertEqual(calls[1][1], 'POST')
        self.assertEqual(calls[1][2], {'ref': m.TARGET_BRANCH})
        self.assertIn('/actions/workflows/', calls[1][0])
        self.assertTrue(calls[1][0].endswith('/dispatches'))

    def test_moved_ref_blocks_before_dispatch(self):
        with mock.patch.object(m, 'api', return_value={'object': {'sha': 'b' * 40}}) as api:
            with self.assertRaises(m.Blocked):
                m.dispatch_one('t', m.WORKFLOWS[0], m.TARGET_BRANCH, 'a' * 40)
        self.assertEqual(api.call_count, 1)

    def test_unknown_workflow_blocks_without_api(self):
        with mock.patch.object(m, 'api') as api:
            with self.assertRaises(m.Blocked):
                m.dispatch_one('t', 'evil.yml', m.TARGET_BRANCH, 'a' * 40)
        api.assert_not_called()

    def test_execute_dispatches_exact_allowlist_and_final_readback(self):
        req = self.request()
        dispatched = []
        with mock.patch.object(m, 'dispatch_one', side_effect=lambda token, workflow, branch, sha: dispatched.append(workflow)), \
             mock.patch.object(m, 'assert_exact_target') as readback:
            m.execute(req, 't')
        self.assertEqual(dispatched, list(m.WORKFLOWS))
        readback.assert_called_once_with('t', m.TARGET_BRANCH, 'a' * 40)

    def test_script_contains_no_repo_write_endpoints(self):
        source = P.read_text(encoding='utf-8')
        self.assertNotIn('/git/refs/heads/', source)
        self.assertNotIn('/contents/', source)
        self.assertNotIn('"PATCH"', source)
        self.assertNotIn("'PATCH'", source)
        self.assertNotIn('"PUT"', source)
        self.assertNotIn("'PUT'", source)

    def test_contract_constants_are_fixed(self):
        self.assertEqual(m.REPO, 'kmephis-ai/VPS-Control-PNCC')
        self.assertEqual(m.ISSUE, 410)
        self.assertEqual(m.WU, 'PIPE-WU-180')
        self.assertEqual(len(m.WORKFLOWS), 6)


if __name__ == '__main__':
    unittest.main()
