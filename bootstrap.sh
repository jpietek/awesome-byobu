#!/bin/sh
# Download the complete source bundle; no Git or Python needed beforehand.
set -eu
[ "$(id -u)" -ne 0 ] || { echo 'Run as your desktop user, without sudo.' >&2; exit 1; }
command -v curl >/dev/null || { echo 'Install curl first; see the README command for your OS.' >&2; exit 1; }
command -v tar >/dev/null || { echo 'Install tar and gzip first.' >&2; exit 1; }
bootstrap_tmp=$(mktemp -d)
trap 'rm -rf "$bootstrap_tmp"' EXIT HUP INT TERM
curl --fail --location --proto '=https' --tlsv1.2 \
    https://github.com/jpietek/awesome-byobu/archive/refs/heads/main.tar.gz \
    -o "$bootstrap_tmp/source.tar.gz"
tar -xzf "$bootstrap_tmp/source.tar.gz" -C "$bootstrap_tmp"
cd "$bootstrap_tmp/awesome-byobu-main"
sh setup.sh "$@"
