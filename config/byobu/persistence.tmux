# Session persistence. Scheduling belongs to launchd/systemd, not redraws.
set -g @resurrect-dir @RESURRECT_DIR@
set -g @resurrect-capture-pane-contents 'on'
set -g @resurrect-pane-contents-area 'full'
set -g @continuum-save-interval '0'
set -g @continuum-restore 'off'
run-shell @RESURRECT_COMMAND@
# The service/launcher owns restore and the timer owns save. Loading continuum
# would add another status command and race startup restoration.
set -g @resurrect-hook-post-save-all @AGENT_SAVE_COMMAND@
