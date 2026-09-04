#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/validate_wave6_wu184_installer_acquisition_receipt.py'
POLICY = ROOT / '.pncc-dev/contracts/wave6-wu184-installer-acquisition-receipt-policy.json'
spec = importlib.util.spec_from_file_location('wu184', SCRIPT)
wu184 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wu184)


def receipt():
    return {
        'schema_version': 1,
        'receipt_type': 'PNCC_INSTALLER_COMPILER_ACQUISITION',
        'policy_source': 'PIPE-WU-184',
        'toolchain': {
            'family': 'Inno Setup', 'version': '7.1.0', 'edition': 'x64',
            'upstream_repository': 'jrsoftware/issrc', 'immutable_release_tag': 'is-7_1_0',
            'release_id': 369110765, 'asset_id': 511336600, 'asset_filename': 'innosetup-7.1.0-x64.exe'
        },
        'artifact': {'sha256': '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f', 'byte_count': 14304168},
        'source': {
            'url': 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe',
            'mutable_latest': False, 'mirror_trust_anchor': False, 'package_manager_sole_trust': False
        },
        'github_release_attestation': {'verified': True, 'repository': 'jrsoftware/issrc', 'verifier': 'gh release verify-asset'},
        'authenticode': {'verified': True, 'publisher': 'Pyrsys B.V.'},
        'acquisition': {'runner_provider': 'github-hosted', 'runner_os': 'Windows', 'runner_image': 'windows-2025', 'acquired_at_utc': '2026-09-04T05:20:00Z'},
        'verification': {'status': 'VERIFIED', 'fail_closed': True}
    }


class Wu184ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding='utf-8'))

    def blocked(self, mutate):
        value = receipt(); mutate(value)
        with self.assertRaises(ValueError):
            wu184.validate(value, self.policy)

    def test_in_memory_canonical_shape_passes(self): self.assertTrue(wu184.validate(receipt(), self.policy))
    def test_version_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('version', '7.1.1'))
    def test_edition_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('edition', 'x86'))
    def test_repo_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('upstream_repository', 'mirror/issrc'))
    def test_tag_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('immutable_release_tag', 'latest'))
    def test_release_id_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('release_id', 1))
    def test_asset_id_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('asset_id', 1))
    def test_filename_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('asset_filename', 'latest.exe'))
    def test_sha_uppercase(self): self.blocked(lambda d: d['artifact'].__setitem__('sha256', d['artifact']['sha256'].upper()))
    def test_sha_wrong(self): self.blocked(lambda d: d['artifact'].__setitem__('sha256', '0' * 64))
    def test_byte_count_zero(self): self.blocked(lambda d: d['artifact'].__setitem__('byte_count', 0))
    def test_byte_count_drift(self): self.blocked(lambda d: d['artifact'].__setitem__('byte_count', 14304167))
    def test_http_source(self): self.blocked(lambda d: d['source'].__setitem__('url', d['source']['url'].replace('https://','http://')))
    def test_latest_source(self): self.blocked(lambda d: d['source'].__setitem__('url', 'https://github.com/jrsoftware/issrc/releases/latest/download/innosetup-7.1.0-x64.exe'))
    def test_mutable_latest_true(self): self.blocked(lambda d: d['source'].__setitem__('mutable_latest', True))
    def test_mirror_trust_true(self): self.blocked(lambda d: d['source'].__setitem__('mirror_trust_anchor', True))
    def test_package_manager_sole_trust_true(self): self.blocked(lambda d: d['source'].__setitem__('package_manager_sole_trust', True))
    def test_attestation_false(self): self.blocked(lambda d: d['github_release_attestation'].__setitem__('verified', False))
    def test_attestation_repo_drift(self): self.blocked(lambda d: d['github_release_attestation'].__setitem__('repository', 'other/repo'))
    def test_attestation_verifier_drift(self): self.blocked(lambda d: d['github_release_attestation'].__setitem__('verifier', 'custom'))
    def test_authenticode_false(self): self.blocked(lambda d: d['authenticode'].__setitem__('verified', False))
    def test_publisher_drift(self): self.blocked(lambda d: d['authenticode'].__setitem__('publisher', 'Unknown'))
    def test_self_hosted_runner(self): self.blocked(lambda d: d['acquisition'].__setitem__('runner_provider', 'self-hosted'))
    def test_linux_runner(self): self.blocked(lambda d: d['acquisition'].__setitem__('runner_os', 'Linux'))
    def test_blank_runner_image(self): self.blocked(lambda d: d['acquisition'].__setitem__('runner_image', ''))
    def test_non_z_timestamp(self): self.blocked(lambda d: d['acquisition'].__setitem__('acquired_at_utc', '2026-09-04T05:20:00+00:00'))
    def test_invalid_timestamp(self): self.blocked(lambda d: d['acquisition'].__setitem__('acquired_at_utc', '2026-02-31T05:20:00Z'))
    def test_status_drift(self): self.blocked(lambda d: d['verification'].__setitem__('status', 'PARTIAL'))
    def test_fail_closed_false(self): self.blocked(lambda d: d['verification'].__setitem__('fail_closed', False))
    def test_unexpected_authority_field(self): self.blocked(lambda d: d.__setitem__('authority', {'binary_build': True}))
    def test_nested_unexpected_field(self): self.blocked(lambda d: d['artifact'].__setitem__('trusted', True))


if __name__ == '__main__': unittest.main()
