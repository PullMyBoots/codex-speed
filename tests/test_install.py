import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='codex-speed-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.prefix=self.root/"data 'quote' and spaces"
        self.bin=self.root/"bin 'quote' and spaces"
        self.package=self.root/'package';(self.package/'bin').mkdir(parents=True)
        features=' '.join(x.decode() for x in installer.FEATURES)
        self.calls=self.root/'calls'
        for name in ('codex','codex-code-mode-host'):
            p=self.package/'bin'/name
            p.write_text('#!/bin/sh\n# '+features+'\nprintf "%s\\n" "$*" >> '+installer.shlex.quote(str(self.calls))+'\n[ "${1:-}" != --version ] || exit 99\nprintf "fixture-help\\n"\n')
            p.chmod(0o755)
        for name in ('codex-path','codex-resources'):(self.package/name).mkdir()
        (self.package/'codex-package.json').write_text(json.dumps({'version':'9999.0.0','target':'fixture'}))

    def install(self,alias=True):return installer.install_package(self.package,self.prefix,self.bin,alias)

    def test_install_reinstall_and_restore_files_and_symlinks(self):
        self.bin.mkdir();old=self.bin/'codex';old.write_text('original launcher\n');old.chmod(0o751)
        target=self.root/'original-target';target.write_text('original')
        (self.bin/'codex-speed').symlink_to(target)
        state=self.install();backups={k:v['backup'] for k,v in state['entries'].items()}
        again=self.install()
        self.assertEqual(len(again['releases']),1)
        self.assertEqual(backups,{k:v['backup'] for k,v in again['entries'].items()})
        self.assertTrue((self.prefix/'current/CXSTATUSLINE-LICENSE').is_file())
        result=subprocess.run([str(self.bin/'codex-speed'),'--help'],capture_output=True,text=True,check=True)
        self.assertIn('fixture-help',result.stdout)
        self.assertNotIn('--version',self.calls.read_text())
        # Run the installed standalone uninstall entry; source repo is not needed.
        subprocess.run([str(self.bin/'codex-speed-uninstall')],check=True)
        self.assertEqual(old.read_text(),'original launcher\n')
        self.assertEqual(old.stat().st_mode & 0o777,0o751)
        self.assertTrue((self.bin/'codex-speed').is_symlink())
        self.assertEqual((self.bin/'codex-speed').readlink(),target)
        self.assertFalse((self.prefix/'current').exists())

    def test_stock_cli_rejected_before_launchers_are_touched(self):
        (self.package/'bin/codex').write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(RuntimeError,'lacks native'):self.install()
        self.assertFalse(self.prefix.exists());self.assertFalse(self.bin.exists())

    def test_modified_launcher_blocks_uninstall_before_any_removal(self):
        self.install();p=self.bin/'codex-speed';p.write_text(p.read_text()+'# user change\n')
        with self.assertRaisesRegex(RuntimeError,'modified'):installer.uninstall(self.prefix)
        self.assertTrue((self.bin/'codex').exists());self.assertTrue((self.prefix/'current').exists())

    def test_modified_launcher_blocks_reinstall(self):
        self.install();p=self.bin/'codex';p.write_text('# user change\n')
        with self.assertRaisesRegex(RuntimeError,'modified'):self.install()
        self.assertEqual(p.read_text(),'# user change\n')

    def test_missing_backup_blocks_uninstall_before_any_removal(self):
        self.bin.mkdir();(self.bin/'codex').write_text('original')
        state=self.install();Path(state['entries']['codex']['backup']).unlink()
        with self.assertRaisesRegex(RuntimeError,'Backup missing'):installer.uninstall(self.prefix)
        self.assertTrue((self.bin/'codex-speed').exists())

    def test_no_codex_alias_and_no_config_mutation(self):
        self.bin.mkdir();original=self.bin/'codex';original.write_text('original')
        home=self.root/'home';(home/'.codex').mkdir(parents=True)
        config=home/'.codex/config.toml';config.write_text('model = "my-existing-model"\n')
        with patch.dict(os.environ,{'HOME':str(home)}):self.install(alias=False)
        self.assertEqual(config.read_text(),'model = "my-existing-model"\n')
        self.assertEqual(original.read_text(),'original')
        installer.uninstall(self.prefix);self.assertEqual(original.read_text(),'original')

    def test_actual_native_host_failure_preserves_original(self):
        (self.package/'bin/codex-code-mode-host').write_text('#!/bin/sh\nexit 2\n')
        self.bin.mkdir();(self.bin/'codex').write_text('original')
        with self.assertRaises(subprocess.CalledProcessError):self.install()
        self.assertEqual((self.bin/'codex').read_text(),'original')
        self.assertFalse((self.prefix/'current').exists())

    def test_source_tag_selection_has_no_whitelist(self):
        for tag in ('0.163.0','9999.0.0','future-custom-tag'):
            args=installer.parser().parse_args(['--upstream-version',tag])
            self.assertEqual(args.upstream_version,tag)

    def test_missing_runtime_assets_fail_before_download_or_build(self):
        args=installer.parser().parse_args(['--upstream-version','future-custom-tag'])
        with patch.object(installer,'run') as run,patch.object(installer,'download') as download:
            with self.assertRaisesRegex(RuntimeError,'runtime package'):
                installer.build_package(args,self.root/'cache',dict(os.environ),None)
            (self.package/'codex-resources').rmdir()
            with self.assertRaisesRegex(RuntimeError,'Missing runtime assets'):
                installer.build_package(args,self.root/'cache',dict(os.environ),self.package)
            run.assert_not_called();download.assert_not_called()

    def test_changed_code_mode_host_creates_new_release(self):
        state=self.install()
        p=self.package/'bin/codex-code-mode-host';p.write_text(p.read_text()+'# new host\n')
        newer=self.install()
        self.assertNotEqual(state['active'],newer['active']);self.assertEqual(len(newer['releases']),2)
        installer.uninstall(self.prefix)


if __name__=='__main__':unittest.main()
