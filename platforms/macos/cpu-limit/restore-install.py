#!/usr/bin/env python3
"""Install the staged recovery payload; preserve/restore the previous services."""
import datetime
import fcntl
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".restore-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(payload, limit, headroom, ecores, source_sha):
    root = Path.home()
    source = root / ".local/src/byobu-cpu-cap"
    loader = importlib.machinery.SourceFileLoader("cpu_cap_restore_control", str(payload / "byobu-cpu-cap"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cap = importlib.util.module_from_spec(spec)
    loader.exec_module(cap)
    cap.STATE.mkdir(parents=True, exist_ok=True)
    cap.STATE.chmod(0o700)
    cap.PLIST.parent.mkdir(parents=True, exist_ok=True)
    with (cap.STATE / "management.lock").open("a") as management:
        try:
            fcntl.flock(management, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("CPU settings are being changed by another process; rerun in a moment.")
        old_main, old_monitor = cap.loaded(), cap.loaded(cap.MONITOR_SERVICE)
        backup = cap.STATE / "restore-backups" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + str(os.getpid()))
        backup.mkdir(parents=True)
        saved = {}

        def remember(path):
            if path in saved:
                return
            if path.exists():
                destination = backup / path.relative_to(root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                saved[path] = destination
            else:
                saved[path] = None

        def write(path, content, mode=0o644):
            remember(path)
            atomic_write(path, content, mode)

        def unload():
            for service in (cap.MONITOR_SERVICE, cap.SERVICE):
                cap.launchctl("disable", service)
                if cap.loaded(service):
                    cap.launchctl("bootout", service)
            # The controller/watchdog must finish resuming their paused jobs.
            with (cap.STATE / "controller.lock").open("a") as controller:
                deadline = time.monotonic() + 12
                while True:
                    try:
                        fcntl.flock(controller, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Previous CPU controller did not exit; files have not been replaced.")
                        time.sleep(0.1)

        for path in (cap.PLIST, cap.MONITOR_PLIST, cap.STATE / "setup.json"):
            remember(path)
        try:
            unload()
            for path in sorted((payload / "source").rglob("*")):
                if path.is_file() and path.name != "cpulimit-terminal":
                    write(source / path.relative_to(payload / "source"), path.read_bytes())
            write(source / "cpulimit-terminal", (payload / "source/cpulimit-terminal").read_bytes(), 0o755)
            write(cap.BINARY, (payload / "source/cpulimit-terminal").read_bytes(), 0o755)
            control = (payload / "byobu-cpu-cap").read_text().splitlines(keepends=True)
            control[0] = "#!" + sys.executable + "\n"
            write(root / ".local/bin/byobu-cpu-cap", "".join(control).encode(), 0o755)
            cap.start(limit, announce=False)
            cap.health_check()
            cap.verified_status()
            if not cap.loaded(cap.MONITOR_SERVICE):
                raise RuntimeError("Periodic checker did not start.")
            write(cap.STATE / "setup.json", (json.dumps({
                "installed_at": datetime.datetime.now().astimezone().isoformat(),
                "headroom_percent": headroom, "efficiency_cores": ecores,
                "limit_percent": limit, "payload_sha256": source_sha,
                "python": sys.executable, "backup": str(backup),
            }, indent=2) + "\n").encode(), 0o600)
            cap.status()
            print("Recovery setup installed. Previous files: " + str(backup))
            print("Control: ~/.local/bin/byobu-cpu-cap status | stop | start | set PERCENT")
        except BaseException:
            errors = []
            try:
                unload()
            except Exception as error:
                # Never overwrite a binary still in use by a controller that
                # failed to stop; retain the backup for explicit recovery.
                raise RuntimeError("Setup failed and controller shutdown failed; backup retained at " + str(backup)) from error
            for path, previous in reversed(list(saved.items())):
                try:
                    if previous is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_write(path, previous.read_bytes(), previous.stat().st_mode & 0o777)
                except Exception as error:
                    errors.append(str(error))
            for service, plist, was_loaded in ((cap.SERVICE, cap.PLIST, old_main),
                                               (cap.MONITOR_SERVICE, cap.MONITOR_PLIST, old_monitor)):
                if was_loaded and plist.exists():
                    try:
                        cap.launchctl("enable", service)
                        cap.launchctl("bootstrap", cap.DOMAIN, str(plist))
                    except Exception as error:
                        errors.append(str(error))
            print("Setup failed; previous setup restoration attempted. Backup: " + str(backup), file=sys.stderr)
            if errors:
                print("Restore errors: " + "; ".join(errors), file=sys.stderr)
            raise


if __name__ == "__main__":
    try:
        run(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr or "", file=sys.stderr)
        sys.exit(1)
