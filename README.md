# Terminal setup

Byobu/tmux customization, a shared host-stats collector, session persistence, and
the macOS CPU-limiter recovery setup. Extracted from the working Mac configuration
on 2026-10-27. The repository contains configuration and source, not saved pane
contents, conversation IDs, shell history, credentials, or machine binaries.

The existing Mac installation is separate. Creating or testing this repository
does not replace its running services or reload its tmux server.

## One-command restore

Unzip `terminal-setup.zip`. On macOS, double-click **Setup.command**. On either
supported system, run this from the extracted folder:

```sh
sh setup.sh
```

This installs dependencies, builds the native helpers, backs up replaced
configuration, installs fonts and the full tab-name rules, enables services,
verifies live CPU/RAM readings and opens the configured terminal. It also adds
a **Terminal setup** launcher for subsequent use. See the
[one-click guide](docs/one-click.md) for clean/existing installations and limits.

Automatic bootstrap targets **macOS 15+** and **Fedora 43/44**. Apple Silicon
is the primary Mac target; Intel support is best-effort and untested locally.
OS administrator, developer-tool and automation dialogs may require approval.

The Linux target is **Fedora Asahi Remix 43 or 44 on aarch64**, with KDE Plasma
and Konsole/Yakuake. The original plots, palette, font and terminal profile are
preserved; see [appearance fidelity](docs/appearance.md) and the
[Fedora setup guide](docs/fedora-asahi.md).

## Platform support

| Component | macOS | Linux |
|---|---|---|
| Byobu layout, Ctrl-A bindings, scrollback and tab labels | Included | Shared configuration |
| Per-core CPU, memory, load, network | Mach/native backend, tested on this Mac | `/proc` backend, tested with fixtures |
| Battery charge and estimated remaining time | IOKit | `/sys/class/power_supply`, including charge/energy unit conversion |
| P/E-core groups | Discovered from IORegistry | Apple M1/M2 device-tree types, or complete two-tier CPU capacity data; otherwise unknown |
| Collector startup | LaunchAgent | systemd user service |
| Session save/restore | LaunchAgents | systemd user service/timer |
| Wake/unlock age | Native AppKit event agent; no Hammerspoon dependency | logind and KDE/GNOME D-Bus bridge, requires python3-gobject-base |
| Font and terminal colors | Named iTerm profile | Named Konsole/Yakuake profile with the same palette and bundled Hack Nerd Font Mono |
| Job CPU budget | Existing Codex/Claude-aware limiter and recovery script | Interface prepared; quota backend is **not implemented** |

Linux collection and service generation have fixture coverage. An actual Linux
desktop/service activation has not been tested locally. The CI workflow runs on
Ubuntu/macOS and Fedora 43/44 ARM containers when the repository is hosted and
CI is enabled. Fedora container coverage is userspace coverage, not an Asahi
hardware or KDE session test.

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

The original Byobu setup (including the old `tmux-metrics` binary whose source
was not found) was archived separately under `~/Backups/`. Its available native
sources are retained under `platforms/macos/legacy-stats/`. The new collector is
fully buildable from this repository. Upstream plugin, font and cpulimit license
files are retained with their respective sources.
