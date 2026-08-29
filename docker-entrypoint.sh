#!/bin/bash
set -euo pipefail

echo "========================================"
echo " Soy Grandez Engine - Docker Entrypoint"
echo "========================================"
echo "Environment: ${APP_ENV:-not-set}"
echo "User: $(whoami)"
echo "Working directory: $(pwd)"
echo ""

APP_HOME="${APP_HOME:-/app}"
PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"

mkdir -p "${APP_HOME}/logs"
mkdir -p "${APP_HOME}/screenshots"

echo "[1/4] Checking directory permissions..."
if [ ! -w "${APP_HOME}/logs" ]; then
    echo "WARN: logs directory is not writable, attempting fix..."
    chmod -R u+w "${APP_HOME}/logs" 2>/dev/null || true
fi
echo "  OK - logs and screenshots directories ready"

echo ""
echo "[2/4] Verifying Playwright Chromium installation..."
CHROMIUM_PATH="${PLAYWRIGHT_BROWSERS_PATH}/chromium-*"
if compgen -G "${CHROMIUM_PATH}" > /dev/null; then
    CHROMIUM_COUNT=$(compgen -G "${CHROMIUM_PATH}" | wc -l)
    echo "  OK - Chromium found (${CHROMIUM_COUNT} version(s))"
else
    echo "  WARN - Chromium not found in ${PLAYWRIGHT_BROWSERS_PATH}"
    echo "  Installing Chromium for Playwright..."
    python -m playwright install --with-deps chromium || {
        echo "  ERROR: Failed to install Chromium. Attempting fallback..."
        python -m playwright install chromium || {
            echo "  FATAL: Could not install Chromium. Playwright scraping will fail."
            exit 1
        }
    }
    echo "  OK - Chromium installed successfully"
fi

echo ""
echo "[3/4] Validating critical environment variables..."
CRITICAL_VARS=("DB_HOST" "DB_NAME" "DB_USER" "LARAVEL_API_URL" "ENCRYPTION_KEY")
MISSING_VARS=()
for VAR in "${CRITICAL_VARS[@]}"; do
    VALUE="${!VAR:-}"
    if [ -z "$VALUE" ]; then
        MISSING_VARS+=("$VAR")
    else
        echo "  OK - ${VAR} is set"
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo ""
    echo "  ⚠️  WARNING: Missing critical environment variables:"
    for VAR in "${MISSING_VARS[@]}"; do
        echo "    - ${VAR}"
    done
    echo "  Engine will start but some features may not work correctly."
    echo "  Check your .env file or docker-compose environment configuration."
fi

echo ""
echo "[4/4] Entrypoint ready. Executing command:"
echo "  $ $*"
echo "========================================"
echo ""

exec "$@"
