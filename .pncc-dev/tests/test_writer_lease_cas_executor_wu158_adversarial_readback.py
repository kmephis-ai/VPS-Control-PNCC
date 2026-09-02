import base64
import hashlib
import importlib.util
import re
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "wu158_wrapper",
    ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu150_immutable_readback.py",
)
w = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(w)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class ExecutorError(RuntimeError):
    pass


class FakeProvider:
    def __init__(self, action: str = "ACQUIRE", stale_ref_reads: int = 2):
        self.action = action
        self.old = "a" * 40
        self.tree = "c" * 40
        self.commit = "d" * 40
        self.registry_bytes = b'{"schema_version":1,"role":"WRITER_LEASE_REGISTRY"}'
        self.blob = git_blob_sha(self.registry_bytes)
        self.stale_ref_reads = stale_ref_reads
        self.patched = False
        self.ref_reads_after_patch = 0
        self.calls = []
        self.commit_message = f"PIPE-WU-158 {action.lower()} Writer Lease lease"
        self.patch_ack_sha = self.commit
        self.commit_parent = self.old
        self.commit_tree = self.tree
        self.commit_message_readback = self.commit_message
        self.tree_blob = self.blob
        self.blob_bytes_readback = self.registry_bytes
        self.divergent_ref = None

    def gh(self, method, path, token, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and path == "/git/ref/heads/pncc-provider-state":
            if not self.patched:
                return {"object": {"sha": self.old}}
            self.ref_reads_after_patch += 1
            if self.divergent_ref:
                return {"object": {"sha": self.divergent_ref}}
            if self.ref_reads_after_patch <= self.stale_ref_reads:
                return {"object": {"sha": self.old}}
            return {"object": {"sha": self.commit}}
        if method == "GET" and path == f"/contents/registry.json?ref={self.old}":
            return {"sha": git_blob_sha(b"old"), "content": base64.b64encode(b"old").decode(), "encoding": "base64"}
        if method == "GET" and path == "/contents/registry.json?ref=pncc-provider-state":
            raise AssertionError("mutable Contents read must never be used directly")
        if method == "POST" and path == "/git/blobs":
            return {"sha": self.blob}
        if method == "POST" and path == "/git/trees":
            return {"sha": self.tree}
        if method == "POST" and path == "/git/commits":
            return {"sha": self.commit}
        if method == "PATCH" and path == "/git/refs/heads/pncc-provider-state":
            self.patched = True
            return {"object": {"sha": self.patch_ack_sha}}
        if method == "GET" and path == f"/git/commits/{self.commit}":
            return {
                "tree": {"sha": self.commit_tree},
                "parents": [{"sha": self.commit_parent}],
                "message": self.commit_message_readback,
            }
        if method == "GET" and path == f"/git/trees/{self.tree}":
            return {"tree": [{"path": "registry.json", "type": "blob", "sha": self.tree_blob}]}
        if method == "GET" and path == f"/git/blobs/{self.blob}":
            return {"encoding": "base64", "content": base64.b64encode(self.blob_bytes_readback).decode()}
        raise AssertionError((method, path, body))


def make_core(provider: FakeProvider):
    return types.SimpleNamespace(
        gh=provider.gh,
        REGISTRY_PATH="registry.json",
        STATE_BRANCH="pncc-provider-state",
        SHA40=re.compile(r"^[0-9a-f]{40}$"),
        ExecutorError=ExecutorError,
        git_blob_sha=git_blob_sha,
    )


def stage_transaction(core, provider):
    token = "token"
    self_head = core.gh("GET", "/git/ref/heads/pncc-provider-state", token)["object"]["sha"]
    assert self_head == provider.old
    core.gh("POST", "/git/blobs", token, {"content": provider.registry_bytes.decode(), "encoding": "utf-8"})
    core.gh("POST", "/git/trees", token, {"base_tree": "x", "tree": []})
    core.gh(
        "POST",
        "/git/commits",
        token,
        {"message": provider.commit_message, "tree": provider.tree, "parents": [provider.old]},
    )
    core.gh(
        "PATCH",
        "/git/refs/heads/pncc-provider-state",
        token,
        {"sha": provider.commit, "force": False},
    )
    return token


class T(unittest.TestCase):
    def test_prewrite_mutable_contents_is_pinned_to_observed_commit(self):
        p = FakeProvider()
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        out = c.gh("GET", "/contents/registry.json?ref=pncc-provider-state", "token")
        self.assertEqual(out["sha"], git_blob_sha(b"old"))
        self.assertFalse(any(path == "/contents/registry.json?ref=pncc-provider-state" for _, path, _ in p.calls))

    def test_acquire_and_release_tolerate_only_stale_exact_prewrite_ref_then_prove_immutable_bytes(self):
        for action in ("ACQUIRE", "RELEASE"):
            with self.subTest(action=action), mock.patch.object(w.time, "sleep", return_value=None):
                p = FakeProvider(action=action, stale_ref_reads=3)
                c = make_core(p)
                w.install_immutable_registry_reads(c)
                token = stage_transaction(c, p)
                rb_ref = c.gh("GET", "/git/ref/heads/pncc-provider-state", token)
                rb = c.gh("GET", "/contents/registry.json?ref=pncc-provider-state", token)
                self.assertEqual(rb_ref["object"]["sha"], p.commit)
                self.assertEqual(rb["sha"], p.blob)
                self.assertEqual(p.ref_reads_after_patch, 4)

    def test_postwrite_third_ref_sha_fails_closed_immediately(self):
        p = FakeProvider(stale_ref_reads=99)
        p.divergent_ref = "e" * 40
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        token = stage_transaction(c, p)
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_STATE_REF_DIVERGED"):
            c.gh("GET", "/git/ref/heads/pncc-provider-state", token)

    def test_postwrite_stale_ref_timeout_fails_closed(self):
        p = FakeProvider(stale_ref_reads=999)
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        token = stage_transaction(c, p)
        with mock.patch.object(w.time, "sleep", return_value=None):
            with self.assertRaisesRegex(ExecutorError, "POSTWRITE_STATE_REF_CONVERGENCE_TIMEOUT"):
                c.gh("GET", "/git/ref/heads/pncc-provider-state", token)
        self.assertEqual(p.ref_reads_after_patch, len(w.REF_CONVERGENCE_DELAYS_SECONDS))

    def test_patch_ack_must_name_exact_created_commit(self):
        p = FakeProvider()
        p.patch_ack_sha = "e" * 40
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        c.gh("GET", "/git/ref/heads/pncc-provider-state", "token")
        c.gh("POST", "/git/blobs", "token", {"content": p.registry_bytes.decode(), "encoding": "utf-8"})
        c.gh("POST", "/git/trees", "token", {"base_tree": "x", "tree": []})
        c.gh("POST", "/git/commits", "token", {"message": p.commit_message, "tree": p.tree, "parents": [p.old]})
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_PATCH_ACK_MISMATCH"):
            c.gh("PATCH", "/git/refs/heads/pncc-provider-state", "token", {"sha": p.commit, "force": False})

    def _assert_immutable_proof_failure(self, mutate, code):
        p = FakeProvider(stale_ref_reads=0)
        mutate(p)
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        token = stage_transaction(c, p)
        c.gh("GET", "/git/ref/heads/pncc-provider-state", token)
        with self.assertRaisesRegex(ExecutorError, code):
            c.gh("GET", "/contents/registry.json?ref=pncc-provider-state", token)

    def test_wrong_commit_parent_fails_closed(self):
        self._assert_immutable_proof_failure(
            lambda p: setattr(p, "commit_parent", "e" * 40),
            "POSTWRITE_COMMIT_PARENT_MISMATCH",
        )

    def test_wrong_commit_tree_fails_closed(self):
        self._assert_immutable_proof_failure(
            lambda p: setattr(p, "commit_tree", "e" * 40),
            "POSTWRITE_COMMIT_TREE_MISMATCH",
        )

    def test_wrong_registry_tree_blob_fails_closed(self):
        self._assert_immutable_proof_failure(
            lambda p: setattr(p, "tree_blob", "e" * 40),
            "POSTWRITE_REGISTRY_BLOB_MISMATCH",
        )

    def test_wrong_registry_bytes_fail_closed(self):
        self._assert_immutable_proof_failure(
            lambda p: setattr(p, "blob_bytes_readback", b"tampered"),
            "POSTWRITE_REGISTRY_BYTES_MISMATCH",
        )

    def test_force_ref_update_remains_forbidden(self):
        p = FakeProvider()
        c = make_core(p)
        w.install_immutable_registry_reads(c)
        c.gh("GET", "/git/ref/heads/pncc-provider-state", "token")
        c.gh("POST", "/git/blobs", "token", {"content": p.registry_bytes.decode(), "encoding": "utf-8"})
        c.gh("POST", "/git/trees", "token", {"base_tree": "x", "tree": []})
        c.gh("POST", "/git/commits", "token", {"message": p.commit_message, "tree": p.tree, "parents": [p.old]})
        with self.assertRaisesRegex(ExecutorError, "POSTWRITE_FORCE_OR_BODY_INVALID"):
            c.gh("PATCH", "/git/refs/heads/pncc-provider-state", "token", {"sha": p.commit, "force": True})


if __name__ == "__main__":
    unittest.main()
