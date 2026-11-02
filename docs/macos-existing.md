# Add links to an existing Mac setup

The main `setup.sh` installs a complete managed terminal. If you already have
your own Byobu/iTerm profile and only want file links, use this smaller migration
from the checkout. It needs Python 3.9+, tmux and Vim already installed.

Inside your existing Byobu session:

```sh
python3 -m terminal_setup.macos_customizations --profile 'Yakuake' --socket "$(tmux display-message -p '#{socket_path}')"
```

Replace `Yakuake` with your dynamic iTerm profile name. Repeat `--profile` for
multiple profiles. Use `--no-hammerspoon` for native Cmd-click only.

This adds the link helper, file-type routing and Ctrl+Shift+C/V mappings,
and stores the existing tmux socket in `~/.config/awesome-byobu/links.json`.
It preserves other profile fields and custom rules and installs only the
Hammerspoon Ctrl-click bridge; existing paste/trackpad controls keep ownership
of their gestures. It does not reload tmux, restart services or change panes.

Reload Hammerspoon from its menu. iTerm reloads dynamic profiles automatically;
if an already-open window retains old settings, open the profile again and
reattach. Existing legacy Smart Selection actions retain their expression mode;
in that case relative links use the most recently active attached tmux client.

Backups and a `manifest.json` are written under
`~/.local/state/terminal-setup/link-backups/`. Each manifest maps changed paths
to their backups; `null` means the file was newly created. Restore the listed
backups and remove newly created files to undo, then reload Hammerspoon.

Test in the source checkout:

```sh
~/.local/bin/terminal-open-link --dry-run README.md:1
printf '%s\n' 'README.md:1' 'docs/link-test.html' 'docs/images/awesome-byobu-macos-demo.png' 'https://example.com/'
```

Cmd-click the printed text, or use the optional Hammerspoon Ctrl-click shortcut.
With an existing Option/Command swap, **physical Option-click** sends native
Cmd-click and works without Hammerspoon. Use the native shortcut if Ctrl-click
is unreliable; the migration does not change your physical modifier mappings.

Code and text go to
a new Vim tab; HTML/URLs use installed Chromium, then Chrome, then your default
browser. Images, PDFs, media, office files, archives and unknown file types open
in their default apps. Directories open in the file manager. No browser
installation or default-browser change is performed.
