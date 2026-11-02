#!/bin/sh
# Arch's official repos do not ship Byobu. Build verified upstream source as user.
set -eu
byobu_version=7.19
byobu_digest=d246c57ba380b4fa680b783997ff189c51b9f4dd12edf4b719a1f2d84a2e1d2e
byobu_prefix="$HOME/.local/opt/byobu-$byobu_version"
if [ -x "$byobu_prefix/bin/byobu" ] && [ -f "$byobu_prefix/share/byobu/profiles/tmux" ]; then
    exit 0
fi
byobu_work=$(mktemp -d)
trap 'rm -rf "$byobu_work"' EXIT HUP INT TERM
curl --fail --location --proto '=https' --tlsv1.2 \
    "https://github.com/dustinkirkland/byobu/archive/refs/tags/$byobu_version.tar.gz" \
    -o "$byobu_work/byobu.tar.gz"
printf '%s  %s\n' "$byobu_digest" "$byobu_work/byobu.tar.gz" | sha256sum -c -
tar -xzf "$byobu_work/byobu.tar.gz" -C "$byobu_work"
cd "$byobu_work/byobu-$byobu_version"
autoreconf --force --install
./configure --prefix="$byobu_prefix" --disable-trustmux
make
make install
