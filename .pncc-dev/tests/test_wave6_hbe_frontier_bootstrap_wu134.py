from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = ROOT / ".pncc-dev/scripts/evaluate_wave6_hbe_frontier_bootstrap.py"
POLICY = ROOT / ".pncc-dev/contracts/wave6-hbe-frontier-bootstrap-policy.json"
TRANSITION = ROOT / ".pncc-dev/contracts/wave6-hbe-frontier-bootstrap-pipe-wu-134.json"
SUCCESSOR_FIXTURE = ROOT / ".pncc-dev/tests/fixtures/wave6-hbe-frontier-bootstrap-wu134-successor.json"

spec = importlib.util.spec_from_file_location("wu134_bootstrap", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

BASE = "7f86472c2cf66c4a5f3b64fb17ee53059cea8c60"
BRANCH = "agent/PIPE-WU-134-wave6-hbe-frontier-bootstrap"
WORK_UNIT = "PIPE-WU-134"
PREDECESSOR = b'{\n  "schema_version": 1,\n  "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER",\n  "state": "NONE"\n}\n'


class Wave6HbeFrontierBootstrapWu134Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy_bytes = POLICY.read_bytes()
        cls.policy = module.loads_strict(cls.policy_bytes)
        cls.transition = module.load_json(TRANSITION)
        cls.successor_bytes = SUCCESSOR_FIXTURE.read_bytes()
        assert module.git_blob_sha_bytes(cls.successor_bytes) == "c9f16baebd6ba5416e176b76fe69e32387e93786"

    def evaluate(self, transition=None, predecessor=None, successor=None, policy=None, policy_bytes=None, **kwargs):
        return module.evaluate_bootstrap(
            copy.deepcopy(self.transition if transition is None else transition),
            PREDECESSOR if predecessor is None else predecessor,
            self.successor_bytes if successor is None else successor,
            work_unit_id=kwargs.pop("work_unit_id", WORK_UNIT),
            base_sha=kwargs.pop("base_sha", BASE),
            branch=kwargs.pop("branch", BRANCH),
            policy=copy.deepcopy(self.policy if policy is None else policy),
            policy_bytes=self.policy_bytes if policy_bytes is None else policy_bytes,
            check_anchors=kwargs.pop("check_anchors", False),
            **kwargs,
        )

    def test_exact_owner_authorized_bootstrap_is_eligible(self):
        result = self.evaluate()
        self.assertEqual("BOOTSTRAP_ELIGIBLE", result["decision"])
        self.assertEqual("c9f16baebd6ba5416e176b76fe69e32387e93786", result["successor_blob_sha"])
        self.assertFalse(result["merge_authority"])

    def test_wrong_work_unit_is_rejected(self):
        result = self.evaluate(work_unit_id="PIPE-WU-135")
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("WORK_UNIT_NOT_OWNER_AUTHORIZED", result["reasons"][0])

    def test_wrong_base_is_rejected(self):
        result = self.evaluate(base_sha="0" * 40)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("BASE_NOT_OWNER_AUTHORIZED", result["reasons"][0])

    def test_non_terminal_predecessor_is_rejected(self):
        active = b'{"schema_version":1,"role":"WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER","state":"ACTIVE"}\n'
        result = self.evaluate(predecessor=active)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("PREDECESSOR_TERMINAL_NONE_REQUIRED", result["reasons"][0])

    def test_runtime_required_successor_is_rejected(self):
        successor = module.loads_strict(self.successor_bytes)
        successor["runtime_required"] = True
        result = self.evaluate(successor=(json.dumps(successor, indent=2, ensure_ascii=False) + "\n").encode())
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("SUCCESSOR_FIELD_INVALID:runtime_required", result["reasons"][0])

    def test_periodic_scheduling_authority_is_rejected(self):
        successor = module.loads_strict(self.successor_bytes)
        successor["periodic_scheduling_authority"] = True
        result = self.evaluate(successor=(json.dumps(successor, indent=2, ensure_ascii=False) + "\n").encode())
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("SUCCESSOR_PERIODIC_SCHEDULING_AUTHORITY_PRESENT", result["reasons"][0])

    def test_transition_authority_expansion_is_rejected(self):
        transition = copy.deepcopy(self.transition)
        transition["merge_authority"] = True
        result = self.evaluate(transition=transition)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("AUTHORITY_EXPANSION:merge_authority", result["reasons"][0])

    def test_wrong_issue_binding_is_rejected(self):
        transition = copy.deepcopy(self.transition)
        transition["issue_number"] = 999
        result = self.evaluate(transition=transition)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("ISSUE_NOT_OWNER_AUTHORIZED", result["reasons"][0])

    def test_policy_binding_drift_is_rejected(self):
        transition = copy.deepcopy(self.transition)
        transition["policy_binding"]["blob_sha"] = "0" * 40
        result = self.evaluate(transition=transition)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertIn("POLICY_BINDING_MISMATCH", result["reasons"][0])

    def test_anchor_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            reverse = {}
            for key, rel in self.policy["immutable_anchor_paths"].items():
                path = temp_root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(key, encoding="utf-8")
                reverse[path.resolve()] = self.policy["immutable_anchor_blobs"][key]
            drift_path = (temp_root / self.policy["immutable_anchor_paths"]["security"]).resolve()

            def reader(path: Path) -> str:
                resolved = path.resolve()
                if resolved == drift_path:
                    return "0" * 40
                return reverse[resolved]

            result = self.evaluate(check_anchors=True, root=temp_root, blob_reader=reader)
            self.assertEqual("BLOCKED", result["decision"])
            self.assertIn("ANCHOR_DRIFT:security", result["reasons"][0])


if __name__ == "__main__":
    unittest.main()
