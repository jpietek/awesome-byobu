"""Exercise the actual Zsh hooks, with tmux replaced by a harmless function."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('zsh'), 'Zsh not installed')
class TabNameTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.project = Path(self.directory.name) / 'project'
        (self.project / '.git').mkdir(parents=True)
        (self.project / '.git/HEAD').write_text('ref: refs/heads/topic\n')

    def tearDown(self):
        self.directory.cleanup()

    def run_hook(self, body):
        env = dict(os.environ, TERMINAL_SETUP_CONFIG=str(ROOT/'config/byobu'), TMUX='test-socket,1,0', TMUX_PANE='%999')
        env.pop('SSH_CONNECTION', None); env.pop('SSH_TTY', None)
        code = 'tmux() { :; }; source "$TERMINAL_SETUP_CONFIG/tab-labels.zsh"; ' + body
        return subprocess.check_output(['zsh', '-f', '-c', code], cwd=self.project, env=env, text=True)

    def test_directory_and_git_branch(self):
        self.assertEqual(self.run_hook('_jan_tab_build; print -r -- "$JAN_TAB_LABEL"'), 'project:topic\n')

    def test_detached_head_and_worktree(self):
        (self.project/'.git/HEAD').write_text('abcdef1234567890\n')
        self.assertEqual(self.run_hook('_jan_tab_build; print -r -- "$JAN_TAB_LABEL"'), 'project:abcdef12\n')
        metadata=self.project.parent/'metadata'; (self.project/'.git').rename(metadata)
        (self.project/'.git').write_text('gitdir: ../metadata\n')
        self.assertEqual(self.run_hook('_jan_tab_build; print -r -- "$JAN_TAB_LABEL"'), 'project:abcdef12\n')

    def test_agent_names_and_prompt_restoration(self):
        for command, prefix in (('codex --resume', 'codex'), ('claude', 'claude'), ('claude-amagi', 'claude')):
            out = self.run_hook('_jan_screen_title_preexec ' + repr(command) + '; _jan_screen_title_precmd')
            self.assertEqual(out, '\x1bk'+prefix+':project:topic\x1b\\\x1bkproject:topic\x1b\\')

    def test_ssh_and_gcloud_target_rules(self):
        for command in ('ssh -p 2222 user@server', 'gcloud compute ssh server --zone example'):
            self.assertEqual(self.run_hook('_jan_screen_title_preexec ' + repr(command)), '\x1bkssh:server\x1b\\')

    def test_remote_prompt_has_remote_host(self):
        out=self.run_hook('SSH_CONNECTION=test; HOSTNAME=remote.example; _jan_tab_build; print -r -- "$JAN_TAB_LABEL"')
        self.assertEqual(out, 'remote:project:topic\n')

    def test_branch_shortening(self):
        (self.project/'.git/HEAD').write_text('ref: refs/heads/abcdefghijklmnopqrstuvwxyz\n')
        self.assertEqual(self.run_hook('_jan_tab_build; print -r -- "$JAN_TAB_LABEL"'), 'project:abcdefghijklmnopq…\n')
