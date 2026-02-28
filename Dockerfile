FROM ghcr.io/openclaw/openclaw:latest

# Switch to root to install system packages
USER root

# Add custom tools here as needed
# Example: 1Password CLI
# RUN curl -sS https://downloads.1password.com/linux/debian/amd64/stable/1password-cli-amd64-latest.deb -o /tmp/op.deb \
#     && dpkg -i /tmp/op.deb \
#     && rm /tmp/op.deb

COPY docker-entrypoint-railway.sh /usr/local/bin/docker-entrypoint-railway.sh
RUN chmod +x /usr/local/bin/docker-entrypoint-railway.sh

# Switch back to node user
USER node

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-railway.sh"]
