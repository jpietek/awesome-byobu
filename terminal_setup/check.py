"""Check that the installed collector is actually publishing useful data."""
import argparse
import json
from pathlib import Path
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=float, default=15)
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args(argv)
    deadline = time.monotonic() + max(0, args.wait)
    path = args.home / '.cache/terminal-setup/metrics.json'
    while True:
        try:
            data = json.loads(path.read_text())
            if not 0 <= time.time() - data['updated_at'] <= 5:
                raise ValueError('metrics are stale')
            if not data['cpu']['cores'] or data['cpu']['percent'] is None or data['memory']['total'] <= 0:
                raise ValueError('waiting for CPU/RAM samples')
            battery = data.get('battery')
            battery_text = ('%.0f%%' % battery['percent'] if battery and battery.get('percent') is not None
                            else 'not provided by this hardware')
            print('Collector verified: %d CPUs, %.1f GiB RAM, battery %s.' %
                  (len(data['cpu']['cores']), data['memory']['total'] / 1024**3, battery_text))
            return 0
        except (OSError, ValueError, KeyError) as error:
            if time.monotonic() >= deadline:
                print('Setup files are installed, but collector verification failed: ' + str(error))
                print('Inspect terminal-metrics.service on Linux or org.terminal-setup.metrics on macOS.')
                return 1
            time.sleep(0.5)
