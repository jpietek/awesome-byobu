#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
"${CC:-cc}" -O2 -Wall -Wextra native/status_stream.c -o build/tmux-metrics-status
if [ "$(uname -s)" = Darwin ]; then
    "${CC:-cc}" -O2 -Wall -Wextra native/macos_sensor.c -framework IOKit -framework CoreFoundation -o build/tmux-metrics-sensor
    "${CC:-cc}" -O2 -Wall -Wextra -fobjc-arc native/macos_events.m -framework AppKit -o build/tmux-metrics-events
fi
