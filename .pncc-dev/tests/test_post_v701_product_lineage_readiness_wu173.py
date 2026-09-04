import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / '.pncc-dev' / 'contracts' / 'pipe-wu-173-post-v701-product-lineage-readiness.json'


def ensure_historical_commit(ref: str) -> None:
    present = subprocess.run(
        ['git', 'cat-file', '-e', f'{ref}^{{commit}}'],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if present.returncode == 0:
        return
    subprocess.check_call(
        ['git', 'fetch', '--no-tags', '--depth=1', 'origin', ref],
        cwd=ROOT,
    )
    subprocess.check_call(
        ['git', 'cat-file', '-e', f'{ref}^{{commit}}'],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def git_json_at(ref: str, path: str):
    ensure_historical_commit(ref)
    raw = subprocess.check_output(
        ['git', 'show', f'{ref}:{path}'], cwd=ROOT, text=True
    )
    return json.loads(raw)


class PostV701ProductLineageReadinessWU173Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
        cls.authorized_base = cls.contract['authorized_base_sha']
        ensure_historical_commit(cls.authorized_base)
        stable = cls.contract['stable_identity']
        cls.candidate = git_json_at(cls.authorized_base, stable['candidate_source_path'])
        cls.provenance = git_json_at(cls.authorized_base, stable['provenance_path'])

    def test_contract_is_readiness_only_and_default_deny(self):
        c = self.contract
        self.assertEqual(1, c['schema_version'])
        self.assertEqual('PNCC_POST_V701_PRODUCT_LINEAGE_READINESS', c['role'])
        self.assertEqual('PIPE-WU-173', c['work_unit_id'])
        self.assertEqual('05e98ac24422f7c5fdff9077854e2d0594c315d8', c['authorized_base_sha'])
        self.assertEqual('READY_FOR_SEPARATE_PRODUCT_LINEAGE_ACTIVATION_DECISION', c['state'])
        self.assertTrue(all(value is False for value in c['authority'].values()))

    def test_released_v701_identity_is_preserved_exactly(self):
        stable = self.contract['stable_identity']
        self.assertEqual('7.0.1', stable['version'])
        self.assertEqual('src/windows-v7', stable['source_root'])
        self.assertTrue(stable['immutable_in_place'])
        self.assertFalse(stable['provenance_repin_under_same_released_identity_allowed'])
        self.assertEqual('7.0.1', self.candidate['candidate_version'])
        self.assertEqual(['src/windows-v7'], self.candidate['source_roots'])
        self.assertEqual('.pncc-dev/provenance/canonical-source-v7.0.1-patch.json', self.candidate['provenance_path'])
        self.assertEqual('7.0.1', self.provenance['baseline']['activated_candidate_version'])
        self.assertEqual('7.0.1', self.provenance['baseline']['embedded_version'])

    def test_future_product_mutation_requires_distinct_identity_first(self):
        n = self.contract['next_lineage']
        self.assertTrue(n['distinct_product_version_required_before_product_source_mutation'])
        self.assertEqual('PATCH_LINEAGE_CANDIDATE', n['default_semantic_class'])
        self.assertFalse(n['specific_version_assigned'])
        self.assertFalse(n['candidate_source_activation_performed'])
        self.assertFalse(n['candidate_provenance_regeneration_performed'])
        self.assertFalse(n['manifest_regeneration_performed'])
        self.assertFalse(n['build_performed'])
        self.assertFalse(n['runtime_validation_performed'])
        self.assertFalse(n['release_or_promotion_performed'])

    def test_activation_sequence_keeps_runtime_and_promotion_separate(self):
        sequence = self.contract['required_future_activation_sequence']
        self.assertLess(sequence.index('DISTINCT_POST_V701_VERSION_IDENTITY_SELECTION'), sequence.index('APPLY_AUTHORIZED_PRODUCT_FIXES'))
        self.assertLess(sequence.index('APPLY_AUTHORIZED_PRODUCT_FIXES'), sequence.index('REGENERATE_EXACT_SOURCE_MANIFEST_AND_PROVENANCE'))
        self.assertLess(sequence.index('EXACT_HEAD_CI_SUCCESS'), sequence.index('RELEASE_WRITER_LEASE'))
        self.assertEqual('SEPARATE_RUNTIME_VALIDATION_AND_PROMOTION_BOUNDARY', sequence[-1])

    def test_stop_conditions_preserve_tunnel_and_stable_boundaries(self):
        stops = set(self.contract['stop_conditions'])
        for required in (
            'ATTEMPT_TO_REPIN_RELEASED_V701_IDENTITY_IN_PLACE',
            'RUNTIME_REQUIRED',
            'RELEASE_TAG_OR_PROMOTION_REQUIRED',
            'V6_3_1_MUTATION_REQUIRED',
            'PRIMARY_AUTO_1081_LIFECYCLE_CHANGE_REQUIRED',
            'RESERVE_MANUAL_1080_AUTOMATION_REQUIRED',
        ):
            self.assertIn(required, stops)
        inv = self.contract['invariants']
        self.assertEqual('AUTO', inv['primary_auto_1081'])
        self.assertEqual('MANUAL_ONLY', inv['reserve_manual_1080'])
        self.assertTrue(inv['v6_3_1_immutable'])
        self.assertFalse(inv['ci_verified_is_runtime_verified'])

    def test_wu172_is_evidence_not_merged_product_state(self):
        e = self.contract['wu172_evidence']
        self.assertEqual(393, e['issue'])
        self.assertEqual(394, e['pr'])
        self.assertEqual('SUCCESS', e['quality_fast'])
        self.assertEqual('SUCCESS', e['quality_deep_ps51'])
        self.assertEqual('BLOCKED_PROVENANCE_MISMATCH', e['pipeline_state'])
        self.assertFalse(e['merged'])
        self.assertFalse(e['stable_v701_changed'])


if __name__ == '__main__':
    unittest.main()
