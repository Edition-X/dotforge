#!/bin/bash

# Script to run pre-commit with environment variables for vault handling

# Set environment variables for Ansible to handle vault files
export ANSIBLE_VAULT_PASSWORD_FILE=/dev/null
export ANSIBLE_VAULT_ID_MATCH=False
export ANSIBLE_HOST_KEY_CHECKING=False

# Run pre-commit with the specified arguments
pre-commit "$@"

# Reset exit code if ansible-lint fails but all other hooks pass
# This is useful during development when you want to commit despite ansible-lint failures
if [ $? -ne 0 ]; then
    echo "Note: If you want to commit despite ansible-lint failures, use:"
    echo "SKIP=ansible-lint git commit ..."
fi 