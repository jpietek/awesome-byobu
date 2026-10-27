import copy
import fcntl
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from terminal_setup.backends.linux import LinuxBackend, cpu_counters, memory_info, network_counters
from terminal_setup.collector import collect
from terminal_setup.install import config_text
from terminal_setup.model import Metrics
from terminal_setup.render import render
from terminal_setup.services import service_files

ROOT = Path(__file__).resolve().parents[1]


class LinuxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.proc = self.root / "proc"; self.sys = self.root / "sys"
        self.put("proc/stat", "cpu 100 0 0 900\ncpu0 100 20 10 870 10 0 0 0 30 5\n")
        self.put("proc/meminfo", "MemTotal: 10000 kB\nMemAvailable: 4000 kB\nCached: 3000 kB\nSReclaimable: 500 kB\nShmem: 200 kB\nUnevictable: 100 kB\nZswap: 50 kB\n")
        self.put("proc/net/dev", "lo: 999 0 0 0 0 0 0 0 999 0 0 0 0 0 0 0\neth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0\n")
        self.put("proc/loadavg", "1.25 2.0 3.0 1/20 123\n")
        self.put("proc/uptime", "1000.5 500.0\n")
        self.backend = LinuxBackend(self.proc, self.sys)

    def tearDown(self):
        self.directory.cleanup()

    def put(self, relative, data):
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(data)

    def battery(self, name, values):
        for key, value in values.items():
            self.put("sys/class/power_supply/" + name + "/" + key, str(value))

    def test_cpu_does_not_double_count_guest_time(self):
        cpu = self.backend.sample()["cpu"][0]
        self.assertEqual(cpu["total"], 1010)
        self.assertEqual(cpu["busy"], 130)
        self.assertEqual(cpu["kind"], "unknown")

    def test_linux_memory_uses_memavailable(self):
        memory = self.backend.sample()["memory"]
        self.assertEqual(memory["used"], 6000 * 1024)
        self.assertEqual(memory["cached"], 3300 * 1024)
        self.assertIsNone(memory["pressure"])

    def test_network_excludes_loopback(self):
        self.assertEqual(self.backend.sample()["network"], {"eth0": [1000, 2000]})

    def test_missing_battery_is_unavailable(self):
        self.assertIsNone(self.backend.sample()["battery"])

    def test_charge_units_are_converted_to_wh_and_w(self):
        self.battery("BAT0", {"type": "Battery", "present": 1, "charge_now": 2000000,
                             "charge_full": 4000000, "voltage_now": 10000000,
                             "current_now": 1000000, "status": "Discharging"})
        battery = self.backend.sample()["battery"]
        self.assertEqual(battery["energy_now_wh"], 20)
        self.assertEqual(battery["power_w"], 10)
        self.assertEqual(battery["percent"], 50)
        self.assertFalse(battery["plugged"])

    def test_multiple_batteries_weight_energy(self):
        self.battery("BAT0", {"type": "Battery", "energy_now": 10000000, "energy_full": 20000000, "capacity": 90, "status": "Charging"})
        self.battery("BAT1", {"type": "Battery", "energy_now": 40000000, "energy_full": 80000000, "capacity": 10, "status": "Charging"})
        self.assertEqual(self.backend.battery()["percent"], 50)
        self.assertIsNone(self.backend.battery()["power_w"])

    def test_optional_battery_fields_do_not_fabricate_eta(self):
        self.battery("BAT0", {"type": "Battery", "capacity": 73, "status": "Full"})
        snapshot = Metrics(self.root).update(self.backend.sample(), 1, 100)
        self.assertEqual(snapshot["battery"]["percent"], 73)
        self.assertIsNone(snapshot["battery"]["eta_seconds"])
        self.assertIn("73%", render(snapshot))


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.root = Path(self.directory.name)
        self.model = Metrics(self.root)
        self.raw = {"platform": "linux", "cpu": [{"id": 0, "busy": 10, "total": 100, "kind": "unknown"}],
                    "memory": {"total": 1000, "used": 600, "wired": 100, "compressed": 0, "cached": 200, "pressure": None},
                    "network": {"eth0": [1000, 2000]}, "battery": None, "load1": 1.0, "uptime_seconds": 1}

    def tearDown(self):
        self.directory.cleanup()

    def test_first_sample_unknown_then_correct_deltas(self):
        first = self.model.update(copy.deepcopy(self.raw), 1, 100)
        self.assertIsNone(first["cpu"]["percent"])
        self.assertIsNone(first["network"]["rx_bytes_per_second"])
        self.raw["cpu"][0].update(busy=40, total=200)
        self.raw["network"]["eth0"] = [1200, 2400]
        second = self.model.update(self.raw, 3, 102)
        self.assertEqual(second["cpu"]["percent"], 30)
        self.assertEqual(second["network"]["rx_bytes_per_second"], 100)

    def test_counter_reset_and_hotplug_do_not_spike(self):
        self.model.update(copy.deepcopy(self.raw), 1, 100)
        self.raw["cpu"] = [{"id": 0, "busy": 1, "total": 5, "kind": "unknown"}, {"id": 1, "busy": 999, "total": 1000, "kind": "unknown"}]
        self.raw["network"] = {"eth0": [1, 2], "eth1": [999999, 999999]}
        second = self.model.update(self.raw, 2, 101)
        self.assertIsNone(second["cpu"]["percent"])
        self.assertIsNone(second["network"]["rx_bytes_per_second"])

    def test_long_pause_rebaselines_rates(self):
        self.model.update(copy.deepcopy(self.raw), 1, 100)
        self.raw["cpu"][0].update(busy=100, total=200)
        self.assertIsNone(self.model.update(self.raw, 100, 199)["cpu"]["percent"])

    def test_future_unlock_is_not_reported(self):
        (self.root / "last-unlock").write_text("500")
        self.assertIsNone(self.model.update(self.raw, 1, 100)["unlocked_seconds"])

    def test_one_collector_owns_a_state_directory(self):
        with (self.root / "collector.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with patch("terminal_setup.collector.create_backend") as create:
                with self.assertRaisesRegex(RuntimeError, "already owns"):
                    collect(self.root / "cache", self.root, count=1)
                create.assert_not_called()


class ConfigurationTests(unittest.TestCase):
    def test_macos_services_have_one_collector_and_save_timer(self):
        configs = service_files("Darwin", "/Users/test user")
        parsed = [plistlib.loads(data) for data in configs.values()]
        collector = next(p for p in parsed if p["Label"].endswith("metrics"))
        self.assertTrue(collector["KeepAlive"])
        self.assertTrue(any(p.get("StartInterval") == 60 for p in parsed))

    def test_linux_uses_user_systemd_and_quotes_paths(self):
        configs = service_files("Linux", "/home/test user")
        self.assertIn(b'"/home/test user/.local/bin/terminal-stats"', configs[".config/systemd/user/terminal-metrics.service"])
        self.assertIn(b"OnUnitActiveSec=60", configs[".config/systemd/user/terminal-session-save.timer"])
        self.assertFalse(any("LaunchAgents" in key for key in configs))

    def test_templates_have_no_machine_specific_paths(self):
        for name in ("profile.tmux", "persistence.tmux"):
            text = config_text(name, Path("/home/test user"), "Linux")
            self.assertNotIn("/Users/jan", text)
            self.assertNotIn("@STATUS_FORMAT@", text)
            self.assertNotIn("@RESURRECT_COMMAND@", text)
        self.assertIn("Linux", config_text("profile.tmux", "/home/test", "Linux"))

    def test_status_client_marks_stale_cache(self):
        binary = ROOT / "build/tmux-metrics-status"
        if not binary.exists():
            self.skipTest("native helper has not been built")
        with tempfile.TemporaryDirectory() as directory:
            import os
            path = Path(directory) / "status.tmux"; path.write_text("old data\n")
            os.utime(path, (1, 1))
            output = subprocess.check_output([str(binary), str(path), "--once"], text=True)
            self.assertIn("stale", output)
            self.assertNotIn("old data", output)


if __name__ == "__main__":
    unittest.main()
