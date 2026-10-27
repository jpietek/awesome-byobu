#!/usr/bin/env python3
"""Small, isolated CPU-limit probe; never targets existing user processes."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time


def workload(role, count, seconds):
    if role == "worker":
        start = time.process_time()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for _ in range(10000):
                pass
        print(json.dumps({"cpu_seconds": time.process_time() - start}), flush=True)
        return
    children = [subprocess.Popen([
        sys.executable, __file__, "--role", "middle" if role == "root" else "worker",
        "--workers", str(count), "--seconds", str(seconds),
    ]) for _ in range(1 if role == "root" else count)]
    for child in children:
        child.wait()


def probe(limiter, workers, seconds, limit):
    root = subprocess.Popen([
        sys.executable, __file__, "--role", "root", "--workers", str(workers),
        "--seconds", str(seconds),
    ], stdout=subprocess.PIPE, text=True, start_new_session=True)
    controller = None
    start = time.monotonic()
    try:
        controller = subprocess.Popen([
            limiter, "-i", "-p", str(root.pid), "-l", str(limit),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        output, _ = root.communicate(timeout=seconds * 5 + 10)
        wall = time.monotonic() - start
        cpu = sum(json.loads(line)["cpu_seconds"] for line in output.splitlines())
        print(json.dumps({"limiter": limiter, "limit_percent": limit,
                          "workers": workers, "wall_seconds": round(wall, 2),
                          "measured_percent": round(100 * cpu / wall, 1)}))
    finally:
        if controller:
            controller.terminate()
            try:
                _, errors = controller.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                controller.kill()
                _, errors = controller.communicate()
            if errors:
                print(errors[:1000], file=sys.stderr)
        try:
            os.killpg(root.pid, signal.SIGCONT)
            os.killpg(root.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        root.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["root", "middle", "worker"])
    parser.add_argument("--limiter", default="/opt/homebrew/bin/cpulimit")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if args.role:
        workload(args.role, args.workers, args.seconds)
    else:
        probe(args.limiter, args.workers, args.seconds, args.limit)
