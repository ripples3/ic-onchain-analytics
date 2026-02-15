#!/bin/bash
# Deep investigation of individual whale addresses using Claude Code agents
# Each runs as a separate background process with output saved to files
#
# Usage:
#   ./scripts/deep_investigate.sh                    # Top 5 unknowns
#   ./scripts/deep_investigate.sh 0xABC 0xDEF        # Specific addresses
#   ./scripts/deep_investigate.sh --model sonnet      # Use sonnet instead of haiku

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/data/investigations"
MODEL="haiku"
MAX_TURNS=25

# Parse flags
ADDRESSES=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --model) MODEL="$2"; shift 2 ;;
    --max-turns) MAX_TURNS="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    0x*) ADDRESSES+=("$1"); shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

# Default: top 5 unknowns by borrowed value
if [ ${#ADDRESSES[@]} -eq 0 ]; then
  ADDRESSES=(
    "0xe051fb91ec09eefb77e7f7a599291bf921eb504d"  # $502M
    "0x9b4772e59385ec732bccb06018e318b7b3477459"  # $430M
    "0x701bd63938518d7db7e0f00945110c80c67df532"  # $349M
    "0x3ba21b6477f48273f41d241aa3722ffb9e07e247"  # $331M
    "0x3ee505ba316879d246a8fd2b3d7ee63b51b44fab"  # $300M
  )
fi

PROMPT_TEMPLATE='You are investigating an Ethereum address to determine who controls it. This is for Index Coop business development research on DeFi lending protocol borrowers.

TARGET ADDRESS: %s

INVESTIGATION STEPS (do ALL of these):

1. ETHERSCAN BASICS
   - Fetch the address page: https://etherscan.io/address/%s
   - Check if contract or EOA
   - Check for any Etherscan labels/tags
   - Note the ETH balance and token holdings

2. TRACE FUNDING CHAIN (most important)
   - Fetch first transactions: https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address=%s&sort=asc&page=1&offset=10&apikey='"$ETHERSCAN_API_KEY"'
   - Find who first funded this address
   - If the funder is not a known CEX, trace THAT address too (up to 5 hops)
   - Check each funder against known CEX hot wallets (Binance, Coinbase, Kraken, etc.)

3. CHECK INTERNAL TRANSACTIONS (DeFi activity)
   - Fetch: https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlistinternal&address=%s&sort=desc&page=1&offset=20&apikey='"$ETHERSCAN_API_KEY"'
   - What protocols does this address use?

4. SOCIAL SEARCH
   - Search Twitter/X for this address
   - Search for the first 10 chars of the address + "whale" or "liquidated" or "DeFi"
   - Check if any whale trackers (Lookonchain, OnchainLens) have mentioned it

5. DEBANK PROFILE
   - Fetch: https://debank.com/profile/%s
   - Check if there is a Web3 social profile linked

6. SANCTIONS CHECK
   - Check against OFAC: https://www.chainalysis.com/free-cryptocurrency-sanctions-screening-tools/

7. CROSS-REFERENCE WITH KNOWLEDGE GRAPH
   - Read the file: data/knowledge_graph.db (use sqlite3 to query)
   - Check: SELECT * FROM relationships WHERE source = "%s" OR target = "%s"
   - Check: SELECT * FROM evidence WHERE entity_address = "%s"
   - Check: SELECT * FROM behavioral_fingerprints WHERE address = "%s"

8. SYNTHESIZE
   - Combine all findings into a identity hypothesis
   - Assign a confidence score (0-100)
   - List all evidence supporting the hypothesis

Write your final report in this format:
---
ADDRESS: %s
IDENTITY: [your best guess or "Unknown"]
CONFIDENCE: [0-100]
EVIDENCE:
- [list each piece of evidence]
FUNDING CHAIN: [origin] -> [hop1] -> ... -> [target]
REGION: [timezone/region if determinable]
TYPE: [EOA/Contract/Safe/Bot]
RECOMMENDATION: [what additional steps could confirm identity]
---

Save the report to: %s'

echo "=== Deep Whale Investigation ==="
echo "Model: $MODEL"
echo "Max turns: $MAX_TURNS"
echo "Output: $OUTPUT_DIR"
echo "Addresses: ${#ADDRESSES[@]}"
echo ""

PIDS=()
for addr in "${ADDRESSES[@]}"; do
  short="${addr:0:10}..."
  outfile="$OUTPUT_DIR/investigation_${addr}.md"
  logfile="$OUTPUT_DIR/investigation_${addr}.log"

  prompt=$(printf "$PROMPT_TEMPLATE" \
    "$addr" "$addr" "$addr" "$addr" "$addr" \
    "$addr" "$addr" "$addr" "$addr" "$addr" "$outfile")

  echo "Launching investigation: $short -> $outfile"

  claude -p "$prompt" \
    --model "$MODEL" \
    --max-turns "$MAX_TURNS" \
    --output-format text \
    > "$logfile" 2>&1 &

  PIDS+=($!)
  sleep 1  # stagger launches slightly
done

echo ""
echo "All ${#ADDRESSES[@]} investigations launched in background."
echo "PIDs: ${PIDS[*]}"
echo ""
echo "Monitor progress:"
for i in "${!ADDRESSES[@]}"; do
  addr="${ADDRESSES[$i]}"
  echo "  tail -f $OUTPUT_DIR/investigation_${addr}.log"
done
echo ""
echo "Wait for all to complete:"
echo "  wait ${PIDS[*]}"
echo ""
echo "View results:"
echo "  ls -la $OUTPUT_DIR/investigation_*.md"
