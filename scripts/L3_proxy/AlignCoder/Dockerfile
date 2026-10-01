# AlignCoder Docker environment

FROM docker.1ms.run/python:3.10-slim

# 代理（用于额外 pip 安装）
ARG HTTP_PROXY=http://172.19.135.130:5000
ARG HTTPS_PROXY=http://172.19.135.130:5000
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

# System and Python dependencies required by AlignCoder.
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g; \
            s|http://security.debian.org|http://mirrors.aliyun.com|g' \
            /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g; \
            s|http://security.debian.org|http://mirrors.aliyun.com|g' \
            /etc/apt/sources.list && \
    apt-get update && apt-get install -y git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /tmp/aligncoder_requirements.txt

RUN pip install --no-cache-dir \
    torch==2.0.1+cu118 torchaudio==2.0.2+cu118 torchvision==0.15.2+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

RUN grep -v "^torch" /tmp/aligncoder_requirements.txt | \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /dev/stdin

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    requests sacrebleu rank-bm25 prettytable editdistance \
    python-Levenshtein openai anthropic

# 清除代理
ENV http_proxy=
ENV https_proxy=

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/workspace/.cache/huggingface

CMD ["/bin/bash"]
