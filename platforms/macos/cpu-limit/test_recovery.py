#!/usr/bin/env python3
"""Check graceful exit, crash recovery and user-suspended-job preservation."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def worker():
    return subprocess.Popen([sys.executable, str(HERE / "probe.py"), "--role", "worker",
                             "--seconds", "3"], stdout=subprocess.PIPE, text=True,
                            start_new_session=True)


def clean(process):
    if process.poll() is None:
        os.kill(process.pid, signal.SIGCONT)
        process.terminate()
    process.communicate(timeout=5)


def wait_stopped(process):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        pid, status = os.waitpid(process.pid, os.WUNTRACED | os.WNOHANG)
        if pid:
            assert os.WIFSTOPPED(status), f"worker exited unexpectedly: {status}"
            return
        time.sleep(0.01)
    raise AssertionError("limiter did not pause worker")


for ending in (signal.SIGTERM, signal.SIGKILL):
    job = worker()
    controller = subprocess.Popen([str(HERE / "cpulimit-terminal"), "-p", str(job.pid),
                                   "-l", "10"], stdout=subprocess.DEVNULL)
    try:
        wait_stopped(job)
        os.kill(controller.pid, ending)
        controller.wait(timeout=5)
        job.communicate(timeout=6)
        assert job.returncode == 0
        print(f"PASS: {ending.name} resumes paused job", flush=True)
    finally:
        if controller.poll() is None:
            controller.terminate()
            controller.wait(timeout=5)
        clean(job)

job = worker()
controller = None
try:
    os.kill(job.pid, signal.SIGSTOP)
    wait_stopped(job)
    controller = subprocess.Popen([str(HERE / "cpulimit-terminal"), "-p", str(job.pid),
                                   "-l", "10"], stdout=subprocess.DEVNULL)
    time.sleep(0.3)
    controller.terminate()
    controller.wait(timeout=5)
    state = subprocess.check_output(["ps", "-p", str(job.pid), "-o", "stat="], text=True)
    assert "T" in state, state
    print("PASS: previously suspended job stays suspended", flush=True)
finally:
    if controller and controller.poll() is None:
        controller.terminate()
        controller.wait(timeout=5)
    clean(job)
