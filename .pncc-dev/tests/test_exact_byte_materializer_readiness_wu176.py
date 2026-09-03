#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/evaluate_exact_byte_materializer_readiness_wu176.py"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-exact-byte-branch-materializer-readiness.json"

spec = importlib.util.spec_from_file_location("wu176", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)

GOOD = {
    "repository": "kmephis-ai/VPS-Control-PNCC",
    "base_sha": "1" * 40,
    "branch": "agent/PIPE-WU-175-v702-activation-wu172-fix",
    "path": "src/windows-v7/VPS-Control-v7.ps1",
    "content_b64_sha": "2" * 40,
    "decoded_bytes_sha": "3" * 40,
    "expected_git_blob_sha": "3" * 40,
    "force_ref_update": False,
    "immutable_readback": True,
    "owner_authorization": True,
}


class ReadinessTests(unittest.TestCase):
    def test_good_plan_is_only_ready_for_separate_authorized_execution(self):
        self.assertEqual(mod.evaluate(GOOD)["decision"], "READY_FOR_SEPARATE_OWNER_AUTHORIZED_EXECUTION")

    def test_owner_authorization_required(self):
        p = deepcopy(GOOD); p["owner_authorization"] = False
        self.assertEqual(mod.evaluate(p)["reason"], "OWNER_AUTHORIZATION_REQUIRED")

    def test_exact_base_required(self):
        p = deepcopy(GOOD); p["base_sha"] = "main"
        self.assertEqual(mod.evaluate(p)["reason"], "BASE_SHA_INVALID")

    def test_main_and_unbounded_branch_forbidden(self):
        for branch in ("main", "feature/x"):
            p = deepcopy(GOOD); p["branch"] = branch
            self.assertEqual(mod.evaluate(p)["reason"], "BOUNDED_BRANCH_REQUIRED")

    def test_force_ref_forbidden(self):
        p = deepcopy(GOOD); p["force_ref_update"] = True
        self.assertEqual(mod.evaluate(p)["reason"], "FORCE_REF_FORBIDDEN")

    def test_immutable_readback_required(self):
        p = deepcopy(GOOD); p["immutable_readback"] = False
        self.assertEqual(mod.evaluate(p)["reason"], "IMMUTABLE_READBACK_REQUIRED")

    def test_exact_byte_blob_identity_required(self):
        p = deepcopy(GOOD); p["decoded_bytes_sha"] = "4" * 40
        self.assertEqual(mod.evaluate(p)["reason"], "EXACT_BYTE_GIT_BLOB_IDENTITY_MISMATCH")

    def test_path_escape_forbidden(self):
        p = deepcopy(GOOD); p["path"] = "../src/windows-v7/VPS-Control-v7.ps1"
        self.assertEqual(mod.evaluate(p)["reason"], "PATH_INVALID")

    def test_schema_is_closed(self):
        p = deepcopy(GOOD); p["extra"] = True
        self.assertEqual(mod.evaluate(p)["reason"], "PLAN_SCHEMA_MISMATCH")

    def test_readiness_contract_grants_no_execution_authority(self):
        c = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(c["authority_state"], "READINESS_ONLY")
        self.assertFalse(c["execution_authorized"])
        self.assertTrue(c["required_future_owner_authorization"])
        self.assertFalse(c["self_hosted_runner_allowed"])
        self.assertFalse(c["target"]["main_write_allowed"])
        self.assertFalse(c["target"]["force_ref_update_allowed"])
        self.assertEqual(c["readiness_workflow_permissions"], {"contents": "read"})
        for key, value in c["scope"].items():
            if key.endswith("_allowed"):
                self.assertFalse(value, key)


if __name__ == "__main__":
    unittest.main()
