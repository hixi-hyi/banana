#!/bin/sh
set -e

echo "[entrypoint] Starting - user: $(id -u), STATE_DIR env: ${OPENCLAW_STATE_DIR}"

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
CONFIG="${STATE_DIR}/openclaw.json"

# Create state dir
mkdir -p "${STATE_DIR}"
echo "[entrypoint] STATE_DIR ready: ${STATE_DIR}"

# Always write/patch the config to ensure dangerouslyAllowHostHeaderOriginFallback is set
node -e "
  const fs = require('fs');
  const p = '${CONFIG}';
  let c = {};
  try { c = JSON.parse(fs.readFileSync(p, 'utf8')); } catch(e) { console.log('[entrypoint] No existing config, creating fresh'); }
  c.gateway = c.gateway || {};
  c.gateway.controlUi = c.gateway.controlUi || {};
  c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
  fs.writeFileSync(p, JSON.stringify(c, null, 2));
  console.log('[entrypoint] Config written to ' + p);
  console.log('[entrypoint] Config:', JSON.stringify(c.gateway.controlUi));
"

echo "[entrypoint] Launching: $@"
exec "$@"
