import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'tools' / 'local-git-mirror' / 'materialize_bundle.py'
spec = importlib.util.spec_from_file_location('materialize_bundle', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def build_artifact(root: Path, *, source_sha_override=None, checksum_override=None):
    repo = root / 'source'
    repo.mkdir()
    run('git', 'init', '-q', str(repo))
    run('git', '-C', str(repo), 'config', 'user.email', 'test@example.invalid')
    run('git', '-C', str(repo), 'config', 'user.name', 'Local Mirror Test')
    (repo / 'sample.txt').write_text('mirror test\n', encoding='utf-8')
    run('git', '-C', str(repo), 'add', 'sample.txt')
    run('git', '-C', str(repo), 'commit', '-q', '-m', 'seed')
    sha = run('git', '-C', str(repo), 'rev-parse', 'HEAD').stdout.strip()
    run('git', '-C', str(repo), 'branch', 'local-mirror-source', sha)

    artifact_dir = root / 'artifact'
    artifact_dir.mkdir()
    bundle = artifact_dir / 'repository.bundle'
    run('git', '-C', str(repo), 'bundle', 'create', str(bundle), 'refs/heads/local-mirror-source')
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    manifest = {
        'schema_version': 1,
        'source_repository': 'example/repo',
        'source_branch': 'main',
        'source_sha': source_sha_override or sha,
        'transport_sha': '0' * 40,
        'bundle_sha256': digest,
        'bundle_bytes': bundle.stat().st_size,
        'bundle_ref': 'refs/heads/local-mirror-source',
    }
    (artifact_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (artifact_dir / 'SHA256SUMS.txt').write_text(f"{checksum_override or digest}  repository.bundle\n", encoding='utf-8')
    archive = root / 'artifact.zip'
    with zipfile.ZipFile(archive, 'w') as zf:
        for p in artifact_dir.iterdir():
            zf.write(p, p.name)
    return archive, sha


class LocalGitMirrorTests(unittest.TestCase):
    def test_valid_artifact_materializes_exact_head(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, sha = build_artifact(root)
            target = root / 'workspace'
            result = mod.materialize(archive, target, sha, 'main', 'https://github.com/example/repo.git')
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['head'], sha)
            self.assertEqual(result['fsck'], 'PASS')
            self.assertEqual(run('git', '-C', str(target), 'status', '--porcelain').stdout, '')

    def test_requested_sha_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, _ = build_artifact(root)
            with self.assertRaises(mod.MaterializationError):
                mod.materialize(archive, root / 'workspace', 'f' * 40, 'main')

    def test_checksum_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, sha = build_artifact(root, checksum_override='0' * 64)
            with self.assertRaises(mod.MaterializationError):
                mod.materialize(archive, root / 'workspace', sha, 'main')

    def test_zip_traversal_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as zf:
                zf.writestr('../escape', 'no')
            with self.assertRaises(mod.MaterializationError):
                mod.materialize(archive, root / 'workspace', 'a' * 40, 'main')

    def test_templates_keep_preferred_lane_read_only_and_pinned(self):
        preferred = (ROOT / 'tools' / 'local-git-mirror' / 'bootstrap-workflow.yml.template').read_text(encoding='utf-8')
        fallback = (ROOT / 'tools' / 'local-git-mirror' / 'bootstrap-workflow-fallback.yml.template').read_text(encoding='utf-8')
        self.assertIn('contents: read', preferred)
        self.assertIn('persist-credentials: false', preferred)
        self.assertIn('retention-days: 1', preferred)
        self.assertIn('actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd', preferred)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', preferred)
        self.assertIn('contents: write', fallback)
        self.assertNotIn('pull_request_target:', preferred)
        self.assertNotIn('self-hosted', preferred)


if __name__ == '__main__':
    unittest.main()
