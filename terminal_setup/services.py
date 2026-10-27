"""Service configuration is generated, keeping OS details outside collection."""
from pathlib import Path
import plistlib


def systemd_arg(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def service_files(system, home):
    home = Path(home)
    binary = home / ".local/bin"
    log = home / ".local/state/terminal-setup/logs"
    commands = {"metrics": [str(binary / "terminal-stats"), "collect"],
                "session-save": [str(binary / "byobu-session-save")],
                "session-restore": [str(binary / "byobu-session-restore")]}
    if system == "Darwin":
        result = {}
        for name, command in commands.items():
            label = "org.terminal-setup." + name
            data = {"Label": label, "ProgramArguments": command, "RunAtLoad": True,
                    "ProcessType": "Standard", "StandardOutPath": str(log / (name + ".log")),
                    "StandardErrorPath": str(log / (name + ".log"))}
            if name == "metrics":
                data.update(KeepAlive=True, ThrottleInterval=10, ExitTimeOut=10)
            elif name == "session-save":
                data["StartInterval"] = 60
            result["Library/LaunchAgents/" + label + ".plist"] = plistlib.dumps(data)
        return result
    if system != "Linux":
        raise ValueError("Unsupported service platform: " + system)
    result = {}
    for name, command in commands.items():
        unit = "terminal-" + name + ".service"
        data = "[Unit]\nDescription=Terminal setup " + name + "\n\n[Service]\n"
        data += "Type=" + ("simple" if name == "metrics" else "oneshot") + "\n"
        data += "ExecStart=" + " ".join(systemd_arg(v) for v in command) + "\n"
        if name == "metrics":
            data += "Restart=on-failure\nRestartSec=5\n"
        data += "\n[Install]\nWantedBy=default.target\n"
        result[".config/systemd/user/" + unit] = data.encode()
    result[".config/systemd/user/terminal-session-save.timer"] = (
        "[Unit]\nDescription=Save Byobu sessions every minute\n\n[Timer]\n"
        "OnStartupSec=90\nOnUnitActiveSec=60\nUnit=terminal-session-save.service\n\n"
        "[Install]\nWantedBy=timers.target\n").encode()
    result[".config/systemd/user/terminal-events.service"] = (
        "[Unit]\nDescription=Terminal wake/unlock events (Fedora KDE)\nPartOf=graphical-session.target\n\n"
        "[Service]\nType=simple\nExecStart=" + systemd_arg(binary / "terminal-stats") + " watch-events\n"
        "Restart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=graphical-session.target\n").encode()
    return result
