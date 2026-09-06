# Homebrew bundle — the single source of truth for packages on this machine.
#
# Generated from the live machine with `brew bundle dump --describe`, then
# curated. Applied by the `packages` role, but usable directly:
#
#   brew bundle check --verbose   # what has drifted
#   brew bundle install           # install what is missing
#   brew bundle dump --force      # recapture reality after installing by hand
#
# Note: `brew bundle check` reports outdated packages as unmet. The packages
# role deliberately installs with --no-upgrade so that `make apply` stays
# predictable; use `make upgrade` to actually pull upgrades in.
#
# Warning about `brew bundle dump`: it silently omits anything from a tap you
# have not trusted. Run `brew trust <tap>` for every tap below before trusting
# a dump, or packages quietly vanish from this file. That is how terraform and
# six other formulae went missing the first time this was generated.

# Third-party taps. Every one of these needs `brew trust <tap>` locally;
# Homebrew refuses to load formulae from untrusted taps and that refusal is
# fatal to a whole `brew bundle` run.
tap "antoniorodr/memo"
tap "hashicorp/tap"
tap "hudochenkov/sshpass"
tap "koekeishiya/formulae"
tap "ngrok/ngrok"
tap "openclaw/tap"
tap "steipete/tap"
tap "streetpea/streetpea"

## Hotkeys ##
# Global hotkey daemon — binds bare F-keys to open specific apps. Requires an
# interactive one-time setup; see roles/dotfiles/tasks/main.yml.
brew "koekeishiya/formulae/skhd", trusted: true

## Shell and core utilities ##
# Plugin manager for zsh, inspired by oh-my-zsh and vundle — sourced by .zshrc
brew "antigen"
# GNU File, Shell, and Text utilities
brew "coreutils"
# GNU implementation of the famous stream editor
brew "gnu-sed"
# Utility for directing compilation
brew "make"
# Display directories as trees (with optional color/HTML output)
brew "tree"
# Simple, fast and user-friendly alternative to find
brew "fd"
# Search tool like grep and The Silver Searcher
brew "ripgrep"
# Lightweight and flexible command-line JSON processor
brew "jq"
# Process YAML, JSON, XML, CSV and properties documents from the CLI
brew "yq"
# Improved top (interactive process viewer)
brew "htop"
# NCurses Disk Usage
brew "ncdu"
# File browser
brew "ranger"
# Monitor data's progress through a pipe
brew "pv"
# Internet file retriever
brew "wget"
# Render markdown on the CLI
brew "glow"
# Manipulate and query tags on macOS files
brew "tag"
# Mac App Store CLI — drives the `mas` entries at the end of this file
brew "mas"
# Terminal multiplexer
brew "tmux"
# Ambitious Vim-fork focused on extensibility and agility
brew "neovim"
# CLI email client written in Rust
brew "himalaya"
# Note-taking CLI
brew "antoniorodr/memo/memo"

## Git ##
# Distributed revision control system
brew "git"
# Git extension for versioning large files
brew "git-lfs"
# GitHub command-line tool
brew "gh"
# Text interface for Git repositories
brew "tig"
# Simple terminal UI for git commands
brew "lazygit"

## Languages and version managers ##
# Open source programming language to build simple/reliable/efficient software
brew "go"
# Open-source, cross-platform JavaScript runtime environment
brew "node"
# Fast, disk space efficient package manager
brew "pnpm"
# Python version management
brew "pyenv"
# Ruby version manager
brew "rbenv"
# Powerful, clean, object-oriented scripting language
brew "ruby"
brew "ruby@3.3"
# Cross-platform make
brew "cmake"

## Python tooling ##
# Extremely fast Python package installer and resolver, written in Rust
brew "uv"
# Python dependency management tool
brew "poetry"
brew "pipenv"
# Python code formatter
brew "black"
# Lint your Python code for style and logical errors
brew "flake8"
# Python 2 and 3 compatibility utilities — vestigial, safe to drop
brew "six"
# Pulled in for scientific Python builds; kept so they are not GC'd
brew "lapack"
brew "openblas"
# Seamless operability between C++11 and Python
brew "pybind11"

## Infrastructure and cloud ##
# Automate deployment, configuration, and upgrading
brew "ansible"
# Official Amazon AWS command-line interface
brew "awscli"
# Kubernetes package manager
brew "helm"
# Run a Kubernetes cluster locally
brew "minikube"
# Lazier way to manage everything docker
brew "lazydocker"
# Machine image builder
brew "hashicorp/tap/packer", trusted: true
# Infrastructure as code
brew "hashicorp/tap/terraform", trusted: true
# Non-interactive ssh password auth — needed by ansible against the fleet
brew "hudochenkov/sshpass/sshpass"

## Linting and CI ##
# Checks ansible playbooks for practices and behaviour
brew "ansible-lint"
# Linter for YAML files
brew "yamllint"
# Framework for managing multi-language pre-commit hooks
brew "pre-commit"
# Static checker for GitHub Actions workflow files
brew "actionlint"
# Run your GitHub Actions locally
brew "act"
# Static analysis and lint tool, for (ba)sh scripts
brew "shellcheck"
# Bash Automated Testing System
brew "bats-core"

