# 🍌 Banana - OpenClaw Agent Workspace

This is the workspace for the Banana agent personality.

## Structure

- `SOUL.md` - Personality and values
- `AGENTS.md` - Workspace rules and behavior
- `USER.md` - User information
- `MEMORY.md` - Long-term memory
- `HEARTBEAT.md` - Periodic check tasks
- `memory/` - Daily logs
- `skills/` - Custom skills
- `projects/` - Working projects
- `config/` - Configuration files

## OpenClaw Configuration

This workspace is managed by OpenClaw agent `banana`.

```json
{
  "agents": {
    "list": [
      {
        "id": "banana",
        "name": "Banana",
        "workspace": "~/Workspaces/github.com/hixi-hyi/banana",
        "agentDir": "~/.openclaw/agents/banana/agent",
        "identity": {
          "name": "Banana",
          "emoji": "🍌",
          "description": "明るく元気なアシスタント"
        }
      }
    ]
  }
}
```

## Git Management

This workspace is version controlled with Git.
Regular commits help track the agent's evolution.

---

🍌 Stay flexible, stay positive!
