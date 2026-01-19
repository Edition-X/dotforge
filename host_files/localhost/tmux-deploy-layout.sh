#!/bin/bash
set -euo pipefail

# Deploy layout: main terminal and Ansible output
session_name="${1:-}"
workdir="${2:-$HOME}"

if [[ -z "$session_name" ]]; then
  session_name=$(tmux display-message -p '#S')
fi

main_pane=$(tmux new-window -P -F "#{pane_id}" -t "$session_name" -n 'deploy' -c "$workdir")

tmux split-window -P -F "#{pane_id}" -t "$main_pane" -h -p 40 -c "$workdir" >/dev/null
tmux select-pane -t "$main_pane"
