import contextlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from terminal_setup import links
from terminal_setup.macos_customizations import apply_existing, hammerspoon_files, iterm_customizations

ROOT = Path(__file__).resolve().parents[1]


class LinkTests(unittest.TestCase):
    def test_review_references(self):
        for value, expected in [
            ('(src/mixer/primitives/compositor_layers.hpp:205):', ('src/mixer/primitives/compositor_layers.hpp', 205, None)),
            ('src/nodes/hwaccel/cuda_rect_frame.hpp:78', ('src/nodes/hwaccel/cuda_rect_frame.hpp', 78, None)),
            ('tests/cuda/nvdec/compositor_crop.py', ('tests/cuda/nvdec/compositor_crop.py', None, None)),
            ('src/example.cpp:78:5', ('src/example.cpp', 78, 5)),
            ('docs/link-test.html', ('docs/link-test.html', None, None)),
            ('/tmp/claude-crop/demo/compare.png:', ('/tmp/claude-crop/demo/compare.png', None, None)),
        ]:
            with self.subTest(value=value):
                self.assertEqual(links.parse_reference(value), expected)

    def test_smart_selection_matches_whole_reference_without_prose(self):
        patterns = [r['regex'] for r in iterm_customizations('/tmp/test')['Smart Selection Rules']]
        text = '• Output properties (src/nodes/hwaccel/cuda_rect_frame.hpp:78): rendered canvases.'
        self.assertEqual(re.search(patterns[1], text).group(), 'src/nodes/hwaccel/cuda_rect_frame.hpp:78')
        self.assertEqual(re.search(patterns[1], 'HTML: docs/link-test.html').group(), 'docs/link-test.html')

    def test_invalid_line_and_nonlocal_scheme(self):
        for target, line in [('x.cpp', '1 | touch bad'), ('ssh://host/a', None), ('file://host/a', None), ('a\nb', None)]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                links.parse_reference(target, line)

    def test_file_url_decoding(self):
        self.assertEqual(links.parse_reference('file:///tmp/my%20file.cpp')[0], '/tmp/my file.cpp')
        self.assertEqual(links.parse_reference('file:///tmp/report.html#result')[0], '/tmp/report.html#result')

    def test_url_parentheses_and_surrounding_punctuation(self):
        self.assertEqual(links.parse_reference('https://example.com/a(b)')[0], 'https://example.com/a(b)')
        self.assertEqual(links.parse_reference('(https://example.com/a(b))')[0], 'https://example.com/a(b)')

    def test_relative_paths_from_pane_and_repo_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root/'src').mkdir()
            target = root/'src/example.cpp'; target.write_text('hello')
            self.assertEqual(links.resolve_path('example.cpp', [root/'src']), target.resolve())
            self.assertEqual(links.resolve_path('src/example.cpp', [root/'src']), target.resolve())
            with self.assertRaises(ValueError):
                links.resolve_path('missing.cpp', [root])

    def test_client_tty_selects_correct_tmux_session(self):
        with patch.object(subprocess, 'check_output', side_effect=[
                '99\twrong\t/dev/ttys001\n40\tright\t/dev/ttys002\n', '/project\n']) as output:
            command, session, cwd = links.tmux_context('tmux', '/tmp/socket', '/dev/ttys002')
        self.assertEqual((session, cwd), ('right', Path('/project')))
        self.assertIn('right:', output.call_args.args[0])
        self.assertEqual(command, ['tmux', '-S', '/tmp/socket'])

    def test_no_client_fails_without_creating_session(self):
        with patch.object(subprocess, 'check_output', return_value=''), self.assertRaises(ValueError):
            links.tmux_context('tmux')

    def test_vim_command_quotes_filename_and_opens_requested_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'file $(touch BAD); quoted.cpp'; path.write_text('test')
            stdout = io.StringIO()
            with patch.object(links, 'tmux_context', return_value=(['tmux','-S','/tmp/socket'], 'work', Path(directory))), \
                 patch.object(links.shutil, 'which', side_effect=lambda name: '/usr/bin/'+name), \
                 patch.object(links.Path, 'home', return_value=Path(directory)), contextlib.redirect_stdout(stdout):
                self.assertEqual(links.main([str(path)+':78', '--dry-run']), 0)
            command = json.loads(stdout.getvalue())
            self.assertEqual(shlex.split(command[-1]), ['/usr/bin/vim', '+78', '--', str(path.resolve())])
            self.assertEqual(command[command.index('-t')+1], 'work:')
            self.assertFalse((Path(directory)/'BAD').exists())

    def test_html_uses_browser_instead_of_vim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.html'; path.write_text('<html>test</html>')
            stdout = io.StringIO()
            with patch.object(links, 'tmux_context', return_value=(['tmux'], 'work', Path(directory))), \
                 patch.object(links.shutil, 'which', return_value='/bin/tmux'), \
                 patch.object(links.Path, 'home', return_value=Path(directory)), \
                 patch.object(links, 'browser_command', return_value=['chromium', path.as_uri()]) as browser, \
                 contextlib.redirect_stdout(stdout):
                self.assertEqual(links.main(['test.html#example', '--dry-run']), 0)
            browser.assert_called_once_with(path.resolve().as_uri()+'#example', None)
            self.assertEqual(json.loads(stdout.getvalue())[0], 'chromium')

    def test_images_documents_and_unknown_types_use_default_app_without_tmux(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for system, opener in [('Darwin', '/usr/bin/open'), ('Linux', '/usr/bin/xdg-open')]:
                for name in ['compare.png', 'photo.jpg', 'photo.JPEG', 'photo.HEIC',
                             'animation.gif', 'image.webp', 'diagram.svg', 'report.pdf',
                             'report.docx', 'sheet.xlsx', 'slides.pptx', 'video.mp4',
                             'audio.mp3', 'files.zip', 'bundle.tar.gz', 'unknown.bin']:
                    path = home / name
                    path.write_bytes(b'\x00fixture')
                    for suffix in ['', ':78']:
                        with self.subTest(system=system, target=name+suffix):
                            stdout = io.StringIO()
                            with patch.object(links.platform, 'system', return_value=system), \
                                 patch.object(links.Path, 'home', return_value=home), \
                                 patch.object(links.shutil, 'which', side_effect=lambda name: '/usr/bin/xdg-open' if name == 'xdg-open' else None), \
                                 patch.object(links, 'tmux_context', side_effect=AssertionError('non-text file requested tmux')), \
                                 contextlib.redirect_stdout(stdout):
                                self.assertEqual(links.main([str(path)+suffix, '--dry-run']), 0)
                            self.assertEqual(json.loads(stdout.getvalue()), [opener, str(path.resolve())])

    def test_code_and_text_use_vim_at_requested_line(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for name in ['source.hpp', 'source.HPP', 'source.cpp', 'source.cu', 'script.py',
                         'README.md', 'notes.txt', 'config.yaml', 'config.json',
                         'Makefile', 'Dockerfile', '.gitignore', '.env.local']:
                with self.subTest(name=name):
                    path = home / name
                    path.write_text('text fixture\n')
                    stdout = io.StringIO()
                    with patch.object(links.Path, 'home', return_value=home), \
                         patch.object(links.shutil, 'which', side_effect=lambda name: '/usr/bin/'+name), \
                         patch.object(links, 'tmux_context', return_value=(['tmux'], 'work', home)), \
                         contextlib.redirect_stdout(stdout):
                        self.assertEqual(links.main([str(path)+':78', '--dry-run']), 0)
                    command = json.loads(stdout.getvalue())
                    self.assertEqual(command[:4], ['tmux', 'new-window', '-t', 'work:'])
                    self.assertEqual(shlex.split(command[-1]), ['/usr/bin/vim', '+78', '--', str(path.resolve())])

    def test_relative_image_uses_pane_or_explicit_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / 'corners.png'
            path.touch()
            for offline in [False, True]:
                with self.subTest(offline=offline):
                    stdout = io.StringIO()
                    with patch.object(links.Path, 'home', return_value=home), \
                         patch.object(links.platform, 'system', return_value='Darwin'), \
                         patch.object(links.shutil, 'which', return_value='/usr/bin/tmux'), \
                         patch.object(links, 'tmux_context', return_value=(['tmux'], 'work', home),
                                      side_effect=ValueError('no client') if offline else None), \
                         contextlib.redirect_stdout(stdout):
                        args = ['corners.png', '--line=78', '--dry-run']
                        if offline:
                            args += ['--cwd', directory]
                        self.assertEqual(links.main(args), 0)
                    self.assertEqual(json.loads(stdout.getvalue()), ['/usr/bin/open', str(path.resolve())])

    def test_directories_open_file_manager_even_with_source_or_html_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for name in ['folder', 'folder.hpp', 'folder.html']:
                with self.subTest(name=name):
                    path = home / name
                    path.mkdir()
                    stdout = io.StringIO()
                    with patch.object(links.Path, 'home', return_value=home), \
                         patch.object(links.platform, 'system', return_value='Darwin'), \
                         patch.object(links, 'tmux_context', side_effect=AssertionError('directory requested tmux')), \
                         contextlib.redirect_stdout(stdout):
                        self.assertEqual(links.main([str(path), '--dry-run']), 0)
                    self.assertEqual(json.loads(stdout.getvalue()), ['/usr/bin/open', str(path.resolve())])

    def test_web_links_use_browser_regardless_of_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            for target in ['https://example.com/source.hpp:78', 'https://example.com/photo.png',
                           'HTTP://example.com/report.pdf']:
                with self.subTest(target=target), patch.object(links.Path, 'home', return_value=Path(directory)), \
                     patch.object(links, 'browser_command', return_value=['chromium', target]) as browser, \
                     patch.object(links, 'tmux_context', side_effect=AssertionError('URL requested tmux')), \
                     contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(links.main([target, '--dry-run']), 0)
                    browser.assert_called_once_with(target, None)
                    self.assertEqual(json.loads(stdout.getvalue()), ['chromium', target])

    def test_linux_missing_default_opener_reports_dependency(self):
        with patch.object(links.platform, 'system', return_value='Linux'), \
             patch.object(links.shutil, 'which', return_value=None), \
             self.assertRaisesRegex(ValueError, 'install xdg-utils'):
            links.default_file_command(Path('/tmp/image.png'))

    def test_hammerspoon_opt_in_preserves_existing_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); (home/'.hammerspoon').mkdir()
            init = home/'.hammerspoon/init.lua'; init.write_text('-- personal shortcuts\n')
            files = hammerspoon_files(ROOT, home)
            init.write_bytes(files[init][0])
            self.assertTrue(init.read_text().startswith('-- personal shortcuts\n'))
            self.assertNotIn(init, hammerspoon_files(ROOT, home))

    def test_existing_profile_migration_preserves_customizations_and_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home/'Library/Application Support/iTerm2/DynamicProfiles/custom.json'
            profile.parent.mkdir(parents=True)
            original = {'Profiles': [{'Name':'Custom', 'Guid':'existing', 'Command':'keep me',
                'Keyboard Map': {'my-key': {'Action':11,'Text':'keep'}},
                'Smart Selection Rules': [{'notes':'Personal rule','regex':'example','actions':[]}]}]}
            profile.write_text(json.dumps(original))
            with contextlib.redirect_stdout(io.StringIO()):
                backup = apply_existing(home, ['Custom'], '/tmp/test-socket')
            changed = json.loads(profile.read_text())['Profiles'][0]
            self.assertEqual(changed['Command'], 'keep me')
            self.assertIn('my-key', changed['Keyboard Map'])
            self.assertFalse(changed['Smart Selection Actions Use Interpolated Strings'])
            self.assertEqual(changed['Smart Selection Rules'][-1]['notes'], 'Personal rule')
            manifest = json.loads((backup/'manifest.json').read_text())
            self.assertEqual(json.loads(Path(manifest[str(profile)]).read_text()), original)
            self.assertIn('linksOnly=true', (home/'.hammerspoon/init.lua').read_text())
            self.assertTrue(os.access(home/'.local/bin/terminal-open-link', os.X_OK))
            compile((home/'.local/bin/terminal-open-link').read_text(), 'installed opener', 'exec')


if __name__ == '__main__':
    unittest.main()
