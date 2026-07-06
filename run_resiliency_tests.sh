#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_URL="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Ensure license.txt exists (even as a placeholder) so Specmatic doesn't crash with NoSuchFileException
if [ ! -f "${SCRIPT_DIR}/license.txt" ]; then
    echo "# Place your Specmatic trial license here." > "${SCRIPT_DIR}/license.txt"
fi

LICENSE_FILE="${SCRIPT_DIR}/license.txt"
LICENSE_OPTS=()
if [ -f "${LICENSE_FILE}" ]; then
    LICENSE_OPTS=(-v "$(pwd)/license.txt:/usr/src/app/license.txt:ro")
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

echo "Running Specmatic Resiliency Tests..."

docker run --rm --network host \
  "${LICENSE_OPTS[@]}" \
  -e SPECMATIC_GENERATIVE_TESTS=true \
  -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml:ro" \
  -v "$(pwd)/openapi.yaml:/usr/src/app/openapi.yaml:ro" \
  -v "$(pwd)/examples:/usr/src/app/examples:ro" \
  specmatic/specmatic test \
  --testBaseURL=http://localhost:8000 \
  --filter="PATH='/api/evaluation/evaluate'"

echo "Resiliency tests complete."
