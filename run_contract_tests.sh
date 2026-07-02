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
#   - Docker installed and running
#   - Veritas backend running on http://localhost:8000
#   - specmatic.yaml at project root
#
# Usage:
#   bash run_contract_tests.sh
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT_FILE="${SCRIPT_DIR}/specmatic.yaml"
REPORT_FILE="${SCRIPT_DIR}/contract_test_results.json"
BACKEND_URL="http://localhost:8000"
TEST_CONTAINER_NAME="specmatic-contract-test"

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

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    exit 1
fi

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
    echo "Start it with: docker-compose up -d --build"
    exit 1
fi

# ── Clean up any previous test container ───────────────────────────────────

docker stop "${TEST_CONTAINER_NAME}" 2>/dev/null || true
docker rm "${TEST_CONTAINER_NAME}" 2>/dev/null || true

# ── Run Specmatic contract tests ──────────────────────────────────────────

echo ""
echo -e "${BOLD}Running Specmatic contract tests...${NC}"
echo ""

# Run Specmatic test command against the live backend
# --host and --port point to the running Veritas instance
set +e
docker run \
    --name "${TEST_CONTAINER_NAME}" \
    --network host \
    -v "${CONTRACT_FILE}:/usr/src/app/specmatic.yaml:ro" \
    specmatic/specmatic test \
    --host "localhost" \
    --port 8000 \
    "/usr/src/app/specmatic.yaml" \
    2>&1 | tee /tmp/specmatic_output.txt

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
    "tool_version": "docker:specmatic/specmatic:latest"
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

docker rm "${TEST_CONTAINER_NAME}" 2>/dev/null || true

exit "${TEST_EXIT_CODE}"
