FROM docker.1ms.run/python:3.10-slim

ARG HTTP_PROXY=http://172.19.135.130:5000
ARG HTTPS_PROXY=http://172.19.135.130:5000
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    tree-sitter==0.25.2 tree-sitter-python==0.25.0 \
    tree-sitter-java tree-sitter-go tree-sitter-cpp tree-sitter-javascript \
    tree-sitter-typescript \
    openai anthropic numpy httpx python-dotenv tiktoken

ENV http_proxy=
ENV https_proxy=
ENV PYTHONUNBUFFERED=1
CMD ["/bin/bash"]
