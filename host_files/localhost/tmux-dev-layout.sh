#!/bin/bash
set -euo pipefail

# Dev layout: nvim editor with logs and terminal panes
session_name="${1:-}"
workdir="${2:-$HOME}"

if [[ -z "$session_name" ]]; then
  session_name=$(tmux display-message -p '#S')
fi

main_pane=$(tmux new-window -P -F "#{pane_id}" -t "$session_name" -n 'dev' -c "$workdir")

tmux send-keys -t "$main_pane" 'nvim .' Enter
right_pane=$(tmux split-window -P -F "#{pane_id}" -t "$main_pane" -h -p 35 -c "$workdir")
tmux split-window -P -F "#{pane_id}" -t "$right_pane" -v -p 50 -c "$workdir" >/dev/null
tmux select-pane -t "$main_pane"
