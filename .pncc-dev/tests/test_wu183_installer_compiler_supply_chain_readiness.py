#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/evaluate_wave6_wu183_installer_compiler_supply_chain_readiness.py'
CONTRACT = ROOT / '.pncc-dev/contracts/wave6-wu183-installer-compiler-supply-chain-readiness.json'
spec = importlib.util.spec_from_file_location('wu183', SCRIPT)
wu183 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wu183)


class Wu183SupplyChainReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(CONTRACT.read_text(encoding='utf-8'))

    def assertBlocked(self, mutate):
        value = copy.deepcopy(self.base)
        mutate(value)
        with self.assertRaises(ValueError):
            wu183.evaluate(value)

    def test_canonical_contract_passes(self):
        self.assertTrue(wu183.evaluate(copy.deepcopy(self.base)))

    def test_version_drift_blocked(self):
        self.assertBlocked(lambda d: d['toolchain'].__setitem__('version', 'latest'))

    def test_filename_drift_blocked(self):
        self.assertBlocked(lambda d: d['toolchain'].__setitem__('expected_asset_filename', 'innosetup-latest.exe'))

    def test_x86_edition_blocked(self):
        self.assertBlocked(lambda d: d['toolchain'].__setitem__('edition', 'x86'))

    def test_release_date_drift_blocked(self):
        self.assertBlocked(lambda d: d['toolchain'].__setitem__('release_date', '2026-08-13'))

    def test_wrong_repository_blocked(self):
        self.assertBlocked(lambda d: d['toolchain'].__setitem__('upstream_repository', 'mirror/issrc'))

    def test_mutable_latest_url_policy_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('mutable_latest_url_allowed', True))

    def test_attestation_disabled_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('github_release_attestation_required', False))

    def test_attestation_identity_drift_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('release_attestation_repository', 'other/issrc'))

    def test_mirror_trust_anchor_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('mirror_as_trust_anchor_allowed', True))

    def test_package_manager_sole_trust_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('package_manager_as_sole_trust_source_allowed', True))

    def test_attestation_failure_fallback_blocked(self):
        self.assertBlocked(lambda d: d['verification'].__setitem__('fallback_on_attestation_failure_allowed', True))

    def test_binary_build_authority_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('binary_build', True))

    def test_installer_implementation_authority_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('installer_implementation', True))

    def test_self_hosted_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('self_hosted_runner', True))

    def test_runtime_authority_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('runtime_execution', True))

    def test_release_authority_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('release', True))

    def test_promotion_authority_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('promotion', True))

    def test_1080_lifecycle_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('reserve_1080_lifecycle_mutation', True))

    def test_1081_lifecycle_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('primary_1081_lifecycle_mutation', True))

    def test_v631_mutation_blocked(self):
        self.assertBlocked(lambda d: d['authority'].__setitem__('v631_mutation', True))

    def test_download_in_current_wu_blocked(self):
        self.assertBlocked(lambda d: d['execution_boundary'].__setitem__('download_compiler_in_this_work_unit', True))

    def test_product_path_allowlist_blocked(self):
        self.assertBlocked(lambda d: d.__setitem__('allowed_repository_mutation_prefixes', d['allowed_repository_mutation_prefixes'] + ['src/']))


if __name__ == '__main__':
    unittest.main()
