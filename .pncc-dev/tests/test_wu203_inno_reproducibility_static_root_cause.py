#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu203-inno-reproducibility-static-root-cause.json"
WORKFLOW = ROOT / ".github/workflows/wave6-wu203-inno-reproducibility-static-root-cause.yml"
CLASSIFICATION = "HIGH_CONFIDENCE_STATIC_CAUSE_CANDIDATE_NOT_EXECUTION_PROVEN"


class WU203StaticRootCauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_contract_identity_and_classification(self):
        c = self.contract
        self.assertEqual(c["schema_version"], 1)
        self.assertEqual(c["work_unit_id"], "PIPE-WU-203")
        self.assertEqual(c["source_main_sha"], "64e8a45d34022cee82a46f79e34fdb4e2b73a036")
        self.assertEqual(c["classification"], CLASSIFICATION)
        self.assertFalse(c["static_causal_chain"]["execution_proven"])

    def test_observed_wu199_wu200_drift_is_bound(self):
        drift = self.contract["observed_reproducibility_drift"]
        self.assertEqual(drift["wu199"]["size_bytes"], 2230935)
        self.assertEqual(drift["wu199"]["sha256"], "13ea7db85ce1c997f1bcc9566c615c1000eeaf33909a208ab6207f4e5ba22f06")
        self.assertEqual(drift["wu200"]["size_bytes"], 2230934)
        self.assertEqual(drift["wu200"]["sha256"], "b2a7cd7e00d5e8861255680c2b5e79f241d8721ac8636a2e6f5c542ed0f11851")
        self.assertFalse(drift["byte_identical"])

    def test_exact_compiler_and_definition_identity_are_bound(self):
        c = self.contract
        self.assertEqual(c["compiler_identity"]["repository"], "jrsoftware/issrc")
        self.assertEqual(c["compiler_identity"]["tag"], "is-7_1_0")
        self.assertEqual(c["compiler_identity"]["source_commit"], "1ae7bf81dc0d2013235dfe4bb0b6f4e4a0b6b25c")
        self.assertEqual(c["compiler_identity"]["asset_sha256"], "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f")
        self.assertEqual(c["canonical_installer_definition"]["git_blob_sha"], "d30a158aef3535a9066608495b45abcf41112926")

    def test_wu203_observed_definition_had_no_notimestamp_flag(self):
        observed = self.contract["canonical_installer_definition"]
        self.assertEqual(observed["files_flags"], ["ignoreversion", "recursesubdirs", "createallsubdirs"])
        self.assertNotIn("notimestamp", observed["files_flags"])
        self.assertFalse(observed["notimestamp_present"])

    def test_static_causal_chain_is_complete_but_not_overclaimed(self):
        chain = self.contract["static_causal_chain"]
        required = {
            "files_flag_notimestamp_is_recognized",
            "notimestamp_sets_NoTimeStamp_true",
            "NoTimeStamp_includes_floNoTimeStamp",
            "compiler_reads_source_GetFileTime",
            "floNoTimeStamp_clears_FL_TimeStamp",
            "without_floNoTimeStamp_source_timestamp_is_retained",
        }
        self.assertEqual(set(chain["facts"]), required)
        self.assertEqual(chain["confidence"], "HIGH_STATIC_CONFIDENCE")
        self.assertFalse(chain["execution_proven"])

    def test_future_ab_experiment_is_readiness_only(self):
        exp = self.contract["future_ab_experiment_readiness"]
        self.assertFalse(exp["authorized_now"])
        self.assertTrue(exp["required_owner_grant"])
        self.assertIn("notimestamp", exp["treatment"])
        self.assertIn("repeat_build_byte_identity", exp["required_observations"])

    def test_all_authority_is_false(self):
        authority = self.contract["authority"]
        self.assertTrue(authority)
        self.assertTrue(all(value is False for value in authority.values()))

    def test_bounded_three_path_mutation(self):
        expected = {
            ".pncc-dev/contracts/wave6-wu203-inno-reproducibility-static-root-cause.json",
            ".pncc-dev/tests/test_wu203_inno_reproducibility_static_root_cause.py",
            ".github/workflows/wave6-wu203-inno-reproducibility-static-root-cause.yml",
        }
        self.assertEqual(set(self.contract["allowed_mutations"]), expected)

    def test_workflow_has_read_only_permissions_and_no_execution_surface(self):
        wf = self.workflow
        self.assertRegex(wf, r"(?m)^permissions:\s*$")
        self.assertRegex(wf, r"(?m)^\s+contents:\s+read\s*$")
        forbidden = [
            "self" + "-hosted",
            "actions/" + "upload-" + "artifact@",
            "actions/" + "cache@",
            "Invoke-" + "WebRequest",
            "Start-" + "Process",
            "ISCC" + ".exe",
        ]
        for token in forbidden:
            self.assertNotIn(token, wf)
        self.assertNotRegex(wf, r"(?m)^\s+(contents|issues|pull-requests|security-events):\s+write\s*$")


if __name__ == "__main__":
    unittest.main()
