FROM docker.m.daocloud.io/library/ubuntu:22.04

# ARG HTTP_PROXY
# ARG HTTPS_PROXY
ARG HTTP_PROXY=http://172.19.135.130:5000
ARG HTTPS_PROXY=http://172.19.135.130:5000
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# Use Aliyun mirrors for apt (supports both amd64 and arm64)
RUN sed -i \
    's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g; \
     s|http://ports.ubuntu.com|http://mirrors.aliyun.com|g; \
     s|http://security.ubuntu.com|http://mirrors.aliyun.com|g' \
    /etc/apt/sources.list

# ===== Base tools =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl wget git unzip ca-certificates \
    build-essential software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# ===== Python 3.11 =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv redis-server \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip3 config set global.trusted-host mirrors.aliyun.com
RUN pip3 install --no-cache-dir lizard flake8
ENV PIP_TIMEOUT=300

# ===== C++ (gcc-12) =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc-12 g++-12 cmake ninja-build pkg-config libgtest-dev zlib1g-dev \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 100 \
    && rm -rf /var/lib/apt/lists/*

# ===== Go 1.23 (auto-detect arch) =====
RUN ARCH=$(dpkg --print-architecture) && \
    case "$ARCH" in \
        amd64) GOARCH="amd64" ;; \
        arm64) GOARCH="arm64" ;; \
        *) echo "Unsupported arch: $ARCH" && exit 1 ;; \
    esac && \
    wget -qO /tmp/go.tar.gz "https://golang.google.cn/dl/go1.23.4.linux-${GOARCH}.tar.gz" \
    && tar -C /usr/local -xzf /tmp/go.tar.gz && rm /tmp/go.tar.gz
ENV PATH=/usr/local/go/bin:$PATH
ENV GOPROXY=https://goproxy.cn,direct

# ===== Java: JDK 8 + 11 + 17, Maven, Gradle 7.6.4 =====
ENV GRADLE_VERSION=7.6.4
ENV GRADLE_HOME=/opt/gradle/gradle-${GRADLE_VERSION}

# Install Eclipse Temurin JDK 8/11/17 (official, supports arm64 + amd64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg2 apt-transport-https \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/apt/keyrings \
    && wget -qO /etc/apt/keyrings/adoptium.asc https://packages.adoptium.net/artifactory/api/gpg/key/public \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(. /etc/os-release && echo "$VERSION_CODENAME") main" \
       > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       temurin-8-jdk temurin-11-jdk temurin-17-jdk maven \
    && rm -rf /var/lib/apt/lists/*

# Create arch-neutral symlinks
RUN ARCH=$(dpkg --print-architecture) && \
    ln -sf /usr/lib/jvm/temurin-11-jdk-${ARCH} /usr/lib/jvm/java-11-openjdk && \
    ln -sf /usr/lib/jvm/temurin-17-jdk-${ARCH} /usr/lib/jvm/java-17-openjdk && \
    ln -sf /usr/lib/jvm/temurin-8-jdk-${ARCH} /usr/lib/jvm/java-8-openjdk

RUN curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
    -o /tmp/gradle.zip \
    && mkdir -p /opt/gradle \
    && unzip -q /tmp/gradle.zip -d /opt/gradle \
    && rm /tmp/gradle.zip

ENV PATH=${GRADLE_HOME}/bin:${PATH}
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

# Maven: Aliyun mirror + proxy
RUN mkdir -p /root/.m2 && \
    printf '<?xml version="1.0" encoding="UTF-8"?>\n\
<settings>\n\
<mirrors><mirror>\n\
<id>aliyun</id><mirrorOf>*</mirrorOf>\n\
<url>https://maven.aliyun.com/repository/public</url>\n\
</mirror></mirrors>\n\
<proxies><proxy>\n\
<id>http-proxy</id><active>true</active>\n\
<protocol>http</protocol><host>172.19.135.130</host><port>5000</port>\n\
</proxy><proxy>\n\
<id>https-proxy</id><active>true</active>\n\
<protocol>https</protocol><host>172.19.135.130</host><port>5000</port>\n\
</proxy></proxies>\n\
</settings>\n' > /root/.m2/settings.xml

# Gradle: Aliyun mirror (dependencies + plugins)
RUN mkdir -p ${GRADLE_HOME}/init.d && \
    printf 'settingsEvaluated { settings ->\n\
    settings.pluginManagement {\n\
        repositories {\n\
            gradlePluginPortal()\n\
            maven { url "https://maven.aliyun.com/repository/gradle-plugin" }\n\
            maven { url "https://maven.aliyun.com/repository/public" }\n\
            mavenCentral()\n\
        }\n\
    }\n\
}\n\
allprojects {\n\
    repositories {\n\
        maven { url "https://maven.aliyun.com/repository/public" }\n\
        maven { url "https://maven.aliyun.com/repository/gradle-plugin" }\n\
        gradlePluginPortal()\n\
        mavenCentral()\n\
    }\n\
}\n' > ${GRADLE_HOME}/init.d/mirror.gradle

# Gradle: proxy settings
RUN mkdir -p /root/.gradle && \
    printf 'systemProp.http.proxyHost=172.19.135.130\n\
systemProp.http.proxyPort=5000\n\
systemProp.https.proxyHost=172.19.135.130\n\
systemProp.https.proxyPort=5000\n\
systemProp.http.nonProxyHosts=localhost|127.0.0.1\n' > /root/.gradle/gradle.properties

# ===== JavaScript: Node 14/18/20/22 via n =====
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm config set registry https://registry.npmmirror.com \
    && npm install -g n \
    && n 14 && n 18 && n 20 && n 22

# ===== Container-internal batch runner =====
COPY docker/scripts/run_batch.py /entrypoint/run_batch.py

WORKDIR /workspace
