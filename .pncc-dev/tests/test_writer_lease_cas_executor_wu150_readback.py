import importlib.util
import re
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "wu150_wrapper",
    ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu150_immutable_readback.py",
)
w = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(w)


class ExecutorError(RuntimeError):
    pass


class T(unittest.TestCase):
    def fake_core(self):
        calls = []
        state = {"head": "a" * 40}

        def gh(method, path, token, body=None):
            calls.append((method, path, body))
            if path == "/git/ref/heads/pncc-provider-state":
                return {"object": {"sha": state["head"]}}
            if path == "/contents/.pncc-state/writer-lease-registry.json?ref=" + state["head"]:
                return {"sha": "b" * 40, "content": "e30=", "encoding": "base64"}
            return {"ok": True}

        core = types.SimpleNamespace(
            gh=gh,
            REGISTRY_PATH=".pncc-state/writer-lease-registry.json",
            STATE_BRANCH="pncc-provider-state",
            SHA40=re.compile(r"^[0-9a-f]{40}$"),
            ExecutorError=ExecutorError,
        )
        return core, calls, state

    def test_mutable_registry_read_is_pinned_to_observed_commit(self):
        core, calls, _ = self.fake_core()
        w.install_immutable_registry_reads(core)
        result = core.gh(
            "GET",
            "/contents/.pncc-state/writer-lease-registry.json?ref=pncc-provider-state",
            "token",
        )
        self.assertEqual(result["sha"], "b" * 40)
        self.assertEqual(calls[0][1], "/git/ref/heads/pncc-provider-state")
        self.assertEqual(
            calls[1][1],
            "/contents/.pncc-state/writer-lease-registry.json?ref=" + ("a" * 40),
        )
        self.assertFalse(any(p.endswith("ref=pncc-provider-state") for _, p, _ in calls))

    def test_each_registry_read_observes_fresh_state_head(self):
        core, calls, state = self.fake_core()
        w.install_immutable_registry_reads(core)
        target = "/contents/.pncc-state/writer-lease-registry.json?ref=pncc-provider-state"
        core.gh("GET", target, "token")
        state["head"] = "c" * 40
        core.gh("GET", target, "token")
        ref_reads = [p for m, p, _ in calls if m == "GET" and p == "/git/ref/heads/pncc-provider-state"]
        self.assertEqual(len(ref_reads), 2)
        self.assertTrue(any(p.endswith("ref=" + ("c" * 40)) for _, p, _ in calls))

    def test_non_registry_request_is_unchanged(self):
        core, calls, _ = self.fake_core()
        w.install_immutable_registry_reads(core)
        core.gh("GET", "/issues/349", "token")
        self.assertEqual(calls, [("GET", "/issues/349", None)])

    def test_workflow_invokes_wrapper_and_validates_repair_prs(self):
        text = (ROOT / ".github/workflows/wave6-wu149-writer-lease-cas-executor.yml").read_text()
        self.assertIn("writer_lease_cas_executor_wu150_immutable_readback.py", text)
        self.assertIn("test_writer_lease_cas_executor_wu*.py", text)
        self.assertNotIn("github.head_ref == 'agent/PIPE-WU-149-bounded-dispatch-fallback'", text)
        self.assertIn("contents: write", text)
        self.assertIn("cancel-in-progress: false", text)


if __name__ == "__main__":
    unittest.main()
