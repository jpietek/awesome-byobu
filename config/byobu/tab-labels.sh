# Shared Bash/Zsh tab-label functions. No git, hostname, basename, or tmux
# subprocesses are started when drawing a prompt.
_jan_tab_build() {
    local directory="$PWD" leaf git_directory="" line="" branch="" host=""
    if [ "$PWD" = "$HOME" ]; then
        leaf='~'
    else
        leaf=${PWD##*/}
        [ -n "$leaf" ] || leaf='/'
    fi

    if [ "${_JAN_TAB_GIT_PWD-}" = "$PWD" ] && [ -r "${_JAN_TAB_GIT_DIR-}/HEAD" ]; then
        git_directory=$_JAN_TAB_GIT_DIR
    else
        while :; do
            if [ -r "$directory/.git/HEAD" ]; then
                git_directory="$directory/.git"
                break
            elif [ -f "$directory/.git" ] && [ -r "$directory/.git" ]; then
                IFS= read -r line < "$directory/.git"
                case "$line" in
                    'gitdir: '*)
                        git_directory=${line#gitdir: }
                        case "$git_directory" in /*) ;; *) git_directory="$directory/$git_directory" ;; esac
                        break ;;
                esac
            fi
            [ "$directory" != / ] || break
            directory=${directory%/*}
            [ -n "$directory" ] || directory=/
        done
        _JAN_TAB_GIT_PWD=$PWD
        _JAN_TAB_GIT_DIR=$git_directory
    fi
    if [ -n "$git_directory" ] && [ -r "$git_directory/HEAD" ]; then
        IFS= read -r line < "$git_directory/HEAD"
        case "$line" in
            'ref: refs/heads/'*) branch=${line#ref: refs/heads/} ;;
            *) branch=${line:0:8} ;;
        esac
    fi
    # Keep the meaningful directory and branch, not the whole local path.
    [ ${#leaf} -le 20 ] || leaf="${leaf:0:19}…"
    [ ${#branch} -le 18 ] || branch="${branch:0:17}…"
    JAN_TAB_LABEL=$leaf
    [ -z "$branch" ] || JAN_TAB_LABEL="$JAN_TAB_LABEL:$branch"
    if [ -n "${SSH_CONNECTION-}${SSH_TTY-}" ]; then
        host=${HOSTNAME:-${HOST:-remote}}
        host=${host%%.*}
        JAN_TAB_LABEL="$host:$JAN_TAB_LABEL"
    fi
    JAN_TAB_LABEL=${JAN_TAB_LABEL//[[:cntrl:]]/}
}

_jan_tab_emit() {
    if [ -z "${TMUX-}${STY-}" ]; then
        [ -n "${SSH_TTY-}" ] || return 0
        case "${TERM-}" in screen*|tmux*) ;; *) return 0 ;; esac
    fi
    _jan_tab_build
    printf '\033k%s\033\\' "$JAN_TAB_LABEL"
}
