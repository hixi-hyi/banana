#!/bin/sh
set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
WORKSPACE_DIR="${STATE_DIR}/workspace"
CONFIG="${STATE_DIR}/openclaw.json"
AGENT_ID="${OPENCLAW_AGENT_ID:-banana}"
AGENT_DIR="${STATE_DIR}/agents/${AGENT_ID}/agent"

echo "[startup] state dir: ${STATE_DIR}"
echo "[startup] workspace: ${WORKSPACE_DIR}"
mkdir -p "${STATE_DIR}" "${WORKSPACE_DIR}" "${AGENT_DIR}"

# ── 1. Fetch GITHUB_TOKEN from 1Password ─────────────────────────────────────
echo "[startup] fetching GITHUB_TOKEN from 1Password"
GITHUB_TOKEN=$(op read "op://banana/github/password")

# ── 2. Clone or pull the banana repo ─────────────────────────────────────────
REPO_URL="https://${GITHUB_TOKEN}@github.com/hixi-hyi/banana"
if [ -d "${WORKSPACE_DIR}/.git" ]; then
  echo "[startup] repo: pulling latest"
  git -C "${WORKSPACE_DIR}" remote set-url origin "${REPO_URL}" 2>/dev/null || true
  git -C "${WORKSPACE_DIR}" pull --ff-only origin main 2>&1 || echo "[startup] git pull skipped (local changes?)"
else
  echo "[startup] repo: cloning"
  rm -rf "${WORKSPACE_DIR}"
  git clone "${REPO_URL}" "${WORKSPACE_DIR}" 2>&1
fi

git config --global user.email "banana-railway@openclaw"
git config --global user.name "Banana (Railway)"
git config --global credential.helper store
git -C "${WORKSPACE_DIR}" config core.hooksPath .githooks
echo "https://${GITHUB_TOKEN}@github.com" > /root/.git-credentials
chmod 600 /root/.git-credentials
echo "[startup] git credentials configured"

# ── 3. Inject Anthropic API key into auth-profiles.json ──────────────────────
echo "[startup] injecting auth-profiles.json"
op inject --force -i "${WORKSPACE_DIR}/runtime/auth-profiles.json" -o "${AGENT_DIR}/auth-profiles.json"

# ── 4. Inject all secrets into openclaw.json ─────────────────────────────────
echo "[startup] injecting openclaw.json"
op inject --force -i "${WORKSPACE_DIR}/openclaw.json" -o "${CONFIG}"

# ── 5. Launch gateway ─────────────────────────────────────────────────────────
PORT="${PORT:-8080}"
echo "[startup] launching gateway on port ${PORT} (agent: ${AGENT_ID})"

exec node /app/openclaw.mjs gateway run \
  --bind lan \
  --port "${PORT}" \
  --auth token \
  --allow-unconfigured
