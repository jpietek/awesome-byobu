"""Install or stage configuration. Never kill/restart the user's tmux server."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from .services import service_files
from .appearance import appearance_files
from .macos_customizations import hammerspoon_files

ROOT = Path(__file__).resolve().parents[1]


def tmux_quote(value):
    # tmux parses these quoted tokens; reject newline/control injection.
    text = str(value)
    if any(ord(c) < 32 for c in text):
        raise ValueError("Control characters in installation path")
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def config_text(name, home, system):
    home = Path(home)
    text = (ROOT / "config/byobu" / name).read_text()
    status = shlex.join([str(home / '.local/bin/tmux-metrics-status'), str(home / '.cache/terminal-setup/status.tmux')])
    values = {"@STATUS_FORMAT@": "#(" + status + ")#[fg=#111827,bg=#facc15,bold] %b %d %H:%M ",
              "@BASE_PROFILE@": str(home / '.config/byobu/base.tmux'),
              "@COLOR_PATH@": str(home / '.config/byobu/color.tmux'),
              "@DATETIME_PATH@": str(home / '.config/byobu/datetime.tmux'),
              "@PROFILE_PATH@": str(home / '.config/byobu/profile.tmux'),
              "@KEYBINDINGS_PATH@": str(home / '.config/byobu/keybindings.tmux'),
              "@EXTRA_PATH@": str(home / '.config/byobu/.tmux.conf'),
              "@SHELLINIT_PATH@": str(home / '.config/byobu/shellinit.tmux'),
              "@AUTO_RENAME@": "#{?#{==:pane_current_path," + str(home) + "},~,#{b:pane_current_path}}",
              "@PERSISTENCE_PATH@": str(home / '.config/byobu/persistence.tmux'),
              "@LOCAL_TEST@": "test -f " + shlex.quote(str(home / '.config/byobu/local.tmux')),
              "@LOCAL_SOURCE@": "source-file " + tmux_quote(home / '.config/byobu/local.tmux'),
              "@URL_OPEN_COMMAND@": shlex.join([str(home / '.local/bin/url-open')]),
              "@ZSH_PATH@": shutil.which('zsh') or '/bin/zsh',
              "@SHELL_COMMAND@": "exec " + shlex.join([str(home / '.local/bin/terminal-shell')]),
              "@RESURRECT_DIR@": str(home / '.local/state/terminal-setup/byobu/resurrect'),
              "@RESURRECT_COMMAND@": shlex.join([str(home / '.config/byobu/plugins/tmux-resurrect/resurrect.tmux')]),
              "@CONTINUUM_COMMAND@": shlex.join([str(home / '.config/byobu/plugins/tmux-continuum/continuum.tmux')]),
              "@AGENT_SAVE_COMMAND@": shlex.join([str(home / '.local/bin/byobu-agent-resume'), 'save'])}
    for key, value in values.items():
        text = text.replace(key, tmux_quote(value))
    # Preserve the original Apple-hardware badge on macOS and Fedora Asahi.
    text = text.replace("@LOGO@", "")
    return text


def install(home, system, activate=False, stage=False, with_hammerspoon=False):
    home = Path(home).resolve()
    if system not in ("Darwin", "Linux"):
        raise RuntimeError("Unsupported platform: " + system)
    if activate and stage:
        raise RuntimeError("Staging cannot activate services")
    if stage and home == Path.home().resolve():
        raise RuntimeError("Choose a separate directory for staging, not your real home")
    if activate and home != Path.home().resolve():
        raise RuntimeError("Only the current user's home can activate services")
    files = {}
    if with_hammerspoon:
        if system != 'Darwin':
            raise RuntimeError('Hammerspoon is macOS-only')
        files.update(hammerspoon_files(ROOT, home))
    files.update(appearance_files(ROOT, home, system))
    link_config = home / '.config/awesome-byobu/links.json'
    if not link_config.exists():
        files[link_config] = ((json.dumps({
            'socket': str(home / '.local/state/terminal-setup/tmux' / ('tmux-' + str(os.getuid())) / 'default'),
            'tmux': shutil.which('tmux'), 'vim': shutil.which('vim')}, indent=2) + '\n').encode(), 0o644)
    zsh = shutil.which('zsh')
    if not zsh:
        raise RuntimeError('Zsh is required for the full tab-name rules; run setup.sh to install dependencies')
    byobu = shutil.which('byobu-tmux') or shutil.which('byobu')
    if not byobu:
        raise RuntimeError('Byobu is required; run setup.sh to install dependencies')
    prefix = Path(byobu).resolve().parents[1]
    stock = prefix / 'share/byobu/profiles/tmux'
    if not stock.is_file():
        raise RuntimeError('Cannot locate the installed Byobu profile: ' + str(stock))
    # The stock janitor rewrites shell rc files and cleans shared Byobu caches.
    # Our installer supplies the files it needs; keep its bindings/settings,
    # but do not launch that migration process in a different user's setup.
    base = '\n'.join(line for line in stock.read_text().splitlines()
                     if 'byobu-janitor' not in line or line.lstrip().startswith('#')) + '\n'
    files[home / '.config/byobu/base.tmux'] = (base.encode(), 0o644)
    substitutions = {'@PYTHON@': sys.executable, '@INSTALL_HOME@': shlex.quote(str(home)),
                     '@BYOBU_PREFIX@': shlex.quote(str(prefix)),
                     '@TOOLS_BIN@': shlex.quote(str(Path(shutil.which('tmux') or '/usr/bin/tmux').parent)),
                     '@ZSH_PATH@': shlex.quote(zsh), '@INSTALL_HOME_PYTHON@': repr(str(home)),
                     '@PACKAGE_PATH@': repr(str(home / '.local/share/terminal-setup')),
                     '@SESSION_ENV@': shlex.quote(str(home / '.local/share/terminal-setup/session-env.sh'))}
    def substitute(text):
        for key, value in substitutions.items():
            text = text.replace(key, value)
        return text
    files[home / '.local/share/terminal-setup/session-env.sh'] = (substitute((ROOT / 'config/session-env.sh').read_text()).encode(), 0o644)
    files[home / '.local/share/terminal-setup/zsh/.zshrc'] = ((ROOT / 'config/zshrc').read_bytes(), 0o644)
    for path in (ROOT / "terminal_setup").rglob("*.py"):
        files[home / ".local/share/terminal-setup" / path.relative_to(ROOT)] = (path.read_bytes(), 0o644)
    for path in (ROOT / "vendor").rglob("*"):
        if path.is_file() and not path.is_symlink() and ".git" not in path.parts:
            files[home / ".config/byobu/plugins" / path.relative_to(ROOT / "vendor")] = (path.read_bytes(), path.stat().st_mode & 0o777)
    for path in (ROOT / "scripts").iterdir():
        if path.is_file():
            data = substitute(path.read_text())
            files[home / ".local/bin" / path.name] = (data.encode(), 0o755)
    wrapper = ("#!" + sys.executable + "\nimport sys\nsys.path.insert(0, " +
               repr(str(home / ".local/share/terminal-setup")) + ")\nfrom terminal_setup.cli import main\nsys.exit(main())\n")
    files[home / ".local/bin/terminal-stats"] = (wrapper.encode(), 0o755)
    for name in ("tmux-metrics-status",) + (("tmux-metrics-sensor", "tmux-metrics-events") if system == "Darwin" else ()):
        path = ROOT / "build" / name
        if not path.is_file():
            raise RuntimeError("Missing native helper; run ./build.sh first: " + name)
        target = home / (".local/bin" if name.endswith("status") else ".local/libexec") / name
        files[target] = (path.read_bytes(), 0o755)
    for path in (ROOT / "config/byobu").iterdir():
        if not path.is_file():
            continue
        data = config_text(path.name, home, system)
        files[home / ".config/byobu" / path.name] = (data.encode(), 0o644)
    files[home / ".config/byobu/backend"] = (b"BYOBU_BACKEND=tmux\n", 0o644)
    # The managed shell reads personal settings without rewriting shell files.
    shellinit = home / '.config/byobu/shellinit.tmux'
    if not shellinit.exists():
        files[shellinit] = (b'', 0o644)
    for relative, data in service_files(system, home).items():
        files[home / relative] = (data, 0o644)
    # Backups precede writes; private pane history and agent-session state are
    # never copied into the repository or overwritten by this installer.
    backup = home / ".local/state/terminal-setup/install-backups" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + str(os.getpid()))
    saved = {}
    try:
        for path, (data, mode) in files.items():
            if path.exists() or path.is_symlink():
                backup.mkdir(mode=0o700, parents=True, exist_ok=True)
                old = backup / path.relative_to(home)
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, old, follow_symlinks=False); saved[path] = old
            else:
                saved[path] = None
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".install-" + str(os.getpid()))
            temporary.write_bytes(data); temporary.chmod(mode); temporary.replace(path)
        (home / ".local/state/terminal-setup/logs").mkdir(parents=True, exist_ok=True)
    except BaseException:
        for path, old in reversed(list(saved.items())):
            if old:
                path.unlink(missing_ok=True)
                shutil.copy2(old, path, follow_symlinks=False)
            else:
                path.unlink(missing_ok=True)
        raise
    print(("Staged" if stage else "Installed") + " terminal setup under " + str(home))
    print("Existing files backed up under " + str(backup))
    if activate:
        activate_services(system, home)
    else:
        print("Services were not activated. Use --activate when ready; existing tmux sessions are left running.")


def activate_services(system, home):
    if system == "Darwin":
        domain = "gui/" + str(os.getuid())
        for name in ("metrics", "events", "session-restore", "session-save"):
            label = "org.terminal-setup." + name
            subprocess.run(["launchctl", "bootout", domain + "/" + label], capture_output=True)
            subprocess.run(["launchctl", "enable", domain + "/" + label], check=True)
            subprocess.run(["launchctl", "bootstrap", domain, str(home / "Library/LaunchAgents" / (label + ".plist"))], check=True)
    else:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "terminal-metrics.service", "terminal-events.service", "terminal-session-restore.service", "terminal-session-save.timer"], check=True)
        subprocess.run(["systemctl", "--user", "restart", "terminal-metrics.service", "terminal-events.service"], check=True)
        if shutil.which("fc-cache"):
            subprocess.run(["fc-cache", str(home / '.local/share/fonts/terminal-setup')], check=True)
    subprocess.run(['/bin/sh', '-c', '. "$1"; if tmux has-session 2>/dev/null; then tmux source-file "$BYOBU_CONFIG_DIR/terminal-setup.tmux"; fi',
                    'terminal-setup', str(home / '.local/share/terminal-setup/session-env.sh')], check=True)
    print("Metrics and session services enabled; managed tmux configuration applied.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, help="write into a test home without service activation")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--with-hammerspoon", action="store_true")
    args = parser.parse_args()
    if os.getuid() == 0 and not args.stage:
        parser.error("Run as your normal user, without sudo")
    install(args.stage or Path.home(), platform.system(), args.activate, bool(args.stage), args.with_hammerspoon)


if __name__ == "__main__":
    main()
