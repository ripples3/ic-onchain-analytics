#!/usr/bin/env python3
"""
Multi-Source Identity Verification

Cross-checks identity findings from multiple sources to:
1. Increase confidence in identifications
2. Catch false positives
3. Fill gaps with complementary data

Based on ZachXBT's methodology: "Never publish based on one data point.
Cross-reference on-chain + off-chain + social."

Usage:
    python3 verify_identity.py enriched.csv -o verified.csv
    python3 verify_identity.py --address 0x1234...
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# Import other scripts
try:
    from etherscan_labels import get_contract_info
    from trace_funding import trace_funding_origin
    from batch_arkham_check import check_arkham_label
    from governance_scraper import analyze_governance_activity
    from cio_detector import run_cio_detection
except ImportError:
    # Running standalone
    pass

def calculate_confidence(sources: Dict[str, Optional[str]]) -> Tuple[float, str]:
    """
    Calculate overall confidence based on source agreement.

    Returns (confidence_score, reasoning)
    """
    # Count non-empty sources
    filled_sources = {k: v for k, v in sources.items() if v}
    source_count = len(filled_sources)

    if source_count == 0:
        return 0.0, "No identity signals found"

    # Check for agreement
    identities = list(filled_sources.values())

    # Normalize identities for comparison
    def normalize(s: str) -> str:
        return s.lower().replace(" ", "").replace("-", "").replace("_", "")

    normalized = [normalize(i) for i in identities]

    # Check if all sources agree
    unique_normalized = set(normalized)

    if len(unique_normalized) == 1:
        # All sources agree
        confidence = min(0.95, 0.5 + 0.15 * source_count)
        return confidence, f"All {source_count} sources agree"

    # Partial agreement
    # Find most common identity
    from collections import Counter
    counts = Counter(normalized)
    most_common, most_count = counts.most_common(1)[0]

    if most_count >= 2:
        confidence = 0.4 + 0.1 * most_count
        disagreeing = source_count - most_count
        return confidence, f"{most_count} sources agree, {disagreeing} disagree"

    # No agreement
    return 0.3, f"Sources disagree: {list(filled_sources.values())}"

def verify_identity(
    address: str,
    existing_data: dict = None,
    run_checks: bool = True
) -> dict:
    """
    Verify identity from multiple sources.

    Args:
        address: The address to verify
        existing_data: Pre-collected data (from enriched CSV)
        run_checks: Whether to run live checks (slower)

    Returns:
        Dictionary with verification results
    """
    sources = {}
    raw_data = existing_data or {}

    # Source 1: Etherscan labels
    if "etherscan_label" in raw_data:
        sources["etherscan"] = raw_data.get("etherscan_label")
    elif run_checks:
        try:
            info = get_contract_info(address)
            sources["etherscan"] = info.get("label")
        except:
            pass

    # Source 2: Arkham Intelligence
    if "arkham_label" in raw_data:
        sources["arkham"] = raw_data.get("arkham_label")
    elif run_checks:
        try:
            label = check_arkham_label(address)
            sources["arkham"] = label
        except:
            pass

    # Source 3: ENS name
    if "ens_name" in raw_data:
        sources["ens"] = raw_data.get("ens_name")

    # Source 4: CEX funding origin
    if "first_funder_label" in raw_data:
        sources["cex_funding"] = raw_data.get("first_funder_label")

    # Source 5: Dune labels (owner_key, custody_owner)
    if "owner_key" in raw_data:
        sources["dune_owner"] = raw_data.get("owner_key")
    if "custody_owner" in raw_data:
        sources["dune_custody"] = raw_data.get("custody_owner")

    # Source 6: Contract name (for verified contracts)
    if "contract_name" in raw_data:
        sources["contract_name"] = raw_data.get("contract_name")

    # Source 7: Custom identity mapping (from reference file)
    if "identity" in raw_data:
        sources["custom"] = raw_data.get("identity")

    # Source 8: Governance activity (if available)
    if "governance_spaces" in raw_data:
        sources["governance"] = raw_data.get("governance_spaces")

    # Calculate confidence
    confidence, reasoning = calculate_confidence(sources)

    # Determine best identity
    filled_sources = {k: v for k, v in sources.items() if v}

    if not filled_sources:
        best_identity = None
    elif len(set(filled_sources.values())) == 1:
        best_identity = list(filled_sources.values())[0]
    else:
        # Prefer certain sources over others
        source_priority = [
            "custom",      # Manual research (highest trust)
            "arkham",      # Professional labeling
            "etherscan",   # Verified labels
            "dune_owner",  # Dune community labels
            "ens",         # Self-identified
            "contract_name",
            "cex_funding",
            "governance"
        ]

        for source in source_priority:
            if source in filled_sources:
                best_identity = filled_sources[source]
                break
        else:
            best_identity = list(filled_sources.values())[0]

    return {
        "address": address,
        "identity": best_identity,
        "confidence": confidence,
        "reasoning": reasoning,
        "sources": sources,
        "source_count": len(filled_sources),
        "sources_agree": len(set(v for v in sources.values() if v)) <= 1
    }

def verify_batch(rows: List[dict], run_live_checks: bool = False) -> List[dict]:
    """Verify identities for a batch of addresses."""
    results = []

    for i, row in enumerate(rows):
        if i % 100 == 0:
            print(f"Verifying {i}/{len(rows)}...")

        address = row.get("address") or row.get("borrower")
        if not address:
            continue

        result = verify_identity(address, row, run_checks=run_live_checks)
        result["original_data"] = row
        results.append(result)

    return results

def generate_verification_report(results: List[dict]) -> str:
    """Generate a summary report of verification results."""
    total = len(results)
    identified = [r for r in results if r["identity"]]
    high_confidence = [r for r in results if r["confidence"] >= 0.7]
    medium_confidence = [r for r in results if 0.4 <= r["confidence"] < 0.7]
    low_confidence = [r for r in results if 0 < r["confidence"] < 0.4]
    unidentified = [r for r in results if not r["identity"]]

    # Source coverage
    source_counts = defaultdict(int)
    for r in results:
        for source, value in r["sources"].items():
            if value:
                source_counts[source] += 1

    # Disagreement analysis
    disagreements = [r for r in results if not r["sources_agree"] and r["source_count"] > 1]

    report = f"""
{'='*60}
IDENTITY VERIFICATION REPORT
{'='*60}

