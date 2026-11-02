# Generated paths; this file is sourced by the managed launchers and services.
terminal_setup_home=@INSTALL_HOME@
terminal_setup_tools=@TOOLS_BIN@
export PATH="$terminal_setup_tools:$terminal_setup_home/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:${PATH:-/usr/bin:/bin}:/usr/sbin:/sbin"
export BYOBU_CONFIG_DIR="$terminal_setup_home/.config/byobu"
export BYOBU_PREFIX=@BYOBU_PREFIX@
export PATH="$BYOBU_PREFIX/bin:$PATH"
export BYOBU_BACKEND=tmux
export BYOBU_TERM=tmux-256color
export BYOBU_RUN_DIR="$terminal_setup_home/.cache/terminal-setup/byobu"
export TERMINAL_SETUP_CONFIG="$BYOBU_CONFIG_DIR"
export TMUX_TMPDIR="$terminal_setup_home/.local/state/terminal-setup/tmux"
export TERMINAL_SETUP_SESSION_STATE="$terminal_setup_home/.local/state/terminal-setup/byobu"
export SHELL=@ZSH_PATH@
export LANG="${LANG:-en_US.UTF-8}"
mkdir -p "$TMUX_TMPDIR" "$TERMINAL_SETUP_SESSION_STATE" "$BYOBU_RUN_DIR"
chmod 700 "$TMUX_TMPDIR" "$TERMINAL_SETUP_SESSION_STATE" "$BYOBU_RUN_DIR"
# A launcher called from a different tmux server must target the managed one.
unset TMUX
