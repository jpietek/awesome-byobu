# Implementation notes

For installation commands, supported platforms, packages and shortcuts, see
the [README](../README.md). macOS is the primary supported desktop; Linux
desktop activation remains to be validated on target machines. Runtime paths
and service names retain `terminal-setup` for compatibility with existing installs.

## Design

One collector owns the sampling baselines and writes two atomic cache files:
`~/.cache/terminal-setup/metrics.json` (schema version 1) and `status.tmux`.
Each tmux server runs a tiny native cache reader, `tmux-metrics-status`, which
does not collect stats or fork commands on redraw. It marks missing/stale data
visibly after five seconds.

`terminal_setup/backends/` supplies raw counters in a common interface. macOS
uses one persistent native helper; Linux reads kernel files directly. Shared
code calculates CPU/network deltas, battery estimates, and the status layout.
No private `$HOME` substitution, duplicate baseline caches, or recurring
`pmset` log scans are required. CPU hotplug, counter resets, and long sampling
gaps reset baselines rather than generating artificial spikes.

Network rates sum non-loopback interfaces; VPN/bridge traffic can be counted
at multiple interfaces and is not an Internet-usage meter. Memory semantics
are OS-specific: Linux uses `MemTotal - MemAvailable`; macOS uses wired,
application and compressed memory. Optional values are `null`, not fabricated
zeros. Battery estimates use a rolling three-minute power average and reset
on charging-mode changes. They remain estimates.

Linux fields follow the [kernel `/proc` documentation](https://docs.kernel.org/filesystems/proc.html)
and [power-supply units](https://docs.kernel.org/power/power_supply_class.html).
The proposed Linux CPU-quota contract is in
`platforms/linux/cpu-limit-interface.json`; it is intentionally separate from
the working stats backend.

## Build and inspect

Requires Python 3.9+, a C compiler, Byobu, tmux, Bash and Perl. macOS's Apple
Command Line Tools provide the compiler/Python; Homebrew can provide Byobu/tmux.
Use `sh setup.sh` to install dependencies and activate services. The collector
itself needs no Python packages; the Fedora wake/unlock bridge uses the
distribution's `python3-gobject-base` package.

```sh
sh build.sh
python3 -m unittest discover -s tests -v
./install.sh --stage /tmp/terminal-setup-preview
```

Staging writes a separate home layout and does not load services. It targets the
host OS and architecture; it is not a cross-compiler. The fixture tests render
Linux service files independently on either OS.

Read actual metrics without changing the desktop setup:

```sh
python3 -m terminal_setup.cli --cache-dir /tmp/terminal-stats/cache \
  --state-dir /tmp/terminal-stats/state collect --count 3
python3 -m terminal_setup.cli --cache-dir /tmp/terminal-stats/cache status
```

## Install when ready

```sh
sh setup.sh              # full dependency/setup/verification/open flow
./install.sh             # advanced: install files only; dependencies must exist
./install.sh --activate  # advanced: install and enable services, without opening UI
~/.local/bin/start-byobu
```

Installation backs up replaced files under
`~/.local/state/terminal-setup/install-backups/`. A private tmux socket and
session-state directory keep unrelated sessions separate. Rerunning setup
refreshes its own services and server configuration without killing panes.
It does not disable unrelated/legacy service labels.

The configured terminal uses Zsh on both OSes. A managed startup file reads
your personal Zsh configuration, then installs the full tab-title hooks. It
does not rewrite `.zshrc`, `.bashrc`, or your account's login shell. Byobu's
stock bindings are retained without running its shell-migration janitor.
Machine/project-specific bindings belong in `~/.config/byobu/local.tmux`, which
is not tracked. Clipboard URL opening uses `open` on macOS and `xdg-open` with
`wl-paste` or `xclip` on Linux; an explicit URL needs no clipboard helper.

Session snapshots live in `~/.local/state/terminal-setup/byobu/`. The bundled
plugins are pinned in `vendor/versions.json`, including the empty-pane-title
fix. Only tmux-resurrect is loaded: the launcher/service owns restoration and
the timer owns saving, avoiding continuum redraw polling or competing restores.
Agent resumption is best-effort and uses the local agent CLIs/session state.
Old private snapshots are not automatically replayed into the new server.

Wake/unlock timestamps are collected by a native Mac agent or Fedora's D-Bus
bridge. Other integrations can call `terminal-stats event wake` / `event unlock`.
The optional Hammerspoon module remains archived, but is no longer needed.
"Awake" means time since a recorded resume, not the old helper's deliberate-
sleep-only heuristic. Badges appear after the first corresponding event.

## CPU recovery and archives

`recovery/setup-cpu-limit.sh` is the tested, self-contained **macOS-only** recovery
script. It restores 25% target E-core headroom (450% shared job CPU time on the
six-E-core Mac), Codex/Claude coverage, login startup, and the 60-second check.
It is an average job limit, not a hard global E-core ceiling.

```sh
sh recovery/setup-cpu-limit.sh --check
sh recovery/setup-cpu-limit.sh
python3 platforms/macos/cpu-limit/package-setup.py --output recovery/setup-cpu-limit.sh
```

The original local Byobu setup (including the old `tmux-metrics` binary whose source
was not found) was archived separately under `~/Backups/`. Its available native
sources are retained under `platforms/macos/legacy-stats/`. The new collector is
fully buildable from this repository. Upstream plugin, font and cpulimit license
files are retained with their respective sources.
