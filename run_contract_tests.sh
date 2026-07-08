#!/usr/bin/env bash
# ============================================================================
# Specmatic Contract Test Runner
# ============================================================================
#
# Runs Specmatic contract tests against the live Veritas backend.
# Used by CI pipeline (.github/workflows/specmatic-contract-tests.yml)
# and can be run locally.
#
# Prerequisites:
#   - Docker installed and running (preferred) OR Java 17+ (JAR fallback)
#   - Veritas backend running on http://localhost:8000
#   - specmatic.yaml at project root
#
# Usage:
#   bash run_contract_tests.sh
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure license.txt exists (even as a placeholder) so Specmatic doesn't crash with NoSuchFileException
if [ ! -f "${SCRIPT_DIR}/license.txt" ]; then
    echo "# Place your Specmatic trial license here." > "${SCRIPT_DIR}/license.txt"
fi

CONTRACT_FILE="${SCRIPT_DIR}/specmatic.yaml"
REPORT_FILE="${SCRIPT_DIR}/contract_test_results.json"
BACKEND_URL="http://localhost:8000"
TEST_CONTAINER_NAME="specmatic-contract-test"
SPECMATIC_JAR="${SCRIPT_DIR}/specmatic.jar"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}Specmatic Contract Test Runner${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────────

if [ ! -f "${CONTRACT_FILE}" ]; then
    echo -e "${RED}Error: Contract file not found: ${CONTRACT_FILE}${NC}"
    exit 1
fi

# Check if backend is running
echo -n "Checking if Veritas backend is running... "
if curl -sf "${BACKEND_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo ""
    echo "The Veritas backend is not responding at ${BACKEND_URL}/health"
    echo "Start it with: docker compose up -d --build"
    exit 1
fi

# Check if SUT is in contract test mode
echo -n "Verifying that Veritas backend is in Contract Test Mode... "
HEALTH_STATUS=$(curl -sf "${BACKEND_URL}/api/health" || echo "")
if [[ "$HEALTH_STATUS" != *"contract-test"* ]]; then
    echo -e "${RED}FAILED${NC}"
    echo ""
    echo "The Veritas backend is not running in Contract Test Mode."
    echo "To fix this:"
    echo "  1. Add 'CONTRACT_TEST_MODE=true' to backend/.env"
    echo "  2. Restart the backend container: docker compose up -d"
    echo ""
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# ── Verify actuator endpoint is reachable ─────────────────────────────────

echo -n "Verifying /actuator/mappings endpoint... "
if curl -sf "${BACKEND_URL}/actuator/mappings" > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING: /actuator/mappings not reachable — coverage may be incomplete${NC}"
fi

# ── Detect execution mode: Docker image or JAR fallback ──────────────────

USE_DOCKER=false
if command -v docker &>/dev/null && docker image inspect specmatic/specmatic > /dev/null 2>&1; then
    USE_DOCKER=true
    echo -e "${GREEN}Using Specmatic Docker image${NC}"
elif [ -f "${SPECMATIC_JAR}" ]; then
    echo -e "${YELLOW}Specmatic Docker image unavailable — using JAR fallback${NC}"
elif command -v docker &>/dev/null; then
    echo -e "${YELLOW}Docker image not cached — will use JAR if available${NC}"
fi

if [ "$USE_DOCKER" = false ] && [ ! -f "${SPECMATIC_JAR}" ]; then
    echo -e "${RED}Error: Neither Specmatic Docker image nor specmatic.jar found.${NC}"
    echo "Run the CI workflow (which downloads the JAR) or pull the image:"
    echo "  docker pull specmatic/specmatic:latest"
    exit 1
fi

# ── Clean up any previous test container ───────────────────────────────────

if [ "$USE_DOCKER" = true ]; then
    docker stop "${TEST_CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${TEST_CONTAINER_NAME}" 2>/dev/null || true
fi

# ── Run Specmatic contract tests ──────────────────────────────────────────

echo ""
echo -e "${BOLD}Running Specmatic contract tests...${NC}"
echo ""

LICENSE_FILE="${SCRIPT_DIR}/license.txt"
set +e

if [ "$USE_DOCKER" = true ]; then
    # ── Docker path ──────────────────────────────────────────────────────
    LICENSE_OPTS=()
    if [ -f "${LICENSE_FILE}" ]; then
        LICENSE_OPTS=(-v "$(pwd)/license.txt:/usr/src/app/license.txt:ro")
    fi

    docker run \
        --name "${TEST_CONTAINER_NAME}" \
        --network host \
        "${LICENSE_OPTS[@]}" \
        -e SPECMATIC_LICENSE_KEY="${SPECMATIC_LICENSE_KEY:-}" \
        -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml:ro" \
        -v "$(pwd)/openapi.yaml:/usr/src/app/openapi.yaml:ro" \
        -v "$(pwd)/examples:/usr/src/app/examples:ro" \
        specmatic/specmatic test \
        --testBaseURL="${BACKEND_URL}" \
        2>&1 | tee /tmp/specmatic_output.txt
else
    # ── JAR fallback path ────────────────────────────────────────────────
    if ! command -v java &>/dev/null; then
        echo -e "${RED}Error: Java not found. Install Java 17+ to use the JAR fallback.${NC}"
        exit 1
    fi

    SPECMATIC_LICENSE_KEY="${SPECMATIC_LICENSE_KEY:-}" \
    java -jar "${SPECMATIC_JAR}" test \
        --testBaseURL="${BACKEND_URL}" \
        2>&1 | tee /tmp/specmatic_output.txt
fi

TEST_EXIT_CODE=${PIPESTATUS[0]}
set -e

# ── Capture results ───────────────────────────────────────────────────────

echo ""

# Build a JSON report from the output
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ "${TEST_EXIT_CODE}" -eq 0 ]; then
    STATUS="passed"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  All contract tests PASSED ✓${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    STATUS="failed"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  Contract tests FAILED ✗ (exit: ${TEST_EXIT_CODE})${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

# Write JSON report
cat > "${REPORT_FILE}" << EOF
{
  "test_run": {
    "timestamp": "${TIMESTAMP}",
    "status": "${STATUS}",
    "exit_code": ${TEST_EXIT_CODE},
    "contract_file": "specmatic.yaml",
    "backend_url": "${BACKEND_URL}",
    "tool": "specmatic",
    "tool_version": "$([ "$USE_DOCKER" = true ] && echo 'docker:specmatic/specmatic:latest' || echo "jar:${SPECMATIC_JAR}")"
  },
  "output": $(python3 -c "
import json, sys
with open('/tmp/specmatic_output.txt', 'r') as f:
    print(json.dumps(f.read()))
" 2>/dev/null || echo '"output capture failed"')
}
EOF

echo ""
echo -e "${YELLOW}Report saved to: ${REPORT_FILE}${NC}"

# ── Cleanup ───────────────────────────────────────────────────────────────

if [ "$USE_DOCKER" = true ]; then
    docker rm "${TEST_CONTAINER_NAME}" 2>/dev/null || true
fi

exit "${TEST_EXIT_CODE}"
