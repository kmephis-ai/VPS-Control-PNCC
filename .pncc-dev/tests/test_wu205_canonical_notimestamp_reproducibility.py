#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "8149979a977ae3412d6742150c4f15886d66eb45"
PRE_BLOB = "d30a158aef3535a9066608495b45abcf41112926"
POST_BLOB = "b744a7446e86b34b4be1df01349e7c033da81644"
ISS = ROOT / "installer/windows/VPS-Control-PNCC.iss"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu205-canonical-notimestamp-reproducibility.json"
SCRIPT = ROOT / ".pncc-dev/scripts/wu205_canonical_notimestamp_reproducibility.ps1"
WORKFLOW = ROOT / ".github/workflows/wave6-wu205-canonical-notimestamp-reproducibility.yml"
EXPECTED_FILES_LINE = 'Source: "..\\..\\src\\windows-v7\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs notimestamp'
OLD_FILES_LINE = 'Source: "..\\..\\src\\windows-v7\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs'
EXPECTED_PATHS = sorted([
    ".github/workflows/wave6-wu205-canonical-notimestamp-reproducibility.yml",
    ".pncc-dev/contracts/wave6-wu205-canonical-notimestamp-reproducibility.json",
    ".pncc-dev/scripts/wu205_canonical_notimestamp_reproducibility.ps1",
    ".pncc-dev/tests/test_wu205_canonical_notimestamp_reproducibility.py",
    "installer/windows/VPS-Control-PNCC.iss",
])

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

class WU205Tests(unittest.TestCase):
    def test_contract_is_exact_and_least_authority(self):
        c = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(c["work_unit_id"], "PIPE-WU-205")
        self.assertEqual(c["source_main_sha"], BASE)
        self.assertEqual(c["installer_definition"]["pre_remediation_git_blob_sha"], PRE_BLOB)
        self.assertEqual(c["installer_definition"]["post_remediation_git_blob_sha"], POST_BLOB)
        self.assertEqual(c["installer_definition"]["required_files_line"], EXPECTED_FILES_LINE)
        self.assertEqual(c["qualification"]["builds"], ["canonical_a", "canonical_b"])
        self.assertTrue(c["authority"]["canonical_installer_definition_mutation"])
        for k in ["artifact_upload","artifact_publication","artifact_persistence","other_product_runtime_mutation","release","tag","stable_transition","self_hosted_runner","port_1080_lifecycle","port_1081_lifecycle","v6_3_1_mutation","ruleset_or_security_weakening","force_or_bypass"]:
            self.assertFalse(c["authority"][k], k)

    def test_canonical_iss_is_exact_single_semantic_remediation(self):
        current = ISS.read_text(encoding="utf-8")
        old = subprocess.check_output(["git", "show", f"{BASE}:installer/windows/VPS-Control-PNCC.iss"], cwd=ROOT, text=True)
        self.assertEqual(git("rev-parse", f"{BASE}:installer/windows/VPS-Control-PNCC.iss"), PRE_BLOB)
        self.assertEqual(git("hash-object", "installer/windows/VPS-Control-PNCC.iss"), POST_BLOB)
        self.assertEqual(current.count("notimestamp"), 1)
        self.assertEqual(current.count(EXPECTED_FILES_LINE), 1)
        self.assertEqual(old.count(OLD_FILES_LINE), 1)
        self.assertNotIn("notimestamp", old.lower())
        self.assertEqual(current.replace(EXPECTED_FILES_LINE, OLD_FILES_LINE), old)

    def test_executor_has_bom_pins_and_fail_closed_reproducibility(self):
        raw = SCRIPT.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8-sig")
        for needle in [POST_BLOB, "PNCC-WU205-REPRO-EXECUTE", "14304168", "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f", "CANONICAL_CANDIDATE_SHA256_MISMATCH", "CANONICAL_CANDIDATE_SIZE_MISMATCH", "PNCC_WU205_REPRO_RECEIPT=", "CANONICAL_NOTIMESTAMP_REPRODUCIBILITY_QUALIFIED"]:
            self.assertIn(needle, text)
        self.assertNotIn("upload-artifact", text)

    def test_workflow_is_pr_validation_then_exact_issue_execution_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for needle in ["pull_request:", "issues:", "github.event.issue.number == 460", "PNCC-WU205-REPRO-EXECUTE", "windows-2025", POST_BLOB, "persist-credentials: false"]:
            self.assertIn(needle, text)
        for forbidden in ["self" + "-hosted", "actions/" + "upload-artifact", "actions/" + "cache", "contents: write", "security-events: write"]:
            self.assertNotIn(forbidden, text)

    def test_branch_diff_is_exactly_five_paths(self):
        actual = sorted(x for x in git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if x)
        self.assertEqual(actual, EXPECTED_PATHS)

if __name__ == "__main__":
    unittest.main(verbosity=2)
