#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"

# Create state dir (runs as root, so no permission issues)
mkdir -p "${STATE_DIR}"

# Create minimal initial config if not present
if [ ! -f "${STATE_DIR}/openclaw.json" ]; then
  cat > "${STATE_DIR}/openclaw.json" << 'EOF'
{
  "gateway": {
    "controlUi": {
      "dangerouslyAllowHostHeaderOriginFallback": true
    }
  }
}
EOF
  echo "[entrypoint] Created initial openclaw.json"
fi

exec "$@"
