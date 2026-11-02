import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def test_print_dependencies_never_runs_a_package_manager(self):
        for family, manager in [('macos','brew'), ('fedora','dnf'), ('ubuntu','apt-get'), ('debian','apt-get'), ('arch','pacman')]:
            with self.subTest(family=family):
                result = subprocess.run(['sh', str(ROOT/'setup.sh'), '--print-deps', family], capture_output=True, text=True, check=True)
                self.assertIn(manager, result.stdout)
                for package in ('tmux', 'git', 'vim'):
                    self.assertIn(package, result.stdout)
                if family == 'arch':
                    self.assertIn('-Syu', result.stdout)
                    self.assertIn('install-byobu-source.sh', result.stdout)

    def test_unknown_distro_fails_before_installing(self):
        result = subprocess.run(['sh', str(ROOT/'setup.sh'), '--print-deps', 'alpine'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported distribution', result.stderr)

    def test_bootstrap_download_failure_never_runs_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in [('id','echo 501'), ('curl','exit 22')]:
                path=root/name; path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'])
            result = subprocess.run(['sh', str(ROOT/'bootstrap.sh')], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 22)

    def test_download_and_extract_forwards_flags_and_preserves_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle=root/'awesome-byobu-main'; bundle.mkdir()
            (bundle/'setup.sh').write_text('#!/bin/sh\nprintf "flags:%s\\n" "$*"\nread -r answer\nprintf "input:%s\\n" "$answer"\n')
            archive=root/'fixture.tar.gz'
            with tarfile.open(archive,'w:gz') as stream:
                stream.add(bundle,arcname=bundle.name)
            bin_dir=root/'bin'; bin_dir.mkdir()
            (bin_dir/'id').write_text('#!/bin/sh\necho 501\n')
            (bin_dir/'curl').write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then cp "$TEST_ARCHIVE" "$2"; exit; fi; shift; done\nexit 1\n')
            for path in bin_dir.iterdir(): path.chmod(0o755)
            env=dict(os.environ, PATH=str(bin_dir)+':'+os.environ['PATH'], TEST_ARCHIVE=str(archive))
            result=subprocess.run(['sh',str(ROOT/'bootstrap.sh'),'--with-hammerspoon','--no-open'], env=env,
                input='approval input\n', capture_output=True, text=True, check=True)
            self.assertIn('flags:--with-hammerspoon --no-open', result.stdout)
            self.assertIn('input:approval input', result.stdout)
