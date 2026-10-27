# Optional remote Bash integration; source from ~/.bashrc after the existing
# prompt setup. This preserves PS1 and the exit status seen by other hooks.
source "${TERMINAL_SETUP_CONFIG:-$HOME/.config/byobu}/tab-labels.sh"
_jan_tab_prompt_command() {
    local command_status=$?
    _jan_tab_emit
    return "$command_status"
}
if [ -z "${_JAN_TAB_BASH_INSTALLED-}" ]; then
    case "$(declare -p PROMPT_COMMAND 2>/dev/null)" in
        'declare -a '*) PROMPT_COMMAND=(_jan_tab_prompt_command "${PROMPT_COMMAND[@]}") ;;
        *) PROMPT_COMMAND="_jan_tab_prompt_command${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;;
    esac
    _JAN_TAB_BASH_INSTALLED=1
fi
