#!/bin/bash
set -euo pipefail

# Monitor layout: htop, k9s, and terminal
session_name="${1:-}"
workdir="${2:-$HOME}"

if [[ -z "$session_name" ]]; then
  session_name=$(tmux display-message -p '#S')
fi

main_pane=$(tmux new-window -P -F "#{pane_id}" -t "$session_name" -n 'monitor' -c "$workdir")

tmux send-keys -t "$main_pane" 'htop' Enter
right_pane=$(tmux split-window -P -F "#{pane_id}" -t "$main_pane" -h -p 60 -c "$workdir")
tmux send-keys -t "$right_pane" 'k9s 2>/dev/null || echo "k9s not installed"' Enter
tmux split-window -P -F "#{pane_id}" -t "$right_pane" -v -p 50 -c "$workdir" >/dev/null
tmux select-pane -t "$main_pane"
