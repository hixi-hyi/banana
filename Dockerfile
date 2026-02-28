FROM ghcr.io/openclaw/openclaw:latest

# Switch to root for Railway (volume permissions, system package installs)
USER root

# Use shell as entrypoint so Railway's startCommand always runs through /bin/sh
ENTRYPOINT ["/bin/sh", "-c"]

# Add custom tools here as needed
# Example: 1Password CLI
# RUN curl -sS https://downloads.1password.com/linux/debian/amd64/stable/1password-cli-amd64-latest.deb -o /tmp/op.deb \
#     && dpkg -i /tmp/op.deb \
#     && rm /tmp/op.deb
