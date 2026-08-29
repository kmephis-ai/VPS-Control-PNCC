from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pncc_frontier_lifecycle",
    ROOT / ".pncc-dev" / "scripts" / "evaluate_governed_frontier_lifecycle.py",
)
lifecycle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lifecycle)

POLICY_PATH = ROOT / ".pncc-dev" / "contracts" / "governed-frontier-lifecycle-policy.json"
TRANSITION_PATH = ROOT / ".pncc-dev" / "contracts" / "governed-frontier-transition-pipe-wu-104.json"
BASE = "bec942781e006b3fe3e2da837d1f71b46181f2e4"
BRANCH = "agent/PIPE-WU-104-governed-frontier-lifecycle"
DOMAIN = "wave5-governed-frontier-lifecycle-advancement"


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def active_frontier(frontier_id, *, runtime=False, goal="goal"):
    return {
        "schema_version": 1,
        "role": "WAVE5_NEXT_GOVERNED_WORK_UNIT_FRONTIER",
        "state": "ACTIVE",
        "frontier_id": frontier_id,
        "title_template": "{work_unit_id} — Example",
        "goal": goal,
        "conflict_domain": "example-domain-" + frontier_id.lower(),
        "runtime_required": runtime,
        "scope": ["scope"],
        "forbidden_scope": ["forbidden"],
        "required_checks": ["check"],
        "exit_criteria": ["exit"],
        "next_natural_boundary": "NEXT",
    }


def transition_for(predecessor_bytes, successor_bytes, *, work_unit_id="PIPE-WU-104", base=BASE, branch=BRANCH):
    predecessor = lifecycle.loads_strict(predecessor_bytes)
    successor = lifecycle.loads_strict(successor_bytes)
    successor_state = successor["state"]
    return {
        "schema_version": 1,
        "role": "GOVERNED_FRONTIER_TRANSITION",
        "transition_state": "PREPARED_FOR_IN_PR_ADVANCEMENT",
        "work_unit_id": work_unit_id,
        "issue_number": 255,
        "conflict_domain": DOMAIN,
        "base_sha": base,
        "branch": branch,
        "runtime_required": False,
        "predecessor_frontier": {
            "state": "ACTIVE",
            "frontier_id": predecessor["frontier_id"],
            "blob_sha": lifecycle.git_blob_sha_bytes(predecessor_bytes),
        },
        "successor_frontier": {
            "state": successor_state,
            "frontier_id": successor.get("frontier_id", "NONE") if successor_state == "ACTIVE" else "NONE",
            "blob_sha": lifecycle.git_blob_sha_bytes(successor_bytes),
        },
        "same_pr_advancement_required": True,
        "predecessor_replay_forbidden": True,
        "successor_must_be_canonical_before_merge": True,
        "provider_truth_observed": {},
        "provider_mutation_authority": False,
        "issue_mutation_authority": False,
        "direct_main_write_authority": False,
        "merge_authority": False,
        "runtime_action_authority": False,
        "product_runtime_mutation_authority": False,
        "adwf_binding_mutation_authority": False,
        "adwf_repository_mutation_authority": False,
        "release_tag_promotion_authority": False,
        "ruleset_policy_mutation_authority": False,
        "private_evidence_publication_authority": False,
        "reserve_1080_lifecycle_mutation_authority": False,
        "primary_1081_lifecycle_mutation_authority": False,
    }


