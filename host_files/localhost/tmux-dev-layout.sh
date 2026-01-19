#!/bin/bash
set -euo pipefail

# Dev layout: nvim editor with logs and terminal panes
workdir="${1:-$HOME}"
window_id=$(tmux new-window -P -F "#{window_id}" -n 'dev' -c "$workdir")

tmux send-keys -t "$window_id" 'nvim .' Enter
sleep 0.2
tmux split-window -t "$window_id" -h -p 35 -c "$workdir"
tmux split-window -t "${window_id}.1" -v -p 50 -c "$workdir"
tmux select-pane -t "${window_id}.0"
