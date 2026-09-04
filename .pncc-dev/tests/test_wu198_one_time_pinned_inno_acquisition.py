import hashlib
import importlib.util
import io
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.pncc-dev/scripts/wu198_one_time_pinned_inno_acquisition.py'
spec = importlib.util.spec_from_file_location('wu198', SCRIPT)
wu198 = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(wu198)


class FakeResponse:
    def __init__(self, data: bytes, url='https://example.invalid/final'):
        self._io = io.BytesIO(data)
        self._url = url
    def read(self, n=-1):
        return self._io.read(n)
    def geturl(self):
        return self._url


class Wu198Tests(unittest.TestCase):
    def test_contract_is_exact_and_least_authority(self):
        c = wu198.load_contract()
        self.assertEqual(c['target']['asset_id'], 511336600)
        self.assertEqual(c['target']['size_bytes'], 14304168)
        self.assertEqual(c['target']['sha256'], '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f')
        self.assertEqual([k for k, v in c['authority'].items() if v], ['network_acquisition'])

    def test_marker_binds_exact_main(self):
        sha = 'a' * 40
        wu198.validate_execution_marker(f'<!-- PNCC-WU198-ACQUISITION-EXECUTE schema=1 expected_main={sha} -->', sha)
        with self.assertRaisesRegex(RuntimeError, 'EXPECTED_MAIN_MISMATCH'):
            wu198.validate_execution_marker(f'<!-- PNCC-WU198-ACQUISITION-EXECUTE schema=1 expected_main={sha} -->', 'b' * 40)

    def test_duplicate_or_missing_marker_blocks(self):
        sha = 'a' * 40
        marker = f'<!-- PNCC-WU198-ACQUISITION-EXECUTE schema=1 expected_main={sha} -->'
        with self.assertRaisesRegex(RuntimeError, 'EXECUTION_MARKER_INVALID'):
            wu198.validate_execution_marker('', sha)
        with self.assertRaisesRegex(RuntimeError, 'EXECUTION_MARKER_INVALID'):
            wu198.validate_execution_marker(marker + '\n' + marker, sha)

    def test_stream_hash_helper(self):
        payload = b'pncc-test-payload'
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'asset.bin'
            size, digest = wu198.stream_to_file_and_hash(FakeResponse(payload), p)
            self.assertEqual(size, len(payload))
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
            self.assertEqual(p.read_bytes(), payload)

    def test_verify_observation_fail_closed(self):
        target = {'size_bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
        wu198.verify_observation(3, target['sha256'], target)
        with self.assertRaisesRegex(RuntimeError, 'SIZE_MISMATCH'):
            wu198.verify_observation(4, target['sha256'], target)
        with self.assertRaisesRegex(RuntimeError, 'SHA256_MISMATCH'):
            wu198.verify_observation(3, '0' * 64, target)

    def test_acquire_deletes_bytes_before_return(self):
        payload = b'abc'
        sha = hashlib.sha256(payload).hexdigest()
        contract = {
            'target': {
                'repository': 'test/repo', 'tag': 't', 'release_id': 1, 'asset_id': 2,
                'asset_name': 'fixture.exe', 'source_url': 'https://example.invalid/a',
                'size_bytes': 3, 'sha256': sha,
            }
        }
        old = wu198.urllib.request.urlopen
        try:
            wu198.urllib.request.urlopen = lambda request, timeout=60: _Context(FakeResponse(payload))
            with tempfile.TemporaryDirectory() as td:
                receipt = wu198.acquire_once(contract, pathlib.Path(td), 'a' * 40)
                self.assertFalse((pathlib.Path(td) / 'fixture.exe').exists())
                self.assertTrue(receipt['identity_verified'])
                self.assertFalse(receipt['asset_persisted_after_job'])
                self.assertFalse(receipt['installed'])
                self.assertFalse(receipt['executed'])
                self.assertFalse(receipt['built'])
        finally:
            wu198.urllib.request.urlopen = old

    def test_hash_failure_still_deletes_asset(self):
        payload = b'abc'
        contract = {
            'target': {
                'repository': 'test/repo', 'tag': 't', 'release_id': 1, 'asset_id': 2,
                'asset_name': 'fixture.exe', 'source_url': 'https://example.invalid/a',
                'size_bytes': 3, 'sha256': '0' * 64,
            }
        }
        old = wu198.urllib.request.urlopen
        try:
            wu198.urllib.request.urlopen = lambda request, timeout=60: _Context(FakeResponse(payload))
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(RuntimeError, 'SHA256_MISMATCH'):
                    wu198.acquire_once(contract, pathlib.Path(td), 'a' * 40)
                self.assertFalse((pathlib.Path(td) / 'fixture.exe').exists())
        finally:
            wu198.urllib.request.urlopen = old


class _Context:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self.value
    def __exit__(self, exc_type, exc, tb):
        return False


if __name__ == '__main__':
    unittest.main()
