"""Open terminal file references in a new Vim tab, and HTML/URLs in a browser."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


def parse_reference(text, line=None):
    text = text.strip().strip('`\"\'')
    if text.startswith('(') and text.endswith('):'):
        text = text[1:-2]
    if text.startswith('(') and text.endswith(')'):
        text = text[1:-1]
    text = text.rstrip('.,;')
    while text.endswith(')') and text.count(')') > text.count('('):
        text = text[:-1]
    if not text or any(ord(c) < 32 for c in text):
        raise ValueError('Empty link or control character in link')
    if text.startswith(('http://', 'https://')):
        return text, None, None
    if text.startswith('file://'):
        url = urlsplit(text)
        if url.netloc not in ('', 'localhost'):
            raise ValueError('Only local file:// links are supported')
        text = unquote(url.path) + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')
    elif '://' in text:
        raise ValueError('Only HTTP, HTTPS and local file links are supported')
    match = re.fullmatch(r'(.+?):([1-9][0-9]*)(?::([1-9][0-9]*))?', text)
    column = None
    if match:
        text, found_line, column = match.groups()
        line = line or found_line
    if line and (not str(line).isdigit() or int(line) < 1):
        raise ValueError('Line number must be a positive integer')
    return text, int(line) if line else None, int(column) if column else None


def tmux_context(tmux, socket=None, tty=None):
    command = [tmux] + (['-S', socket] if socket else [])
    clients = subprocess.check_output(command + ['list-clients', '-F',
        '#{client_activity}\t#{client_session}\t#{client_tty}'], text=True).splitlines()
    rows = [row.split('\t', 2) for row in clients if row]
    if tty:
        rows = [row for row in rows if row[2] == tty]
    if not rows:
        raise ValueError('No attached Byobu client; open Terminal setup first')
    session = max(rows, key=lambda row: int(row[0]))[1]
    cwd = subprocess.check_output(command + ['display-message', '-p', '-t', session + ':',
        '#{pane_current_path}'], text=True).strip()
    return command, session, Path(cwd)


def resolve_path(reference, directories):
    path = Path(reference).expanduser()
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = []
        for directory in directories:
            if not directory:
                continue
            directory = Path(directory)
            if (directory / path).is_file():
                return (directory / path).resolve()
            candidates.append(directory / path)
            git = shutil.which('git')
            if git:
                root = subprocess.run([git, '-C', str(directory), 'rev-parse', '--show-toplevel'],
                    capture_output=True, text=True)
                if root.returncode == 0:
                    candidates.append(Path(root.stdout.strip()) / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError('File not found relative to the active pane: ' + reference)


def browser_command(target, browser=None):
    if platform.system() == 'Darwin':
        for name in ([browser] if browser else ['Chromium', 'Google Chrome']):
            if any((root / (name + '.app')).is_dir() for root in (Path('/Applications'), Path.home() / 'Applications')):
                return ['/usr/bin/open', '-a', name, target]
        if browser:
            raise ValueError('Browser is not installed: ' + browser)
        return ['/usr/bin/open', target]
    choices = [browser] if browser else ['chromium', 'chromium-browser', 'google-chrome', 'xdg-open']
    for name in choices:
        executable = shutil.which(name)
        if executable:
            return [executable, target]
    raise ValueError('Install Chromium or configure a default browser')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?')
    parser.add_argument('--target', dest='named_target')
    parser.add_argument('--line')
    parser.add_argument('--cwd')
    parser.add_argument('--tty')
    parser.add_argument('--socket')
    parser.add_argument('--browser')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        config_path = Path.home() / '.config/awesome-byobu/links.json'
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        target, line, column = parse_reference(args.named_target or args.target or '', args.line)
        browser = args.browser or config.get('browser')
        if target.startswith(('http://', 'https://')):
            command = browser_command(target, browser)
        else:
            tmux = config.get('tmux') or shutil.which('tmux')
            if not tmux:
                raise ValueError('tmux is missing; rerun setup.sh')
            socket = args.socket or config.get('socket')
            # A GUI-launched script lacks the pane's environment. The attached
            # client identifies both the destination session and its active cwd.
            prefix, session, cwd = tmux_context(tmux, socket, args.tty)
            html = re.fullmatch(r'(.+\.html?)([?#].*)?', target, re.IGNORECASE)
            path = resolve_path(html[1] if html else target, [cwd, args.cwd])
            if path.suffix.lower() in ('.html', '.htm'):
                command = browser_command(path.as_uri() + ((html[2] or '') if html else ''), browser)
            else:
                vim = config.get('vim') or shutil.which('vim')
                if not vim:
                    raise ValueError('Vim is missing; rerun setup.sh')
                editor = [vim]
                if column:
                    editor += ['-c', 'call cursor(%d,%d)' % (line or 1, column)]
                elif line:
                    editor.append('+' + str(line))
                editor += ['--', str(path)]
                command = prefix + ['new-window', '-t', session + ':', '-c', str(path.parent),
                    '-n', 'vim:' + path.name, shlex.join(editor)]
        if args.dry_run:
            print(json.dumps(command))
        else:
            subprocess.run(command, check=True)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Cannot open link: ' + str(error))
        return 1
