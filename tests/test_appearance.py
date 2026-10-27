import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

from terminal_setup.appearance import appearance_files
from terminal_setup.backends.linux import LinuxBackend
from terminal_setup.install import config_text
from terminal_setup.model import Metrics
from terminal_setup.render import memory_bar, rate, render

ROOT = Path(__file__).resolve().parents[1]


class AppearanceTests(unittest.TestCase):
    def test_memory_half_cells_match_original_native_renderer(self):
        memory = dict(total=1600, used=400, wired=100, compressed=100, cached=300, pressure=1)
        expected = ('#[fg=#e2e8f0,bg=#1e293b,bold] '
                    '#[fg=#f87171,bg=#4ade80]▌#[bg=#1e293b]'
                    '#[fg=#4ade80,bg=#c084fc]▌#[bg=#1e293b]'
                    '#[fg=#64748b,bg=#1e293b]█'
                    '#[fg=#64748b,bg=#1e293b]▌#[bg=#1e293b]' +
                    '#[fg=#334155,bg=#1e293b]░' * 4 + '#[fg=#e2e8f0] 25% #[default]')
        self.assertEqual(memory_bar(memory), expected)
        memory['pressure'] = 4
        self.assertIn('#[fg=#111827,bg=#dc2626,bold]', memory_bar(memory))

    def test_original_order_icons_and_compact_formatting(self):
        snapshot = {'cpu': {'percent': 50, 'cores': [
            {'kind': 'efficiency', 'percent': 100}, {'kind': 'performance', 'percent': 0}]},
            'memory': dict(total=1600, used=400, wired=100, compressed=100, cached=300, pressure=1),
            'network': {'rx_bytes_per_second': 1536, 'tx_bytes_per_second': 2 * 1024**2},
            'battery': {'percent': 50, 'plugged': True, 'status': 'Charging', 'eta_seconds': 480},
            'load1': 1.25, 'awake_seconds': 3660, 'unlocked_seconds': 120}
        output = render(snapshot)
        plain = re.sub(r'#\[[^]]*\]', '', output)
        self.assertEqual(plain, ' ▁ █  50.0%  1.25   ▌▌█▌░░░░ 25%   1.5K↓  2M↑   ▰▰▱▱ 50% ϟ +0h08m    1h01m  󰌾 2m  ')
        positions = [output.index('bg=' + color) for color in ('#38bdf8', '#f472b6', '#1e293b', '#4ade80', '#22d3ee', '#fde047', '#a78bfa', '#fb923c')]
        # Memory uses green backgrounds inside half cells too; ordering is
        # asserted above using visible text rather than a false palette match.
        self.assertLess(positions[0], positions[1])
        self.assertEqual(rate(500), '500B')  # no false M suffix for sub-KiB rates
        self.assertEqual(rate(1024), '1K')

    def test_memory_smoothing_keeps_original_two_second_cadence(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Metrics(directory)
            raw = dict(platform='macos', cpu=[], network={}, battery=None, load1=0, uptime_seconds=1,
                       memory=dict(total=1600, used=400, wired=100, compressed=100, cached=300, pressure=1))
            first = model.update(copy.deepcopy(raw), 0, 100)
            raw['memory']['wired'] = 300; raw['memory']['used'] = 600
            half_second = model.update(copy.deepcopy(raw), 0.5, 100.5)
            two_seconds = model.update(copy.deepcopy(raw), 2, 102)
            self.assertEqual(first['memory']['display_segments'][0], 100)
            self.assertEqual(half_second['memory']['display_segments'][0], 100)
            self.assertEqual(two_seconds['memory']['display_segments'][0], 160)
            self.assertEqual(two_seconds['memory']['used'], 600)

    def test_fedora_profile_preserves_font_colors_and_opacity(self):
        home = Path('/home/asahi user')
        files = appearance_files(ROOT, home, 'Linux')
        profile = files[home / '.local/share/konsole/TerminalSetup.profile'][0].decode()
        palette = files[home / '.local/share/konsole/TerminalSetup.colorscheme'][0].decode()
        self.assertIn('Font=Hack Nerd Font Mono,13,', profile)
        self.assertIn('Opacity=0.75', palette)
        self.assertIn('[Background]\nColor=35,38,41', palette)
        self.assertIn('[Color1]\nColor=237,21,21', palette)
        self.assertEqual(len([p for p in files if p.suffix == '.ttf']), 4)
        self.assertFalse(any('Library/' in str(p) for p in files))

    def test_mac_export_is_named_and_contains_only_appearance_and_launcher(self):
        home = Path('/Users/test')
        files = appearance_files(ROOT, home, 'Darwin')
        path = home / 'Library/Application Support/iTerm2/DynamicProfiles/TerminalSetup.json'
        profile = json.loads(files[path][0])['Profiles'][0]
        self.assertEqual(profile['Normal Font'], 'HackNFM-Regular 13')
        self.assertEqual(profile['Name'], 'Terminal setup')
        self.assertNotIn('HotKey Key Code', profile)
        self.assertNotIn('/Users/jan', json.dumps(profile))

    def test_same_layout_and_colors_on_asahi(self):
        self.assertEqual(config_text('profile.tmux', '/home/test', 'Darwin'),
                         config_text('profile.tmux', '/home/test', 'Linux'))
        self.assertIn('unbind-key -T prefix C-z', (ROOT / 'config/byobu/.tmux.conf').read_text())


class AsahiTopologyTests(unittest.TestCase):
    def test_device_tree_classifies_apple_cores_without_assuming_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for cpu, kind in ((0, 'apple,firestorm'), (3, 'apple,icestorm'), (6, 'apple,avalanche'), (9, 'apple,blizzard')):
                path = root / ('devices/system/cpu/cpu%d/of_node/compatible' % cpu)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(kind.encode() + b'\0')
            backend = LinuxBackend(sys_root=root)
            self.assertEqual(backend.core_kinds([0, 3, 6, 9]), {0:'performance',3:'efficiency',6:'performance',9:'efficiency'})

    def test_capacity_fallback_requires_complete_two_tier_topology(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for cpu, capacity in ((0, 1024), (1, 600)):
                path = root / ('devices/system/cpu/cpu%d/cpu_capacity' % cpu)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(str(capacity))
            backend = LinuxBackend(sys_root=root)
            self.assertEqual(backend.core_kinds([0,1]), {0:'performance',1:'efficiency'})
            self.assertEqual(backend.core_kinds([0,1,2]), {})


if __name__ == '__main__':
    unittest.main()
