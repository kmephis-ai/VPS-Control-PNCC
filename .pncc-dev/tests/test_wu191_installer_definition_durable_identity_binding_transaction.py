import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wu191_installer_definition_durable_identity_binding_transaction.py"
spec = importlib.util.spec_from_file_location("wu191", SCRIPT)
wu191 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(wu191)

PROPOSAL_SHA = "a" * 64
BINDING_SHA = "b" * 64


def source_receipt():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-190",
        "source_envelope_work_unit": "PIPE-WU-189",
        "decision": "READY_ONLY",
        "reasons": [],
        "proposal_sha256": PROPOSAL_SHA,
        "proposal_byte_count": 1234,
        "binding_request_sha256": BINDING_SHA,
        "exact_identity_match": True,
        "verified": False,
        "durable_identity_bound": False,
        "proposal_materialized": False,
        "compiler_execution_authorized": False,
        "build_authorized": False,
    }


def intent():
    return {
        "schema_version": 1,
        "work_unit_id": "PIPE-WU-191",
        "source_binding_request_work_unit": "PIPE-WU-190",
        "proposal_sha256": PROPOSAL_SHA,
        "proposal_byte_count": 1234,
        "binding_request_sha256": BINDING_SHA,
    }


class WU191Tests(unittest.TestCase):
    def test_happy_path_is_readiness_only_and_digest_is_deterministic(self):
        i = intent()
        result = wu191.evaluate(source_receipt(), i)
        expected = hashlib.sha256(json.dumps(i, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(result["decision"], "TRANSACTION_READY_ONLY")
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["exact_request_lineage_match"])
        self.assertEqual(result["transaction_intent_sha256"], expected)
        for key in ("verified", "durable_identity_bound", "proposal_materialized", "binding_receipt_persisted", "compiler_execution_authorized", "build_authorized"):
            self.assertFalse(result[key])

    def test_inputs_are_not_mutated(self):
        s, i = source_receipt(), intent()
        before_s, before_i = copy.deepcopy(s), copy.deepcopy(i)
        wu191.evaluate(s, i)
        self.assertEqual(s, before_s)
        self.assertEqual(i, before_i)

    def test_source_must_be_wu190_ready_only_without_reasons(self):
        for mutate, reason in (
            (lambda s: s.update(work_unit_id="PIPE-WU-189"), "INVALID_SOURCE_RECEIPT_WORK_UNIT"),
            (lambda s: s.update(decision="BLOCKED"), "SOURCE_RECEIPT_NOT_READY_ONLY"),
            (lambda s: s.update(reasons=["X"]), "SOURCE_RECEIPT_REASONS_NOT_EMPTY"),
            (lambda s: s.update(exact_identity_match=False), "SOURCE_RECEIPT_IDENTITY_NOT_EXACT"),
        ):
            s = source_receipt(); mutate(s)
            r = wu191.evaluate(s, intent())
            self.assertEqual(r["decision"], "BLOCKED")
            self.assertIn(reason, r["reasons"])

    def test_source_authority_escalation_fails_closed(self):
        for key in ("verified", "durable_identity_bound", "proposal_materialized", "compiler_execution_authorized", "build_authorized"):
            s = source_receipt(); s[key] = True
            r = wu191.evaluate(s, intent())
            self.assertEqual(r["decision"], "BLOCKED")
            self.assertIn("SOURCE_RECEIPT_AUTHORITY_ESCALATION", r["reasons"])
            self.assertFalse(r["durable_identity_bound"])
            self.assertFalse(r["verified"])

    def test_exact_lineage_mismatches_fail_closed(self):
        cases = (
            ("proposal_sha256", "c" * 64, "PROPOSAL_SHA256_MISMATCH"),
            ("proposal_byte_count", 1235, "PROPOSAL_BYTE_COUNT_MISMATCH"),
            ("binding_request_sha256", "d" * 64, "BINDING_REQUEST_SHA256_MISMATCH"),
        )
        for key, value, reason in cases:
            i = intent(); i[key] = value
            r = wu191.evaluate(source_receipt(), i)
            self.assertEqual(r["decision"], "BLOCKED")
            self.assertIn(reason, r["reasons"])
            self.assertFalse(r["exact_request_lineage_match"])

    def test_unknown_fields_fail_closed(self):
        s = source_receipt(); s["extra"] = 1
        i = intent(); i["installer_definition_path"] = "setup.iss"
        r = wu191.evaluate(s, i)
        self.assertEqual(r["decision"], "BLOCKED")
        self.assertIn("INVALID_SOURCE_RECEIPT_KEYS", r["reasons"])
        self.assertIn("INVALID_TRANSACTION_INTENT_KEYS", r["reasons"])

    def test_boolean_is_not_a_valid_byte_count(self):
        i = intent(); i["proposal_byte_count"] = True
        r = wu191.evaluate(source_receipt(), i)
        self.assertEqual(r["decision"], "BLOCKED")
        self.assertIn("INVALID_TRANSACTION_INTENT_PROPOSAL_BYTE_COUNT", r["reasons"])
        self.assertEqual(r["proposal_byte_count"], 0)

    def test_invalid_hashes_fail_closed_and_safe_output(self):
        i = intent(); i["proposal_sha256"] = "BAD"; i["binding_request_sha256"] = "BAD"
        r = wu191.evaluate(source_receipt(), i)
        self.assertEqual(r["decision"], "BLOCKED")
        self.assertEqual(r["proposal_sha256"], "0" * 64)
        self.assertEqual(r["binding_request_sha256"], "0" * 64)

    def test_reasons_are_sorted_unique(self):
        r = wu191.evaluate({}, {})
        self.assertEqual(r["reasons"], sorted(set(r["reasons"])))

    def test_non_dict_inputs_fail_closed(self):
        r = wu191.evaluate([], [])
        self.assertEqual(r["decision"], "BLOCKED")
        self.assertIn("INVALID_SOURCE_RECEIPT_TYPE", r["reasons"])
        self.assertIn("INVALID_TRANSACTION_INTENT_TYPE", r["reasons"])


if __name__ == "__main__":
    unittest.main()
