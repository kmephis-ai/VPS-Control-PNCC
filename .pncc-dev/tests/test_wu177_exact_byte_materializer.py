import importlib.util, json, pathlib, unittest

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
        self.assertNotIn('git_blob_sha(changes[MAIN_PATH]) != HISTORICAL_MAIN_BLOB',source)
        self.assertNotIn('MAIN_SCRIPT_BLOB_MISMATCH',source)

    def test_execute_remains_plan_pinned(self):
        source=P.read_text(encoding='utf-8')
        self.assertIn('PLAN_SHA_MISMATCH',source)
        self.assertIn('PATH_ALLOWLIST_MISMATCH',source)
        self.assertIn('EXECUTE_REQUIRES_UNMUTATED_EXACT_BASE',source)
        self.assertIn('"force":False',source)

if __name__ == '__main__': unittest.main()
