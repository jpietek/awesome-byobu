"""Open code/text in Vim, HTML/URLs in a browser, and other files in their default app."""
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


TEXT_EXTENSIONS = frozenset('''
.c .cc .cpp .cxx .h .hh .hpp .hxx .cu .cuh .m .mm .asm .s
.py .pyi .pyx .pxd .js .jsx .mjs .cjs .ts .tsx .java .kt .kts
.rs .go .rb .php .swift .scala .sc .cs .fs .fsx .vb .r .jl
.sh .bash .zsh .fish .ps1 .lua .pl .pm .sql .ex .exs .erl .hrl
.hs .lhs .clj .cljs .cljc .edn .lisp .el .scm .rkt .ml .mli
.css .scss .sass .less .vue .svelte .astro .toml .yaml .yml
.json .jsonc .jsonl .ndjson .xml .ini .conf .cfg .env .properties
.txt .text .md .markdown .rst .adoc .tex .bib .log .diff .patch
.csv .tsv .proto .graphql .gql .cmake .mk .make .gradle .nix .tf
.tfvars .ipynb .lock
'''.split())
TEXT_FILENAMES = frozenset('''
makefile gnumakefile dockerfile containerfile vagrantfile gemfile rakefile
justfile procfile brewfile readme license copying authors changelog
.gitignore .gitattributes .gitmodules .dockerignore .editorconfig
.bashrc .bash_profile .zshrc .zprofile .profile .env .npmrc .yarnrc
.prettierrc .eslintrc
'''.split())


def opens_in_vim(path):
    name = path.name.lower()
    return path.is_file() and (
        path.suffix.lower() in TEXT_EXTENSIONS or name in TEXT_FILENAMES or
        name.startswith(('.env.', 'dockerfile.', 'containerfile.')))


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
    if text.lower().startswith(('http://', 'https://')):
        return text, None, None
    if text.lower().startswith('file://'):
        url = urlsplit(text)
        if url.netloc not in ('', 'localhost'):
            raise ValueError('Only local file:// links are supported')
        text = unquote(url.path) + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')
    elif '://' in text:
        raise ValueError('Only HTTP, HTTPS and local file links are supported')
    # A colon after a path is commonly sentence punctuation: "compare.png: ...".
    text = text.rstrip(':')
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
            if (directory / path).is_file() or (directory / path).is_dir():
                return (directory / path).resolve()
            candidates.append(directory / path)
            git = shutil.which('git')
            if git:
                root = subprocess.run([git, '-C', str(directory), 'rev-parse', '--show-toplevel'],
                    capture_output=True, text=True)
                if root.returncode == 0:
                    candidates.append(Path(root.stdout.strip()) / path)
    for candidate in candidates:
        if candidate.is_file() or candidate.is_dir():
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


def default_file_command(path):
    if platform.system() == 'Darwin':
        return ['/usr/bin/open', str(path)]
    opener = shutil.which('xdg-open')
    if not opener:
        raise ValueError('xdg-open is missing; install xdg-utils or rerun setup.sh')
    return [opener, str(path)]


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
        if target.lower().startswith(('http://', 'https://')):
            command = browser_command(target, browser)
        else:
            attached = None
            def context():
                nonlocal attached
                if attached is None:
                    tmux = config.get('tmux') or shutil.which('tmux')
                    if not tmux:
                        raise ValueError('tmux is missing; rerun setup.sh')
                    attached = tmux_context(tmux, args.socket or config.get('socket'), args.tty)
                return attached

            html = re.fullmatch(r'(.+\.html?)([?#].*)?', target, re.IGNORECASE)
            reference = html[1] if html else target
            directories = []
            # Absolute images/documents need no running tmux client. Relative
            # paths use the active pane, or an explicitly supplied cwd offline.
            if not Path(reference).expanduser().is_absolute():
                try:
                    directories.append(context()[2])
                except (ValueError, OSError, subprocess.CalledProcessError):
                    if not args.cwd:
                        raise
                directories.append(args.cwd)
            path = resolve_path(reference, directories)
            if path.is_file() and path.suffix.lower() in ('.html', '.htm'):
                command = browser_command(path.as_uri() + ((html[2] or '') if html else ''), browser)
            elif opens_in_vim(path):
                prefix, session, _ = context()
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
            else:
                command = default_file_command(path)
        if args.dry_run:
            print(json.dumps(command))
        else:
            subprocess.run(command, check=True)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Cannot open link: ' + str(error))
        return 1
