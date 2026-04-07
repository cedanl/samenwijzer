FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m vscode
USER vscode
WORKDIR /workspace
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/vscode/.local/bin:${PATH}"
