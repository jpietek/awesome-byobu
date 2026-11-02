from pathlib import Path
import shutil
import subprocess
import unittest


class HammerspoonTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('lua'), 'Lua is optional outside CI')
    def test_terminal_input_routing_without_real_events(self):
        subprocess.run(['lua', 'tests/hammerspoon.lua'],
            cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True)
