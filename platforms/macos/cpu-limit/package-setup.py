#!/usr/bin/env python3
"""Create one portable recovery shell script from the current limiter sources."""
import base64
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import textwrap

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path.home() / "setup-cpu-limit.sh")
args = parser.parse_args()
files = {}
for name in ("terminal_control.c", "build.sh", "README.md", "probe.py",
             "test_recovery.py", "cpulimit-v0.2.tar.gz", "setup-header.sh",
             "restore-install.py", "package-setup.py", "byobu-cpu-cap"):
    files["payload/source/" + name] = (root / name).read_bytes()
for path in sorted((root / "cpulimit-0.2").rglob("*")):
    if path.is_file() and not path.is_symlink():
        files["payload/source/" + path.relative_to(root).as_posix()] = path.read_bytes()
files["payload/byobu-cpu-cap"] = (root / "byobu-cpu-cap").read_bytes()
raw = io.BytesIO()
with tarfile.open(fileobj=raw, mode="w") as archive:
    for name, data in sorted(files.items()):
        entry = tarfile.TarInfo(name)
        entry.size = len(data)
        entry.mode = 0o644
        entry.mtime = 0
        archive.addfile(entry, io.BytesIO(data))
compressed = gzip.compress(raw.getvalue(), mtime=0)
digest = hashlib.sha256(compressed).hexdigest()
header = (root / "setup-header.sh").read_text().replace("@@PAYLOAD_SHA256@@", digest)
encoded = "\n".join(textwrap.wrap(base64.b64encode(compressed).decode(), 76))
script = (header + "\n\nemit_payload() {\n    cat <<'CPU_LIMIT_SOURCE_PAYLOAD'\n" +
          encoded + "\nCPU_LIMIT_SOURCE_PAYLOAD\n}\n\nmain \"$@\"\n")
destination = args.output.expanduser().resolve()
destination.parent.mkdir(parents=True, exist_ok=True)
temporary = destination.with_name(destination.name + ".new")
temporary.write_text(script)
temporary.chmod(0o755)
temporary.replace(destination)
print(str(destination) + " (" + str(len(script.encode())) + " bytes; embedded source " + digest + ")")
