"""OS adapters return the same raw counter/sensor dictionary.

sample(): cpu[{id, busy, total, kind}], memory{total, used, wired, compressed,
cached, pressure}, network{interface: [rx_bytes, tx_bytes]}, battery (or None),
load1 and uptime_seconds. Missing optional measurements are None, not zero.
All memory/network quantities are bytes; energy is Wh; power is W.
"""
import platform


def create_backend(interval=0.5, sensor=None):
    system = platform.system()
    if system == "Linux":
        from .linux import LinuxBackend
        return LinuxBackend()
    if system == "Darwin":
        from .macos import MacOSBackend
        return MacOSBackend(interval, sensor)
    raise RuntimeError("Unsupported platform: " + system)
