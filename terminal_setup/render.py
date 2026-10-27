"""Shared tmux presentation for both OS backends."""

COLORS = ["#38bdf8", "#22d3ee", "#4ade80", "#a3e635", "#facc15", "#fb923c", "#f87171", "#ef4444"]
GLYPHS = "▁▂▃▄▅▆▇█"


def badge(color, text):
    return "#[fg=#111827,bg=" + color + ",bold] " + text + " #[default]"


def duration(seconds):
    minutes = int(max(0, seconds) / 60)
    if minutes >= 1440:
        return "%dd%dh" % (minutes // 1440, minutes % 1440 // 60)
    return "%dh%02dm" % (minutes // 60, minutes % 60) if minutes >= 60 else str(minutes) + "m"


def rate(value):
    if value is None:
        return "--"
    for unit in ("B/s", "KiB/s", "MiB/s", "GiB/s"):
        if value < 1024 or unit == "GiB/s":
            return ("%.0f" if value >= 100 else "%.1f") % value + unit
        value /= 1024


def render(snapshot):
    cores = snapshot["cpu"]["cores"]
    groups = {kind: [c for c in cores if c["kind"] == kind] for kind in ("performance", "efficiency", "unknown")}
    sparks = []
    for kind, rows in groups.items():
        if not rows:
            continue
        line = ""
        for row in rows:
            pct = row["percent"]
            level = min(7, max(0, int(pct * 8 / 100))) if pct is not None else 0
            line += "#[fg=" + COLORS[level] + "]" + (GLYPHS[level] if pct is not None else "·")
        sparks.append(line)
    cpu = snapshot["cpu"]["percent"]
    parts = ["#[bg=default,bold] " + " ".join(sparks) + " #[default]",
             badge("#38bdf8", "--" if cpu is None else "%.0f%%" % cpu),
             badge("#f472b6", "%.2f" % snapshot["load1"])]
    mem = snapshot["memory"]; total = mem["total"]
    if total > 0:
        used = min(total, max(0, mem["used"]))
        wired = min(used, max(0, mem["wired"]))
        comp = min(used - wired, max(0, mem["compressed"]))
        sizes = [wired, used - wired - comp, comp, min(total - used, max(0, mem["cached"]))]
        colors = ["#f87171", "#4ade80", "#c084fc", "#64748b"]
        ends = []; acc = 0
        for size in sizes:
            acc += size; ends.append(min(8, int(acc / total * 8 + 0.5)))
        pressure = mem.get("pressure") or 0
        background = "#dc2626" if pressure >= 4 else "#facc15" if pressure >= 2 else "#1e293b"
        foreground = "#111827" if pressure >= 2 else "#e2e8f0"
        bar = "#[bg=" + background + "] "
        for cell in range(8):
            index = next((i for i, end in enumerate(ends) if cell < end), None)
            bar += "#[fg=" + (colors[index] if index is not None else "#334155") + "]" + ("█" if index is not None else "░")
        parts.append(bar + "#[fg=" + foreground + "] %.0f%% #[default]" % (used / total * 100))
    net = snapshot["network"]
    parts += [badge("#4ade80", "↓" + rate(net["rx_bytes_per_second"])), badge("#22d3ee", "↑" + rate(net["tx_bytes_per_second"]))]
    battery = snapshot.get("battery")
    if battery and battery.get("percent") is not None:
        pct = min(100, max(0, battery["percent"]))
        filled = min(4, max(0, int((pct + 12) // 25)))
        text = "▰" * filled + "▱" * (4 - filled) + " %.0f%%" % pct
        if battery.get("plugged"):
            text += " ϟ"
        if battery.get("eta_seconds") is not None:
            text += " " + ("+" if battery["status"] == "Charging" else "") + duration(battery["eta_seconds"])
        parts.append(badge("#fde047", text))
    for key, color, label in (("awake_seconds", "#a78bfa", "awake "), ("unlocked_seconds", "#fb923c", "unlock ")):
        if snapshot.get(key) is not None:
            parts.append(badge(color, label + duration(snapshot[key])))
    return " ".join(parts)
