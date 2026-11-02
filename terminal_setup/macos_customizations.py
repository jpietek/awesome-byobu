"""Portable iTerm file links, terminal bindings, and optional Hammerspoon loader."""
import json
import argparse
import datetime
import os
from pathlib import Path
import platform
import shlex
import shutil
import sys


def iterm_customizations(home, socket=None):
    opener = shlex.quote(str(Path(home) / '.local/bin/terminal-open-link'))
    socket = socket or str(Path(home) / '.local/state/terminal-setup/tmux' / ('tmux-' + str(os.getuid())) / 'default')
    opener += ' --socket=' + shlex.quote(socket)
    # iTerm shell-escapes its capture substitutions. Do not wrap them in quotes.
    command = opener + r' --target=\(matches[0]) --tty=\(session.tty)'
    rules = []
    for pattern, title in (
        (r'https?://[^\s<>"`]+', 'Open URL in Chromium'),
        (r'(?:~?/)?[\w.@+-]+(?:/[\w.@+-]+)*\.[A-Za-z0-9_]+(?::[1-9][0-9]*(?::[1-9][0-9]*)?)?(?:[?#][^\s<>"`()]+)?', 'Open file in Vim / HTML in browser'),
    ):
        rules.append({'notes': 'Awesome Byobu: ' + title, 'regex': pattern,
            'precision': 'very_high', 'actions': [{'action': 2, 'title': title, 'parameter': command}]})
    return {
        'Semantic History': {'action': 'command', 'text': opener + r' --target=\1 --line=\2 --tty=\(session.tty)'},
        'Smart Selection Rules': rules,
        'Smart Selection Actions Use Interpolated Strings': True,
        'Keyboard Map': {
            '0x63-0x60000': {'Action': 25, 'Text': 'Copy'},
            '0x76-0x60000': {'Action': 25, 'Text': 'Paste'},
            '0x72-0x40000': {'Action': 11, 'Text': '0x12'},
            '0xf702-0x40000': {'Action': 10, 'Text': '[1;5D'},
            '0xf703-0x40000': {'Action': 10, 'Text': '[1;5C'},
            '0xf72c-0x0': {'Action': 10, 'Text': '[5~'},
            '0xf72d-0x0': {'Action': 10, 'Text': '[6~'},
        },
    }


def hammerspoon_files(root, home):
    root, home = Path(root), Path(home)
    files = {}
    for source in (root / 'platforms/macos/hammerspoon').glob('*.lua'):
        files[home / '.hammerspoon/awesome_byobu' / source.name] = (source.read_bytes(), 0o644)
    init = home / '.hammerspoon/init.lua'
    existing = init.read_text() if init.exists() else ''
    marker = '-- Awesome Byobu terminal controls'
    if marker not in existing:
        existing += '\n' + marker + '\nrequire("awesome_byobu").start()\n'
        files[init] = (existing.encode(), 0o644)
    elif 'require("awesome_byobu").start({linksOnly=true})' in existing:
        files[init] = (existing.replace('require("awesome_byobu").start({linksOnly=true})',
            'require("awesome_byobu").start()').encode(), 0o644)
    return files


def merge_profile(profile, home, socket=None):
    changes = iterm_customizations(home, socket)
    keys = dict(profile.get('Keyboard Map', {}))
    keys.update(changes.pop('Keyboard Map'))
    old_rules = [rule for rule in profile.get('Smart Selection Rules', [])
                 if not rule.get('notes', '').startswith('Awesome Byobu:')]
    if old_rules and not profile.get('Smart Selection Actions Use Interpolated Strings'):
        # Do not reinterpret the user's existing action expressions. Legacy
        # iTerm substitutions lack a client tty; the helper uses latest activity.
        changes['Smart Selection Actions Use Interpolated Strings'] = False
        for rule in changes['Smart Selection Rules']:
            rule['actions'][0]['parameter'] = shlex.quote(str(Path(home) / '.local/bin/terminal-open-link')) + \
                (' --socket=' + shlex.quote(socket) if socket else '') + r' --target=\0'
    changes['Smart Selection Rules'] += old_rules
    profile.update(changes)
    profile['Keyboard Map'] = keys


def apply_existing(home, names, socket, with_hammerspoon=True):
    """Install link controls only; preserve the existing tmux server and services."""
    root, home = Path(__file__).resolve().parents[1], Path(home)
    dynamic = home / 'Library/Application Support/iTerm2/DynamicProfiles'
    files, found = {}, set()
    for path in dynamic.glob('*.json'):
        data = json.loads(path.read_text())
        changed = False
        for profile in data.get('Profiles', []):
            if profile.get('Name') in names:
                merge_profile(profile, home, socket)
                found.add(profile['Name']); changed = True
        if changed:
            files[path] = ((json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
    missing = set(names) - found
    if missing:
        raise ValueError('Dynamic iTerm profiles not found: ' + ', '.join(sorted(missing)))
    # Self-contained executable, independent of a checkout or preexisting package.
    wrapper = '#!' + sys.executable + '\n' + (root / 'terminal_setup/links.py').read_text()
    wrapper += '\nif __name__ == "__main__":\n    sys.exit(main())\n'
    wrapper = wrapper.replace('import argparse\n', 'import argparse\nimport sys\n', 1)
    files[home / '.local/bin/terminal-open-link'] = (wrapper.encode(), 0o755)
    config_path = home / '.config/awesome-byobu/links.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config.update(socket=socket, tmux=shutil.which('tmux'), vim=shutil.which('vim'))
    files[config_path] = ((json.dumps(config, indent=2) + '\n').encode(), 0o644)
    if with_hammerspoon:
        # Existing users may already own middle-click and three-finger paste.
        # Install only Ctrl-click; do not start a second gesture recognizer.
        files.update(hammerspoon_files(root, home))
        init = home / '.hammerspoon/init.lua'
        if init in files:
            data, mode = files[init]
            files[init] = (data.replace(b'require("awesome_byobu").start()',
                b'require("awesome_byobu").start({linksOnly=true})'), mode)
    backup = home / '.local/state/terminal-setup/link-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    saved = {}
    try:
        for path, (data, mode) in files.items():
            old = backup / path.relative_to(home)
            if path.exists() or path.is_symlink():
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, old, follow_symlinks=False)
                saved[path] = old
            else:
                saved[path] = None
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.awesome-byobu-' + str(os.getpid()))
            temporary.write_bytes(data); temporary.chmod(mode); temporary.replace(path)
    except BaseException:
        for path, old in reversed(list(saved.items())):
            path.unlink(missing_ok=True)
            if old:
                shutil.copy2(old, path, follow_symlinks=False)
        raise
    backup.mkdir(parents=True, exist_ok=True)
    manifest = {str(path): str(old) if old else None for path, old in saved.items()}
    (backup/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Updated profiles: ' + ', '.join(sorted(found)))
    print('Backup and restore manifest: ' + str(backup))
    print('Reload Hammerspoon config to enable Ctrl-click; reopen the profile if iTerm retains old settings.')
    return backup


def main():
    parser = argparse.ArgumentParser(description='Add file links to existing Mac Byobu profiles without reinstalling services')
    parser.add_argument('--profile', action='append', required=True)
    parser.add_argument('--socket', required=True, help='Existing tmux socket from tmux display-message -p "#{socket_path}"')
    parser.add_argument('--no-hammerspoon', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('This migration is for existing macOS/iTerm installations')
    apply_existing(Path.home(), args.profile, args.socket, not args.no_hammerspoon)


if __name__ == '__main__':
    main()
