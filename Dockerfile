# ========================================
# Stage 1: Builder - Instalación de dependencias
# ========================================
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ========================================
# Stage 2: Runtime - Imagen de ejecución final
# ========================================
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR ${APP_HOME}

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser && \
    mkdir -p ${APP_HOME}/logs ${APP_HOME}/screenshots ${PLAYWRIGHT_BROWSERS_PATH} && \
    chown -R appuser:appuser ${APP_HOME} ${PLAYWRIGHT_BROWSERS_PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    wget \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/* && \
    rm -rf /wheels

RUN python -m playwright install --with-deps chromium && \
    chown -R appuser:appuser ${PLAYWRIGHT_BROWSERS_PATH}

COPY . ${APP_HOME}

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown -R appuser:appuser ${APP_HOME}

USER appuser

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "docker-entrypoint.sh"]

CMD ["python", "worker.py"]
