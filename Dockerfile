# FreelanceFlow web app: the API and the dashboard behind one URL.
#
# Stage 1 builds the React dashboard; stage 2 runs FastAPI, which serves that
# build alongside /api. For the AgentCore Runtime container, see deploy/Dockerfile.

# --- 1. build the dashboard ---------------------------------------------------
FROM node:24-slim AS dashboard
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. the API, serving the dashboard ----------------------------------------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The rupee sign U+20B9 is absent from the PDF core fonts; pdf_generator.py
# embeds DejaVu when it finds it. Without this, PDFs print "Rs." instead of ₹.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY --from=dashboard /web/dist ./frontend/dist

# Hosted-demo defaults. The disk on most hosts is wiped on restart, so the
# sample ledger is re-seeded whenever the database is empty. GEMINI_API_KEY is
# never baked in: set it as a secret in the host's dashboard.
ENV FF_DATA_DIR=/app/data \
    FF_SEED_DEMO=true \
    FF_MODEL_PROVIDER=gemini \
    FF_GEMINI_THINKING=low
RUN mkdir -p /app/data

EXPOSE 8000

# Hosts such as Render inject PORT; locally it defaults to 8000.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
