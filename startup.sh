#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
CONFIG="${STATE_DIR}/openclaw.json"

echo "[startup] state dir: ${STATE_DIR}"
mkdir -p "${STATE_DIR}"

node -e "
const fs = require('fs');
const p = '${CONFIG}';
let c = {};
try { c = JSON.parse(fs.readFileSync(p, 'utf8')); } catch(e) {}
c.gateway = c.gateway || {};
c.gateway.controlUi = c.gateway.controlUi || {};
c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
fs.writeFileSync(p, JSON.stringify(c, null, 2));
console.log('[startup] config patched');
"

PORT="${PORT:-8080}"
echo "[startup] launching gateway on port ${PORT}"
exec node /app/openclaw.mjs gateway run \
  --bind lan \
  --port "${PORT}" \
  --auth token \
  --allow-unconfigured
