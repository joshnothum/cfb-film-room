#!/usr/bin/env zsh
set -euo pipefail

# Load OPENAI_API_KEY from macOS Keychain into current shell.
# Usage:
#   source scripts/load_openai_key.sh
#
# Store/update key first:
#   security add-generic-password -U -a "$USER" -s OPENAI_API_KEY -w 'your-api-key'

if [[ "${ZSH_EVAL_CONTEXT:-}" != *:file ]]; then
  echo "error: source this script instead of executing it" >&2
  echo "usage: source scripts/load_openai_key.sh" >&2
  return 1 2>/dev/null || exit 1
fi

if ! command -v security >/dev/null 2>&1; then
  echo "error: macOS security CLI not found" >&2
  return 1
fi

key="$(security find-generic-password -a "$USER" -s OPENAI_API_KEY -w 2>/dev/null || true)"
if [[ -z "$key" ]]; then
  echo "error: OPENAI_API_KEY not found in Keychain for user '$USER'" >&2
  echo "hint: security add-generic-password -U -a \"$USER\" -s OPENAI_API_KEY -w 'your-api-key'" >&2
  return 1
fi

export OPENAI_API_KEY="$key"
echo "OPENAI_API_KEY loaded from Keychain for user '$USER'."
