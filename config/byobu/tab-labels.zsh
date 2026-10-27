source "$HOME/.config/byobu/tab-labels.sh"
autoload -Uz add-zsh-hook

_jan_screen_title_precmd() {
    if [[ -n ${_JAN_TAB_AGENT_ACTIVE-} && -n ${TMUX-} ]]; then
        tmux set-option -w -u -t "$TMUX_PANE" @jan_agent_label 2>/dev/null
        unset _JAN_TAB_AGENT_ACTIVE
    fi
    _jan_tab_emit
}

# Label agents while running, restoring directory/branch at the next prompt.
# For SSH, label the destination immediately; a remote prompt hook can add
# the remote directory and branch. Never use the LOCAL cwd for SSH.
_jan_screen_title_preexec() {
    [[ -n $STY || -n $TMUX ]] || return
    local -a words
    words=("${(@Q)${(z)1}}")
    local word target="" command_name="" mode=""
    local -i start=1 index skip_next=0
    while (( start <= ${#words} )); do
        case ${words[start]} in
            command|exec|noglob|*=*) (( start++ )) ;;
            *) break ;;
        esac
    done
    command_name=${words[start]:t}
    case $command_name in
        codex)
            _jan_tab_build
            if [[ -n ${TMUX-} ]]; then
                tmux set-option -w -t "$TMUX_PANE" @jan_agent_label "codex:$JAN_TAB_LABEL"
                _JAN_TAB_AGENT_ACTIVE=1
            fi
            print -rn -- $'\ek'"codex:$JAN_TAB_LABEL"$'\e\\'
            return ;;
        claude|claude-amagi)
            _jan_tab_build
            if [[ -n ${TMUX-} ]]; then
                tmux set-option -w -t "$TMUX_PANE" @jan_agent_label "claude:$JAN_TAB_LABEL"
                _JAN_TAB_AGENT_ACTIVE=1
            fi
            print -rn -- $'\ek'"claude:$JAN_TAB_LABEL"$'\e\\'
            return ;;
    esac
    if [[ $command_name == ssh ]]; then
        mode=ssh
        (( start++ ))
    elif [[ $command_name == gcloud || $command_name == gcloud.py ]]; then
        for (( index=start+1; index < ${#words}; index++ )); do
            if [[ ${words[index]} == compute && ${words[index+1]} == ssh ]]; then
                mode=gcloud
                start=$(( index + 2 ))
                break
            fi
        done
    fi
    [[ -n $mode ]] || return
    for (( index=start; index <= ${#words}; index++ )); do
        word=${words[index]}
        if (( skip_next )); then skip_next=0; continue; fi
        if [[ $mode == ssh ]]; then
            case $word in
                --) target=${words[index+1]}; break ;;
                -[bBcDEeFIiJLlmOoPpQRSWw]) skip_next=1 ;;
                -*) ;;
                *) target=$word; break ;;
            esac
        else
            case $word in
                --*=*) ;;
                --project|--zone|--region|--configuration|--account|--impersonate-service-account|--ssh-key-file|--verbosity) skip_next=1 ;;
                -*) ;;
                *) target=$word; break ;;
            esac
        fi
    done
    target=${target##*@}
    target=${target//[[:cntrl:]]/}
    [[ -n $target ]] && print -rn -- $'\ek'"ssh:$target"$'\e\\'
}

add-zsh-hook precmd _jan_screen_title_precmd
add-zsh-hook preexec _jan_screen_title_preexec
