#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"

# Create state dir (runs as root, so no permission issues)
mkdir -p "${STATE_DIR}"

# Ensure controlUi dangerouslyAllowHostHeaderOriginFallback is set
# (required for Railway - merges with existing config if present)
CONFIG="${STATE_DIR}/openclaw.json"
if [ ! -f "${CONFIG}" ]; then
  echo '{"gateway":{"controlUi":{"dangerouslyAllowHostHeaderOriginFallback":true}}}' > "${CONFIG}"
  echo "[entrypoint] Created initial openclaw.json"
else
  # Patch existing config to ensure the setting is present
  node -e "
    const fs = require('fs');
    const c = JSON.parse(fs.readFileSync('${CONFIG}', 'utf8'));
    c.gateway = c.gateway || {};
    c.gateway.controlUi = c.gateway.controlUi || {};
    c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
    fs.writeFileSync('${CONFIG}', JSON.stringify(c, null, 2));
    console.log('[entrypoint] Patched openclaw.json');
  "
fi

exec "$@"
