#!/bin/bash
set -euo pipefail

# Deploy layout: main terminal and Ansible output
session_name="${1:-}"
workdir="${2:-$HOME}"

if [[ -z "$session_name" ]]; then
  session_name=$(tmux display-message -p '#S')
fi

window_id=$(tmux new-window -P -F "#{window_id}" -t "$session_name" -n 'deploy' -c "$workdir")

tmux split-window -t "$window_id" -h -p 40 -c "$workdir"
tmux select-pane -t "${window_id}.0"
