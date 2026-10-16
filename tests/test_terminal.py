"""Opt-in full native binary test. Normal CI only runs the small unit suite."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('CODEX_SPEED_TEST_PACKAGE'),'set CODEX_SPEED_TEST_PACKAGE to a patched native package for the PTY test')
class TerminalTest(unittest.TestCase):
    def test_installed_launcher_streaming_and_layout(self):
        try:import pyte
        except ImportError:self.skipTest('optional test dependency: pip install -r tests/requirements.txt')
        repo=Path(__file__).resolve().parents[1]
        # Keep records for reviewing a failed test; they contain synthetic data only.
        work=Path(tempfile.mkdtemp(prefix='codex-speed-integration-'))
        prefix=work/"install with 'quotes'";bin_dir=work/"bin with 'quotes'"
        subprocess.run([sys.executable,str(repo/'install.py'),'--from-build',os.environ['CODEX_SPEED_TEST_PACKAGE'],'--prefix',str(prefix),'--bin-dir',str(bin_dir),'--no-codex-link'],check=True)
        result=work/'result.json'
        version=json.loads((Path(os.environ['CODEX_SPEED_TEST_PACKAGE'])/'codex-package.json').read_text())['version']
        env=dict(os.environ,CODEX_STATUSLINE_SMOKE_BINARY=str(bin_dir/'codex-speed'),CODEX_SPEED_SMOKE_RESULT=str(result),CODEX_SPEED_EXPECTED_VERSION=version)
        subprocess.run([sys.executable,str(repo/'tests/terminal_smoke.py')],env=env,check=True)
        report=json.loads(result.read_text())
        self.assertTrue(report['all_decode_phases_observed'])
        self.assertTrue(report['last_survives_buffered_request'])
        self.assertTrue(report['throughput_matches_known_stream'])
        subprocess.run([str(bin_dir/'codex-speed-uninstall')],check=True)
        print('Synthetic integration records: '+str(work))


if __name__=='__main__':unittest.main()
