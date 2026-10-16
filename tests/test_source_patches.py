"""Exercise real git applicability checks without downloading upstream sources."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('source_installer', ROOT / 'install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class SourcePatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='codex-speed-source-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        (self.source / 'codex-rs').mkdir(parents=True)
        subprocess.run(['git', 'init', '--quiet', str(self.source)], check=True)
        self.patches = self.root / 'repository' / 'patches'
        self.patches.mkdir(parents=True)
        for name, value in (('ROOT', self.patches.parent), ('PATCH', self.patches / 'codex.patch')):
            replacement = patch.object(installer, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def source_files(self, version, content):
        (self.source / 'codex-rs/Cargo.toml').write_text(
            '[workspace.package]\nversion = "' + version + '"\n'
        )
        (self.source / 'value.txt').write_text(content + '\n')

    def add_patch(self, name, before, after):
        (self.patches / name).write_text(
            '--- a/value.txt\n+++ b/value.txt\n@@ -1 +1 @@\n-'
            + before + '\n+' + after + '\n'
        )

    def test_ported_patch_applies_and_retry_is_idempotent(self):
        self.source_files('0.160.0', 'legacy')
        self.add_patch('codex.patch', 'modern', 'patched-modern')
        self.add_patch('codex-0.160.0.patch', 'legacy', 'patched-legacy')
        self.assertEqual(installer.check_patch(self.source), 'applicable')
        self.assertEqual((self.source / 'value.txt').read_text(), 'legacy\n')
        self.assertEqual(installer.check_patch(self.source, apply=True), 'applicable')
        self.assertEqual((self.source / 'value.txt').read_text(), 'patched-legacy\n')
        self.assertEqual(installer.check_patch(self.source, apply=True), 'already applied')

    def test_unknown_release_uses_actual_source_compatibility(self):
        self.source_files('9999.0.0', 'modern')
        self.add_patch('codex.patch', 'modern', 'patched-modern')
        self.assertEqual(installer.check_patch(self.source, apply=True), 'applicable')
        self.assertEqual((self.source / 'value.txt').read_text(), 'patched-modern\n')

    def test_exact_source_metadata_orders_compatible_lock_variants(self):
        self.source_files('0.160.1', 'same-base')
        self.add_patch('codex.patch', 'different-base', 'modern')
        self.add_patch('codex-0.160.0.patch', 'same-base', 'lock-0.160.0')
        self.add_patch('codex-0.160.1.patch', 'same-base', 'lock-0.160.1')
        installer.check_patch(self.source, apply=True)
        self.assertEqual((self.source / 'value.txt').read_text(), 'lock-0.160.1\n')

    def test_conflicts_do_not_modify_source(self):
        self.source_files('future-custom-tag', 'unknown-code')
        self.add_patch('codex.patch', 'modern', 'patched-modern')
        self.add_patch('codex-0.160.0.patch', 'legacy', 'patched-legacy')
        with self.assertRaisesRegex(RuntimeError, 'actual source conflicts'):
            installer.check_patch(self.source, apply=True)
        self.assertEqual((self.source / 'value.txt').read_text(), 'unknown-code\n')


if __name__ == '__main__':
    unittest.main()
