#!/usr/bin/env bash
# ============================================================================
# Specmatic Contract + Resiliency Test Runner
# ============================================================================
#
# Runs Specmatic contract tests AND schema resiliency tests against the live
# Veritas backend using the specmatic.jar binary. Reports are generated into
# build/reports/specmatic/.
#
# Prerequisites:
#   - Java 17+ available on PATH
#   - specmatic.jar present at project root (downloaded by CI or manually)
#   - Veritas backend running on http://localhost:8000
#   - specmatic.yaml at project root
#
# Usage:
#   bash run_contract_tests.sh
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_URL="http://localhost:8000"
SPECMATIC_JAR="${HOME}/.specmatic/specmatic.jar"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}Specmatic Contract + Resiliency Test Runner${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Pre-flight: specmatic.yaml ─────────────────────────────────────────────

if [ ! -f "${SCRIPT_DIR}/specmatic.yaml" ]; then
    echo -e "${RED}Error: specmatic.yaml not found at ${SCRIPT_DIR}${NC}"
    exit 1
fi

# ── Pre-flight: specmatic-groq/specmatic.yaml ──────────────────────────────

if [ ! -f "${SCRIPT_DIR}/specmatic-groq/specmatic.yaml" ]; then
    echo -e "${RED}Error: specmatic-groq/specmatic.yaml not found.${NC}"
    echo "This file drives the Specmatic LLM mock."
    exit 1
fi

# ── Pre-flight: Java ──────────────────────────────────────────────────────

if ! command -v java &>/dev/null && ! command -v java.exe &>/dev/null; then
    echo -e "${RED}Error: Java not found. Install Java 17+.${NC}"
    exit 1
fi

JAVA_CMD="java"
if command -v java.exe &>/dev/null && ! command -v java &>/dev/null; then
    JAVA_CMD="java.exe"
fi

# ── Pre-flight: specmatic.jar ─────────────────────────────────────────────

SPECMATIC_VERSION="2.50.0"  # pin to a specific version

if [ ! -f "$SPECMATIC_JAR" ]; then
    echo "Downloading Specmatic JAR..."
    mkdir -p "${HOME}/.specmatic"
    curl -L -o "$SPECMATIC_JAR" \
      "https://github.com/specmatic/specmatic/releases/download/${SPECMATIC_VERSION}/specmatic.jar"
    echo "Specmatic JAR downloaded to $SPECMATIC_JAR"
fi

SPECMATIC_JAR_PATH="${SPECMATIC_JAR}"
if [[ "$JAVA_CMD" == *".exe" ]] && command -v wslpath &>/dev/null; then
    SPECMATIC_JAR_PATH=$(wslpath -w "$SPECMATIC_JAR")
fi

# ── Start Specmatic LLM mock via specmatic-groq/specmatic.yaml ────────────
#
# Previously used: java -jar specmatic.jar stub groq_openapi.yaml
# That ran in MOCK_LLM mode, bypassing the Specmatic mock server entirely,
# causing unmatched requests during resiliency tests.
#
# Now uses: java -jar specmatic.jar mock --config specmatic-groq/specmatic.yaml
# This starts the proper Specmatic mock driven by the v3 config.

echo "Starting Specmatic LLM mock (specmatic-groq/specmatic.yaml)..."
cd "${SCRIPT_DIR}/specmatic-groq"
"$JAVA_CMD" -jar "${SPECMATIC_JAR_PATH}" virtualize \
    --config "${SCRIPT_DIR}/specmatic-groq/specmatic.yaml" \
    --port 9000 &
STUB_PID=$!
cd "${SCRIPT_DIR}"

# Wait for stub to be ready
ELAPSED=0
until curl -sf http://localhost:9000/_specmatic/health \
  > /dev/null 2>&1; do
  if [ "$ELAPSED" -ge 30 ]; then
    echo "ERROR: Groq stub did not start within 30s"
    kill $STUB_PID 2>/dev/null
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo "Groq stub is ready on port 9000."

# ── Configure backend to use the stub ────────────────────────────────────

export GROQ_BASE_URL=http://localhost:9000
export GROQ_API_KEY=mock-key

# ── Start Veritas backend ─────────────────────────────────────────────────

if command -v docker-compose &>/dev/null; then
    echo "Starting Veritas backend..."
    docker-compose up -d > /dev/null
fi

# Cross-platform wait for backend health
# Works on Linux and macOS — no timeout command needed
WAIT_SECONDS=120
ELAPSED=0
INTERVAL=3

echo "Waiting for Veritas backend to be ready..."
until curl -sf http://localhost:8000/health \
  > /dev/null 2>&1; do
  if [ "$ELAPSED" -ge "$WAIT_SECONDS" ]; then
    echo "ERROR: Backend did not start within ${WAIT_SECONDS}s"
    kill $STUB_PID 2>/dev/null
    exit 1
  fi
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done
echo "Backend is ready."

echo "Verifying actuator endpoint..."
ELAPSED=0
until curl -sf http://localhost:8000/actuator/mappings \
  > /dev/null 2>&1; do
  if [ "$ELAPSED" -ge "$WAIT_SECONDS" ]; then
    echo "ERROR: Actuator endpoint not ready within ${WAIT_SECONDS}s"
    kill $STUB_PID 2>/dev/null
    exit 1
  fi
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done
echo "Actuator endpoint verified."

# ── Run Specmatic contract + resiliency tests via JAR ─────────────────────

echo ""
echo -e "${BOLD}Running Specmatic contract + resiliency tests...${NC}"
echo "(schemaResiliencyTests: all is enabled in specmatic.yaml)"
echo ""

set +e

"$JAVA_CMD" -jar "${SPECMATIC_JAR_PATH}" test \
    --testBaseURL="${BACKEND_URL}" \
    2>&1

TEST_EXIT_CODE=${PIPESTATUS[0]:-$?}
set -e

# ── Stop Groq stub ────────────────────────────────────────────────────────

echo "Stopping Groq stub..."
kill $STUB_PID 2>/dev/null
wait $STUB_PID 2>/dev/null || true

# ── Result summary ────────────────────────────────────────────────────────

echo ""
if [ "${TEST_EXIT_CODE}" -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  All contract + resiliency tests PASSED ✓${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  Contract + resiliency tests FAILED ✗ (exit: ${TEST_EXIT_CODE})${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

echo ""
echo -e "${YELLOW}HTML report: build/reports/specmatic/test/html/index.html${NC}"
echo -e "${YELLOW}CTRF report: build/reports/specmatic/test/ctrf/ctrf-report.json${NC}"

exit "${TEST_EXIT_CODE}"
