# Session persistence. Scheduling belongs to launchd/systemd, not redraws.
set -g @resurrect-dir @RESURRECT_DIR@
set -g @resurrect-capture-pane-contents 'on'
set -g @resurrect-pane-contents-area 'full'
set -g @continuum-save-interval '0'
set -g @continuum-restore 'on'
run-shell @RESURRECT_COMMAND@
run-shell @CONTINUUM_COMMAND@
set -g @resurrect-hook-post-save-all @AGENT_SAVE_COMMAND@
