#!/usr/bin/env python3
import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/evaluate_wave6_wu185_installer_compiler_receipt_admission.py'
spec = importlib.util.spec_from_file_location('wu185', SCRIPT)
wu185 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wu185)


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
        'acquisition': {'runner_provider': 'github-hosted', 'runner_os': 'Windows', 'runner_image': 'windows-2025', 'acquired_at_utc': '2026-09-04T06:30:00Z'},
        'verification': {'status': 'VERIFIED', 'fail_closed': True}
    }


class Wu185AdmissionTests(unittest.TestCase):
    def admitted(self, value=None):
        result = wu185.evaluate(receipt() if value is None else value)
        self.assertEqual(result['decision'], 'ADMITTED')
        self.assertEqual(result['reason_codes'], ['WU184_RECEIPT_VERIFIED'])
        self.assertEqual(result['authority'], 'RECEIPT_CONSUMER_ADMISSION_ONLY')

    def blocked(self, mutate):
        value = receipt(); mutate(value)
        result = wu185.evaluate(value)
        self.assertEqual(result['decision'], 'BLOCKED')
        self.assertTrue(result['reason_codes'])
        self.assertEqual(result['authority'], 'RECEIPT_CONSUMER_ADMISSION_ONLY')

    def test_exact_verified_receipt_is_admitted(self): self.admitted()
    def test_non_object_is_blocked(self): self.assertEqual(wu185.evaluate([])['decision'], 'BLOCKED')
    def test_digest_drift(self): self.blocked(lambda d: d['artifact'].__setitem__('sha256', '0' * 64))
    def test_byte_count_drift(self): self.blocked(lambda d: d['artifact'].__setitem__('byte_count', 1))
    def test_version_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('version', '7.1.1'))
    def test_repo_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('upstream_repository', 'mirror/issrc'))
    def test_tag_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('immutable_release_tag', 'latest'))
    def test_release_id_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('release_id', 1))
    def test_asset_id_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('asset_id', 1))
    def test_filename_drift(self): self.blocked(lambda d: d['toolchain'].__setitem__('asset_filename', 'latest.exe'))
    def test_source_url_drift(self): self.blocked(lambda d: d['source'].__setitem__('url', 'https://example.invalid/innosetup.exe'))
    def test_attestation_false(self): self.blocked(lambda d: d['github_release_attestation'].__setitem__('verified', False))
    def test_attestation_repo_drift(self): self.blocked(lambda d: d['github_release_attestation'].__setitem__('repository', 'other/repo'))
    def test_authenticode_false(self): self.blocked(lambda d: d['authenticode'].__setitem__('verified', False))
    def test_publisher_drift(self): self.blocked(lambda d: d['authenticode'].__setitem__('publisher', 'Unknown'))
    def test_self_hosted_runner(self): self.blocked(lambda d: d['acquisition'].__setitem__('runner_provider', 'self-hosted'))
    def test_linux_runner(self): self.blocked(lambda d: d['acquisition'].__setitem__('runner_os', 'Linux'))
    def test_verification_status_drift(self): self.blocked(lambda d: d['verification'].__setitem__('status', 'PARTIAL'))
    def test_fail_closed_false(self): self.blocked(lambda d: d['verification'].__setitem__('fail_closed', False))
    def test_extra_top_level_authority_field(self): self.blocked(lambda d: d.__setitem__('authority', {'binary_build': True}))
    def test_extra_nested_authority_field(self): self.blocked(lambda d: d['artifact'].__setitem__('trusted_for_build', True))

    def test_validator_false_is_blocked(self):
        class FalseValidator:
            @staticmethod
            def validate(receipt_value, policy_value): return False
        policy = json.loads((ROOT / '.pncc-dev/contracts/wave6-wu184-installer-acquisition-receipt-policy.json').read_text(encoding='utf-8'))
        self.assertEqual(wu185.evaluate(receipt(), policy=policy, validator=FalseValidator())['decision'], 'BLOCKED')

    def test_wrong_policy_identity_is_blocked(self):
        policy = {'work_unit_id': 'PIPE-WU-999'}
        self.assertEqual(wu185.evaluate(receipt(), policy=policy)['decision'], 'BLOCKED')

    def test_decision_output_is_deterministic(self):
        a = wu185.evaluate(receipt()); b = wu185.evaluate(copy.deepcopy(receipt()))
        self.assertEqual(json.dumps(a, sort_keys=True, separators=(',', ':')), json.dumps(b, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__': unittest.main()
