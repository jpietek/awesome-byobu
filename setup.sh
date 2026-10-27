#!/bin/sh
# One entry point for a clean or existing desktop. Run as the normal user.
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
    --help|-h)
        echo 'Usage: sh setup.sh [--no-open] [--with-cpu-limit]'
        echo '       sh setup.sh --stage DIRECTORY    (no dependency installation or activation)'
        exit 0 ;;
    --stage) exec ./install.sh "$@" ;;
esac
setup_open=yes
setup_cpu=no
while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-open) setup_open=no ;;
        --with-cpu-limit) setup_cpu=yes ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done
[ "$(id -u)" -ne 0 ] || { echo 'Run setup as your desktop user, without sudo.' >&2; exit 1; }
case "$(uname -s)" in
    Darwin)
        setup_major=$(/usr/bin/sw_vers -productVersion); setup_major=${setup_major%%.*}
        [ "$setup_major" -ge 15 ] || { echo 'Automatic setup targets macOS 15 or newer (Homebrew requirement).' >&2; exit 1; }
        if [ "$setup_cpu" = yes ]; then
            setup_ecores=$(/usr/sbin/sysctl -n hw.perflevel1.physicalcpu 2>/dev/null || echo 0)
            [ "$setup_ecores" -gt 0 ] || { echo 'The optional CPU limiter needs Apple Silicon E-cores. Rerun without --with-cpu-limit.' >&2; exit 1; }
        fi
        case "$(uname -m)" in
            arm64) export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" ;;
            x86_64) export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH" ;;
            *) echo 'Unsupported Mac CPU architecture.' >&2; exit 1 ;;
        esac
        if ! command -v brew >/dev/null 2>&1; then
            echo 'Installing Homebrew and Apple command line tools. Administrator approval may be needed.'
            setup_tmp=$(mktemp -d)
            trap 'rm -rf "$setup_tmp"' EXIT
            curl --fail --location --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$setup_tmp/homebrew-install.sh"
            /bin/bash "$setup_tmp/homebrew-install.sh"
        fi
        if ! /usr/bin/xcrun --find clang >/dev/null 2>&1; then
            /usr/bin/xcode-select --install || true
            echo 'Complete the Apple Command Line Tools dialog; setup will continue when clang is ready.'
            setup_wait=0
            until /usr/bin/xcrun --find clang >/dev/null 2>&1; do
                [ "$setup_wait" -lt 720 ] || { echo 'Tools are not ready. Rerun this setup after installation.' >&2; exit 1; }
                sleep 5; setup_wait=$((setup_wait + 1))
            done
        fi
        echo 'Installing Byobu, tmux, Python and iTerm2…'
        brew install byobu tmux python
        if [ ! -d /Applications/iTerm.app ] && [ ! -d "$HOME/Applications/iTerm.app" ]; then
            brew install --cask iterm2
        fi
        export PYTHON="$(command -v python3)"
        ;;
    Linux)
        . /etc/os-release
        case "$ID:$VERSION_ID" in fedora:43|fedora:44) ;; *) echo 'Automatic Linux setup targets Fedora 43/44.' >&2; exit 1 ;; esac
        [ "$setup_cpu" = no ] || { echo 'Linux CPU limiting is not implemented; rerun without --with-cpu-limit.' >&2; exit 1; }
        echo 'Installing Fedora terminal dependencies…'
        sudo dnf install -y gcc python3 byobu tmux bash zsh perl perl-Fcntl procps-ng which python3-gobject-base fontconfig xdg-utils wl-clipboard konsole yakuake
        export PYTHON=/usr/bin/python3
        export PATH="/usr/bin:/bin:$PATH"
        ;;
    *) echo 'Supported systems: macOS 15+, Fedora 43/44.' >&2; exit 1 ;;
esac
./install.sh --activate
if [ "$setup_cpu" = yes ]; then
    /bin/sh recovery/setup-cpu-limit.sh
fi
"$HOME/.local/bin/terminal-setup-check"
if [ "$setup_open" = yes ]; then
    "$HOME/.local/bin/open-terminal-setup"
fi
echo 'Terminal setup is ready. Use the Terminal setup launcher next time.'
