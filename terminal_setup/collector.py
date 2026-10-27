"""A single owner of counters publishes atomic cache files for all tmux clients."""
import fcntl
import json
import os
from pathlib import Path
import signal
import tempfile
import time
from .backends import create_backend
from .model import Metrics
from .render import render


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def collect(cache_dir, state_dir, interval=0.5, count=None, sensor=None):
    if not 0.1 <= interval <= 2:
        raise ValueError("Sampling interval must be from 0.1 to 2 seconds")
    cache = Path(cache_dir); state = Path(state_dir)
    cache.mkdir(parents=True, exist_ok=True); state.mkdir(parents=True, exist_ok=True)
    with (state / "collector.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A metrics collector already owns this state directory")
        stopping = False
        def stop(signum, frame):
            nonlocal stopping
            stopping = True
        previous_handlers = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
        backend = None
        try:
            backend = create_backend(interval, sensor)
            model = Metrics(state, Path.home())
            samples = 0
            while not stopping and (count is None or samples < count):
                start = time.monotonic()
                snapshot = model.update(backend.sample())
                atomic_write(cache / "metrics.json", json.dumps(snapshot, allow_nan=False) + "\n")
                atomic_write(cache / "status.tmux", render(snapshot) + "\n")
                samples += 1
                if not stopping and (count is None or samples < count):
                    time.sleep(max(0, interval - (time.monotonic() - start)))
        finally:
            if backend:
                backend.close()
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
