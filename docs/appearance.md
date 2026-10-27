# Recreating the original appearance

The first repository version preserved the layout but simplified several status
segments. The current renderer restores the details found in the live Mac
configuration and the original `tmux-cpuspark`, `tmux-memstack`, `tmux-watts`,
`tmux-metrics-bat`, `tmux-net`, `tmux-awake` and `tmux-unlock` helpers.

| Display | Preserved behavior |
|---|---|
| Tabs | Full upper row; blue active tab, slate inactive tabs, yellow activity indicator |
| Lower row | Green Apple-hardware badge on the left, metrics/date on the right |
| CPU plot | One ▁–█ glyph per CPU, P group before E group, original eight-color cool-to-red scale |
| CPU/load badges | Cyan CPU percentage with one decimal, pink load with two decimals |
| Memory | Eight cells with half-cell transitions: wired red, applications green, compressed purple, cached gray, empty dim |
| Memory movement | Original 0.7/0.3 exponential smoothing every two seconds; percentage uses actual current usage |
| Pressure | Original normal/yellow/red backgrounds when the OS supplies that measurement |
| Network | Adjacent green/cyan badges, compact B/K/M/G rates and trailing ↓/↑ arrows |
| Battery | Yellow four-part charge gauge, percentage, AC bolt and rounded h/mm estimate; + while charging |
| Awake/unlock | Purple duration, orange Nerd Font lock icon and duration |
| Date | Yellow `%b %d %H:%M` badge |
| Other settings | Ctrl-A bindings, scrolling, million-line history, tab labels, Byobu message colors, Ctrl-A Ctrl-Z suspension prevention |

The original iTerm **Yakuake** profile uses **Hack Nerd Font Mono 13**, normal
character spacing, bold text, a 16-color palette and 25% transparency. These
appearance fields are captured in `config/terminal/appearance.json`. The four
exact font files (Nerd Fonts 3.5.1, Hack 3.003) are included with their notices
and SHA-256 hashes under `assets/fonts/`.

Installation adds a named **Terminal setup** profile to iTerm on macOS or
Konsole/Yakuake on Fedora. Select it in the terminal. It does not replace your
default profile or globally change desktop shortcuts. The same Apple badge is
retained for the Apple hardware on both OSes. The renderer is shared, so the
same supplied measurements yield the same tmux text, glyphs and RGB colors.

## What “exact” does and does not mean

This preserves the Byobu theme and its plot styles. Pixel-identical rendering
between iTerm/macOS and Konsole/KDE is not guaranteed: font rasterization,
display scale, opacity/compositing and glyph widths are terminal/desktop
properties. Use the bundled font and true color; compare at the same terminal
width so tmux's 140-column right-hand area is not clipped.

Measurements differ between operating systems. Linux memory categories do not
exactly correspond to macOS wired/application/compressed memory; unavailable
Mac memory-pressure values are not invented. P/E grouping appears only when
the kernel identifies the topology. Battery data depends on the Asahi driver.
Wake/unlock segments stay absent until their timestamp source supplies an event.
The new wake bridge records resume events; the old Mac helper scanned `pmset`
for deliberate lid/menu sleeps. Rate accounting and counter-reset handling
have been corrected; the old helper's erroneous sub-KiB-to-M label conversion
is not reproduced.

Project-specific `demo-links` shortcuts, saved private session contents,
Hammerspoon's global keyboard/trackpad remaps and iTerm's global drop-down
hotkey are outside this portable theme. The untouched original Byobu archive
remains in `~/Backups/` for reference. The Linux job limiter is still an interface,
not an active quota implementation.

Tests pin the memory half-cell output, palette/order/icons/spacing, memory
smoothing cadence, terminal font/palette export and Apple CPU grouping. An
actual Fedora Asahi desktop comparison remains to be done.
