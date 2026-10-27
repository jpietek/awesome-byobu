#!/bin/sh
# Run as your normal desktop user on Fedora Asahi Remix 43 or 44.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
packages='gcc python3 byobu tmux bash zsh perl perl-Fcntl procps-ng which python3-gobject-base fontconfig xdg-utils wl-clipboard konsole yakuake'
if [ "${1:-}" = --print-deps ]; then
    printf 'sudo dnf install %s\n' "$packages"
    exit 0
fi
[ "$(uname -s)" = Linux ] || { echo 'Run this on Fedora Asahi, not macOS.' >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo 'Run as your normal user; sudo is used only for packages.' >&2; exit 1; }
. /etc/os-release
case "$ID:$VERSION_ID" in fedora:43|fedora:44) ;; *) echo 'This helper targets Fedora 43/44.' >&2; exit 1 ;; esac
# Intentional word splitting: the fixed list above contains package names only.
sudo dnf install -y $packages
exec "$repo/install.sh" --activate "$@"
