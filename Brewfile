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

# Third-party taps. `trusted: true` is required since Homebrew 6 refuses to
# load formulae from untrusted taps.
tap "antoniorodr/memo"
tap "hashicorp/tap"
tap "hudochenkov/sshpass"
tap "openclaw/tap"
tap "streetpea/streetpea"

## Shell and core utilities ##
# Plugin manager for zsh, inspired by oh-my-zsh and vundle — sourced by .zshrc
brew "antigen"
# Cross-shell prompt for astronauts
brew "starship"
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
# NOTE: goplaces migrated from a formula to a cask upstream. The cask is
# declared below. An unlinked 0.2.1 keg from the old formula is still in the
# Cellar; it is inert, remove with: brew uninstall --formula goplaces

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

## Casks ##
# Terminal-based AI coding assistant
cask "claude-code@latest"
# Automated testing of webapps for Google Chrome
cask "chromedriver"
# Get up and running with large language models locally
cask "ollama-app"
# Knowledge base that works on top of a local folder of plain text Markdown files
cask "obsidian"
# Development environment
cask "vagrant"
# Secure tunnels to localhost
cask "ngrok"
# 3D creation suite
cask "blender"
# PlayStation Remote Play client
cask "chiaki-ng"
cask "openclaw/tap/goplaces", trusted: true

## Go tools ##
go "github.com/bootdotdev/bootdev"
go "golang.org/x/tools/gopls"

## uv tools ##
uv "arcane", source: "file:///Users/dkelly/Projects/arcane"
uv "echovault", source: "git+https://github.com/mraza007/echovault.git"
uv "localstack"
uv "mlx-audio", with: ["misaki", "numpy<2", "spacy<4"]

## npm globals ##
# OpenAI Codex CLI — installed via npm, not the brew formula of the same name
npm "@openai/codex"
npm "clawdhub"
