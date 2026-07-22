#!/bin/bash
set -e

SPECMATIC_JAR="${HOME}/.specmatic/specmatic.jar"

if [ ! -f "$SPECMATIC_JAR" ]; then
  echo "Downloading Specmatic JAR..."
  mkdir -p "${HOME}/.specmatic"
  curl -L -o "$SPECMATIC_JAR" \
    "https://github.com/specmatic/specmatic/releases/download/2.50.0/specmatic.jar"
fi

echo "Starting Specmatic stub server for Groq on port 9000..."
echo "Veritas will call this instead of real Groq."
echo ""

cd specmatic-groq
java -jar "$SPECMATIC_JAR" stub groq_openapi.yaml --port 9000
