#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <path-to-client-secret.json> [--skip-install]" >&2
  exit 1
fi

CLIENT_SECRET_PATH="$1"
SKIP_INSTALL="${2:-}"

if [[ ! -f "$CLIENT_SECRET_PATH" ]]; then
  echo "Client secret file not found: $CLIENT_SECRET_PATH" >&2
  exit 1
fi

if [[ "$SKIP_INSTALL" != "--skip-install" ]]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev]"
fi

if [[ ! -x ".venv/bin/gsc" ]]; then
  echo "Expected .venv/bin/gsc to exist. Did installation fail?" >&2
  exit 1
fi

echo "Starting OAuth login for gsc..."
.venv/bin/gsc auth login --client-secret "$CLIENT_SECRET_PATH"

echo
echo "Setup complete."
echo "Run commands with:"
echo "  .venv/bin/gsc site list"
echo "Optional: set a default site"
echo "  .venv/bin/gsc config set default-site sc-domain:example.com"