## Network and security ##
# Powerful, enterprise-ready, open source web server with automatic HTTPS
brew "caddy"
# Lightweight DNS forwarder and DHCP server
brew "dnsmasq"
# Simple tool to make locally trusted development certificates
brew "mkcert"
# Port scanning utility for large networks
brew "nmap"
# Modern load testing tool, using Go and JavaScript
brew "k6"
# User interface to the TELNET protocol
brew "telnet"
# Anti-virus software
brew "clamav"

## Media ##
# Play, record, convert, and stream select audio and video codecs
brew "ffmpeg"

## AI and agents ##
# Create, run, and share large language models (LLMs)
brew "ollama"
# AI coding agent, built for the terminal
brew "opencode"
# Multi-modal AI tool to extract and summarize content
brew "summarize"
# GOG.com CLI
brew "openclaw/tap/gogcli"
# WhatsApp CLI
brew "openclaw/tap/wacli"
# Search GIFs from the terminal
brew "steipete/tap/gifgrep"
# Screenshot and UI automation for AI agents
brew "steipete/tap/peekaboo"
# Screenshot annotation tool
brew "steipete/tap/sag"
# NOTE: goplaces migrated from a formula to a cask upstream, so it is declared
# in the cask section below rather than here.

## Toys ##
# Aquarium animation in ASCII art
brew "asciiquarium"
# Console Matrix
brew "cmatrix"
# Apjanke's fork of the classic cowsay project
brew "cowsay"
# Banner-like program prints strings as ASCII art
brew "figlet"
# Infamous electronic fortune-cookie generator
brew "fortune"
# Rainbows and unicorns in your console!
brew "lolcat"
# Animated pipes terminal screensaver
brew "pipes-sh"
# Fast, highly customisable system info script — archived upstream
brew "neofetch"

## Casks — editors and terminals ##
cask "cursor"
cask "visual-studio-code"
cask "ghostty"
cask "cmux"
cask "antigravity"

## Casks — developer tooling ##
# Terminal-based AI coding assistant
cask "claude-code@latest"
# Automated testing of webapps for Google Chrome
cask "chromedriver"
# Get up and running with large language models locally
cask "ollama-app"
# Development environment
cask "vagrant"
# Secure tunnels to localhost
cask "ngrok/ngrok/ngrok"
# AI agents and assistants
cask "claude"
cask "chatgpt-classic"
cask "devin-desktop"
cask "t3-code"
# Design
cask "figma"
cask "openclaw/tap/goplaces", trusted: true

## Casks — browsers ##
cask "brave-browser"
cask "firefox"
cask "google-chrome"
cask "microsoft-edge"
cask "vivaldi"

## Casks — applications ##
# Knowledge base that works on top of a local folder of plain text Markdown files
cask "obsidian"
cask "linear"
cask "spotify"
cask "discord"
cask "vlc"
# 3D creation suite
cask "blender"
# Run Windows software on macOS
cask "crossover"
# VPN
cask "surfshark"
# Games and controllers
cask "steam"
# PlayStation Remote Play client
cask "streetpea/streetpea/chiaki-ng"
cask "8bitdo-firmware-updater"
cask "8bitdo-ultimate-software"
# Media automation
cask "radarr"
cask "sonarr"
# Launcher
cask "raycast"

# Apps in /Applications that Homebrew is NOT managing.
#
# Adopting needs sudo — Homebrew runs `chmod -R a+rX` on the bundle — so it
# cannot run unattended. Use scripts/adopt-casks.sh, then move the cask up into
# a list above. Do not uncomment before adopting: `brew bundle install` would
# attempt a fresh install, collide with the existing app and fail the run.
#
#   chatgpt     — adoption still pending, needs an interactive sudo prompt.
#   privadovpn  — installed 3.15.0, cask is 4.2.0 and the bundle version check
#                 rejects the mismatch. Upgrade by hand, then adopt.
#   vnc-viewer  — the cask's download URL is currently broken upstream.
#
# Beyond those, ~20 apps have no cask at all: Steam games, Battle.net,
# DisplayLink Manager, logioptionsplus, OpenVPN Connect, NZBGet, zoom.us,
# Spectacle (archived upstream) and similar. They stay unmanaged.

## Mac App Store ##
# Managed with mas. These cannot be casks — App Store apps are receipt-signed
# to the purchasing Apple ID, so `brew bundle` shells out to mas instead.
mas "iMovie", id: 408981434
mas "LastPass for Safari", id: 6504626762
mas "Microsoft OneNote", id: 784801555
mas "Notenik", id: 1465997984
mas "Slack", id: 803453959
mas "uBlock Origin Lite", id: 6745342698

## Go tools ##
go "github.com/bootdotdev/bootdev"
go "golang.org/x/tools/gopls"

## uv tools ##
uv "arcane-mcp", source: "git+https://github.com/Edition-X/arcane.git@v0.2.0-beta.19"
uv "localstack"
uv "mlx-audio", with: ["misaki", "numpy<2", "spacy<4"]

## npm globals ##
# OpenAI Codex CLI — installed via npm, not the brew formula of the same name
npm "@openai/codex"
npm "clawdhub"
