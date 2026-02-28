#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
WORKSPACE_DIR="${OPENCLAW_WORKSPACE_DIR:-${STATE_DIR}/workspace}"
CONFIG="${STATE_DIR}/openclaw.json"
AGENT_ID="${OPENCLAW_AGENT_ID:-banana}"
AGENT_DIR="${STATE_DIR}/agents/${AGENT_ID}/agent"

echo "[startup] state dir: ${STATE_DIR}"
echo "[startup] workspace: ${WORKSPACE_DIR}"
mkdir -p "${STATE_DIR}" "${WORKSPACE_DIR}" "${AGENT_DIR}"

# ── 1. Workspace: clone or pull the banana repo ──────────────────────────────
if [ -n "${GITHUB_TOKEN}" ]; then
  REPO_URL="https://${GITHUB_TOKEN}@github.com/hixi-hyi/banana"
  if [ -d "${WORKSPACE_DIR}/.git" ]; then
    echo "[startup] workspace: pulling latest"
    git -C "${WORKSPACE_DIR}" remote set-url origin "${REPO_URL}" 2>/dev/null || true
    git -C "${WORKSPACE_DIR}" pull --ff-only origin main 2>&1 || echo "[startup] git pull skipped (local changes?)"
  else
    echo "[startup] workspace: cloning repo"
    git clone "${REPO_URL}" "${WORKSPACE_DIR}" 2>&1
  fi
  # git config for auto-push
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

# ── 3. Main openclaw.json config patch ───────────────────────────────────────
node -e "
const fs = require('fs');
const p = '${CONFIG}';
let c = {};
try { c = JSON.parse(fs.readFileSync(p, 'utf8')); } catch(e) {}

// Agent list (banana agent)
c.agents = c.agents || {};
c.agents.defaults = c.agents.defaults || {};
c.agents.defaults.model = c.agents.defaults.model || {};
if (!c.agents.defaults.model.primary)
  c.agents.defaults.model.primary = 'anthropic/claude-sonnet-4-6';
c.agents.defaults.workspace = '${WORKSPACE_DIR}';

const agentEntry = {
  id: '${AGENT_ID}',
  name: 'Banana',
  workspace: '${WORKSPACE_DIR}',
  agentDir: '${AGENT_DIR}',
  identity: { name: 'Banana', emoji: '\uD83C\uDF4C' }
};
c.agents.list = c.agents.list || [];
const existing = c.agents.list.findIndex(a => a.id === '${AGENT_ID}');
if (existing >= 0) c.agents.list[existing] = agentEntry;
else c.agents.list.push(agentEntry);

// Auth profile reference
c.auth = c.auth || {};
c.auth.profiles = c.auth.profiles || {};
c.auth.profiles['anthropic:default'] = { provider: 'anthropic', mode: 'api_key' };

// Gateway settings
c.gateway = c.gateway || {};
c.gateway.controlUi = c.gateway.controlUi || {};
c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
c.gateway.controlUi.allowInsecureAuth = true;
c.gateway.auth = c.gateway.auth || {};
if (!c.gateway.auth.token) c.gateway.auth.token = process.env.OPENCLAW_GATEWAY_TOKEN || '';
// Trust Railway's internal proxy IPs (100.64.x.x CGNAT range)
c.gateway.trustedProxies = ['127.0.0.1', '100.64.0.0/10'];

// Slack channel - inject tokens from env vars if not already set
if (process.env.SLACK_BOT_TOKEN || process.env.SLACK_APP_TOKEN) {
  c.channels = c.channels || {};
  c.channels.slack = c.channels.slack || {};
  c.channels.slack.enabled = true;
  c.channels.slack.mode = c.channels.slack.mode || 'socket';
  if (process.env.SLACK_BOT_TOKEN && !c.channels.slack.botToken)
    c.channels.slack.botToken = process.env.SLACK_BOT_TOKEN;
  if (process.env.SLACK_APP_TOKEN && !c.channels.slack.appToken)
    c.channels.slack.appToken = process.env.SLACK_APP_TOKEN;
  console.log('[startup] slack channel configured');
}

fs.writeFileSync(p, JSON.stringify(c, null, 2));
console.log('[startup] openclaw.json patched');
"

# ── 4. Launch gateway ─────────────────────────────────────────────────────────
PORT="${PORT:-8080}"
echo "[startup] launching gateway on port ${PORT} (agent: ${AGENT_ID})"
exec node /app/openclaw.mjs gateway run \
  --bind lan \
  --port "${PORT}" \
  --auth token \
  --allow-unconfigured
