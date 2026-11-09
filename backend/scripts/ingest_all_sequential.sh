#!/bin/bash
# Sequential ingestion script — waits for each source to finish before starting the next.
# Handles SQLite single-writer limitation by serializing all ingest API calls.

API="http://127.0.0.1:8000/api/data/ingest"
SOURCES=("pfam" "brenda" "protherm" "enzengdb")

echo "=== Sequential Data Ingestion ==="
echo "Start: $(date)"
echo ""

for src in "${SOURCES[@]}"; do
    echo "--- Ingesting: $src ---"
    echo "Start: $(date)"
    RESPONSE=$(curl -s -X POST "$API/$src?force=false" 2>&1)
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo "Done: $src at $(date)"
    echo ""
done

echo "=== All ingestions complete: $(date) ==="
