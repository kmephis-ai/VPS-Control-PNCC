import importlib.util, json, pathlib, unittest
from unittest import mock

P = pathlib.Path('.pncc-dev/scripts/wu177_exact_byte_materializer.py')
spec = importlib.util.spec_from_file_location('m', P)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class MaterializerTests(unittest.TestCase):
    def marker(self, obj):
        return '<!-- PNCC-EXACT-BYTE-MATERIALIZER-REQUEST ' + json.dumps(obj,separators=(',',':')) + ' -->'

    def base(self, action='PLAN'):
        return {'schema_version':1,'action':action,'work_unit':'PIPE-WU-175','branch':'agent/PIPE-WU-175-v702-activation-wu172-fix','base_sha':'a'*40,'expected_head_sha':'a'*40}

    def test_git_blob_identity(self):
        self.assertEqual(m.git_blob_sha(b'test content\n'),'d670460b4b4aece5915caf5c68d12f560a9fe3e4')

    def test_exact_scope_parses(self):
        r=m.parse_request(self.marker(self.base()))
        self.assertEqual(r['action'],'PLAN')

    def test_repair_actions_parse(self):
        for action in ('REPAIR_PLAN','REPAIR_EXECUTE'):
            self.assertEqual(m.parse_request(self.marker(self.base(action)))['action'],action)

    def test_main_is_rejected(self):
        x=self.base(); x['branch']='main'
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(x))

    def test_wrong_wu_is_rejected(self):
        x=self.base(); x['work_unit']='PIPE-WU-999'
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(x))

    def test_unknown_field_is_rejected(self):
        x=self.base(); x['force']=True
        with self.assertRaises(m.Blocked): m.parse_request(self.marker(x))

    def test_duplicate_marker_is_rejected(self):
        body=self.marker(self.base())+'\n'+self.marker(self.base())
        with self.assertRaises(m.Blocked): m.parse_request(body)

    def test_execute_requires_exact_plan(self):
        req=self.base('EXECUTE'); req['plan_sha256']='0'*64; req['paths']=[]
        obj={'paths':[{'path':'src/windows-v7/a','git_blob_sha':'b'*40}]}
        with self.assertRaises(m.Blocked): m.verify_execute_request(req,obj,'1'*64)

    def test_execute_rejects_path_allowlist_drift(self):
        req=self.base('EXECUTE'); req['plan_sha256']='1'*64; req['paths']=[{'path':'src/windows-v7/b','git_blob_sha':'b'*40}]
        obj={'paths':[{'path':'src/windows-v7/a','git_blob_sha':'b'*40}]}
        with self.assertRaises(m.Blocked): m.verify_execute_request(req,obj,'1'*64)

    def test_exact_allowlist_accepts(self):
        req=self.base('EXECUTE'); req['plan_sha256']='1'*64; req['paths']=[{'path':'src/windows-v7/a','git_blob_sha':'b'*40}]
        obj={'paths':[{'path':'src/windows-v7/a','git_blob_sha':'b'*40}]}
        m.verify_execute_request(req,obj,'1'*64)

    def test_contract_anchors_are_fixed(self):
        self.assertEqual(m.ISSUE,399); self.assertEqual(m.WU,'PIPE-WU-175')
        self.assertEqual(m.WU172_BLOB,'6c4a8ddcaea7f4c651b6d4be74d925358d81f3c5')
        self.assertEqual(m.HISTORICAL_MAIN_BLOB,'44f7e6433881733f4aa5ca251e33bc3e2cd98988')

    def test_historical_main_blob_is_evidence_not_execution_gate(self):
        source=P.read_text(encoding='utf-8')
        self.assertIn('HISTORICAL_MAIN_BLOB',source)
        self.assertNotIn('MAIN_SCRIPT_BLOB_MISMATCH',source)

    def test_execute_remains_plan_pinned_and_nonforce(self):
        source=P.read_text(encoding='utf-8')
        self.assertIn('PLAN_SHA_MISMATCH',source)
        self.assertIn('PATH_ALLOWLIST_MISMATCH',source)
        self.assertIn('EXECUTE_REQUIRES_UNMUTATED_EXACT_BASE',source)
        self.assertIn('"force":False',source)

    def test_git_object_bytes_preserves_exact_crlf_bytes(self):
        exact=b'line1\r\nline2\r\n'
        with mock.patch.object(m,'run',return_value=exact) as r:
            self.assertEqual(m.git_object_bytes('a'*40,'src/windows-v7/a.ps1'),exact)
            r.assert_called_once_with('git','show','a'*40+':src/windows-v7/a.ps1')

    def test_materializer_does_not_use_worktree_read_bytes(self):
        source=P.read_text(encoding='utf-8')
        self.assertNotIn('.read_bytes()',source)
        self.assertIn('git_object_bytes(base, p)',source)
        with mock.patch.object(m,'run',return_value=b'src/windows-v7/a.ps1\nsrc/windows-v7/VPS-Control-v7-SHA256.txt\n') as r:
            paths=m.tracked_source_paths('a'*40)
            self.assertIn('src/windows-v7/a.ps1',paths)
            r.assert_called_once_with('git','ls-tree','-r','--name-only','a'*40,'--',m.ROOT)

    def test_optional_git_object_is_only_for_new_provenance(self):
        with mock.patch.object(m,'git_object_bytes',side_effect=m.Blocked('COMMAND_FAILED:git show x')):
            self.assertIsNone(m.git_object_bytes_optional('a'*40,m.PROVENANCE))
            with self.assertRaises(m.Blocked): m.git_object_bytes_optional('a'*40,'src/windows-v7/a.ps1')

    def test_read_ref_retries_get_only_until_success(self):
        values=iter(['a'*40,'a'*40,'b'*40]); calls=[]
        def fake_api(path,token,method='GET',payload=None):
            calls.append((method,payload)); return {'object':{'sha':next(values)}}
        with mock.patch.object(m,'api',side_effect=fake_api), mock.patch.object(m.time,'sleep') as sl:
            self.assertEqual(m.read_ref_until('t','b'*40,attempts=3,delay=0.01),'b'*40)
            self.assertTrue(all(method=='GET' and payload is None for method,payload in calls))
            self.assertEqual(sl.call_count,2)

    def test_read_ref_fails_after_bounded_stale_reads(self):
        with mock.patch.object(m,'api',return_value={'object':{'sha':'a'*40}}), mock.patch.object(m.time,'sleep'):
            with self.assertRaisesRegex(m.Blocked,'POSTWRITE_REF_MISMATCH'):
                m.read_ref_until('t','b'*40,attempts=2,delay=0)

    def test_repair_plan_is_delta_against_exact_materialized_head(self):
        desired={'src/windows-v7/a':b'good-a','.pncc-dev/provenance/canonical-source-v7.0.2-patch.json':b'good-p'}
        current={'src/windows-v7/a':b'good-a','.pncc-dev/provenance/canonical-source-v7.0.2-patch.json':b'bad-p'}
        with mock.patch.object(m,'assemble',return_value=desired), mock.patch.object(m,'git_object_bytes',side_effect=lambda sha,p: current[p]):
            obj,ph,delta=m.repair_plan('a'*40,'b'*40)
        self.assertEqual(obj['mode'],'REPAIR_DELTA')
        self.assertEqual(set(delta),{'.pncc-dev/provenance/canonical-source-v7.0.2-patch.json'})
        self.assertEqual(len(ph),64)

if __name__ == '__main__': unittest.main()
