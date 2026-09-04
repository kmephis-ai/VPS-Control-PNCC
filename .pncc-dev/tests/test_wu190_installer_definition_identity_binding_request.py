#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev" / "scripts" / "wu190_installer_definition_identity_binding_request.py"
WU189_SCRIPT = ROOT / ".pncc-dev" / "scripts" / "wu189_installer_definition_proposal_envelope.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


WU190 = load_module("pncc_wu190", SCRIPT)
WU189 = load_module("pncc_wu189_for_wu190_tests", WU189_SCRIPT)
GOOD = f"""; PNCC future installer-definition proposal text only
; Windows 10 target intent
; PowerShell 5.1 compatibility required
; 127.0.0.1:1080 = RESERVE_MANUAL / MANUAL_ONLY
; 127.0.0.1:1081 = PRIMARY_AUTO
; V6.3.1 immutable SHA-256 {WU189.WU188.V631_SHA256}
; PuTTY transport uses -pwfile only
; host-key verification is fail-closed and must remain enabled
"""


class WU190Tests(unittest.TestCase):
    def admitted(self):
        # Static safety remains owned by WU188 through the real WU189 builder.
        envelope = WU189.build_envelope(GOOD)
        self.assertEqual(envelope["classification"], "ADMITTED")
        return envelope

    def request_for(self, envelope):
        return {
            "schema_version": 1,
            "work_unit_id": "PIPE-WU-190",
            "source_envelope_work_unit": "PIPE-WU-189",
            "proposal_sha256": envelope["proposal_sha256"],
            "proposal_byte_count": envelope["proposal_byte_count"],
        }

    def test_exact_admitted_envelope_is_ready_only_never_verified_or_bound(self):
        envelope = self.admitted()
        receipt = WU190.evaluate(envelope, self.request_for(envelope))
        self.assertEqual(receipt["decision"], "READY_ONLY")
        self.assertTrue(receipt["exact_identity_match"])
        for key in ("verified", "durable_identity_bound", "proposal_materialized", "compiler_execution_authorized", "build_authorized"):
            self.assertFalse(receipt[key])

    def test_blocked_wu189_envelope_fails_closed(self):
        envelope = WU189.build_envelope(GOOD + "\nrun ISCC.exe during setup")
        self.assertEqual(envelope["classification"], "BLOCKED")
        receipt = WU190.evaluate(envelope, self.request_for(envelope))
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("ENVELOPE_NOT_ADMITTED", receipt["reasons"])

    def test_digest_mismatch_fails_closed(self):
        envelope = self.admitted()
        request = self.request_for(envelope)
        request["proposal_sha256"] = "0" * 64
        receipt = WU190.evaluate(envelope, request)
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("PROPOSAL_SHA256_MISMATCH", receipt["reasons"])

    def test_byte_count_mismatch_fails_closed(self):
        envelope = self.admitted()
        request = self.request_for(envelope)
        request["proposal_byte_count"] += 1
        receipt = WU190.evaluate(envelope, request)
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("PROPOSAL_BYTE_COUNT_MISMATCH", receipt["reasons"])

    def test_unknown_request_field_fails_closed(self):
        envelope = self.admitted()
        request = self.request_for(envelope)
        request["verified"] = True
        receipt = WU190.evaluate(envelope, request)
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("INVALID_REQUEST_KEYS", receipt["reasons"])
        self.assertFalse(receipt["verified"])

    def test_envelope_authority_escalation_fails_closed(self):
        envelope = self.admitted()
        envelope["build_authorized"] = True
        receipt = WU190.evaluate(envelope, self.request_for(envelope))
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("ENVELOPE_AUTHORITY_ESCALATION", receipt["reasons"])
        self.assertFalse(receipt["build_authorized"])

    def test_binding_request_digest_is_canonical_and_deterministic(self):
        envelope = self.admitted()
        request = self.request_for(envelope)
        reversed_request = dict(reversed(list(request.items())))
        a = WU190.evaluate(envelope, request)
        b = WU190.evaluate(envelope, reversed_request)
        expected = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(a["binding_request_sha256"], expected)
        self.assertEqual(b["binding_request_sha256"], expected)

    def test_invalid_sha_and_boolean_count_fail_closed(self):
        envelope = self.admitted()
        request = self.request_for(envelope)
        request["proposal_sha256"] = "ABC"
        request["proposal_byte_count"] = True
        receipt = WU190.evaluate(envelope, request)
        self.assertEqual(receipt["decision"], "BLOCKED")
        self.assertIn("INVALID_REQUEST_PROPOSAL_SHA256", receipt["reasons"])
        self.assertIn("INVALID_REQUEST_PROPOSAL_BYTE_COUNT", receipt["reasons"])
        self.assertEqual(receipt["proposal_sha256"], "0" * 64)
        self.assertEqual(receipt["proposal_byte_count"], 0)


if __name__ == "__main__":
    unittest.main()
