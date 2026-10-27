"""Shared tmux presentation for both OS backends."""

COLORS = ["#38bdf8", "#22d3ee", "#4ade80", "#a3e635", "#facc15", "#fb923c", "#f87171", "#ef4444"]
GLYPHS = "▁▂▃▄▅▆▇█"


def badge(color, text):
    return "#[fg=#111827,bg=" + color + ",bold] " + text + " "


def duration(seconds):
    minutes = int(max(0, seconds) / 60)
    if minutes >= 1440:
        return "%dd%dh" % (minutes // 1440, minutes % 1440 // 60)
    return "%dh%02dm" % (minutes // 60, minutes % 60) if minutes >= 60 else str(minutes) + "m"


def rate(value):
    if value is None:
        return "--"
    # Original compact B/K/M/G labels; arrows follow the number.
    units = ("B", "K", "M", "G")
    index = 0
    while index < 3 and value >= (1024 if index == 0 else 100):
        value /= 1024; index += 1
    if value >= 10 or index == 0:
        return "%.0f%s" % (value, units[index])
    tenths = int(value * 10 + 0.5)
    return (str(tenths // 10) + ("." + str(tenths % 10) if tenths % 10 else "") + units[index])


def memory_bar(mem):
    total = mem["total"]
    if total <= 0:
        return ""
    used = max(0, mem["used"])
    sizes = mem.get("display_segments", [mem["wired"], max(0, used - mem["wired"] - mem["compressed"]),
                                         mem["compressed"], mem["cached"]])
    ends = []; acc = 0
    for size in sizes:
        acc += max(0, size)
        ends.append(min(16, int(acc / total * 16 + 0.5)))
    colors = ["#f87171", "#4ade80", "#c084fc", "#64748b", "#334155"]
    pressure = mem.get("pressure") or 0
    bg = "#dc2626" if pressure >= 4 else "#facc15" if pressure >= 2 else "#1e293b"
    fg = "#111827" if pressure >= 2 else "#e2e8f0"
    bar = "#[fg=" + fg + ",bg=" + bg + ",bold] "
    for cell in range(8):
        left, right = [next((i for i, end in enumerate(ends) if half < end), 4)
                       for half in (cell * 2, cell * 2 + 1)]
        if left == right:
            bar += "#[fg=" + colors[left] + ",bg=" + bg + "]" + ("█" if left < 4 else "░")
        else:
            bar += "#[fg=" + colors[left] + ",bg=" + (colors[right] if right < 4 else bg) + "]▌#[bg=" + bg + "]"
    return bar + "#[fg=" + fg + "] %.0f%% #[default]" % (used / total * 100)


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
    line = ("#[bg=default,bold] " + " ".join(sparks) + " #[default]" +
            badge("#38bdf8", "--" if cpu is None else "%.1f%%" % cpu) +
            badge("#f472b6", "%.2f" % snapshot["load1"]) + "#[default] " + memory_bar(snapshot["memory"]) + " ")
    net = snapshot["network"]
    line += (badge("#4ade80", rate(net["rx_bytes_per_second"]) + "↓") +
             badge("#22d3ee", rate(net["tx_bytes_per_second"]) + "↑") + "#[default] ")
    battery = snapshot.get("battery")
    if battery and battery.get("percent") is not None:
        pct = min(100, max(0, battery["percent"]))
        filled = min(4, max(0, int((pct + 12) // 25)))
        text = "▰" * filled + "▱" * (4 - filled) + " %.0f%%" % pct
        if battery.get("plugged"):
            text += " ϟ"
        if battery.get("eta_seconds") is not None:
            minutes = int(battery["eta_seconds"] / 60 + 0.5)
            text += " " + ("+" if battery["status"] == "Charging" else "") + "%dh%02dm" % (minutes // 60, minutes % 60)
        line += badge("#fde047", text) + "#[default] "
    for key, color, label in (("awake_seconds", "#a78bfa", " "), ("unlocked_seconds", "#fb923c", "󰌾 ")):
        if snapshot.get(key) is not None:
            line += badge(color, label + duration(snapshot[key]))
    return line + "#[default] "
