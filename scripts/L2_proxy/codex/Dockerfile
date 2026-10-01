FROM node:20

ARG HTTP_PROXY=http://host.docker.internal:7897
ARG HTTPS_PROXY=http://host.docker.internal:7897
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

RUN npm install -g @openai/codex

ENV http_proxy=
ENV https_proxy=
ENV CODEX_HOME=/home/codex_user/.codex
ENV NODE_NO_WARNINGS=1

RUN useradd -m -s /bin/bash codex_user && \
    mkdir -p /workspaces /home/codex_user/.codex && \
    chown -R codex_user:codex_user /workspaces /home/codex_user/.codex /home/codex_user 2>/dev/null || true

WORKDIR /workspaces
USER codex_user
CMD ["tail", "-f", "/dev/null"]
