"""Linux /proc and /sys adapter: no subprocesses in the sampling loop."""
from pathlib import Path


def read_number(path):
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return None


def read_text(path, default=""):
    try:
        return path.read_text().strip()
    except OSError:
        return default


def cpu_counters(text):
    rows = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0].startswith("cpu") and fields[0][3:].isdigit():
            # guest and guest_nice already contribute to user/nice. Do not
            # count them again. Treat iowait as idle, as top-like displays do.
            values = [int(v) for v in fields[1:9]]
            values += [0] * (8 - len(values))
            idle = values[3] + values[4]
            rows.append({"id": int(fields[0][3:]), "busy": sum(values) - idle,
                         "total": sum(values), "kind": "unknown"})
    return rows


def memory_info(text):
    values = {}
    for line in text.splitlines():
        fields = line.replace(":", " ").split()
        if len(fields) >= 2:
            values[fields[0]] = int(fields[1]) * (1024 if len(fields) > 2 and fields[2] == "kB" else 1)
    total = values.get("MemTotal", 0)
    cached = max(0, values.get("Cached", 0) + values.get("SReclaimable", 0) - values.get("Shmem", 0))
    available = min(total, values.get("MemAvailable", values.get("MemFree", 0) + cached + values.get("Buffers", 0)))
    used = max(0, total - available)
    wired = min(used, values.get("Unevictable", 0))
    compressed = min(max(0, used - wired), values.get("Zswap", 0))
    return {"total": total, "used": used, "wired": wired, "compressed": compressed,
            "cached": min(available, cached), "pressure": None}


def network_counters(text):
    result = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, values = line.split(":", 1)
        fields = values.split(); name = name.strip()
        if name != "lo" and len(fields) >= 16:
            result[name] = [int(fields[0]), int(fields[8])]
    return result


class LinuxBackend:
    def __init__(self, proc_root="/proc", sys_root="/sys"):
        self.proc = Path(proc_root)
        self.sys = Path(sys_root)

    def battery(self):
        supplies = list((self.sys / "class/power_supply").glob("*"))
        ac = any(read_number(p / "online") == 1 for p in supplies
                 if read_text(p / "type") != "Battery")
        batteries = []
        for path in supplies:
            if read_text(path / "type") != "Battery" or read_number(path / "present") == 0:
                continue
            voltage = read_number(path / "voltage_now")
            def energy(name):
                value = read_number(path / ("energy_" + name))
                if value is not None:
                    return value / 1e6
                charge = read_number(path / ("charge_" + name))
                return charge * voltage / 1e12 if charge is not None and voltage is not None else None
            now, full = energy("now"), energy("full")
            power = read_number(path / "power_now")
            if power is not None:
                power = abs(power) / 1e6
            else:
                current = read_number(path / "current_now")
                power = abs(current * voltage) / 1e12 if current is not None and voltage is not None else None
            pct = read_number(path / "capacity")
            if pct is None and now is not None and full:
                pct = 100 * now / full
            batteries.append({"percent": pct, "energy_now_wh": now, "energy_full_wh": full,
                              "power_w": power, "status": read_text(path / "status", "Unknown")})
        if not batteries:
            return None
        # Aggregate energy across batteries when possible; a simple average of
        # charge percentages would misrepresent unequal battery capacities.
        def complete_sum(key):
            return sum(b[key] for b in batteries) if all(b[key] is not None for b in batteries) else None
        now, full = complete_sum("energy_now_wh"), complete_sum("energy_full_wh")
        pct = 100 * now / full if now is not None and full else (batteries[0]["percent"] if len(batteries) == 1 else None)
        states = {b["status"] for b in batteries}
        status = next(iter(states)) if len(states) == 1 else "Unknown"
        return {"percent": pct, "energy_now_wh": now, "energy_full_wh": full,
                "power_w": complete_sum("power_w"), "status": status,
                "plugged": ac or status in ("Charging", "Full", "Not charging")}

    def sample(self):
        return {"platform": "linux", "cpu": cpu_counters((self.proc / "stat").read_text()),
                "memory": memory_info((self.proc / "meminfo").read_text()),
                "network": network_counters((self.proc / "net/dev").read_text()),
                "load1": float((self.proc / "loadavg").read_text().split()[0]),
                "uptime_seconds": float((self.proc / "uptime").read_text().split()[0]),
                "battery": self.battery()}

    def close(self):
        pass
