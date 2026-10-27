#!/bin/sh
# Create a source-and-font installer archive from the committed repository.
set -eu
cd "$(dirname "$0")"
[ -z "$(git status --porcelain)" ] || { echo 'Commit changes before packaging.' >&2; exit 1; }
archive=${1:-"$HOME/terminal-setup.zip"}
case "$archive" in /*) ;; *) archive="$(pwd)/$archive" ;; esac
mkdir -p "$(dirname "$archive")"
umask 077
git archive --format=zip --prefix=terminal-setup/ --output="$archive" HEAD
(
    cd "$(dirname "$archive")"
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$(basename "$archive")"
    else
        sha256sum "$(basename "$archive")"
    fi
) > "$archive.sha256"
printf 'Installer archive: %s\n' "$archive"
