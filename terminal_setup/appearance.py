"""Named terminal profiles from the original iTerm Yakuake appearance."""
import json
from pathlib import Path
import shlex
import plistlib
import uuid


def appearance_files(root, home, system):
    root, home = Path(root), Path(home)
    source = json.loads((root / "config/terminal/appearance.json").read_text())
    files = {}
    launcher = home / '.local/bin/open-terminal-setup'
    font_root = root / "assets/fonts/HackNerdFontMono"
    destination = home / ("Library/Fonts" if system == "Darwin" else ".local/share/fonts/terminal-setup")
    for path in font_root.glob("*.ttf"):
        files[destination / path.name] = (path.read_bytes(), 0o644)
    if system == "Darwin":
        profile = dict(source, Name="Terminal setup", Guid=str(uuid.uuid5(uuid.NAMESPACE_URL, "terminal-setup/profile")))
        profile.update({"Custom Command": "Yes", "Command": shlex.join([str(home / '.local/bin/start-byobu')])})
        target = home / "Library/Application Support/iTerm2/DynamicProfiles/TerminalSetup.json"
        files[target] = ((json.dumps({"Profiles": [profile]}, indent=2) + "\n").encode(), 0o644)
        application = home / 'Applications/Terminal setup.app/Contents'
        files[application / 'Info.plist'] = (plistlib.dumps({'CFBundleExecutable': 'TerminalSetup',
            'CFBundleIdentifier': 'org.terminal-setup.launcher', 'CFBundleName': 'Terminal setup',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1'}), 0o644)
        files[application / 'MacOS/TerminalSetup'] = (('#!/bin/sh\nexec ' + shlex.quote(str(launcher)) + '\n').encode(), 0o755)
        return files
    def rgb(value):
        return ",".join(str(int(value[name + " Component"] * 255 + 0.5)) for name in ("Red", "Green", "Blue"))
    palette = {"Background": source["Background Color"], "BackgroundIntense": source["Background Color"],
               "Foreground": source["Foreground Color"], "ForegroundIntense": source["Bold Color"]}
    for i in range(8):
        palette["Color" + str(i)] = source["Ansi " + str(i) + " Color"]
        palette["Color" + str(i) + "Intense"] = source["Ansi " + str(i + 8) + " Color"]
    scheme = "[General]\nDescription=Original Byobu Yakuake colors\nOpacity=%.2f\n\n" % (1 - source["Transparency"])
    scheme += "\n".join("[" + key + "]\nColor=" + rgb(value) + "\n" for key, value in palette.items())
    profile = ("[General]\nName=Terminal setup\nParent=FALLBACK/\nCommand=" + shlex.join([str(home / '.local/bin/start-byobu')]) +
               "\nEnvironment=TERM=xterm-256color;COLORTERM=truecolor\n\n"
               "[Appearance]\nColorScheme=TerminalSetup\nFont=Hack Nerd Font Mono,13,-1,5,50,0,0,0,0,0\n"
               "BoldIntense=true\nAntiAliasFonts=true\nUseFontLineChararacters=true\n\n"
               "[Scrolling]\nHistorySize=1000000\n")
    for filename, data in (("TerminalSetup.colorscheme", scheme), ("TerminalSetup.profile", profile)):
        files[home / ".local/share/konsole" / filename] = (data.encode(), 0o644)
    desktop_exec = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`').replace('%', '%%')
    files[home / '.local/share/applications/terminal-setup.desktop'] = (
        ('[Desktop Entry]\nType=Application\nName=Terminal setup\nIcon=utilities-terminal\n'
         'Exec="' + desktop_exec + '"\nTerminal=false\nCategories=System;TerminalEmulator;\n').encode(), 0o644)
    return files
