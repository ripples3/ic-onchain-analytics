#!/usr/bin/env python3
"""
Whale Investigation Pipeline

Single command to run full investigation on a set of addresses.
Uses knowledge_graph.db as the central data store.

Usage:
    python3 scripts/investigate.py addresses.csv
    python3 scripts/investigate.py addresses.csv --skip-enrichment
    python3 scripts/investigate.py --stats
    python3 scripts/investigate.py --export

Examples:
    # Full investigation on new addresses
    python3 scripts/investigate.py data/raw/borrowers.csv

    # Just run analysis (skip API calls)
    python3 scripts/investigate.py addresses.csv --skip-enrichment

    # View current stats
    python3 scripts/investigate.py --stats

    # Export results
    python3 scripts/investigate.py --export
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
PIPELINE_DIR = DATA_DIR / "pipeline"
RESULTS_DIR = DATA_DIR / "results"

# Ensure directories exist
PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_script(script_name: str, *args, check: bool = True) -> subprocess.CompletedProcess:
    """Run a script and return the result."""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"  [SKIP] {script_name} not found")
        return None

    cmd = [sys.executable, str(script_path)] + list(args)
    print(f"  Running: {script_name} {' '.join(args)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per script
        )
        if result.returncode != 0 and check:
            print(f"  [WARN] {script_name} returned {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
        return result
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {script_name} exceeded 10 minutes")
        return None
    except Exception as e:
        print(f"  [ERROR] {script_name}: {e}")
        return None


def count_addresses(csv_path: str) -> int:
    """Count addresses in CSV file."""
    try:
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def show_stats():
    """Show current knowledge graph statistics."""
    kg_path = DATA_DIR / "knowledge_graph.db"
    if not kg_path.exists():
        print("Knowledge graph not initialized. Run with addresses first.")
        return

    run_script("build_knowledge_graph.py", "stats")


def export_results(output_path: str = None):
    """Export results from knowledge graph."""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        output_path = str(RESULTS_DIR / f"{timestamp}_identified_whales.csv")

    run_script("build_knowledge_graph.py", "export", "-o", output_path)
    print(f"\nExported to: {output_path}")


def run_pipeline(input_csv: str, skip_enrichment: bool = False, skip_apis: bool = False):
    """
    Run full investigation pipeline.

    Stages:
    1. Initialize knowledge graph with seed addresses
    2. Layer 1: On-chain analysis (CIO, funding, bridges)
    3. Layer 2: Behavioral fingerprinting (timing, gas, trading)
    4. Layer 3: OSINT aggregation (ENS, governance, whale trackers)
    5. Pattern matching and identity assignment
    6. Export results
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    print("=" * 60)
    print(f"WHALE INVESTIGATION PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Input: {input_csv}")
    print("=" * 60)

    # Validate input
    if not Path(input_csv).exists():
        print(f"ERROR: Input file not found: {input_csv}")
        sys.exit(1)

    num_addresses = count_addresses(input_csv)
    print(f"\nAddresses to investigate: {num_addresses}")

    # Stage 1: Initialize knowledge graph
    print("\n[1/6] Initializing knowledge graph...")
    run_script("build_knowledge_graph.py", "init", "--seeds", input_csv)

    if not skip_enrichment:
        # Stage 2: Basic enrichment (Etherscan labels, contract types)
        print("\n[2/6] Basic enrichment (Etherscan, contract types)...")
        enriched_path = str(PIPELINE_DIR / f"{timestamp}_enriched.csv")
        run_script("enrich_addresses.py", input_csv, "-o", enriched_path, check=False)

        # Use enriched file for subsequent steps if it exists
        if Path(enriched_path).exists():
            input_csv = enriched_path
    else:
        print("\n[2/6] Skipping enrichment (--skip-enrichment)")

    # Stage 3: On-chain analysis
    print("\n[3/6] On-chain analysis...")

    print("  - CIO clustering (common funders)...")
    cio_path = str(PIPELINE_DIR / f"{timestamp}_cio.csv")
    run_script("cio_detector.py", input_csv, "-o", cio_path, check=False)

    print("  - Funding chain tracing...")
    funding_path = str(PIPELINE_DIR / f"{timestamp}_funding.csv")
    run_script("trace_funding.py", input_csv, "-o", funding_path, check=False)

    print("  - Bridge activity tracking...")
    bridge_path = str(PIPELINE_DIR / f"{timestamp}_bridges.csv")
    run_script("bridge_tracker.py", input_csv, "-o", bridge_path, check=False)

    print("  - Change address detection...")
    change_path = str(PIPELINE_DIR / f"{timestamp}_change.csv")
    run_script("change_detector.py", input_csv, "-o", change_path, check=False)

    # Stage 4: Behavioral analysis
    print("\n[4/6] Behavioral fingerprinting...")

    print("  - Timing and gas patterns...")
    behavior_path = str(PIPELINE_DIR / f"{timestamp}_behavioral.json")
    run_script("behavioral_fingerprint.py", input_csv, "-o", behavior_path, check=False)

    print("  - DEX trading patterns...")
    dex_path = str(PIPELINE_DIR / f"{timestamp}_dex.csv")
    run_script("dex_analyzer.py", input_csv, "-o", dex_path, check=False)

    print("  - NFT holdings...")
    nft_path = str(PIPELINE_DIR / f"{timestamp}_nft.csv")
    run_script("nft_tracker.py", input_csv, "-o", nft_path, check=False)

    # Stage 5: OSINT aggregation
    print("\n[5/6] OSINT aggregation...")

    print("  - ENS name resolution...")
    ens_path = str(PIPELINE_DIR / f"{timestamp}_ens.csv")
    run_script("ens_resolver.py", input_csv, "-o", ens_path, check=False)

    print("  - Governance activity (Snapshot)...")
    gov_path = str(PIPELINE_DIR / f"{timestamp}_governance.csv")
    run_script("governance_scraper.py", input_csv, "-o", gov_path, check=False)

    print("  - Safe multisig owners...")
    safe_path = str(PIPELINE_DIR / f"{timestamp}_safes.csv")
    run_script("resolve_safe_owners.py", input_csv, "-o", safe_path, check=False)

    print("  - Known whale tracker lookup...")
    whale_path = str(PIPELINE_DIR / f"{timestamp}_whales.csv")
    run_script("whale_tracker_aggregator.py", input_csv, "-o", whale_path, check=False)

    # Stage 6: Pattern matching and export
    print("\n[6/6] Pattern matching and identity assignment...")
    run_script("build_knowledge_graph.py", "run", check=False)

    # Final verification
    print("\n  - Multi-source verification...")
    verified_path = str(PIPELINE_DIR / f"{timestamp}_verified.csv")
    run_script("verify_identity.py", input_csv, "-o", verified_path, "--report", check=False)

    # Export final results
    print("\n" + "=" * 60)
    print("EXPORTING RESULTS")
    print("=" * 60)

    results_csv = str(RESULTS_DIR / f"{timestamp}_identified_whales.csv")
    results_json = str(RESULTS_DIR / f"{timestamp}_identified_whales.json")

    run_script("build_knowledge_graph.py", "export", "-o", results_csv, check=False)
    run_script("build_knowledge_graph.py", "export", "-o", results_json, "--format", "json", check=False)

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nResults:")
    print(f"  CSV: {results_csv}")
    print(f"  JSON: {results_json}")
    print(f"\nPipeline outputs: {PIPELINE_DIR}/")
    print(f"\nRun 'python3 scripts/investigate.py --stats' for summary statistics.")


def main():
    parser = argparse.ArgumentParser(
        description="Whale Investigation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/investigate.py data/raw/borrowers.csv   # Full investigation
  python3 scripts/investigate.py addresses.csv --skip-enrichment  # Skip API calls
  python3 scripts/investigate.py --stats                  # View statistics
  python3 scripts/investigate.py --export                 # Export results
        """
    )

    parser.add_argument("input_csv", nargs="?", help="CSV file with addresses to investigate")
    parser.add_argument("--skip-enrichment", action="store_true",
                        help="Skip enrichment stage (no external API calls)")
    parser.add_argument("--stats", action="store_true",
                        help="Show knowledge graph statistics")
    parser.add_argument("--export", action="store_true",
                        help="Export current results to CSV")
    parser.add_argument("-o", "--output", help="Output path for export")

    args = parser.parse_args()

    # Change to project root
    os.chdir(ROOT_DIR)

    # Activate venv if exists
    venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        os.environ["PATH"] = f"{venv_python.parent}:{os.environ.get('PATH', '')}"

    if args.stats:
        show_stats()
    elif args.export:
        export_results(args.output)
    elif args.input_csv:
        run_pipeline(args.input_csv, skip_enrichment=args.skip_enrichment)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
