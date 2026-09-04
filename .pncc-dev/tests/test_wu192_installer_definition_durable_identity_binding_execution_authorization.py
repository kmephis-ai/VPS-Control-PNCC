import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "wu192_installer_definition_durable_identity_binding_execution_authorization.py"
spec = importlib.util.spec_from_file_location("wu192", SCRIPT)
wu192 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wu192)

A = "a" * 64
B = "b" * 64
C = "c" * 64


def source():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-191",
        "source_binding_request_work_unit": "PIPE-WU-190",
        "decision": "TRANSACTION_READY_ONLY",
        "reasons": [],
        "proposal_sha256": A,
        "proposal_byte_count": 1234,
        "binding_request_sha256": B,
        "transaction_intent_sha256": C,
        "exact_request_lineage_match": True,
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "binding_receipt_persisted": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def request():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-192",
        "source_transaction_work_unit": "PIPE-WU-191",
        "proposal_sha256": A,
        "proposal_byte_count": 1234,
        "binding_request_sha256": B,
        "transaction_intent_sha256": C,
        "target_path": "installer/windows/VPS-Control-v7.iss",
    }


class WU192Tests(unittest.TestCase):
    def test_exact_lineage_is_ready_only_without_authority(self):
        result = wu192.evaluate(source(), request())
        self.assertEqual(result["decision"], "EXECUTION_AUTHORIZATION_READY_ONLY")
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["exact_transaction_lineage_match"])
        self.assertTrue(result["target_metadata_safe"])
        for key in (
            "verified",
            "durable_identity_bound",
            "proposal_materialized",
            "binding_receipt_persisted",
            "write_authorized",
            "compiler_execution_authorized",
            "build_authorized",
        ):
            self.assertFalse(result[key])

    def test_unknown_request_field_fails_closed(self):
        value = request()
        value["write"] = True
        result = wu192.evaluate(source(), value)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("INVALID_AUTHORIZATION_REQUEST_KEYS", result["reasons"])

    def test_source_authority_escalation_fails_closed(self):
        value = source()
        value["durable_identity_bound"] = True
        result = wu192.evaluate(value, request())
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("SOURCE_RECEIPT_AUTHORITY_ESCALATION", result["reasons"])

    def test_transaction_digest_mismatch_fails_closed(self):
        value = request()
        value["transaction_intent_sha256"] = "d" * 64
        result = wu192.evaluate(source(), value)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("TRANSACTION_INTENT_SHA256_MISMATCH", result["reasons"])

    def test_proposal_identity_mismatch_fails_closed(self):
        value = request()
        value["proposal_sha256"] = "d" * 64
        result = wu192.evaluate(source(), value)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("PROPOSAL_SHA256_MISMATCH", result["reasons"])

    def test_path_traversal_fails_closed(self):
        for path in ("../evil.iss", "installer/../evil.iss", "/tmp/evil.iss", "C:/evil.iss", "installer\\evil.iss"):
            with self.subTest(path=path):
                value = request()
                value["target_path"] = path
                result = wu192.evaluate(source(), value)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertIn("UNSAFE_TARGET_PATH_METADATA", result["reasons"])
                self.assertEqual(result["target_path"], "")

    def test_non_iss_target_fails_closed(self):
        value = request()
        value["target_path"] = "installer/windows/setup.exe"
        result = wu192.evaluate(source(), value)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("UNSAFE_TARGET_PATH_METADATA", result["reasons"])

    def test_digest_is_deterministic(self):
        first = wu192.evaluate(source(), request())["execution_authorization_request_sha256"]
        reordered = dict(reversed(list(request().items())))
        second = wu192.evaluate(source(), reordered)["execution_authorization_request_sha256"]
        self.assertEqual(first, second)

    def test_cli_outputs_valid_json(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--source-receipt", json.dumps(source()), "--authorization-request", json.dumps(request())],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["decision"], "EXECUTION_AUTHORIZATION_READY_ONLY")
        self.assertFalse(receipt["write_authorized"])

    def test_invalid_json_cli_is_distinct_failure(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--source-receipt", "{", "--authorization-request", json.dumps(request())],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["error"], "INVALID_JSON")


if __name__ == "__main__":
    unittest.main()