SUMMARY
-------
Total addresses: {total}
Identified: {len(identified)} ({100*len(identified)/total:.1f}%)
Unidentified: {len(unidentified)} ({100*len(unidentified)/total:.1f}%)

CONFIDENCE DISTRIBUTION
-----------------------
High (≥70%): {len(high_confidence)} ({100*len(high_confidence)/total:.1f}%)
Medium (40-70%): {len(medium_confidence)} ({100*len(medium_confidence)/total:.1f}%)
Low (<40%): {len(low_confidence)} ({100*len(low_confidence)/total:.1f}%)

SOURCE COVERAGE
---------------
"""

    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        report += f"  {source}: {count} ({100*count/total:.1f}%)\n"

    report += f"""
DISAGREEMENTS
-------------
Addresses with conflicting sources: {len(disagreements)}
"""

    if disagreements:
        report += "\nTop disagreements:\n"
        for r in disagreements[:5]:
            report += f"  {r['address'][:15]}...\n"
            for source, value in r["sources"].items():
                if value:
                    report += f"    - {source}: {value}\n"

    return report

def main():
    parser = argparse.ArgumentParser(description="Multi-Source Identity Verification")
    parser.add_argument("input", nargs="?", help="Input CSV file (enriched data)")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to verify")
    parser.add_argument("--live-checks", action="store_true",
                        help="Run live API checks (slower)")
    parser.add_argument("--report", action="store_true",
                        help="Generate verification report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.address:
        # Single address mode
        print(f"Verifying {args.address}...")
        result = verify_identity(args.address, run_checks=args.live_checks)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nAddress: {result['address']}")
            print(f"Identity: {result['identity'] or 'Unknown'}")
            print(f"Confidence: {result['confidence']:.0%}")
            print(f"Reasoning: {result['reasoning']}")
            print(f"\nSources ({result['source_count']}):")
            for source, value in result['sources'].items():
                if value:
                    print(f"  {source}: {value}")

    elif args.input:
        # Batch mode
        print(f"Loading {args.input}...")
        with open(args.input) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Verifying {len(rows)} addresses...")
        results = verify_batch(rows, run_live_checks=args.live_checks)

        # Generate report
        if args.report:
            report = generate_verification_report(results)
            print(report)

        # Output
        if args.json:
            print(json.dumps(results, indent=2))

        if args.output:
            with open(args.output, "w", newline="") as f:
                fieldnames = [
                    "address", "identity", "confidence", "reasoning",
                    "source_count", "sources_agree",
                    "etherscan", "arkham", "ens", "dune_owner",
                    "custom", "cex_funding", "contract_name"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for r in results:
                    row = {
                        "address": r["address"],
                        "identity": r["identity"] or "",
                        "confidence": f"{r['confidence']:.2f}",
                        "reasoning": r["reasoning"],
                        "source_count": r["source_count"],
                        "sources_agree": r["sources_agree"],
                    }
                    for source in ["etherscan", "arkham", "ens", "dune_owner",
                                   "custom", "cex_funding", "contract_name"]:
                        row[source] = r["sources"].get(source, "")

                    writer.writerow(row)

            print(f"\nSaved to {args.output}")

        # Print summary
        identified = [r for r in results if r["identity"]]
        high_conf = [r for r in results if r["confidence"] >= 0.7]
        print(f"\n{'='*40}")
        print(f"Identified: {len(identified)}/{len(results)} ({100*len(identified)/len(results):.1f}%)")
        print(f"High confidence: {len(high_conf)}/{len(results)} ({100*len(high_conf)/len(results):.1f}%)")

    else:
        print("Error: Provide input CSV or --address", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
