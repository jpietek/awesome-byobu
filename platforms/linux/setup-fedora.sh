#!/bin/sh
# Compatibility entry point; setup.sh now handles both operating systems.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
packages='gcc python3 byobu tmux bash zsh perl perl-Fcntl procps-ng which python3-gobject-base fontconfig xdg-utils wl-clipboard konsole yakuake'
if [ "${1:-}" = --print-deps ]; then
    printf 'sudo dnf install %s\n' "$packages"
    exit 0
fi
exec "$repo/setup.sh" "$@"
