FROM polycodeeval/unified:all

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    catch2 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
