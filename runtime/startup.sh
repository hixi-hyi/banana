#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
REPO_DIR="${STATE_DIR}/repo"
WORKSPACE_DIR="${REPO_DIR}/workspace"
CONFIG="${STATE_DIR}/openclaw.json"
AGENT_ID="${OPENCLAW_AGENT_ID:-banana}"
AGENT_DIR="${STATE_DIR}/agents/${AGENT_ID}/agent"

echo "[startup] state dir: ${STATE_DIR}"
echo "[startup] repo:      ${REPO_DIR}"
echo "[startup] workspace: ${WORKSPACE_DIR}"
mkdir -p "${STATE_DIR}" "${REPO_DIR}" "${WORKSPACE_DIR}" "${AGENT_DIR}"

# Remove legacy workspace directory (pre-refactor: was the repo root clone)
# Kept this data in REPO_DIR instead; old path confuses git operations
OLD_WORKSPACE="${STATE_DIR}/workspace"
if [ -d "${OLD_WORKSPACE}/.git" ]; then
  echo "[startup] removing legacy workspace at ${OLD_WORKSPACE}"
  rm -rf "${OLD_WORKSPACE}"
fi

# ── 1. Clone or pull the banana repo ─────────────────────────────────────────
# Full repo lives at REPO_DIR; agent workspace is repo/workspace/ subdirectory
if [ -n "${GITHUB_TOKEN}" ]; then
  REPO_URL="https://${GITHUB_TOKEN}@github.com/hixi-hyi/banana"
  if [ -d "${REPO_DIR}/.git" ]; then
    echo "[startup] repo: pulling latest"
    git -C "${REPO_DIR}" remote set-url origin "${REPO_URL}" 2>/dev/null || true
    git -C "${REPO_DIR}" pull --ff-only origin main 2>&1 || echo "[startup] git pull skipped (local changes?)"
  else
    echo "[startup] repo: cloning"
    # Remove directory if it exists but has no .git (e.g. partial previous clone)
    rm -rf "${REPO_DIR}"
    git clone "${REPO_URL}" "${REPO_DIR}" 2>&1
  fi
  # git config for auto-push (used by heartbeat)
  git config --global user.email "banana-railway@openclaw"
  git config --global user.name "Banana (Railway)"
  git config --global credential.helper store
  echo "https://${GITHUB_TOKEN}@github.com" > /root/.git-credentials
  chmod 600 /root/.git-credentials
  echo "[startup] git credentials configured"
fi

# ── 2. Agent auth profile (API key) ──────────────────────────────────────────
if [ -n "${ANTHROPIC_API_KEY}" ]; then
  node -e "
const fs = require('fs');
const p = '${AGENT_DIR}/auth-profiles.json';
let c = { version: 1, profiles: {}, usageStats: {} };
try { c = JSON.parse(fs.readFileSync(p, 'utf8')); } catch(e) {}
c.profiles['anthropic:default'] = {
  type: 'api_key',
  provider: 'anthropic',
  key: process.env.ANTHROPIC_API_KEY
};
fs.writeFileSync(p, JSON.stringify(c, null, 2));
console.log('[startup] agent auth-profiles.json written');
"
fi

# ── 3. Merge base config from repo, then overlay secrets ─────────────────────
# Base config lives at WORKSPACE_DIR/openclaw-config-base.json (committed to git)
# It has __FROM_ENV__ placeholders for secrets. We merge it with existing state,
# then inject real values from env vars.
node -e "
const fs = require('fs');
const configPath = '${CONFIG}';
const basePath = '${WORKSPACE_DIR}/openclaw-config-base.json';

// Deep merge: target is base, overlay is existing state (preserves runtime-only data)
function deepMerge(base, overlay) {
  if (typeof base !== 'object' || base === null) return overlay ?? base;
  if (typeof overlay !== 'object' || overlay === null) return base;
  const result = { ...base };
  for (const k of Object.keys(overlay)) {
    if (k in base && typeof base[k] === 'object' && !Array.isArray(base[k])) {
      result[k] = deepMerge(base[k], overlay[k]);
    } else {
      result[k] = overlay[k];
    }
  }
  return result;
}

// Load base config from repo (source of truth for structure/settings)
let base = {};
try { base = JSON.parse(fs.readFileSync(basePath, 'utf8')); console.log('[startup] loaded base config from repo'); }
catch(e) { console.log('[startup] no base config in repo, starting fresh'); }

// Load existing runtime state (devices, sessions refs, etc.)
let existing = {};
try { existing = JSON.parse(fs.readFileSync(configPath, 'utf8')); } catch(e) {}

// Merge: base wins for structure, existing wins for runtime-generated data
let c = deepMerge(base, existing);

// Force Railway-specific gateway settings (override local/base values)
c.gateway = c.gateway || {};
c.gateway.controlUi = c.gateway.controlUi || {};
c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
c.gateway.controlUi.allowInsecureAuth = true;
delete c.gateway.controlUi.allowedOrigins; // local-only setting
c.gateway.auth = c.gateway.auth || {};
c.gateway.auth.token = process.env.OPENCLAW_GATEWAY_TOKEN || c.gateway.auth.token || '';
c.gateway.auth.mode = 'token';
c.gateway.bind = 'lan';
c.gateway.trustedProxies = ['127.0.0.1', '100.64.0.0/10'];

// Inject Slack secrets from env vars
if (process.env.SLACK_BOT_TOKEN || process.env.SLACK_APP_TOKEN) {
  c.channels = c.channels || {};
  c.channels.slack = c.channels.slack || {};
  c.channels.slack.enabled = true;
  if (process.env.SLACK_BOT_TOKEN)
    c.channels.slack.botToken = process.env.SLACK_BOT_TOKEN;
  if (process.env.SLACK_APP_TOKEN)
    c.channels.slack.appToken = process.env.SLACK_APP_TOKEN;
  console.log('[startup] slack tokens injected from env');
}

// Remove fields that are invalid in this version of openclaw
// (may have been written by agent with wrong values)
if (c.channels && c.channels.slack) {
  delete c.channels.slack.dmPolicy;
}

// Ensure agent list is set correctly
c.agents = c.agents || {};
c.agents.defaults = c.agents.defaults || {};
c.agents.defaults.workspace = '${WORKSPACE_DIR}';
c.agents.list = c.agents.list || [];
const agentEntry = {
  id: '${AGENT_ID}',
  name: 'Banana',
  workspace: '${WORKSPACE_DIR}',
  agentDir: '${AGENT_DIR}',
  identity: { name: 'Banana', emoji: '\uD83C\uDF4C' }
};
const idx = c.agents.list.findIndex(a => a.id === '${AGENT_ID}');
if (idx >= 0) c.agents.list[idx] = agentEntry;
else c.agents.list.push(agentEntry);

fs.writeFileSync(configPath, JSON.stringify(c, null, 2));
console.log('[startup] openclaw.json merged and patched');
"

# ── 4. Launch gateway ─────────────────────────────────────────────────────────
PORT="${PORT:-8080}"
echo "[startup] launching gateway on port ${PORT} (agent: ${AGENT_ID})"
exec node /app/openclaw.mjs gateway run \
  --bind lan \
  --port "${PORT}" \
  --auth token \
  --allow-unconfigured
