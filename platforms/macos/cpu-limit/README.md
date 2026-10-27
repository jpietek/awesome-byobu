# Terminal CPU budget

Installed for Jan on 2026-10-26. The current configured limit is **450% shared CPU time** across
jobs descended from the user's Byobu/tmux, iTerm2, Codex (including its app-server),
and Claude processes. Here 100% means one core's CPU time; 450% is 4.5 cores,
or 75% of this Mac's six efficiency cores when the jobs run there. Jan clarified
on 2026-10-27 that the goal is to leave roughly 25% E-core headroom. The previous
emergency setting of 25% meant one quarter of a single core and was too restrictive
for that goal. This does not reserve or pin
physical cores, change QoS, or cap unrelated macOS/security software.
Other processes can use the intended headroom, and brief bursts remain possible.

## Restore after a macOS update

Run `~/setup-cpu-limit.sh` as the normal logged-in user. This self-contained shell
script embeds the controller source, control command, build tools and license.
It rebuilds the native binary before stopping the current limiter, backs up files,
then restores the two LaunchAgents and verifies their configuration. The default
is 25% target E-core headroom: 450% aggregate job CPU time on this six-E-core Mac.

Use `~/setup-cpu-limit.sh --check` to verify the payload and build without changing
installed files or services. `--headroom 35` targets a larger reserve; `--extract
NEW_DIRECTORY` makes the embedded source available for inspection. Apple Command
Line Tools supply clang and Python; the Homebrew cpulimit installation is not
required by this recovery script. If the tools were removed, run
`xcode-select --install` and rerun after installation finishes.

Backups are saved in `~/.local/state/byobu-cpu-cap/restore-backups/`. The installer
attempts to restore the previous files and services if installation fails. Keep
a copy of `~/setup-cpu-limit.sh` outside the laptop too. It restores CPU limiting;
Hammerspoon/keyboard configuration is separate.

After changing the controller or control command, regenerate the embedded
snapshot with `python3 ~/.local/src/byobu-cpu-cap/package-setup.py`.

## Controls

```sh
byobu-cpu-cap status
byobu-cpu-cap check
byobu-cpu-cap jobs
byobu-cpu-cap set 450
byobu-cpu-cap stop
byobu-cpu-cap start
```

`stop` disables both the login service and periodic health checks, and resumes jobs paused by the limiter.
`start` enables it again. Changes to the budget persist across logins.

The limiter now uses launchd `KeepAlive=true`. A second LaunchAgent,
`com.jan.terminal-cpu-cap.health`, runs `byobu-cpu-cap check` at login and every
60 seconds. It verifies the current launchd PID, a fresh heartbeat, the configured
budget, and a live recovery watchdog. It repairs a missing/stalled controller or
budget mismatch. It also verifies the `terminal-and-agent-jobs-v2` coverage marker,
so the earlier terminal-only controller cannot pass its check. An observed CPU sample above the budget tolerance is logged for
inspection rather than being falsely reported as healthy. Periodic timing is
subject to macOS scheduling and sleep.

`~/.local/state/byobu-cpu-cap/health.json` records the most recent check and
`health.log` records repairs or over-budget samples. A management lock serializes
configuration changes and checks. The recovery path and a healthy no-restart
check were both verified during setup.

The service is `com.jan.terminal-cpu-cap`, configured in
`~/Library/LaunchAgents/com.jan.terminal-cpu-cap.plist`. Logs and a small current
status file live in `~/.local/state/byobu-cpu-cap/`. The executable is
`~/.local/libexec/cpulimit-terminal`; the control command is
`~/.local/bin/byobu-cpu-cap`.

## Implementation and limits

Homebrew's `/opt/homebrew/bin/cpulimit` is unchanged. Its 0.2 source is vendored
under `cpulimit-0.2/`, with its original GPL license. The source archive's SHA256
is `64312f9ac569ddcadb615593cd002c94b76e93a0d4625d3ce1abb49e08e2c2da`, matching
the Homebrew formula. This local fork routes its macOS entry point to the new
`terminal_control.c` backend; it is not the unmodified Homebrew binary.

The stock macOS backend discovers only immediate children and does not convert
Mach CPU time using the Apple Silicon timebase. An isolated nested-worker probe
ran at 169.5% despite a requested 50% limit. The replacement backend:

- Converts Mach time to seconds before accounting for CPU use.
- Tracks descendants recursively, including newly observed workers, under one
  token budget. Once observed, a job remains tracked if its parent exits.
- Treats Codex/app-server and Claude as independent roots, including native
  version-named Claude executables. The original terminal-only setup missed
  tests and browser validation launched directly by Codex's app-server; that
  coverage gap was corrected on 2026-10-27. Agent UI processes stay exempt;
  their Python, build, test and headless-browser descendants are limited.
- Exempts terminal UIs, shells, SSH/mosh and other terminal transports,
  Claude/Codex front ends, common terminal editors,
  status helpers, and limit controllers. Their CPU is outside the budget.
- SSH was initially included in the job throttle; it was explicitly exempted
  after SSH lag was reported. The updated native binary is installed and active.
- Uses short SIGSTOP/SIGCONT pauses. Jobs may take longer, and wall-clock tests
  can time out. No per-core affinity or kernel CPU quota is claimed.
- Checks PID plus process start time before signals, leaves already suspended
  processes alone, and resumes only processes it paused.
- Has a separate watchdog that resumes paused jobs if the controller crashes
  or becomes unresponsive. A lock prevents duplicate service instances.

This is an average sampled budget, not an instantaneous ceiling. Very short
processes can finish between samples; jobs already orphaned before the service
starts cannot be attributed to a terminal. Programs started by another service
on a terminal job's behalf may not be descendants. Shell computation and agent
UI CPU are exempt. The budget therefore does not guarantee a particular total
E-core utilization or two idle cores.

## Rebuild and isolated checks

```sh
cd ~/.local/src/byobu-cpu-cap
sh build.sh
python3 probe.py --limiter ./cpulimit-terminal --seconds 7 --limit 50
python3 probe.py --limiter ./cpulimit-terminal --workers 6 --seconds 10 --limit 400
python3 test_recovery.py
```

The probes create and clean up their own processes. Recovery checks exercise
SIGTERM, SIGKILL, and preservation of a preexisting user suspension. Install a
new binary only while the service is stopped:

```sh
byobu-cpu-cap stop
install -m 755 cpulimit-terminal ~/.local/libexec/cpulimit-terminal
byobu-cpu-cap start
```

The local binary supports attached PID mode (`-p PID`, optionally `-i`) and
`--terminal-jobs`. It does not implement the stock executable-name or command
launch modes. Use the unchanged Homebrew tool for its original CLI.
