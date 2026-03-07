FROM ghcr.io/openclaw/openclaw:2026.3.2
# https://github.com/openclaw/openclaw/pkgs/container/openclaw

# Switch to root for Railway (volume permissions, system package installs)
USER root

COPY runtime/startup.sh /startup.sh
RUN chmod +x /startup.sh

# Install 1Password CLI for secret injection at startup
RUN apt-get update \
    && apt-get install -y curl gpg \
    && curl -sS https://downloads.1password.com/linux/debian/amd64/stable/1password-cli-amd64-latest.deb -o /tmp/op.deb \
    && apt-get install -y /tmp/op.deb \
    && rm /tmp/op.deb \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (gh)
RUN apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# startup.sh fetches secrets from 1Password and launches the gateway
ENTRYPOINT ["/startup.sh"]
