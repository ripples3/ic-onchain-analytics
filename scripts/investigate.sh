#!/bin/bash
# Whale Investigation Pipeline - Shell Wrapper
#
# Usage:
#   ./investigate.sh addresses.csv          # Full investigation
#   ./investigate.sh --stats                # View statistics
#   ./investigate.sh --export               # Export results

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run the pipeline
python3 scripts/investigate.py "$@"
