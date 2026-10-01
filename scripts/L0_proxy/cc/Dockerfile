FROM node:20

ARG HTTP_PROXY=http://host.docker.internal:7897
ARG HTTPS_PROXY=http://host.docker.internal:7897
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

RUN npm install -g @anthropic-ai/claude-code

ENV http_proxy=
ENV https_proxy=
ENV CLAUDE_CONFIG_DIR=/tmp/claude_config
ENV NODE_NO_WARNINGS=1

# Create non-root user for Claude Code (required by --permission-mode bypassPermissions)
RUN useradd -m -s /bin/bash claude_user && \
    mkdir -p /workspaces && \
    chown -R claude_user:claude_user /workspaces /tmp/claude_config 2>/dev/null || true

WORKDIR /workspaces
USER claude_user
CMD ["tail", "-f", "/dev/null"]
