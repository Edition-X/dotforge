#!/usr/bin/env bash
#
# Hand the apps already sitting in /Applications over to Homebrew, so they can
# be declared in the Brewfile and survive a rebuild.
#
# Why this is a script you run by hand rather than an Ansible task: adopting an
# app makes Homebrew run `chmod -R a+rX` on the bundle, which needs sudo for
# most signed apps. That means an interactive password prompt, so it cannot run
# unattended. Run it once, in a terminal, then move the adopted casks out of the
# commented block in the Brewfile and into the live lists.
#
# Adoption does NOT replace or upgrade the app. Homebrew takes ownership of what
# is already there and records the cask version, so a bundle check may report it
# outdated afterwards. `make upgrade` is what actually moves versions.
set -uo pipefail

CASKS=(
    chatgpt
    chatgpt-classic
    claude
    cmux
    crossover
    cursor
    discord
    firefox
    ghostty
    google-chrome
    linear
    microsoft-edge
    raycast
    steam
    surfshark
    visual-studio-code
    vivaldi
    vlc
)

if [[ ! -t 0 ]]; then
    echo "This script needs a terminal — Homebrew will prompt for your sudo password."
    exit 1
fi

echo "Warming up sudo so each cask does not prompt separately..."
sudo -v || exit 1

adopted=() skipped=()

for cask in "${CASKS[@]}"; do
    if brew list --cask "$cask" >/dev/null 2>&1; then
        echo "  $cask — already managed, skipping"
        continue
    fi

    printf '==> %s\n' "$cask"
    if HOMEBREW_NO_AUTO_UPDATE=1 brew install --cask --adopt "$cask"; then
        adopted+=("$cask")
    else
        skipped+=("$cask")
    fi
done

echo
echo "Adopted (${#adopted[@]}): ${adopted[*]:-none}"
echo "Skipped (${#skipped[@]}): ${skipped[*]:-none}"
echo
echo "Next:"
echo "  1. Move the adopted casks into the live cask lists in ./Brewfile"
echo "  2. make drift   # confirm the Brewfile matches the machine"
