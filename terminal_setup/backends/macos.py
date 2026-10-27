"""One persistent native Mach/IOKit sensor, never one exec per status redraw."""
import json
import select
import subprocess
from pathlib import Path


class MacOSBackend:
    def __init__(self, interval=0.5, sensor=None):
        source_root = Path(__file__).resolve().parents[2]
        path = Path(sensor) if sensor else source_root / "build/tmux-metrics-sensor"
        if not path.is_file():
            path = Path.home() / ".local/libexec/tmux-metrics-sensor"
        if not path.is_file():
            raise RuntimeError("macOS sensor is missing; run ./build.sh or ./install.sh")
        self.process = subprocess.Popen([str(path), "--interval", str(interval)],
                                        stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
        self.timeout = max(10, interval * 3)

    def sample(self):
        if not select.select([self.process.stdout], [], [], self.timeout)[0]:
            raise RuntimeError("macOS metrics sensor stopped responding")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("macOS metrics sensor exited")
        return json.loads(line)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
        self.process.stdout.close()
