# Terminal setup

Byobu/tmux customization, a shared host-stats collector, session persistence, and
the macOS CPU-limiter recovery setup. Extracted from the working Mac configuration
on 2026-10-27. The repository contains configuration and source, not saved pane
contents, conversation IDs, shell history, credentials, or machine binaries.

The existing Mac installation is separate. Creating or testing this repository
does not replace its running services or reload its tmux server.

## Platform support

| Component | macOS | Linux |
|---|---|---|
| Byobu layout, Ctrl-A bindings, scrollback and tab labels | Included | Shared configuration |
| Per-core CPU, memory, load, network | Mach/native backend, tested on this Mac | `/proc` backend, tested with fixtures |
| Battery charge and estimated remaining time | IOKit | `/sys/class/power_supply`, including charge/energy unit conversion |
| P/E-core labels | Discovered from IORegistry | Unknown unless a future topology adapter supplies them |
| Collector startup | LaunchAgent | systemd user service |
| Session save/restore | LaunchAgents | systemd user service/timer |
| Wake/unlock age | Optional Hammerspoon event bridge; existing unlock file supported | Event interface ready; desktop integration is optional |
| Job CPU budget | Existing Codex/Claude-aware limiter and recovery script | Interface prepared; quota backend is **not implemented** |

Linux collection and service generation have fixture coverage. An actual Linux
desktop/service activation has not been tested locally. The CI workflow runs on
Ubuntu and macOS when the repository is hosted and CI is enabled.

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
On Debian/Ubuntu the corresponding packages are `python3`, `build-essential`,
`byobu`, `tmux`, `bash`, and `perl`. No Python packages are required.

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
./install.sh             # install files and service definitions; do not activate
./install.sh --activate  # install and enable the collector/session services
~/.local/bin/start-byobu
```

Installation backs up replaced files under
`~/.local/state/terminal-setup/install-backups/`. It does not terminate/restart
your tmux server. An existing server keeps its loaded configuration until you
explicitly reload it or start a new one. On macOS, activation disables the older
`com.jan.byobu-session-*` jobs to avoid duplicate autosave timers.

For shell tab titles, source `~/.config/byobu/tab-labels.zsh` from `.zshrc`, or
`tab-labels.bash` from `.bashrc`. Existing prompt configuration is preserved.
Machine/project-specific bindings belong in `~/.config/byobu/local.tmux`, which
is not tracked. Clipboard URL opening uses `open` on macOS and `xdg-open` with
`wl-paste` or `xclip` on Linux; an explicit URL needs no clipboard helper.

Session snapshots stay in `~/.local/state/byobu/`. The bundled tmux-resurrect
and tmux-continuum versions are pinned in `vendor/versions.json`, including the
local empty-pane-title fix. Agent resumption is best-effort and uses the local
agent CLIs/session state. Existing sessions are never replaced at service startup.

For wake/unlock timestamps, the optional macOS module is
`platforms/macos/terminal_stats_events.lua`. Load it into Hammerspoon and retain
the object returned by `.start()`. Other desktop/session integrations can call
`terminal-stats event wake` or `terminal-stats event unlock`. No Linux desktop
event hooks are installed automatically. "Awake" means time since the recorded
wake event, not the previous helper's deliberate-sleep-only heuristic.

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
fully buildable from this repository. Upstream plugin and cpulimit license files
are retained with their respective sources.
