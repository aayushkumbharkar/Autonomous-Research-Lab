#!/usr/bin/env bash
# ============================================================================
# Specmatic Contract Test Runner
# ============================================================================
#
# Runs Specmatic contract tests against the live Veritas backend using the
# specmatic.jar binary. Reports are generated into build/reports/specmatic/.
#
# Prerequisites:
#   - Java 17+ available on PATH
#   - specmatic.jar present at project root (downloaded by CI or manually)
#   - Veritas backend running on http://localhost:8000 in CONTRACT_TEST_MODE
#   - specmatic.yaml at project root
#
# Usage:
#   bash run_contract_tests.sh
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure license.txt exists so Specmatic doesn't crash with NoSuchFileException
if [ ! -f "${SCRIPT_DIR}/license.txt" ]; then
    echo "# Place your Specmatic trial license here." > "${SCRIPT_DIR}/license.txt"
fi

BACKEND_URL="http://localhost:8000"
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

# ── Pre-flight: specmatic.yaml ─────────────────────────────────────────────

if [ ! -f "${SCRIPT_DIR}/specmatic.yaml" ]; then
    echo -e "${RED}Error: specmatic.yaml not found at ${SCRIPT_DIR}${NC}"
    exit 1
fi

# ── Pre-flight: Java ──────────────────────────────────────────────────────

if ! command -v java &>/dev/null; then
    echo -e "${RED}Error: Java not found. Install Java 17+.${NC}"
    exit 1
fi

# ── Pre-flight: specmatic.jar ─────────────────────────────────────────────

if [ ! -f "${SPECMATIC_JAR}" ]; then
    echo -e "${RED}Error: specmatic.jar not found at ${SPECMATIC_JAR}${NC}"
    echo "Download it with:"
    echo "  curl -L -o specmatic.jar https://github.com/specmatic/specmatic/releases/latest/download/specmatic.jar"
    exit 1
fi

# ── Pre-flight: Backend health ────────────────────────────────────────────

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

# ── Pre-flight: Contract test mode ────────────────────────────────────────

echo -n "Verifying that Veritas backend is in Contract Test Mode... "
HEALTH_STATUS=$(curl -sf "${BACKEND_URL}/api/health" || echo "")
if [[ "$HEALTH_STATUS" != *"contract-test"* ]]; then
    echo -e "${RED}FAILED${NC}"
    echo ""
    echo "The Veritas backend is not running in Contract Test Mode."
    echo "Add 'CONTRACT_TEST_MODE=true' to backend/.env and restart."
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# ── Pre-flight: Actuator endpoint ─────────────────────────────────────────

echo -n "Verifying /actuator/mappings endpoint... "
if curl -sf "${BACKEND_URL}/actuator/mappings" > /dev/null 2>&1; then
    ROUTE_COUNT=$(curl -sf "${BACKEND_URL}/actuator/mappings" | python3 -c "
import json,sys
data=json.load(sys.stdin)
routes=data['contexts']['application']['mappings']['dispatcherServlets']['dispatcherServlet']
print(len(routes))
" 2>/dev/null || echo "?")
    echo -e "${GREEN}OK (${ROUTE_COUNT} routes discovered)${NC}"
else
    echo -e "${YELLOW}WARNING: /actuator/mappings not reachable — coverage may be incomplete${NC}"
fi

# ── Run Specmatic contract tests via JAR ──────────────────────────────────

echo ""
echo -e "${BOLD}Running Specmatic contract tests...${NC}"
echo ""

set +e

SPECMATIC_LICENSE_KEY="${SPECMATIC_LICENSE_KEY:-}" \
java -jar "${SPECMATIC_JAR}" test \
    --testBaseURL="${BACKEND_URL}" \
    2>&1

TEST_EXIT_CODE=${PIPESTATUS[0]:-$?}
set -e

# ── Result summary ────────────────────────────────────────────────────────

echo ""
if [ "${TEST_EXIT_CODE}" -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  All contract tests PASSED ✓${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  Contract tests FAILED ✗ (exit: ${TEST_EXIT_CODE})${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

echo ""
echo -e "${YELLOW}HTML report: build/reports/specmatic/test/html/index.html${NC}"
echo -e "${YELLOW}CTRF report: build/reports/specmatic/test/ctrf/ctrf-report.json${NC}"

exit "${TEST_EXIT_CODE}"
