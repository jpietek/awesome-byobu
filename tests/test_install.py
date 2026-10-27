import contextlib
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

from terminal_setup.install import install

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('zsh') and shutil.which('byobu') and (ROOT/'build/tmux-metrics-status').exists(), 'build, Byobu and Zsh required')
class InstallTests(unittest.TestCase):
    def test_clean_then_existing_install_preserves_settings_and_backs_up(self):
        with tempfile.TemporaryDirectory(prefix='terminal-install-') as directory:
            home=Path(directory)/'test home'; home.mkdir()
            rc=home/'.zshrc'; rc.write_text('export PERSONAL_SETTING=kept\n')
            system=platform.system()
            with contextlib.redirect_stdout(io.StringIO()):
                install(home,system,stage=True)
            self.assertEqual(rc.read_text(),'export PERSONAL_SETTING=kept\n')
            # The managed shell loads personal rc plus all title hooks, while
            # HOME stays real and untouched even in this staged installation.
            env=dict(os.environ); env.pop('ZDOTDIR',None)
            out=subprocess.check_output([str(home/'.local/bin/terminal-shell'),'-ic',
                'print -r -- "$PERSONAL_SETTING:${+functions[_jan_screen_title_preexec]}:${+functions[_jan_tab_build]}"'],env=env,text=True)
            self.assertIn('kept:1:1',out)
            profile=home/'.config/byobu/profile.tmux'; profile.write_text('# existing profile\n')
            local=home/'.config/byobu/local.tmux'; local.write_text('# local customization\n')
            with contextlib.redirect_stdout(io.StringIO()):
                install(home,system,stage=True)
            backups=list((home/'.local/state/terminal-setup/install-backups').glob('*/.config/byobu/profile.tmux'))
            self.assertTrue(any(p.read_text()=='# existing profile\n' for p in backups))
            self.assertEqual(local.read_text(),'# local customization\n')
            self.assertEqual(rc.read_text(),'export PERSONAL_SETTING=kept\n')
            self.assertIn('terminal-shell',profile.read_text())
            session_env=(home/'.local/share/terminal-setup/session-env.sh').read_text()
            self.assertIn('TMUX_TMPDIR=',session_env)
            self.assertIn('unset TMUX',session_env)
            settings = subprocess.check_output(['/bin/sh', '-c',
                '. "$1"; printf "%s\\n" "$BYOBU_CONFIG_DIR" "$TMUX_TMPDIR" "$SHELL"',
                'settings', str(home/'.local/share/terminal-setup/session-env.sh')], text=True)
            self.assertIn(str(home/'.config/byobu'), settings)
            self.assertIn(str(home/'.local/state/terminal-setup/tmux'), settings)
            self.assertNotIn('@TOOLS_BIN@', session_env)
            self.assertNotIn('@SESSION_ENV@',(home/'.local/bin/start-byobu').read_text())
            if system=='Darwin':
                self.assertTrue((home/'Applications/Terminal setup.app/Contents/MacOS/TerminalSetup').exists())
            else:
                self.assertTrue((home/'.local/share/applications/terminal-setup.desktop').exists())
