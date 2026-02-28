#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"

# Fix volume permissions (Volume is mounted as root, node user needs write access)
mkdir -p "${STATE_DIR}"
chown -R node:node "${STATE_DIR}" 2>/dev/null || true

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
  chown node:node "${STATE_DIR}/openclaw.json"
  echo "[entrypoint] Created initial openclaw.json"
fi

# Drop to node user and exec the command
exec gosu node "$@"
