#!/bin/sh
# CPU limiter recovery snapshot. Embedded source; no existing limiter required.
# Default: jobs use 75% of E-core-equivalent CPU time, leaving 25% target headroom.
# This is an average job budget, not a reservation of physical CPU cores.
set -eu

usage() {
    cat <<'USAGE'
Usage: ~/setup-cpu-limit.sh [--headroom PERCENT]
       ~/setup-cpu-limit.sh --check
       ~/setup-cpu-limit.sh --extract NEW_DIRECTORY

Rebuild and restore the CPU limiter for Codex, Claude, Byobu/tmux and iTerm jobs.
Default: 25% E-core headroom (450% job CPU time on six E-cores).
Restores login startup, crash recovery, and a coverage/health check every 60s.
Run as your normal logged-in user, without sudo.

  --headroom N   Target unused E-core capacity, 0..99; default 25.
  --check        Verify embedded source and compile, without changing services.
  --extract DIR  Extract embedded files for inspection; DIR must not exist.
  --help         Show this help.

Requires Apple's Command Line Tools (clang and Python 3). If missing, install
them using xcode-select --install, then rerun this script. No Homebrew package
or source download is needed. Existing files are backed up before installation.
This restores CPU limiting; it does not modify keyboard/Hammerspoon settings.
USAGE
}

die() { printf '%s\n' "$*" >&2; exit 1; }
cleanup() {
    if [ -n "${cpu_setup_tmp:-}" ]; then /bin/rm -rf "$cpu_setup_tmp"; fi
}

main() {
    cpu_setup_mode=install
    cpu_setup_headroom=25
    cpu_setup_extract=
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --headroom)
                [ "$#" -ge 2 ] || die '--headroom needs a percentage.'
                cpu_setup_headroom=$2
                shift 2 ;;
            --check) cpu_setup_mode=check; shift ;;
            --extract)
                [ "$#" -ge 2 ] || die '--extract needs a new directory.'
                cpu_setup_mode=extract; cpu_setup_extract=$2; shift 2 ;;
            --help|-h) usage; return ;;
            *) usage >&2; die "Unknown option: $1" ;;
        esac
    done
    case "$cpu_setup_headroom" in ''|*[!0-9]*) die 'Headroom must be an integer from 0 to 99.' ;; esac
    [ "$cpu_setup_headroom" -le 99 ] || die 'Headroom must be from 0 to 99.'
    [ "$(/usr/bin/uname -s)" = Darwin ] || die 'This setup is for macOS.'
    [ "$(/usr/bin/id -u)" -ne 0 ] || die 'Run as your normal logged-in user, without sudo.'
    umask 077
    cpu_setup_tmp=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/cpu-limit-restore.XXXXXX")
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    emit_payload > "$cpu_setup_tmp/payload.b64"
    /usr/bin/base64 -D < "$cpu_setup_tmp/payload.b64" > "$cpu_setup_tmp/payload.tar.gz"
    cpu_setup_sha=$(/usr/bin/shasum -a 256 "$cpu_setup_tmp/payload.tar.gz")
    cpu_setup_sha=${cpu_setup_sha%% *}
    [ "$cpu_setup_sha" = '@@PAYLOAD_SHA256@@' ] || die 'Embedded source checksum failed.'
    /usr/bin/tar -xzf "$cpu_setup_tmp/payload.tar.gz" -C "$cpu_setup_tmp"
    cpu_setup_payload="$cpu_setup_tmp/payload"
    if [ "$cpu_setup_mode" = extract ]; then
        [ -n "$cpu_setup_extract" ] && [ ! -e "$cpu_setup_extract" ] || die 'Extraction directory must not exist.'
        /bin/mkdir -p "$cpu_setup_extract"
        /bin/cp -R "$cpu_setup_payload/." "$cpu_setup_extract/"
        printf 'Source extracted to %s\n' "$cpu_setup_extract"
        return
    fi
    if ! /usr/bin/xcrun --find clang >/dev/null 2>&1; then
        die 'Apple Command Line Tools are missing/broken. Run: xcode-select --install ; then rerun this script.'
    fi
    cpu_setup_python=
    for cpu_setup_candidate in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if [ -x "$cpu_setup_candidate" ] && "$cpu_setup_candidate" -c 'import sys,json,plistlib,fcntl; assert sys.version_info >= (3,8)' >/dev/null 2>&1; then
            cpu_setup_python=$cpu_setup_candidate
            break
        fi
    done
    [ -n "$cpu_setup_python" ] || die 'Python 3 is missing. Install Apple Command Line Tools, then rerun this script.'
    if [ "$cpu_setup_mode" = install ]; then
        /bin/launchctl print "gui/$(/usr/bin/id -u)" >/dev/null 2>&1 || die 'Log into the Mac desktop first, then run this script as that user.'
    fi
    cpu_setup_ecores=$(/usr/sbin/sysctl -n hw.perflevel1.physicalcpu 2>/dev/null) || die 'Cannot determine E-core count on this Mac.'
    cpu_setup_limit=$("$cpu_setup_python" -c 'import sys; n=int(sys.argv[1]); h=int(sys.argv[2]); assert n>0; print(n*(100-h))' "$cpu_setup_ecores" "$cpu_setup_headroom")
    printf 'Building embedded limiter: %s E-cores, %s%% target headroom, %s%% shared job budget.\n' "$cpu_setup_ecores" "$cpu_setup_headroom" "$cpu_setup_limit"
    # Use the selected Apple compiler regardless of the caller's PATH.
    PATH=/usr/bin:/bin:/usr/sbin:/sbin
    export PATH
    /bin/sh "$cpu_setup_payload/source/build.sh"
    "$cpu_setup_payload/source/cpulimit-terminal" --help >/dev/null
    "$cpu_setup_python" -c 'import ast,sys; [ast.parse(open(p).read(),filename=p) for p in sys.argv[1:]]' "$cpu_setup_payload/byobu-cpu-cap" "$cpu_setup_payload/source/restore-install.py"
    if [ "$cpu_setup_mode" = check ]; then
        printf '%s\n' 'Checksum, source syntax and native build passed. Installed files and services were not changed.'
        return
    fi
    "$cpu_setup_python" "$cpu_setup_payload/source/restore-install.py" "$cpu_setup_payload" "$cpu_setup_limit" "$cpu_setup_headroom" "$cpu_setup_ecores" "$cpu_setup_sha"
}
