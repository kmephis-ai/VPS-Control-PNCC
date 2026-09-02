import json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-unattended-activation-owner-authorization-readiness-wu153.json"
EVAL = ROOT / ".pncc-dev/scripts/evaluate_wave6_unattended_activation_owner_authorization_readiness_wu153.py"
MAIN = "86e11c191dd084092f16c491700fc79d18cb8886"
WU = "PIPE-WU-154"


def candidate():
    return {
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "issued_by": "kmephis-ai",
        "authorized_main_sha": MAIN,
        "activation_work_unit_id": WU,
        "permitted_conflict_domains": ["wave6-bounded-unattended-window-activation"],
        "max_work_units": 3,
        "max_wall_clock_minutes": 90,
        "max_parallel_mutating_writers": 1,
        "authority_grant_sha": "1" * 40,
        "owner_receipt_sha": "2" * 40,
        "issued_at": "2026-09-02T18:00:00Z",
        "expires_at": "2026-09-03T18:00:00Z",
        "single_use": True,
        "replay_forbidden": True,
        "runtime_required": False
    }


def run(cand=None, main=MAIN, wu=WU):
    cmd = [sys.executable, str(EVAL), "--contract", str(CONTRACT)]
    td = None
    if cand is not None:
        td = tempfile.TemporaryDirectory()
        p = Path(td.name) / "a.json"; p.write_text(json.dumps(cand), encoding="utf-8")
        cmd += ["--authorization-candidate", str(p), "--fresh-main", main, "--expected-activation-wu", wu, "--now", "2026-09-02T19:00:00Z"]
    r = subprocess.run(cmd, text=True, capture_output=True)
    out = json.loads(r.stdout)
    if td: td.cleanup()
    return r.returncode, out


class Wu153(unittest.TestCase):
    def test_contract_is_readiness_only(self):
        c = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(c["activation_envelope"]["max_work_units"], 3)
        self.assertEqual(c["activation_envelope"]["max_wall_clock_minutes"], 90)
        self.assertEqual(c["activation_envelope"]["max_parallel_mutating_writers"], 1)
        self.assertTrue(all(v is False for v in c["authority"].values()))
        self.assertFalse(c["future_owner_authorization_constraints"]["generic_chat_continuation_is_authority"])

    def test_contract_ready_but_no_execution(self):
        rc, o = run(); self.assertEqual(rc, 0)
        self.assertEqual(o["classification"], "READY_FOR_EXPLICIT_OWNER_ACTIVATION_AUTHORIZATION")
        self.assertFalse(o["execution_authority_granted"])

    def test_valid_candidate_is_shape_only(self):
        rc, o = run(candidate()); self.assertEqual(rc, 0)
        self.assertEqual(o["classification"], "SHAPE_VALID_NO_EXECUTION")
        self.assertTrue(o["authorization_shape_valid"]); self.assertFalse(o["execution_authority_granted"])

    def deny(self, mutate=None, main=MAIN, wu=WU):
        c = candidate()
        if mutate: mutate(c)
        rc, o = run(c, main, wu)
        self.assertEqual(rc, 2); self.assertEqual(o["classification"], "NOT_AUTHORIZED")

    def test_exact_main_required(self): self.deny(main="3" * 40)
    def test_exact_activation_wu_required(self): self.deny(wu="PIPE-WU-999")
    def test_wildcard_domain_denied(self): self.deny(lambda c: c.update(permitted_conflict_domains=["wave6-*"]))
    def test_four_work_units_denied(self): self.deny(lambda c: c.update(max_work_units=4))
    def test_91_minutes_denied(self): self.deny(lambda c: c.update(max_wall_clock_minutes=91))
    def test_multiple_writers_denied(self): self.deny(lambda c: c.update(max_parallel_mutating_writers=2))
    def test_replay_denied(self): self.deny(lambda c: c.update(replayed=True))
    def test_expired_denied(self): self.deny(lambda c: c.update(expires_at="2026-09-02T18:30:00Z"))
    def test_runtime_required_denied(self): self.deny(lambda c: c.update(runtime_required=True))
    def test_forbidden_authority_expansion_denied(self):
        for k in ["product_runtime_mutation", "runtime_action", "ruleset_security_mutation", "release_tag_promotion", "self_hosted_runner", "external_token_or_webhook", "force_or_bypass", "direct_main_engineering_write"]:
            with self.subTest(k=k): self.deny(lambda c, k=k: c.update({k: True}))
    def test_generic_continue_is_not_authorization(self):
        self.deny(lambda c: c.clear() or c.update({"message": "Продолжай"}))


if __name__ == "__main__": unittest.main()
