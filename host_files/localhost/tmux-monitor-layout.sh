#!/bin/bash
set -euo pipefail

# Monitor layout: htop, k9s, and terminal
workdir="${1:-$HOME}"
window_id=$(tmux new-window -P -F "#{window_id}" -n 'monitor' -c "$workdir")

tmux send-keys -t "$window_id" 'htop' Enter
sleep 0.2
tmux split-window -t "$window_id" -h -p 60 -c "$workdir"
tmux send-keys -t "${window_id}.1" 'k9s 2>/dev/null || echo "k9s not installed"' Enter
sleep 0.2
tmux split-window -t "${window_id}.1" -v -p 50 -c "$workdir"
tmux select-pane -t "${window_id}.0"
