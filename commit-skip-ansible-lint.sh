#!/bin/bash
# Commit with ansible-lint skipped
export SKIP=ansible-lint
git commit "$@"
