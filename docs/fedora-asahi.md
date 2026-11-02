# Fedora Asahi Remix 43 / 44

Target: aarch64, KDE Plasma, systemd user services, Konsole or Yakuake. Both
releases package [Byobu](https://packages.fedoraproject.org/pkgs/byobu/byobu/).
This installs terminal configuration on an existing Asahi system; it does not
install Linux, alter boot partitions or add support for a Mac model. Check the
[Asahi hardware support information](https://asahilinux.org/fedora/) separately.

From the cloned repository, as your normal desktop user:

```sh
sh setup.sh
```

The helper detects Fedora, uses `sudo dnf` for system packages, then runs
the user installer with service activation. It installs the compiler, Python,
Byobu/tmux, Bash/Zsh, Perl, fontconfig, Wayland clipboard utilities, Konsole,
Yakuake and the D-Bus Python binding. To inspect dependencies only:

```sh
sh platforms/linux/setup-fedora.sh --print-deps
```

Setup opens the **Terminal setup** Konsole profile and adds an application-menu
launcher. The profile is also available in Yakuake. It uses the bundled Hack
Nerd Font Mono at size 13, captured colors and 75% opacity. Its managed Zsh
shell loads all agent/SSH/directory/branch title rules automatically, including
on Fedora accounts whose login shell is Bash. Global desktop hotkeys remain
under your control.

Useful checks:

```sh
systemctl --user status terminal-metrics.service terminal-events.service
systemctl --user list-timers terminal-session-save.timer
~/.local/bin/terminal-stats status
fc-match 'Hack Nerd Font Mono'
```

The event service listens to logind resume and KDE/GNOME screen-unlock events; it
does not poll the process table or power logs. An initial awake/unlock badge
appears after the corresponding event. Other desktops can write events using
`terminal-stats event wake` / `terminal-stats event unlock`; the supplied unlock
bridge targets KDE's ScreenSaver D-Bus API.

CPU groups use Apple's [M1 device-tree CPU types](https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/apple/t8103.dtsi)
and M2 types where exposed through each CPU's `of_node`, with a complete
two-tier `cpu_capacity` fallback. Missing topology stays unknown. Core counts
and CPU IDs are discovered; the Mac's six-E/four-P layout is never assumed.

The CI workflow includes Fedora 43 and 44 containers on an ARM runner. It
checks builds, fixture tests, staging and real Linux `/proc` sampling. It
cannot validate Apple's battery driver, a live KDE session, graphics/font
rasterization or a systemd desktop login. Those checks remain pending on the
actual Asahi laptop. The current Mac services are untouched by repo tests.

CPU quota enforcement on Linux remains unimplemented; see
`platforms/linux/cpu-limit-interface.json`.
