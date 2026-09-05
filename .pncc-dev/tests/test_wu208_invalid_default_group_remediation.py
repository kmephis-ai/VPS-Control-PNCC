#!/usr/bin/env python3
import json, pathlib, subprocess, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = '66772cee01d60489730039b0da8ad76bb290d4f2'
PRE_BLOB = 'b744a7446e86b34b4be1df01349e7c033da81644'
POST_BLOB = '8958839f25cc2ca82a07f90df80fe0d23b2fbb22'
ISS = ROOT / 'installer/windows/VPS-Control-PNCC.iss'
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu208-invalid-default-group-remediation.json'
OLD = 'DefaultGroupName=VPS Control Center / PNCC'
NEW = 'DefaultGroupName=VPS Control Center - PNCC'
def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
class WU208Tests(unittest.TestCase):
    def test_exact_one_line_remediation(self):
        old = subprocess.check_output(['git','show',f'{BASE}:installer/windows/VPS-Control-PNCC.iss'], cwd=ROOT, text=True)
        cur = ISS.read_text(encoding='utf-8')
        self.assertEqual(git('rev-parse', f'{BASE}:installer/windows/VPS-Control-PNCC.iss'), PRE_BLOB)
        self.assertEqual(git('hash-object','installer/windows/VPS-Control-PNCC.iss'), POST_BLOB)
        self.assertEqual(old.count(OLD),1); self.assertEqual(cur.count(NEW),1)
        self.assertNotIn(OLD, cur)
        self.assertEqual(cur.replace(NEW, OLD), old)
    def test_default_group_is_filesystem_valid_leaf(self):
        line = next(x for x in ISS.read_text(encoding='utf-8').splitlines() if x.startswith('DefaultGroupName='))
        value = line.split('=',1)[1]
        for ch in '<>:"/|?*': self.assertNotIn(ch, value)
        self.assertEqual(value, value.rstrip(' .'))
        self.assertTrue(value.strip())
    def test_display_name_and_runtime_contract_unchanged(self):
        t = ISS.read_text(encoding='utf-8')
        self.assertIn('AppName=VPS Control Center / PNCC', t)
        self.assertIn('DefaultDirName={localappdata}\\Programs\\VPS-Control-PNCC', t)
        self.assertIn('Source: "..\\..\\src\\windows-v7\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs notimestamp', t)
    def test_contract_is_bounded(self):
        c=json.loads(CONTRACT.read_text(encoding='utf-8'))
        self.assertEqual(c['work_unit_id'],'PIPE-WU-208')
        self.assertEqual(c['installer_definition']['post_remediation_git_blob_sha'],POST_BLOB)
        self.assertEqual(c['authority']['allowed_product_runtime_paths'],['installer/windows/VPS-Control-PNCC.iss'])
        for k in ['other_product_runtime_mutation','release','tag','stable_transition','self_hosted_runner','port_1080_lifecycle','port_1081_lifecycle','v6_3_1_mutation','ruleset_or_security_weakening','force_or_bypass']:
            self.assertFalse(c['authority'][k], k)
if __name__ == '__main__': unittest.main(verbosity=2)
