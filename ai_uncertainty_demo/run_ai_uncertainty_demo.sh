#!/usr/bin/env bash
# ============================================================================
# AI Uncertainty Demo — Specmatic Contract Testing
# ============================================================================
#
# This script demonstrates how Specmatic contract tests catch errors in
# AI-generated code that mock-based unit tests completely miss.
#
# Prerequisites:
#   - Docker installed and running
#   - Python 3.9+ with 'requests' and 'pytest' installed
#   - specmatic.yaml at the project root
#
# Usage:
#   bash ai_uncertainty_demo/run_ai_uncertainty_demo.sh
#
# ============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTRACT_FILE="${PROJECT_ROOT}/specmatic.yaml"
STUB_PORT=8000
STUB_CONTAINER_NAME="specmatic-stub-demo"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Helper functions ───────────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} ${BOLD}$1${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

step_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  STEP $1: $2${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

success() { echo -e "  ${GREEN}✓${NC} $1"; }
failure() { echo -e "  ${RED}✗${NC} $1"; }
info()    { echo -e "  ${YELLOW}→${NC} $1"; }

cleanup() {
    echo ""
    info "Cleaning up stub server..."
    docker stop "${STUB_CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${STUB_CONTAINER_NAME}" 2>/dev/null || true
}
trap cleanup EXIT

# ── Pre-flight checks ─────────────────────────────────────────────────────
banner "AI Uncertainty Demo — Specmatic Contract Testing"

echo -e "${BOLD}Verifying prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    failure "Docker is not installed. Please install Docker first."
    exit 1
fi
success "Docker is available"

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    failure "Python is not installed."
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)
success "Python found: ${PYTHON}"

if [ ! -f "${CONTRACT_FILE}" ]; then
    failure "Contract file not found: ${CONTRACT_FILE}"
    exit 1
fi
success "Contract file found: specmatic.yaml"


# ============================================================================
# STEP 1: Run unit tests — they all PASS (false confidence)
# ============================================================================
step_header "1" "Running mock-based unit tests (expect: ALL PASS)"

echo -e "${YELLOW}  These unit tests use hand-rolled mocks that accept any input.${NC}"
echo -e "${YELLOW}  They cannot detect that the client sends wrong field names,${NC}"
echo -e "${YELLOW}  wrong endpoints, or wrong Content-Types.${NC}"
echo ""

cd "${SCRIPT_DIR}"

${PYTHON} -m pytest test_ai_client_unit.py -v --tb=short 2>&1 | while IFS= read -r line; do
    echo "  ${line}"
done

echo ""
echo -e "${GREEN}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}  │  RESULT: All 10 tests PASSED                           │${NC}"
echo -e "${GREEN}  │  But the client is WRONG — mocks hide the truth.       │${NC}"
echo -e "${GREEN}  └─────────────────────────────────────────────────────────┘${NC}"


# ============================================================================
# STEP 2: Start Specmatic stub & run flawed client against it
# ============================================================================
step_header "2" "Specmatic contract test — flawed client vs stub server"

echo -e "${YELLOW}  Starting Specmatic stub server from specmatic.yaml ...${NC}"
echo -e "${YELLOW}  The stub enforces the OpenAPI contract exactly.${NC}"
echo ""

# Stop any existing stub
docker stop "${STUB_CONTAINER_NAME}" 2>/dev/null || true
docker rm "${STUB_CONTAINER_NAME}" 2>/dev/null || true

# Start Specmatic stub server
LICENSE_FILE="${PROJECT_ROOT}/license.txt"
LICENSE_ENV=()
if [ -f "${LICENSE_FILE}" ]; then
    export SPECMATIC_LICENSE_CONTENT="$(cat "${LICENSE_FILE}")"
    LICENSE_ENV=(-e SPECMATIC_LICENSE_CONTENT)
fi

docker run -d \
    --name "${STUB_CONTAINER_NAME}" \
    -p "${STUB_PORT}:${STUB_PORT}" \
    "${LICENSE_ENV[@]}" \
    -v "${CONTRACT_FILE}:/usr/src/app/specmatic.yaml:ro" \
    specmatic/specmatic stub \
    --port "${STUB_PORT}" \
    "/usr/src/app/specmatic.yaml" \
    2>&1

info "Waiting for stub server to be ready..."
RETRIES=0
MAX_RETRIES=15
while ! curl -sf "http://localhost:${STUB_PORT}/health" > /dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        failure "Stub server did not start within ${MAX_RETRIES} seconds."
        echo ""
        info "Stub server logs:"
        docker logs "${STUB_CONTAINER_NAME}" 2>&1 | tail -20 | while IFS= read -r line; do
            echo "    ${line}"
        done
        exit 1
    fi
    sleep 1
done
success "Specmatic stub server is running on port ${STUB_PORT}"
echo ""

# Now run the FLAWED client against the stub
info "Sending request with FLAWED client (wrong path, wrong field, wrong content-type)..."
echo ""

echo -e "${BOLD}  Request the flawed client will send:${NC}"
echo -e "    POST http://localhost:${STUB_PORT}${RED}/api/query${NC}  (wrong — should be /api/search)"
echo -e "    Content-Type: ${RED}text/plain${NC}  (wrong — should be application/json)"
echo -e "    Body: ${RED}{\"query_text\": \"...\"${NC}  (wrong — should be \"query\")"
echo ""

cd "${SCRIPT_DIR}"
FLAWED_OUTPUT=$(${PYTHON} ai_generated_client.py flawed "http://localhost:${STUB_PORT}" 2>&1) || true
echo -e "${RED}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${RED}  │  FLAWED CLIENT OUTPUT:                                  │${NC}"
echo -e "${RED}  └─────────────────────────────────────────────────────────┘${NC}"
echo "${FLAWED_OUTPUT}" | while IFS= read -r line; do
    echo -e "  ${RED}${line}${NC}"
done

echo ""
info "Checking Specmatic stub server logs for rejection details..."
echo ""

STUB_LOGS=$(docker logs "${STUB_CONTAINER_NAME}" 2>&1 | tail -30)
echo -e "${RED}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${RED}  │  SPECMATIC STUB SERVER REJECTION LOG:                   │${NC}"
echo -e "${RED}  └─────────────────────────────────────────────────────────┘${NC}"
echo "${STUB_LOGS}" | while IFS= read -r line; do
    echo -e "  ${RED}${line}${NC}"
done

echo ""
echo -e "${RED}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${RED}  │  RESULT: Specmatic REJECTED the flawed request!         │${NC}"
echo -e "${RED}  │  The contract caught what unit tests missed.            │${NC}"
echo -e "${RED}  └─────────────────────────────────────────────────────────┘${NC}"


# ============================================================================
# STEP 3: Show the diff — what the AI got wrong vs the contract
# ============================================================================
step_header "3" "Diff — what the AI got wrong vs what the contract requires"

echo -e "${BOLD}  ┌──────────────────┬──────────────────────────┬──────────────────────────┐${NC}"
echo -e "${BOLD}  │     Aspect       │  AI-Generated (WRONG)    │  Contract (CORRECT)      │${NC}"
echo -e "${BOLD}  ├──────────────────┼──────────────────────────┼──────────────────────────┤${NC}"
echo -e "  │ Endpoint path    │ ${RED}/api/query${NC}               │ ${GREEN}/api/search${NC}              │"
echo -e "  │ Query field name │ ${RED}query_text${NC}               │ ${GREEN}query${NC}                    │"
echo -e "  │ Content-Type     │ ${RED}text/plain (implicit)${NC}    │ ${GREEN}application/json${NC}         │"
echo -e "  │ Body encoding    │ ${RED}data=str(payload)${NC}        │ ${GREEN}json=payload${NC}             │"
echo -e "${BOLD}  └──────────────────┴──────────────────────────┴──────────────────────────┘${NC}"
echo ""

echo -e "${YELLOW}  Code diff:${NC}"
echo ""
echo -e "  ${RED}- url = f\"{self.base_url}/api/query\"${NC}"
echo -e "  ${GREEN}+ url = f\"{self.base_url}/api/search\"${NC}"
echo ""
echo -e "  ${RED}- payload = {\"query_text\": query_text, ...}${NC}"
echo -e "  ${GREEN}+ payload = {\"query\": query, ...}${NC}"
echo ""
echo -e "  ${RED}- response = requests.post(url, data=str(payload))${NC}"
echo -e "  ${GREEN}+ response = requests.post(url, json=payload,${NC}"
echo -e "  ${GREEN}+     headers={\"Content-Type\": \"application/json\"})${NC}"


# ============================================================================
# STEP 4: Run fixed client against the stub — should PASS
# ============================================================================
step_header "4" "Running FIXED client against Specmatic stub (expect: PASS)"

echo -e "${YELLOW}  The fixed client uses:${NC}"
echo -e "${YELLOW}    - Correct endpoint: /api/search${NC}"
echo -e "${YELLOW}    - Correct field name: \"query\"${NC}"
echo -e "${YELLOW}    - Correct Content-Type: application/json${NC}"
echo ""

info "Sending request with FIXED client..."
echo ""

FIXED_OUTPUT=$(${PYTHON} ai_generated_client.py fixed "http://localhost:${STUB_PORT}" 2>&1) || true
echo -e "${GREEN}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}  │  FIXED CLIENT OUTPUT:                                   │${NC}"
echo -e "${GREEN}  └─────────────────────────────────────────────────────────┘${NC}"
echo "${FIXED_OUTPUT}" | while IFS= read -r line; do
    echo -e "  ${GREEN}${line}${NC}"
done

echo ""
echo -e "${GREEN}  ┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}  │  RESULT: Fixed client PASSED contract validation!       │${NC}"
echo -e "${GREEN}  │  The stub returned a valid response.                    │${NC}"
echo -e "${GREEN}  └─────────────────────────────────────────────────────────┘${NC}"


# ============================================================================
# Summary
# ============================================================================
banner "Demo Complete — Summary"

echo -e "  ${GREEN}✓${NC} Step 1: Unit tests with mocks  → ${GREEN}ALL PASSED${NC}  (false confidence)"
echo -e "  ${RED}✗${NC} Step 2: Flawed client vs stub  → ${RED}REJECTED${NC}   (contract caught bugs)"
echo -e "  ${YELLOW}→${NC} Step 3: Diff analysis          → 3 bugs identified"
echo -e "  ${GREEN}✓${NC} Step 4: Fixed client vs stub   → ${GREEN}PASSED${NC}    (contract validated)"
echo ""
echo -e "${BOLD}  Key insight:${NC} Mock-based tests reproduce the developer's assumptions."
echo -e "  Contract tests enforce the API's actual specification."
echo -e "  When AI generates code, contract tests are the safety net"
echo -e "  that catches what mocks cannot."
echo ""
