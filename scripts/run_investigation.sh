#!/usr/bin/env bash
#
# run_investigation.sh - Automated whale investigation pipeline
#
# Chains investigation scripts with checkpointing and resume support.
# Each step saves output to data/pipeline/ so the pipeline can resume
# from the last completed step if interrupted.
#
# Usage:
#   ./scripts/run_investigation.sh                          # Use default CSV
#   ./scripts/run_investigation.sh my_addresses.csv         # Custom input
#   ./scripts/run_investigation.sh --resume                 # Resume from last checkpoint
#   ./scripts/run_investigation.sh --clean                  # Wipe checkpoints and start fresh
#   ./scripts/run_investigation.sh --step behavioral        # Run single step only
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_DIR="$PROJECT_DIR/data/pipeline"
LOG="$PIPELINE_DIR/investigation.log"
CHECKPOINT_FILE="$PIPELINE_DIR/.checkpoint"

DEFAULT_INPUT="$PROJECT_DIR/references/top_lending_protocol_borrowers_eoa_safe_with_identity.csv"

# Pipeline intermediate files
UNKNOWNS_CSV="$PIPELINE_DIR/unknowns.csv"
CONTRACTS_CSV="$PIPELINE_DIR/unknowns_contracts.csv"
EOAS_CSV="$PIPELINE_DIR/unknowns_eoas.csv"
BOT_OUT="$PIPELINE_DIR/step1_bot_operator.csv"
BEHAV_OUT="$PIPELINE_DIR/step2_behavioral.csv"
FUNDING_OUT="$PIPELINE_DIR/step3_funding.csv"
TEMPORAL_OUT="$PIPELINE_DIR/step4_temporal.csv"
COUNTERPARTY_OUT="$PIPELINE_DIR/step5_counterparty.csv"
MERGED_OUT="$PIPELINE_DIR/investigation_results.csv"

# Ordered step names
STEPS=(bot_operator behavioral funding temporal counterparty label_propagation merge)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG"
}

die() {
    log "FATAL: $*"
    exit 1
}

save_checkpoint() {
    echo "$1" > "$CHECKPOINT_FILE"
    log "Checkpoint saved: $1"
}

get_checkpoint() {
    if [[ -f "$CHECKPOINT_FILE" ]]; then
        cat "$CHECKPOINT_FILE"
    else
        echo ""
    fi
}

# Return the index of a step name in STEPS array (0-based), or -1 if not found
step_index() {
    local target="$1"
    for i in "${!STEPS[@]}"; do
        if [[ "${STEPS[$i]}" == "$target" ]]; then
            echo "$i"
            return
        fi
    done
    echo "-1"
}

should_run_step() {
    local step="$1"
    local resume_from="$2"

    # If no resume checkpoint, run everything
    if [[ -z "$resume_from" ]]; then
        return 0
    fi

    local step_idx
    step_idx=$(step_index "$step")
    local resume_idx
    resume_idx=$(step_index "$resume_from")

    # Run this step if it's at or after the resume point
    if [[ "$step_idx" -ge "$resume_idx" ]]; then
        return 0
    else
        return 1
    fi
}

count_lines() {
    # Count data rows (minus header)
    local file="$1"
    if [[ -f "$file" ]]; then
        local total
        total=$(wc -l < "$file")
        echo $(( total - 1 ))
    else
        echo 0
    fi
}

