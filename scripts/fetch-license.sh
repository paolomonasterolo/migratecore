#!/usr/bin/env bash
# Fetch the canonical Apache 2.0 license text and write it to ./LICENSE.
#
# Run this once at the project root after cloning:
#   bash scripts/fetch-license.sh
#
# The Apache 2.0 license text is the same for every project that uses it;
# we fetch from the upstream source rather than retyping it to avoid typos.

set -euo pipefail

URL="https://www.apache.org/licenses/LICENSE-2.0.txt"
OUT="LICENSE"

if [[ -f "$OUT" ]]; then
  echo "$OUT already exists. Delete it first if you want to refetch."
  exit 0
fi

echo "Fetching Apache 2.0 license text from $URL..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$OUT"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$URL" -O "$OUT"
else
  echo "error: neither curl nor wget is available"
  exit 1
fi

echo "Wrote $OUT ($(wc -l < "$OUT") lines)."
