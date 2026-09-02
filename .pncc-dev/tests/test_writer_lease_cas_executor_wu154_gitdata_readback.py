import importlib.util
import re
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "wu154_wrapper",
    ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu150_immutable_readback.py",
)
w = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(w)


class ExecutorError(RuntimeError):
    pass


class T(unittest.TestCase):
    BLOB = "b" * 40
    TREE = "c" * 40
    COMMIT = "d" * 40
    STATE_TREE = "e" * 40

    def fake_core(self, *, ref=None, commit_tree=None, root_entries=None, state_entries=None):
        calls = []
        ref = ref or self.COMMIT
        commit_tree = commit_tree or self.TREE
        root_entries = root_entries if root_entries is not None else [
            {"path": ".pncc-state", "type": "tree", "sha": self.STATE_TREE}
        ]
        state_entries = state_entries if state_entries is not None else [
            {"path": "writer-lease-registry.json", "type": "blob", "sha": self.BLOB}
        ]

        def gh(method, path, token, body=None):
            calls.append((method, path, body))
            if method == "POST" and path == "/git/blobs":
                return {"sha": self.BLOB}
            if method == "POST" and path == "/git/trees":
                return {"sha": self.TREE}
            if method == "POST" and path == "/git/commits":
                return {"sha": self.COMMIT}
            if method == "PATCH" and path == "/git/refs/heads/pncc-provider-state":
                return {"ok": True}
            if method == "GET" and path == "/git/ref/heads/pncc-provider-state":
                return {"object": {"sha": ref}}
            if method == "GET" and path == f"/git/commits/{self.COMMIT}":
                return {"tree": {"sha": commit_tree}}
            if method == "GET" and path == f"/git/trees/{self.TREE}":
                return {"tree": root_entries}
            if method == "GET" and path == f"/git/trees/{self.STATE_TREE}":
                return {"tree": state_entries}
            if method == "GET" and path.startswith("/contents/"):
                raise AssertionError("Contents API must not be used after PATCH")
            return {"ok": True}

        core = types.SimpleNamespace(
            gh=gh,
            REGISTRY_PATH=".pncc-state/writer-lease-registry.json",
            STATE_BRANCH="pncc-provider-state",
            SHA40=re.compile(r"^[0-9a-f]{40}$"),
            ExecutorError=ExecutorError,
        )
        return core, calls

    def run_postwrite_readback(self, core):
        w.install_immutable_registry_reads(core)
        core.gh("POST", "/git/blobs", "token", {"content": "x"})
        core.gh("POST", "/git/trees", "token", {"tree": []})
        core.gh("POST", "/git/commits", "token", {"tree": self.TREE})
        core.gh(
            "PATCH",
            "/git/refs/heads/pncc-provider-state",
            "token",
            {"sha": self.COMMIT, "force": False},
        )
        return core.gh(
            "GET",
            "/contents/.pncc-state/writer-lease-registry.json?ref=pncc-provider-state",
            "token",
        )

    def test_postwrite_readback_uses_only_git_data(self):
        core, calls = self.fake_core()
        result = self.run_postwrite_readback(core)
        self.assertEqual(result, {"sha": self.BLOB})
        patch_index = next(i for i, call in enumerate(calls) if call[0] == "PATCH")
        post_patch = calls[patch_index + 1 :]
        self.assertFalse(any(path.startswith("/contents/") for _, path, _ in post_patch))
        self.assertIn(("GET", f"/git/commits/{self.COMMIT}", None), post_patch)
        self.assertIn(("GET", f"/git/trees/{self.TREE}", None), post_patch)
        self.assertIn(("GET", f"/git/trees/{self.STATE_TREE}", None), post_patch)

    def test_ref_mismatch_fails_closed(self):
        core, _ = self.fake_core(ref="f" * 40)
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_STATE_REF_MISMATCH"):
            self.run_postwrite_readback(core)

    def test_commit_tree_mismatch_fails_closed(self):
        core, _ = self.fake_core(commit_tree="f" * 40)
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_COMMIT_TREE_MISMATCH"):
            self.run_postwrite_readback(core)

    def test_duplicate_path_fails_closed(self):
        duplicate = [
            {"path": ".pncc-state", "type": "tree", "sha": self.STATE_TREE},
            {"path": ".pncc-state", "type": "tree", "sha": "f" * 40},
        ]
        core, _ = self.fake_core(root_entries=duplicate)
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_TREE_PATH_NOT_UNIQUE"):
            self.run_postwrite_readback(core)

    def test_wrong_registry_blob_fails_closed(self):
        wrong = [
            {"path": "writer-lease-registry.json", "type": "blob", "sha": "f" * 40}
        ]
        core, _ = self.fake_core(state_entries=wrong)
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_REGISTRY_BLOB_MISMATCH"):
            self.run_postwrite_readback(core)

    def test_force_true_is_rejected(self):
        core, _ = self.fake_core()
        w.install_immutable_registry_reads(core)
        core.gh("POST", "/git/blobs", "token", {"content": "x"})
        core.gh("POST", "/git/trees", "token", {"tree": []})
        core.gh("POST", "/git/commits", "token", {"tree": self.TREE})
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_FORCE_OR_BODY_INVALID"):
            core.gh(
                "PATCH",
                "/git/refs/heads/pncc-provider-state",
                "token",
                {"sha": self.COMMIT, "force": True},
            )

    def test_workflow_still_uses_same_wrapper_and_permissions(self):
        text = (ROOT / ".github/workflows/wave6-wu149-writer-lease-cas-executor.yml").read_text()
        self.assertIn("writer_lease_cas_executor_wu150_immutable_readback.py", text)
        self.assertIn("contents: write", text)
        self.assertIn("issues: read", text)
        self.assertIn("pull-requests: read", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("self-hosted", text)


if __name__ == "__main__":
    unittest.main()
