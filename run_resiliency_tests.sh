#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LICENSE_FILE="${SCRIPT_DIR}/license.txt"
LICENSE_OPTS=()
if [ -f "${LICENSE_FILE}" ]; then
    LICENSE_OPTS=(-v "$(pwd)/license.txt:/usr/src/app/license.txt:ro")
fi

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
