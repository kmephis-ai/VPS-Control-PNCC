from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/wu193_installer_definition_exact_write_authorization_contract.py"
SPEC = importlib.util.spec_from_file_location("wu193", SCRIPT)
assert SPEC and SPEC.loader
WU193 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WU193)

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
BASE = "1" * 40


def source_receipt():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-192",
        "source_transaction_work_unit": "PIPE-WU-191",
        "decision": "EXECUTION_AUTHORIZATION_READY_ONLY",
        "reasons": [],
        "proposal_sha256": A,
        "proposal_byte_count": 1234,
        "binding_request_sha256": B,
        "transaction_intent_sha256": C,
        "target_path": "installer/windows/VPS-Control-PNCC.iss",
        "execution_authorization_request_sha256": D,
        "exact_transaction_lineage_match": True,
        "target_metadata_safe": True,
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "binding_receipt_persisted": False,
        "write_authorized": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def contract():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-193",
        "source_execution_authorization_work_unit": "PIPE-WU-192",
        "repository": "kmephis-ai/VPS-Control-PNCC",
        "base_sha": BASE,
        "target_branch": "agent/PIPE-WU-194-installer-definition-identity-binding-write",
        "target_path": "installer/windows/VPS-Control-PNCC.iss",
        "proposal_sha256": A,
        "proposal_byte_count": 1234,
        "execution_authorization_request_sha256": D,
        "expected_prewrite_state": "ABSENT",
        "expected_prewrite_blob_sha": "",
        "force": False,
        "immutable_postwrite_blob_readback": True,
        "single_transaction": True,
        "consumed": False,
        "authorization_id": "owner-grant-placeholder-001",
        "owner_authorization_state": "NOT_GRANTED",
    }


class Wu193Tests(unittest.TestCase):
    def test_ready_contract_never_grants_authority(self):
        receipt = WU193.evaluate(source_receipt(), contract())
        self.assertEqual(receipt["decision"], "WRITE_AUTHORIZATION_CONTRACT_READY_ONLY")
        self.assertEqual(receipt["reasons"], [])
        self.assertTrue(receipt["exact_execution_lineage_match"])
        self.assertTrue(receipt["target_metadata_safe"])
        self.assertTrue(receipt["prewrite_expectation_valid"])
        self.assertEqual(receipt["owner_authorization_state"], "NOT_GRANTED")
        for key in (
            "verified", "durable_identity_bound", "proposal_materialized",
            "binding_receipt_persisted", "write_authorized",
            "compiler_execution_authorized", "build_authorized",
        ):
            self.assertFalse(receipt[key], key)

    def test_unknown_contract_field_fails_closed(self):
        value = contract()
        value["unexpected"] = True
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("INVALID_AUTHORIZATION_CONTRACT_KEYS", receipt["reasons"])

    def test_main_branch_is_forbidden(self):
        value = contract()
        value["target_branch"] = "main"
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("UNSAFE_TARGET_BRANCH", receipt["reasons"])

    def test_path_traversal_is_forbidden(self):
        value = contract()
        value["target_path"] = "installer/../escape.iss"
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("UNSAFE_TARGET_PATH", receipt["reasons"])

    def test_force_is_forbidden(self):
        value = contract()
        value["force"] = True
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("FORCE_NOT_ALLOWED", receipt["reasons"])

    def test_owner_grant_cannot_be_activated_here(self):
        value = contract()
        value["owner_authorization_state"] = "GRANTED"
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("OWNER_AUTHORIZATION_MUST_REMAIN_NOT_GRANTED", receipt["reasons"])
        self.assertFalse(receipt["write_authorized"])

    def test_execution_lineage_mismatch_fails(self):
        value = contract()
        value["execution_authorization_request_sha256"] = "e" * 64
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("EXECUTION_AUTHORIZATION_REQUEST_SHA256_MISMATCH", receipt["reasons"])

    def test_target_path_must_match_wu192(self):
        value = contract()
        value["target_path"] = "installer/windows/Other.iss"
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("TARGET_PATH_MISMATCH", receipt["reasons"])

    def test_absent_prewrite_requires_empty_blob(self):
        value = contract()
        value["expected_prewrite_blob_sha"] = "2" * 40
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertIn("INVALID_PREWRITE_EXPECTATION", receipt["reasons"])

    def test_exact_blob_prewrite_requires_sha40(self):
        value = contract()
        value["expected_prewrite_state"] = "EXACT_BLOB"
        value["expected_prewrite_blob_sha"] = "2" * 40
        receipt = WU193.evaluate(source_receipt(), value)
        self.assertEqual(receipt["decision"], "WRITE_AUTHORIZATION_CONTRACT_READY_ONLY")

    def test_source_authority_escalation_fails(self):
        source = source_receipt()
        source["write_authorized"] = True
        receipt = WU193.evaluate(source, contract())
        self.assertIn("SOURCE_RECEIPT_AUTHORITY_ESCALATION", receipt["reasons"])

    def test_cli_emits_valid_json(self):
        completed = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--source-receipt", json.dumps(source_receipt(), separators=(",", ":")),
                "--authorization-contract", json.dumps(contract(), separators=(",", ":")),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "WRITE_AUTHORIZATION_CONTRACT_READY_ONLY")
        self.assertFalse(payload["write_authorized"])


if __name__ == "__main__":
    unittest.main()
