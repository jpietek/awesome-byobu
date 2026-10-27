"""Turn OS counters into schema-v1 observations; presentation never reads OS APIs."""
from collections import deque
from pathlib import Path
import time


class Metrics:
    def __init__(self, state_dir, legacy_home=None):
        self.previous = None
        self.previous_time = None
        self.power = deque()
        self.power_mode = None
        self.state_dir = Path(state_dir)
        self.legacy_home = Path(legacy_home) if legacy_home else None

    def event_age(self, name, wall):
        paths = [self.state_dir / ("last-" + name)]
        if self.legacy_home and name == "unlock":
            paths.append(self.legacy_home / ".cache/jan/last-unlock")
        for path in paths:
            try:
                stamp = float(path.read_text().strip())
                if 0 < stamp <= wall:
                    return wall - stamp
            except (ValueError, OSError):
                pass
        return None

    def update(self, raw, monotonic=None, wall=None):
        mono = time.monotonic() if monotonic is None else monotonic
        wall = time.time() if wall is None else wall
        elapsed = mono - self.previous_time if self.previous_time is not None else 0
        old = self.previous or {}
        old_cpu = {row["id"]: row for row in old.get("cpu", [])}
        rows = []; sum_busy = sum_total = 0
        for cpu in raw["cpu"]:
            before = old_cpu.get(cpu["id"])
            percent = None
            if before and 0 < elapsed <= 10:
                total, busy = cpu["total"] - before["total"], cpu["busy"] - before["busy"]
                if total > 0 and 0 <= busy <= total:
                    percent = 100 * busy / total
                    sum_busy += busy; sum_total += total
            rows.append({"id": cpu["id"], "kind": cpu.get("kind", "unknown"), "percent": percent})
        rx = tx = 0; net_valid = False
        if 0 < elapsed <= 10:
            for name, values in raw["network"].items():
                before = old.get("network", {}).get(name)
                if before and values[0] >= before[0] and values[1] >= before[1]:
                    rx += values[0] - before[0]; tx += values[1] - before[1]; net_valid = True
        battery = dict(raw["battery"]) if raw.get("battery") else None
        mode = (battery.get("status"), battery.get("plugged")) if battery else None
        if mode != self.power_mode or elapsed > 10:
            self.power.clear(); self.power_mode = mode
        if battery:
            watts = battery.get("power_w")
            if watts is not None and watts >= 0:
                self.power.append((mono, watts))
            while self.power and mono - self.power[0][0] > 180:
                self.power.popleft()
            average = sum(p for _, p in self.power) / len(self.power) if self.power else None
            reserve = battery.get("energy_now_wh")
            if battery.get("status") == "Charging":
                full = battery.get("energy_full_wh")
                reserve = full - reserve if full is not None and reserve is not None else None
            battery["eta_seconds"] = (reserve / average * 3600 if reserve is not None and reserve > 0
                                      and average and average > 0.2 and mode[0] in ("Charging", "Discharging") else None)
        result = {"schema_version": 1, "updated_at": wall, "platform": raw["platform"],
                  "cpu": {"cores": rows, "percent": 100 * sum_busy / sum_total if sum_total else None},
                  "memory": dict(raw["memory"]), "load1": raw["load1"],
                  "network": {"rx_bytes_per_second": rx / elapsed if net_valid else None,
                              "tx_bytes_per_second": tx / elapsed if net_valid else None},
                  "battery": battery, "uptime_seconds": raw["uptime_seconds"],
                  "awake_seconds": self.event_age("wake", wall),
                  "unlocked_seconds": self.event_age("unlock", wall)}
        self.previous, self.previous_time = raw, mono
        return result
