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
        self.assertEqual(m.MAIN_BLOB,'44f7e6433881733f4aa5ca251e33bc3e2cd98988')

if __name__ == '__main__': unittest.main()