# ---------------------------------------------------------------------------
# Filtering: extract unknown addresses from input CSV
# ---------------------------------------------------------------------------
filter_unknowns() {
    local input="$1"
    log "Filtering unknown addresses from $(basename "$input")..."

    python3 - "$input" "$UNKNOWNS_CSV" "$CONTRACTS_CSV" "$EOAS_CSV" <<'PYEOF'
import csv
import sys

input_path = sys.argv[1]
unknowns_path = sys.argv[2]
contracts_path = sys.argv[3]
eoas_path = sys.argv[4]

seen = set()
unknowns = []

with open(input_path, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        addr = (row.get("borrower") or row.get("address") or "").strip().lower()
        identity = (row.get("identity") or "").strip()

        # Skip if already identified or duplicate
        if identity or not addr or addr in seen:
            continue
        seen.add(addr)
        unknowns.append(row)

# Write all unknowns with normalized "address" column
all_fields = ["address", "address_type", "total_borrowed_m", "borrowed_assets", "project"]
with open(unknowns_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=all_fields)
    writer.writeheader()
    for row in unknowns:
        writer.writerow({
            "address": (row.get("borrower") or row.get("address") or "").strip().lower(),
            "address_type": row.get("address_type", ""),
            "total_borrowed_m": row.get("total_borrowed_m", ""),
            "borrowed_assets": row.get("borrowed_assets", ""),
            "project": row.get("project", ""),
        })

# Split into contracts and EOAs based on address_type
with open(contracts_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=all_fields)
    writer.writeheader()
    for row in unknowns:
        atype = row.get("address_type", "").upper()
        if atype in ("CONTRACT", "SAFE"):
            writer.writerow({
                "address": (row.get("borrower") or row.get("address") or "").strip().lower(),
                "address_type": row.get("address_type", ""),
                "total_borrowed_m": row.get("total_borrowed_m", ""),
                "borrowed_assets": row.get("borrowed_assets", ""),
                "project": row.get("project", ""),
            })

with open(eoas_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=all_fields)
    writer.writeheader()
    for row in unknowns:
        atype = row.get("address_type", "").upper()
        if atype not in ("CONTRACT", "SAFE"):
            writer.writerow({
                "address": (row.get("borrower") or row.get("address") or "").strip().lower(),
                "address_type": row.get("address_type", ""),
                "total_borrowed_m": row.get("total_borrowed_m", ""),
                "borrowed_assets": row.get("borrowed_assets", ""),
                "project": row.get("project", ""),
            })

total = len(unknowns)
contracts = sum(1 for r in unknowns if r.get("address_type", "").upper() in ("CONTRACT", "SAFE"))
eoas = total - contracts

print(f"Total unknowns: {total} ({contracts} contracts, {eoas} EOAs)")
PYEOF

    log "Unknowns: $(count_lines "$UNKNOWNS_CSV") total, $(count_lines "$CONTRACTS_CSV") contracts, $(count_lines "$EOAS_CSV") EOAs"
}

# ---------------------------------------------------------------------------
# Step 1: Bot Operator Tracer (contracts only)
# ---------------------------------------------------------------------------
run_bot_operator() {
    local contract_count
    contract_count=$(count_lines "$CONTRACTS_CSV")

    if [[ "$contract_count" -eq 0 ]]; then
        log "Step 1/6 [bot_operator]: No contracts to trace, skipping"
        # Create empty output with header
        echo "address,is_contract,deployer,likely_operator,confidence,operator_type,mev_builder,related_contract_count" > "$BOT_OUT"
        return 0
    fi

    log "Step 1/6 [bot_operator]: Tracing operators for $contract_count contracts..."
    python3 "$SCRIPT_DIR/bot_operator_tracer.py" "$CONTRACTS_CSV" -o "$BOT_OUT" 2>&1 | tee -a "$LOG"
    log "Step 1/6 [bot_operator]: Done. Output: $(count_lines "$BOT_OUT") rows"
}

# ---------------------------------------------------------------------------
# Step 2: Behavioral Fingerprint (all unknowns)
# ---------------------------------------------------------------------------
run_behavioral() {
    local addr_count
    addr_count=$(count_lines "$UNKNOWNS_CSV")

    if [[ "$addr_count" -eq 0 ]]; then
        log "Step 2/6 [behavioral]: No addresses, skipping"
        echo "address,tx_count,timezone,activity_pattern,gas_strategy,trading_style,risk_profile,entity_type_signal" > "$BEHAV_OUT"
        return 0
    fi

    log "Step 2/6 [behavioral]: Fingerprinting $addr_count addresses..."
    python3 "$SCRIPT_DIR/behavioral_fingerprint.py" "$UNKNOWNS_CSV" -o "$BEHAV_OUT" 2>&1 | tee -a "$LOG"
    log "Step 2/6 [behavioral]: Done. Output: $(count_lines "$BEHAV_OUT") rows"
}

# ---------------------------------------------------------------------------
# Step 3: Trace Funding (all unknowns)
# ---------------------------------------------------------------------------
run_funding() {
    local addr_count
    addr_count=$(count_lines "$UNKNOWNS_CSV")

    if [[ "$addr_count" -eq 0 ]]; then
        log "Step 3/6 [funding]: No addresses, skipping"
        echo "address,first_funder,funder_entity,funder_label,funding_hops,first_tx_hash,first_tx_value,first_tx_date,is_cex_funded,is_institutional,error" > "$FUNDING_OUT"
        return 0
    fi

    log "Step 3/6 [funding]: Tracing funding for $addr_count addresses..."
    python3 "$SCRIPT_DIR/trace_funding.py" "$UNKNOWNS_CSV" -o "$FUNDING_OUT" 2>&1 | tee -a "$LOG"
    log "Step 3/6 [funding]: Done. Output: $(count_lines "$FUNDING_OUT") rows"
}

# ---------------------------------------------------------------------------
# Step 4: Temporal Correlation (all unknowns)
# ---------------------------------------------------------------------------
run_temporal() {
    local addr_count
    addr_count=$(count_lines "$UNKNOWNS_CSV")

    if [[ "$addr_count" -lt 2 ]]; then
        log "Step 4/6 [temporal]: Need 2+ addresses for correlation, skipping"
        echo "addr1,addr2,confidence,correlation_count,avg_delta_seconds,min_delta_seconds,max_delta_seconds,pattern_description" > "$TEMPORAL_OUT"
        return 0
    fi

    log "Step 4/6 [temporal]: Finding temporal correlations among $addr_count addresses..."
    python3 "$SCRIPT_DIR/temporal_correlation.py" "$UNKNOWNS_CSV" -o "$TEMPORAL_OUT" 2>&1 | tee -a "$LOG"
    log "Step 4/6 [temporal]: Done. Output: $(count_lines "$TEMPORAL_OUT") rows"
}

# ---------------------------------------------------------------------------
# Step 5: Counterparty Graph (all unknowns)
# ---------------------------------------------------------------------------
run_counterparty() {
    local addr_count
    addr_count=$(count_lines "$UNKNOWNS_CSV")

    if [[ "$addr_count" -lt 2 ]]; then
        log "Step 5/6 [counterparty]: Need 2+ addresses for graph, skipping"
        echo "addr1,addr2,confidence,weighted_overlap,shared_counterparties,shared_deposits,basic_jaccard" > "$COUNTERPARTY_OUT"
        return 0
    fi

    log "Step 5/6 [counterparty]: Building counterparty graph for $addr_count addresses..."
    python3 "$SCRIPT_DIR/counterparty_graph.py" "$UNKNOWNS_CSV" -o "$COUNTERPARTY_OUT" 2>&1 | tee -a "$LOG"
    log "Step 5/6 [counterparty]: Done. Output: $(count_lines "$COUNTERPARTY_OUT") rows"
}

# ---------------------------------------------------------------------------
# Step 6: Label Propagation (knowledge graph)
# ---------------------------------------------------------------------------
run_label_propagation() {
    log "Step 6/6 [label_propagation]: Running full label propagation..."
    python3 "$SCRIPT_DIR/label_propagation.py" --full 2>&1 | tee -a "$LOG"
    log "Step 6/6 [label_propagation]: Done"
}

# ---------------------------------------------------------------------------
# Merge: combine all results into a single CSV
# ---------------------------------------------------------------------------
run_merge() {
    log "Merging results..."

    python3 - "$UNKNOWNS_CSV" "$BOT_OUT" "$BEHAV_OUT" "$FUNDING_OUT" "$TEMPORAL_OUT" "$COUNTERPARTY_OUT" "$MERGED_OUT" <<'PYEOF'
import csv
import sys
from collections import defaultdict

unknowns_path = sys.argv[1]
bot_path = sys.argv[2]
behav_path = sys.argv[3]
funding_path = sys.argv[4]
temporal_path = sys.argv[5]
counterparty_path = sys.argv[6]
output_path = sys.argv[7]

# Start with base unknown addresses
addresses = {}
with open(unknowns_path) as f:
    for row in csv.DictReader(f):
        addr = row["address"].lower()
        addresses[addr] = {
            "address": addr,
            "address_type": row.get("address_type", ""),
            "total_borrowed_m": row.get("total_borrowed_m", ""),
            "project": row.get("project", ""),
        }

# Merge bot operator results
try:
    with open(bot_path) as f:
        for row in csv.DictReader(f):
            addr = row["address"].lower()
            if addr in addresses:
                addresses[addr]["bot_deployer"] = row.get("deployer", "")
                addresses[addr]["bot_operator"] = row.get("likely_operator", "")
                addresses[addr]["bot_confidence"] = row.get("confidence", "")
                addresses[addr]["bot_type"] = row.get("operator_type", "")
except (FileNotFoundError, KeyError):
    pass

# Merge behavioral results
try:
    with open(behav_path) as f:
        for row in csv.DictReader(f):
            addr = row["address"].lower()
            if addr in addresses:
                addresses[addr]["timezone"] = row.get("timezone", "")
                addresses[addr]["activity_pattern"] = row.get("activity_pattern", "")
                addresses[addr]["entity_type_signal"] = row.get("entity_type_signal", "")
                addresses[addr]["gas_strategy"] = row.get("gas_strategy", "")
except (FileNotFoundError, KeyError):
    pass

# Merge funding results
try:
    with open(funding_path) as f:
        for row in csv.DictReader(f):
            addr = row["address"].lower()
            if addr in addresses:
                addresses[addr]["funder_entity"] = row.get("funder_entity", "")
                addresses[addr]["funder_label"] = row.get("funder_label", "")
                addresses[addr]["is_cex_funded"] = row.get("is_cex_funded", "")
                addresses[addr]["is_institutional"] = row.get("is_institutional", "")
                addresses[addr]["funding_hops"] = row.get("funding_hops", "")
except (FileNotFoundError, KeyError):
    pass

# Merge temporal correlations (pairwise - attach best match to each address)
temporal_best = defaultdict(lambda: {"partner": "", "confidence": 0})
try:
    with open(temporal_path) as f:
        for row in csv.DictReader(f):
            a1 = row.get("addr1", "").lower()
            a2 = row.get("addr2", "").lower()
            conf = float(row.get("confidence", 0))
            if conf > temporal_best[a1]["confidence"]:
                temporal_best[a1] = {"partner": a2, "confidence": conf}
            if conf > temporal_best[a2]["confidence"]:
                temporal_best[a2] = {"partner": a1, "confidence": conf}
except (FileNotFoundError, KeyError, ValueError):
    pass

for addr in addresses:
    if addr in temporal_best:
        addresses[addr]["temporal_partner"] = temporal_best[addr]["partner"]
        addresses[addr]["temporal_confidence"] = f"{temporal_best[addr]['confidence']:.3f}"
    else:
        addresses[addr]["temporal_partner"] = ""
        addresses[addr]["temporal_confidence"] = ""

# Merge counterparty overlap (pairwise - attach best match)
counterparty_best = defaultdict(lambda: {"partner": "", "confidence": 0})
try:
    with open(counterparty_path) as f:
        for row in csv.DictReader(f):
            a1 = row.get("addr1", "").lower()
            a2 = row.get("addr2", "").lower()
            conf = float(row.get("confidence", 0))
            if conf > counterparty_best[a1]["confidence"]:
                counterparty_best[a1] = {"partner": a2, "confidence": conf}
            if conf > counterparty_best[a2]["confidence"]:
                counterparty_best[a2] = {"partner": a1, "confidence": conf}
except (FileNotFoundError, KeyError, ValueError):
    pass

for addr in addresses:
    if addr in counterparty_best:
        addresses[addr]["counterparty_partner"] = counterparty_best[addr]["partner"]
        addresses[addr]["counterparty_confidence"] = f"{counterparty_best[addr]['confidence']:.3f}"
    else:
        addresses[addr]["counterparty_partner"] = ""
        addresses[addr]["counterparty_confidence"] = ""

# Write merged output
fieldnames = [
    "address", "address_type", "total_borrowed_m", "project",
    "bot_deployer", "bot_operator", "bot_confidence", "bot_type",
    "timezone", "activity_pattern", "entity_type_signal", "gas_strategy",
    "funder_entity", "funder_label", "is_cex_funded", "is_institutional", "funding_hops",
    "temporal_partner", "temporal_confidence",
    "counterparty_partner", "counterparty_confidence",
]

with open(output_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    # Sort by total_borrowed_m descending
    sorted_addrs = sorted(
        addresses.values(),
        key=lambda r: float(r.get("total_borrowed_m") or 0),
        reverse=True
    )
    for row in sorted_addrs:
        writer.writerow(row)

print(f"Merged {len(addresses)} addresses into {output_path}")
PYEOF

    log "Merge complete: $(count_lines "$MERGED_OUT") rows -> $MERGED_OUT"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local input="$DEFAULT_INPUT"
    local resume=false
    local clean=false
    local single_step=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --resume)
                resume=true
                shift
                ;;
            --clean)
                clean=true
                shift
                ;;
            --step)
                single_step="$2"
                shift 2
                ;;
            --help|-h)
                echo "Usage: $0 [input.csv] [--resume] [--clean] [--step STEP]"
                echo ""
                echo "Options:"
                echo "  input.csv     Input CSV (default: references/top_lending_...csv)"
                echo "  --resume      Resume from last checkpoint"
                echo "  --clean       Wipe checkpoints and start fresh"
                echo "  --step STEP   Run single step: bot_operator, behavioral, funding,"
                echo "                temporal, counterparty, label_propagation, merge"
                echo ""
                echo "Steps run in order:"
                echo "  1. bot_operator     - Trace deployer/operator for contracts"
                echo "  2. behavioral       - Timezone, activity patterns for all"
                echo "  3. funding          - CEX funding origin for all"
                echo "  4. temporal         - Cross-address timing correlations"
                echo "  5. counterparty     - Shared counterparty overlap"
                echo "  6. label_propagation - Propagate identities in knowledge graph"
                echo "  7. merge            - Combine all results into single CSV"
                exit 0
                ;;
            *)
                if [[ -f "$1" ]]; then
                    input="$1"
                else
                    die "Unknown argument or file not found: $1"
                fi
                shift
                ;;
        esac
    done

    # Validate input
    [[ -f "$input" ]] || die "Input file not found: $input"

    # Ensure pipeline directory exists
    mkdir -p "$PIPELINE_DIR"

    # Clean mode
    if $clean; then
        log "Cleaning pipeline checkpoints..."
        rm -f "$CHECKPOINT_FILE"
        rm -f "$UNKNOWNS_CSV" "$CONTRACTS_CSV" "$EOAS_CSV"
        rm -f "$BOT_OUT" "$BEHAV_OUT" "$FUNDING_OUT" "$TEMPORAL_OUT" "$COUNTERPARTY_OUT"
        log "Clean complete"
    fi

    # Activate venv if available
    if [[ -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$PROJECT_DIR/.venv/bin/activate"
    fi

    log "=========================================="
    log "Investigation Pipeline Starting"
    log "Input: $input"
    log "=========================================="

    # Determine resume point
    local resume_from=""
    if $resume; then
        resume_from=$(get_checkpoint)
        if [[ -n "$resume_from" ]]; then
            log "Resuming from checkpoint: $resume_from"
        else
            log "No checkpoint found, starting from beginning"
        fi
    fi

    # Single step mode
    if [[ -n "$single_step" ]]; then
        # Still need unknowns CSV if it doesn't exist
        if [[ ! -f "$UNKNOWNS_CSV" ]]; then
            filter_unknowns "$input"
        fi
        case "$single_step" in
            bot_operator)       run_bot_operator ;;
            behavioral)         run_behavioral ;;
            funding)            run_funding ;;
            temporal)           run_temporal ;;
            counterparty)       run_counterparty ;;
            label_propagation)  run_label_propagation ;;
            merge)              run_merge ;;
            *)                  die "Unknown step: $single_step" ;;
        esac
        log "Single step '$single_step' complete"
        return 0
    fi

    # Full pipeline
    # Always re-filter unknowns unless resuming past that point
    if [[ -z "$resume_from" ]] || [[ ! -f "$UNKNOWNS_CSV" ]]; then
        filter_unknowns "$input"
    else
        log "Using existing unknowns CSV ($(count_lines "$UNKNOWNS_CSV") addresses)"
    fi

    # Step 1: Bot Operator Tracer (contracts only)
    if should_run_step "bot_operator" "$resume_from"; then
        save_checkpoint "bot_operator"
        run_bot_operator
    else
        log "Skipping step 1 [bot_operator] (already done)"
    fi

    # Step 2: Behavioral Fingerprint
    if should_run_step "behavioral" "$resume_from"; then
        save_checkpoint "behavioral"
        run_behavioral
    else
        log "Skipping step 2 [behavioral] (already done)"
    fi

    # Step 3: Trace Funding
    if should_run_step "funding" "$resume_from"; then
        save_checkpoint "funding"
        run_funding
    else
        log "Skipping step 3 [funding] (already done)"
    fi

    # Step 4: Temporal Correlation
    if should_run_step "temporal" "$resume_from"; then
        save_checkpoint "temporal"
        run_temporal
    else
        log "Skipping step 4 [temporal] (already done)"
    fi

    # Step 5: Counterparty Graph
    if should_run_step "counterparty" "$resume_from"; then
        save_checkpoint "counterparty"
        run_counterparty
    else
        log "Skipping step 5 [counterparty] (already done)"
    fi

    # Step 6: Label Propagation
    if should_run_step "label_propagation" "$resume_from"; then
        save_checkpoint "label_propagation"
        run_label_propagation
    else
        log "Skipping step 6 [label_propagation] (already done)"
    fi

    # Step 7: Merge
    if should_run_step "merge" "$resume_from"; then
        save_checkpoint "merge"
        run_merge
    else
        log "Skipping merge (already done)"
    fi

    # Clear checkpoint on successful completion
    rm -f "$CHECKPOINT_FILE"

    log "=========================================="
    log "Pipeline complete!"
    log "Results: $MERGED_OUT"
    log "Log: $LOG"
    log "=========================================="
}

main "$@"
