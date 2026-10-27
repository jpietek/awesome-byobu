#!/bin/sh
set -eu
cd "$(dirname "$0")"
python=${PYTHON:-python3}
"$python" -c 'import sys; assert sys.version_info >= (3,9), "Python 3.9+ required"'
/bin/sh ./build.sh
exec "$python" -m terminal_setup.install "$@"
