# Sourced by setup.sh. Package lists also power --print-deps and CI.
dependency_family() {
    case "$1" in
        macos|Darwin) printf '%s\n' macos ;;
        fedora) printf '%s\n' fedora ;;
        ubuntu|linuxmint|pop) printf '%s\n' ubuntu ;;
        debian) printf '%s\n' debian ;;
        arch|manjaro|endeavouros) printf '%s\n' arch ;;
        *) echo "Unsupported distribution: $1. See README.md for manual installation." >&2; return 1 ;;
    esac
}

dependency_packages() {
    case "$1" in
        macos) echo 'byobu tmux python git vim' ;;
        fedora) echo 'gcc make python3 byobu tmux bash zsh perl perl-Fcntl procps-ng which git vim python3-gobject-base fontconfig xdg-utils wl-clipboard xclip konsole yakuake ca-certificates tar gzip' ;;
        ubuntu|debian) echo 'build-essential python3 byobu tmux bash zsh perl procps debianutils git vim python3-gi gir1.2-glib-2.0 fontconfig xdg-utils wl-clipboard xclip konsole yakuake curl ca-certificates tar gzip' ;;
        arch) echo 'base-devel python tmux bash zsh perl procps-ng which git vim python-gobject fontconfig xdg-utils wl-clipboard xclip konsole yakuake curl ca-certificates tar gzip autoconf automake gettext libnewt' ;;
        *) return 1 ;;
    esac
}

dependency_commands() {
    dependency_list=$(dependency_packages "$1")
    case "$1" in
        macos)
            echo "brew install $dependency_list"
            echo 'brew install --cask iterm2' ;;
        fedora) echo "sudo dnf install -y $dependency_list" ;;
        ubuntu|debian)
            echo 'sudo apt-get update'
            echo "sudo apt-get install -y $dependency_list" ;;
        arch)
            echo "sudo pacman -Syu --needed $dependency_list"
            echo 'sh platforms/linux/install-byobu-source.sh' ;;
    esac
}
