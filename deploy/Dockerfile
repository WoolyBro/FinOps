# AgentCore Runtime container.
#
# The runtime contract requires linux/arm64 -- an amd64 image is accepted by
# the build and then fails to start, so the platform is pinned here rather
# than left to the builder's architecture.
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Fonts: the rupee sign U+20B9 is absent from the PDF core fonts, and
# pdf_generator.py looks for DejaVu on Linux. Without this, invoices render
# with "Rs. " instead of the symbol.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements-runtime.txt ./requirements-runtime.txt
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY app/ ./app/

# The container filesystem is ephemeral and per-session. This path is a
# deliberate default, not a durable one -- see docs/AGENTCORE.md.
ENV FF_DATA_DIR=/app/data
RUN mkdir -p /app/data

# The AgentCore HTTP contract: 0.0.0.0:8080, POST /invocations, GET /ping.
EXPOSE 8080

CMD ["python", "-m", "app.agentcore_app"]
