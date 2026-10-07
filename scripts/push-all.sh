#!/usr/bin/env bash
# Companion to pull-all.sh: validate, commit, merge, push and release the workspace.
set -euo pipefail
script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"
exec python3 "$(dirname -- "$script_path")/push_all.py" "$@"
