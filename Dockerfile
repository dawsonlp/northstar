# Northstar Intent & Governance Authority Service Container
FROM python:3.12-slim

# Install system dependencies & uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml README.md ./

# Copy source code
COPY src/ src/
COPY intent/ intent/
COPY adrs/ adrs/
COPY .northstar/ .northstar/

# Install python package and dependencies
RUN uv pip install --system --no-cache .

# Environment configuration
ENV NORTHSTAR_WORKSPACE_ROOT=/workspace
ENV PORT=9480
ENV PYTHONUNBUFFERED=1

EXPOSE 9480

CMD ["uvicorn", "northstar.service.app:app", "--host", "0.0.0.0", "--port", "9480"]
