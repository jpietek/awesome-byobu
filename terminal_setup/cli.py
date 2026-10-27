import argparse
import json
from pathlib import Path
import sys
import time
from .collector import atomic_write, collect


def main(argv=None):
    parser = argparse.ArgumentParser(description="Shared terminal stats, with macOS/Linux adapters")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache/terminal-setup")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".local/state/terminal-setup")
    sub = parser.add_subparsers(dest="action", required=True)
    service = sub.add_parser("collect")
    service.add_argument("--interval", type=float, default=0.5)
    service.add_argument("--count", type=int)
    service.add_argument("--sensor", type=Path)
    sub.add_parser("status")
    event = sub.add_parser("event")
    event.add_argument("kind", choices=("wake", "unlock"))
    args = parser.parse_args(argv)
    try:
        if args.action == "collect":
            if args.count is not None and args.count < 1:
                parser.error("--count must be positive")
            collect(args.cache_dir, args.state_dir, args.interval, args.count, args.sensor)
        elif args.action == "event":
            atomic_write(args.state_dir / ("last-" + args.kind), str(int(time.time())) + "\n")
        else:
            snapshot = json.loads((args.cache_dir / "metrics.json").read_text())
            snapshot["stale"] = not 0 <= time.time() - snapshot["updated_at"] <= 5
            print(json.dumps(snapshot, indent=2))
            return 1 if snapshot["stale"] else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
