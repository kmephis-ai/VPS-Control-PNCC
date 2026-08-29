#!/usr/bin/env python3
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECEIPT = ROOT / '.pncc-dev/attestations/runtime-qualification-v7.0.1.json'
DECISION = ROOT / '.pncc-dev/attestations/stable-runtime-authority-decision-v7.0.1.json'
RECEIPT_VALIDATOR = ROOT / '.pncc-dev/scripts/validate_runtime_qualification_v701_receipt.py'
DECISION_VALIDATOR = ROOT / '.pncc-dev/scripts/evaluate_stable_runtime_authority_decision_v701.py'
HISTORICAL_RECEIPT_VALIDATOR = ROOT / '.pncc-dev/scripts/validate_runtime_qualification_receipt.py'

class V701RuntimeTruthReceiptTests(unittest.TestCase):
    def run_script(self, path):
        p = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + '\n' + p.stderr)
        return p.stdout

    def test_v701_receipt_validator_passes(self):
        out = self.run_script(RECEIPT_VALIDATOR)
        self.assertIn('V701_RUNTIME_RECEIPT_STATE=ADMITTED', out)
        self.assertIn('RUNTIME_AUTHORITY=false', out)

    def test_v701_decision_validator_passes(self):
        out = self.run_script(DECISION_VALIDATOR)
        self.assertIn('ELIGIBLE_FOR_OWNER_RUNTIME_AUTHORITY_DECISION', out)
        self.assertIn('PROMOTION_ELIGIBLE=false', out)

    def test_historical_receipt_admission_still_passes(self):
        out = self.run_script(HISTORICAL_RECEIPT_VALIDATOR)
        self.assertIn('RUNTIME_RECEIPT_STATE=ADMITTED', out)

    def test_receipt_is_exact_and_sanitized(self):
        raw = RECEIPT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '14bd850d8465f1e5de040360a7ee040d9b1224175705c2623c83f10340514456')
        text = raw.decode('utf-8-sig')
        for pattern in (
            r'(?i)yandexdisk|dropbox|localappdata|desktop-|putty_portable\.exe',
            r'(?i)\b[a-z]:\\',
            r'(?<![0-9a-f])(?:\d{1,3}\.){3}\d{1,3}(?![0-9a-f])',
        ):
            self.assertIsNone(re.search(pattern, text), pattern)

    def test_authority_boundary_remains_default_deny(self):
        receipt = json.loads(RECEIPT.read_text(encoding='utf-8-sig'))
        decision = json.loads(DECISION.read_text(encoding='utf-8-sig'))
        self.assertTrue(receipt['runtime_authority_candidate'])
        self.assertFalse(receipt['repository_runtime_authority'])
        self.assertFalse(receipt['promotion_eligible'])
        self.assertFalse(receipt['release_or_tag_authorized'])
        self.assertTrue(decision['runtime_authority_candidate'])
        for key in ('runtime_authority','promotion_eligible','release_or_tag_authorized','tag_created','release_created','stable_declared'):
            self.assertFalse(decision[key])

if __name__ == '__main__':
    unittest.main(verbosity=2)
