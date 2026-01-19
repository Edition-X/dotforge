#!/bin/bash
set -euo pipefail

# Deploy layout: main terminal and Ansible output
workdir="${1:-$HOME}"
window_id=$(tmux new-window -P -F "#{window_id}" -n 'deploy' -c "$workdir")

tmux split-window -t "$window_id" -h -p 40 -c "$workdir"
tmux select-pane -t "${window_id}.0"
