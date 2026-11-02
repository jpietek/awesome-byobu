#!/bin/sh
# Compatibility entry point; setup.sh now handles both operating systems.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "${1:-}" = --print-deps ]; then
    exec sh "$repo/setup.sh" --print-deps fedora
fi
exec sh "$repo/setup.sh" "$@"
