source $BYOBU_PREFIX/share/byobu/profiles/tmux

# A shared collector publishes the status cache; tmux only streams it.
set -g status 2
set -g history-limit 1000000
set -g status-position bottom
set -g status-interval 5
set -g status-justify left
set -g status-style 'fg=#cbd5e1,bg=#334155'
set -g status-left '#[fg=#111827,bg=#a3e635,bold] @LOGO@ #[default]'
set -g status-left-length 8
set -g window-status-separator ''
# The shell title hook includes the agent, directory, and Git branch in #W.
set -g window-status-style 'fg=#cbd5e1,bg=#334155,nobold,noreverse'
set -g window-status-activity-style 'fg=#facc15,bg=#334155,bold,noreverse'
set -g window-status-format ' #I #{?@jan_agent_label,#{@jan_agent_label},#W}#{?window_activity_flag, ●,} '
set -g window-status-current-format '#[fg=#ffffff,bg=#2563eb,bold,noreverse] #I #{?@jan_agent_label,#{@jan_agent_label},#W} '
# Built-in unread-output tracking: no shell polling, sound, or popup.
# Visiting the tab clears its activity flag.
set -g monitor-activity on
set -g activity-action none
set -g visual-activity off
set -g bell-action none
set -g visual-bell off
set -g visual-silence off
set -g status-right @STATUS_FORMAT@
set -g status-right-length 140

# Tabs use the full upper row. Logo and right-aligned metrics/date sit below.
# Keep tmux's native window-list styling, activity indicators, and overflow.
set -g status-format[0] '#[list=on align=#{status-justify}]#[list=left-marker]<#[list=right-marker]>#[list=on]#{W:#[range=window|#{window_index} #{E:window-status-style}#{?#{&&:#{window_last_flag},#{!=:#{E:window-status-last-style},default}}, #{E:window-status-last-style},}#{?#{&&:#{window_bell_flag},#{!=:#{E:window-status-bell-style},default}}, #{E:window-status-bell-style},#{?#{&&:#{||:#{window_activity_flag},#{window_silence_flag}},#{!=:#{E:window-status-activity-style},default}}, #{E:window-status-activity-style},}}]#[push-default]#{T:window-status-format}#[pop-default]#[norange default]#{?loop_last_flag,,#{E:window-status-separator}},#[range=window|#{window_index} list=focus #{?#{!=:#{E:window-status-current-style},default},#{E:window-status-current-style},#{E:window-status-style}}#{?#{&&:#{window_last_flag},#{!=:#{E:window-status-last-style},default}}, #{E:window-status-last-style},}#{?#{&&:#{window_bell_flag},#{!=:#{E:window-status-bell-style},default}}, #{E:window-status-bell-style},#{?#{&&:#{||:#{window_activity_flag},#{window_silence_flag}},#{!=:#{E:window-status-activity-style},default}}, #{E:window-status-activity-style},}}]#[push-default]#{T:window-status-current-format}#[pop-default]#[norange list=on default]#{?loop_last_flag,,#{E:window-status-separator}}}#[nolist default]'
set -g status-format[1] '#[align=left range=left #{E:status-left-style}]#[push-default]#{T;=/#{status-left-length}:status-left}#[pop-default]#[norange default]#[nolist align=right range=right #{E:status-right-style}]#[push-default]#{T;=/#{status-right-length}:status-right}#[pop-default]#[norange default]'

set -g automatic-rename on
set -g automatic-rename-format @AUTO_RENAME@
set -g allow-rename on
set -g default-terminal 'tmux-256color'
set -as terminal-features ',xterm-256color:RGB'

# GNU Screen / Linux-style Control-A prefix. Byobu's stock F-key profile
# installs a root-table C-a shortcut; remove it and use tmux's native prefix.
unbind-key -q C-b
unbind-key -q -T root C-a
set -g prefix C-a
set -g prefix2 F12
bind-key -T prefix C-a send-prefix
bind-key -n C-a switch-client -T prefix
bind-key -n C-b switch-client -T prefix
bind-key -T prefix a send-prefix
bind-key -T prefix c new-window -c '#{pane_current_path}'
bind-key -T prefix C new-window -c '#{pane_current_path}'
bind-key -T prefix C-c new-window -c '#{pane_current_path}'
bind-key -T prefix n next-window
bind-key -T prefix C-n next-window
bind-key -T prefix p previous-window
bind-key -T prefix C-p previous-window
bind-key -T prefix d detach-client
bind-key -T prefix C-d detach-client
bind-key -T prefix 0 select-window -t ':=0'
bind-key -T prefix 1 select-window -t ':=1'
bind-key -T prefix 2 select-window -t ':=2'
bind-key -T prefix 3 select-window -t ':=3'
bind-key -T prefix 4 select-window -t ':=4'
bind-key -T prefix 5 select-window -t ':=5'
bind-key -T prefix 6 select-window -t ':=6'
bind-key -T prefix 7 select-window -t ':=7'
bind-key -T prefix 8 select-window -t ':=8'
bind-key -T prefix 9 select-window -t ':=9'

# iTerm2 understands OSC 8, so let tmux pass hyperlinks through instead of
# flattening them to plain text.
set -as terminal-features ',xterm-256color:hyperlinks'
set -as terminal-features ',iTerm2:hyperlinks'


# C-a o: open the clipboard URL in the default browser.
bind-key -T prefix o run-shell -b @URL_OPEN_COMMAND@

# Page Up enters scrollback and pages; Page Down pages back toward the bottom
# and drops out of copy mode at the end (-e). Full-screen apps (vim, less,
# Claude Code) use the alternate screen, so they keep their own page keys.
bind-key -T root PPage if-shell -F '#{alternate_on}' 'send-keys PPage' 'copy-mode -e; send-keys -X page-up'
bind-key -T root NPage if-shell -F '#{alternate_on}' 'send-keys NPage' 'send-keys NPage'
bind-key -T copy-mode-vi PPage send-keys -X page-up
bind-key -T copy-mode-vi NPage send-keys -X page-down

# Ctrl+Up / Ctrl+Down page through scrollback too; keyboard remaps may send
# PPage/NPage instead, so both forms are bound.
bind-key -T root C-Up if-shell -F '#{alternate_on}' 'send-keys C-Up' 'copy-mode -e; send-keys -X page-up'
bind-key -T copy-mode-vi C-Up send-keys -X page-up
bind-key -T copy-mode-vi C-Down send-keys -X page-down

# Fast movement inside copy mode (C-a [): shifted arrows scroll 5 lines at a
# time, C-u/C-d are vi half-page, and space/b page like less.
bind-key -T copy-mode-vi S-Up   send-keys -X -N 5 scroll-up
bind-key -T copy-mode-vi S-Down send-keys -X -N 5 scroll-down
bind-key -T copy-mode-vi Space  send-keys -X page-down
bind-key -T copy-mode-vi b      send-keys -X page-up

# Load last so automatic saving survives custom status-bar configuration.
source-file @PERSISTENCE_PATH@

if-shell @LOCAL_TEST@ @LOCAL_SOURCE@