class GovernedFrontierLifecycleWu104Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = lifecycle.load_json(POLICY_PATH)
        cls.transition = lifecycle.load_json(TRANSITION_PATH)

    def test_policy_is_read_only_default_deny_and_anchors_exact(self):
        lifecycle.validate_policy(self.policy)
        lifecycle.validate_anchor_map(self.policy)
        for key in (
            "provider_mutation_authority",
            "issue_mutation_authority",
            "branch_mutation_authority",
            "pull_request_mutation_authority",
            "writer_lease_mutation_authority",
            "merge_authority",
            "runtime_action_authority",
            "product_runtime_mutation_authority",
            "adwf_binding_mutation_authority",
            "release_tag_promotion_authority",
            "ruleset_policy_mutation_authority",
            "private_evidence_publication_authority",
            "reserve_1080_lifecycle_mutation_authority",
            "primary_1081_lifecycle_mutation_authority",
        ):
            self.assertIs(self.policy[key], False, key)

    def test_canonical_wu104_transition_identity_and_successor_blob(self):
        t = self.transition
        self.assertEqual(t["work_unit_id"], "PIPE-WU-104")
        self.assertEqual(t["issue_number"], 255)
        self.assertEqual(t["base_sha"], BASE)
        self.assertEqual(t["branch"], BRANCH)
        self.assertEqual(t["conflict_domain"], DOMAIN)
        self.assertEqual(
            t["predecessor_frontier"],
            {
                "state": "ACTIVE",
                "frontier_id": "GOVERNED_FRONTIER_LIFECYCLE_AND_IN_PR_ADVANCEMENT",
                "blob_sha": "d350bd1d06cbba6af4dda30f777c294261f66083",
            },
        )
        self.assertEqual(
            t["successor_frontier"],
            {
                "state": "ACTIVE",
                "frontier_id": "ADWF_CONSUMER_PROJECT_PACK_PROVENANCE_RECONCILIATION",
                "blob_sha": "ebc619943a66dd5030b0299cab35c430bf530e7a",
            },
        )

    def test_canonical_wu104_provider_truth_is_proof_only(self):
        observed = self.transition["provider_truth_observed"]
        self.assertEqual(observed["pncc_main_sha"], BASE)
        self.assertEqual(observed["adwf_main_sha"], "aad3aba5ccb5f37882b8d51e89ff2c66da6e2822")
        self.assertEqual(observed["powershell_pack_blob_sha"], "b4ad2f2459079039a59c3e687ea269d2c6ca73fe")
        self.assertEqual(observed["external_binding_schema_blob_sha"], "c3762053920076ea1ac9ba1865cbfacb6fdcf0c0")
        self.assertEqual(observed["project_pack_digest"], "fbe69c4e93ff8b07e7d0dc6f0cbd1f9ceb80617f472f1fbe5a1ce181279a0c8c")
        self.assertEqual(observed["source_only_candidate_binding_sha256"], "5f7622683832f14d935974d5c90ba48ab5cf4709136ae602da77eb61c1dc3a34")
        self.assertIs(self.transition["adwf_binding_mutation_authority"], False)
        self.assertIs(self.transition["adwf_repository_mutation_authority"], False)

    def test_exact_advancement_is_eligible(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode(active_frontier("NEW"))
        result = lifecycle.evaluate_transition(
            transition_for(predecessor, successor),
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "ADVANCEMENT_ELIGIBLE")

    def test_unchanged_frontier_blocks(self):
        predecessor = encode(active_frontier("OLD"))
        result = lifecycle.evaluate_transition(
            transition_for(predecessor, predecessor),
            predecessor,
            predecessor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("FRONTIER_NOT_ADVANCED", result["reasons"][0])

    def test_same_frontier_id_replay_blocks_even_if_bytes_change(self):
        predecessor = encode(active_frontier("OLD", goal="before"))
        successor = encode(active_frontier("OLD", goal="after"))
        result = lifecycle.evaluate_transition(
            transition_for(predecessor, successor),
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("FRONTIER_ID_REPLAY", result["reasons"][0])

    def test_wrong_work_unit_or_base_blocks(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode(active_frontier("NEW"))
        transition = transition_for(predecessor, successor)
        for work_unit_id, base in (("PIPE-WU-999", BASE), ("PIPE-WU-104", "a" * 40)):
            result = lifecycle.evaluate_transition(
                transition,
                predecessor,
                successor,
                work_unit_id=work_unit_id,
                base_sha=base,
                branch=BRANCH,
                policy=self.policy,
                check_anchors=False,
            )
            self.assertEqual(result["decision"], "BLOCKED")

    def test_malformed_successor_blocks(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode({"schema_version": 1, "role": "WRONG", "state": "ACTIVE"})
        transition = transition_for(predecessor, successor)
        result = lifecycle.evaluate_transition(
            transition,
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "BLOCKED")

    def test_runtime_successor_blocks(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode(active_frontier("NEW", runtime=True))
        transition = transition_for(predecessor, successor)
        result = lifecycle.evaluate_transition(
            transition,
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("FRONTIER_RUNTIME_REQUIRED", result["reasons"][0])

    def test_explicit_terminal_none_is_eligible(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode(self.policy["terminal_none_shape"])
        transition = transition_for(predecessor, successor)
        result = lifecycle.evaluate_transition(
            transition,
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=False,
        )
        self.assertEqual(result["decision"], "TERMINAL_ELIGIBLE")

    def test_anchor_drift_blocks_fail_closed(self):
        predecessor = encode(active_frontier("OLD"))
        successor = encode(active_frontier("NEW"))
        result = lifecycle.evaluate_transition(
            transition_for(predecessor, successor),
            predecessor,
            successor,
            work_unit_id="PIPE-WU-104",
            base_sha=BASE,
            branch=BRANCH,
            policy=self.policy,
            check_anchors=True,
            root=ROOT,
            blob_reader=lambda path: "0" * 40,
        )
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("ANCHOR_DRIFT", result["reasons"][0])

    def test_transition_path_is_deterministic(self):
        self.assertEqual(
            lifecycle.expected_transition_path(self.policy, "PIPE-WU-104"),
            ".pncc-dev/contracts/governed-frontier-transition-pipe-wu-104.json",
        )


if __name__ == "__main__":
    unittest.main()
