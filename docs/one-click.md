# Clean or existing machine setup

For one-line downloads and full package lists, start with the [README](../README.md).

Copy **awesome-byobu.zip** to the target machine and extract it. Git and Python
are not needed to begin setup. The archive contains source, pinned plugins,
the exact fonts, and all setup scripts.

* **Mac:** double-click `Setup.command` in the extracted folder.
* **Fedora, Ubuntu/Debian, Arch:** open a terminal in that folder and run `sh setup.sh`.
* The same `sh setup.sh` command also works on Mac.

The bootstrap installs dependencies, compiles native components, installs the
configuration, enables login services, checks that the collector is producing
fresh measurements, and opens the correct terminal profile. Internet access is
needed for missing packages. The OS/package manager may ask for an administrator
password, developer-tool installation, or permission to open iTerm via automation.
Those OS approvals cannot be silently skipped by a one-click script.

After setup, launch **Terminal setup** from `~/Applications` on Mac or the
application menu on Fedora. This always opens the configured profile. You do
not have to select fonts or manually choose a profile. Fedora opens Konsole;
the same profile is available in Yakuake.

## Included

* Two-row Byobu layout, original colors, fonts, opacity, Ctrl-A navigation and scrollback.
* Rainbow per-core CPU bars, CPU/load figures, smoothed half-cell RAM plot,
  network rates, battery gauge/percentage/estimate, date and wake/unlock badges.
* Directory and Git-branch tab names, detached-head abbreviations, worktree
  support, shortening rules, `codex:` / `claude:` labels while agents run,
  SSH/gcloud destination names, remote-host labels, and normal titles after exit.
* The same Zsh hooks on both OSes. Personal Zsh settings are read first; the
  account's default shell and its rc files are not rewritten.
* One shared stats collector with login startup, automatic restart, periodic
  session saves, startup/session restoration, and a live collector check.

No manual font installation, shell-hook editing or service creation is needed.
Agent programs/accounts themselves are not bundled: names work when the locally
installed Codex/Claude/SSH/gcloud commands run. Remote shells need the supplied
tab-label hook installed remotely to send remote directory/branch changes.

## Existing configurations

Replaced files are backed up under
`~/.local/state/terminal-setup/install-backups/TIMESTAMP/`. Rerunning is supported.
Machine-specific `~/.config/byobu/local.tmux` and existing shell-init hooks are
preserved, so their explicit overrides can still affect the theme.

The managed tmux socket is under `~/.local/state/terminal-setup/tmux/`; its
session history is under `~/.local/state/terminal-setup/byobu/`. Other running
tmux sessions are not killed or automatically adopted. Setup reapplies the
theme to its own server and restarts only its own metrics/event services.
Original `~/.local/state/byobu/` snapshots and private agent conversations are
not automatically imported or included in the portable archive.

## Compatibility and checks

Automatic Mac bootstrap targets **macOS 15 or newer**, following the current
[Homebrew requirements](https://docs.brew.sh/Installation). Apple Silicon is the
primary target; Intel builds are supported by the source but remain untested
here, and Homebrew treats Intel as Tier 3. Older macOS is not claimed supported.
No fixed CPU count, username or memory size is assumed. A desktop without a
battery simply has no battery badge. P/E groups require topology information.

Linux bootstrap targets Fedora 43+, Ubuntu 24.04+, Debian 12+, and current Arch,
including Fedora Asahi Remix on supported Apple hardware. A systemd desktop
login is required. The KDE and GNOME unlock interfaces are supported;
other desktops may need an event bridge. This is an application setup, not an
Asahi OS installer or hardware-enablement package.

```sh
sh setup.sh --no-open             # install/verify without opening a window
sh setup.sh --stage /tmp/preview  # no packages/services/UI; existing build tools required
~/.local/bin/terminal-setup-check # verify the live collector again
```

The optional Apple Silicon job limiter can be restored with
`sh setup.sh --with-cpu-limit`. Linux CPU quotas remain unimplemented.
`sh setup.sh --with-hammerspoon` adds terminal-only paste/trackpad controls,
Ctrl-click links and a Ctrl+grave iTerm toggle. See the README shortcut table.
Physical modifier remaps and desktop-wide GUI shortcuts remain separate.

Validation covers staged clean/existing homes, personal-shell preservation,
backup creation, title rules, metrics, a real isolated tmux session save/restore,
and Mac helper startup. Dependency bootstrap on a freshly erased Mac, Intel
hardware, and an actual Fedora Asahi desktop have not been run locally.

To build a new portable ZIP after committing changes, run `sh package.sh` in
the Git checkout. It writes `~/awesome-byobu.zip` and a SHA-256 checksum file.
