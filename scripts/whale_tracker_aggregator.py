#!/usr/bin/env python3
"""
Whale Tracker Aggregator - Check if addresses are tracked by whale watchers.

Aggregates data from:
- Lookonchain (@lookonchain on X)
- OnchainLens (@OnchainLens on X)
- Spot On Chain (@spotonchain on X)
- Arkham entity labels
- Known whale clusters

Note: Most whale trackers don't have public APIs, so this script:
1. Checks known whale address lists (pre-compiled)
2. Searches web for address mentions
3. Uses Arkham entity lookups

Usage:
    # Single address
    python3 scripts/whale_tracker_aggregator.py --address 0x1234...

    # Batch from CSV
    python3 scripts/whale_tracker_aggregator.py addresses.csv -o whale_matches.csv

    # With web search (slower, more thorough)
    python3 scripts/whale_tracker_aggregator.py --address 0x1234... --search

Based on: ZachXBT methodology - check whale trackers first
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

# Known whale addresses from public tracking
# Format: address -> (name, tracker_source, notes)
KNOWN_WHALES = {
    # Trend Research cluster (Lookonchain, OnchainLens tracked)
    "0xfaf1358fe6a9fa29a169dfc272b14e709f54840f": ("Trend Research (LD Capital)", "Lookonchain", "55-wallet cluster"),
    "0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c": ("Trend Research (LD Capital)", "Lookonchain", "55-wallet cluster"),
    "0x85e05c10db73499fbdecab0dfbb794a446feeec8": ("Trend Research (LD Capital)", "Lookonchain", "55-wallet cluster"),

    # 7 Siblings (Arkham entity)
    "0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0": ("7 Siblings", "Arkham", "wNXM whale"),
    "0x741aa7cfb2c7bf2a1e7d4da2e3df6a56ca4131f3": ("7 Siblings", "Arkham", "wNXM whale"),

    # BitcoinOG / 1011short
    "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae": ("BitcoinOG (1011short)", "Arkham/Lookonchain", "$4B+ holder"),
    "0x2ea18c23f72a4b6172c55b411823cdc5335923f4": ("BitcoinOG (1011short)", "Arkham", "Oct 2025 BTC short"),
    "0x4b70525ecf8819a6d1422ba878be87e602f8b42e": ("BitcoinOG (1011short)", "Arkham", "Related wallet"),

    # Justin Sun
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": ("Justin Sun (TRON/HTX)", "Etherscan/Arkham", "Confirmed"),

    # World Liberty Financial
    "0x5be9a4959308a0d0c7bc0870e319314d8d957dbb": ("World Liberty Financial (Trump)", "Etherscan", "Trump DeFi project"),
    "0x97f1f8003ad0fb1c99361170310c65dc84f921e3": ("World Liberty Financial (Trump)", "Etherscan", "Trump DeFi project"),

    # Michael Egorov
    "0x7a16ff8270133f063aab6c9977183d9e72835428": ("Michael Egorov (llamalend.eth)", "ENS/Etherscan", "Curve founder"),

    # Abraxas Capital
    "0xed0c6079229e2d407672a117c22b62064f4a4312": ("Abraxas Capital", "Arkham", "Crypto fund"),
    "0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5": ("Abraxas Capital", "Arkham", "Crypto fund"),

    # Protocol wallets (not individuals but good to flag)
    "0xf0bb20865277abd641a307ece5ee04e79073416c": ("Ether.fi LIQUIDETH", "Etherscan", "Protocol vault"),
    "0x9600a48ed0f931d0c422d574e3275a90d8b22745": ("Fluid (Instadapp)", "Etherscan", "Protocol vault"),
    "0xef417fce1883c6653e7dc6af7c6f85ccde84aa09": ("Lido GG Vault", "Etherscan", "Protocol vault"),
    "0x893aa69fbaa1ee81b536f0fbe3a3453e86290080": ("Mellow strETH Sub Vault 2", "Etherscan", "Protocol vault"),

    # Additional known whales
    "0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3": ("Aave Genesis Team", "Etherscan", "Early Aave"),
    "0x197f0a20c1d96f7dffd5c7b5453544947e717d66": ("Copper Custodian Client", "Etherscan", "Institutional"),
    "0x517ce9b6d1fcffd29805c3e19b295247fcd94aef": ("FalconX Client", "Etherscan", "Prime broker client"),
    "0x50fc9731dace42caa45d166bff404bbb7464bf21": ("Paxos/Singapore Institutional", "Etherscan", "Institutional"),
}

# Whale tracker Twitter handles for reference
WHALE_TRACKERS = {
    "lookonchain": "@lookonchain",
    "onchainlens": "@OnchainLens",
    "spotonchain": "@spotonchain",
    "whale_alert": "@whale_alert",
    "arkham": "@arkaboratories",
}


class WhaleTrackerAggregator:
    """Aggregate whale tracking data."""

    def __init__(self):
        self.known_whales = KNOWN_WHALES.copy()
        self.arkham_cache = {}

    def check_known_whale(self, address: str) -> Optional[dict]:
        """Check if address is in known whale list."""
        address = address.lower()
        if address in self.known_whales:
            name, source, notes = self.known_whales[address]
            return {
                "address": address,
                "name": name,
                "source": source,
                "notes": notes,
                "confidence": "HIGH",
            }
        return None

    def check_arkham(self, address: str) -> Optional[dict]:
        """Check Arkham for entity label (scrapes public page)."""
        address = address.lower()

        if address in self.arkham_cache:
            return self.arkham_cache[address]

        try:
            # Arkham public explorer
            url = f"https://platform.arkhamintelligence.com/explorer/address/{address}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                content = response.text

                # Look for entity name in page (basic scraping)
                # This is fragile - Arkham may change their HTML
                entity_match = re.search(r'"entityName":"([^"]+)"', content)
                if entity_match:
                    entity_name = entity_match.group(1)
                    result = {
                        "address": address,
                        "name": entity_name,
                        "source": "Arkham",
                        "notes": "Entity label",
                        "confidence": "HIGH",
                    }
                    self.arkham_cache[address] = result
                    return result

            self.arkham_cache[address] = None
            return None

        except Exception:
            self.arkham_cache[address] = None
            return None

    def search_web_for_whale(self, address: str) -> Optional[dict]:
        """Search web for whale mentions (address prefix search)."""
        # Use address prefix for search
        prefix = address[:10].lower()

        # Search patterns that might find whale mentions
        search_queries = [
            f'"{prefix}" whale',
            f'"{prefix}" Lookonchain',
            f'"{prefix}" OnchainLens',
        ]

        # Note: In production, you'd use a proper search API
        # For now, we just return None as we can't do web search here
        # The --search flag would enable more thorough checking

        return None

    def analyze_address(self, address: str, include_arkham: bool = True, include_search: bool = False) -> dict:
        """
        Check if an address is tracked by whale watchers.

        Returns:
            Dict with tracking info
        """
        address = address.lower()
        results = {
            "address": address,
            "is_known_whale": False,
            "whale_name": None,
            "source": None,
            "confidence": None,
            "notes": None,
        }

        # Check known whale list first (fastest)
        known = self.check_known_whale(address)
        if known:
            results["is_known_whale"] = True
            results["whale_name"] = known["name"]
            results["source"] = known["source"]
            results["confidence"] = known["confidence"]
            results["notes"] = known["notes"]
            return results

        # Check Arkham (if enabled)
        if include_arkham:
            arkham = self.check_arkham(address)
            if arkham:
                results["is_known_whale"] = True
                results["whale_name"] = arkham["name"]
                results["source"] = arkham["source"]
                results["confidence"] = arkham["confidence"]
                results["notes"] = arkham["notes"]
                return results

            # Rate limit for Arkham
            time.sleep(1)

        # Web search (if enabled, very slow)
        if include_search:
            web_result = self.search_web_for_whale(address)
            if web_result:
                results["is_known_whale"] = True
                results.update(web_result)

        return results

    def analyze_batch(self, addresses: list[str], include_arkham: bool = True, show_progress: bool = True) -> list[dict]:
        """Analyze multiple addresses."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            # Only do Arkham check for first 50 (rate limiting)
            check_arkham = include_arkham and i < 50
            result = self.analyze_address(address, include_arkham=check_arkham)
            results.append(result)

            if show_progress and (i + 1) % 10 == 0:
                whales = sum(1 for r in results if r["is_known_whale"])
                print(f"  Progress: {i + 1}/{total} ({whales} known whales found)")

        return results

    def add_known_whale(self, address: str, name: str, source: str, notes: str = ""):
        """Add a whale to the known list."""
        self.known_whales[address.lower()] = (name, source, notes)


def process_csv(input_path: str, output_path: str, aggregator: WhaleTrackerAggregator,
                address_column: str = "address", include_arkham: bool = False):
    """Process CSV file and add whale tracking."""
    rows = []
    addresses = []

    # Read input
    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        for row in reader:
            rows.append(row)
            addr = row.get(address_column, row.get('borrower', ''))
            if addr:
                addresses.append(addr)

    print(f"Checking {len(addresses)} addresses against whale trackers")

    # Add columns
    new_columns = ["is_known_whale", "whale_name", "whale_source", "whale_confidence"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    # Analyze
    results = aggregator.analyze_batch(addresses, include_arkham=include_arkham)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        row["is_known_whale"] = "Yes" if result.get("is_known_whale") else ""
        row["whale_name"] = result.get("whale_name", "")
        row["whale_source"] = result.get("source", "")
        row["whale_confidence"] = result.get("confidence", "")

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    whales = sum(1 for r in results if r["is_known_whale"])
    by_source = {}
    for r in results:
        if r.get("source"):
            by_source[r["source"]] = by_source.get(r["source"], 0) + 1

    print(f"\nResults:")
    print(f"  Known whales found: {whales}/{len(results)}")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {source}: {count}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Whale tracker aggregator")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to check")
    parser.add_argument("--arkham", action="store_true", help="Include Arkham lookup (slower)")
    parser.add_argument("--search", action="store_true", help="Include web search (very slow)")
    parser.add_argument("--column", default="address", help="Column containing addresses")
    parser.add_argument("--add-whale", nargs=3, metavar=("ADDRESS", "NAME", "SOURCE"),
                       help="Add a whale to the known list")

    args = parser.parse_args()

    aggregator = WhaleTrackerAggregator()

    # Add whale if specified
    if args.add_whale:
        address, name, source = args.add_whale
        aggregator.add_known_whale(address, name, source)
        print(f"Added: {name} ({address[:10]}...) from {source}")
        return

    if args.address:
        # Single address
        print(f"Checking {args.address}...")
        result = aggregator.analyze_address(
            args.address,
            include_arkham=args.arkham,
            include_search=args.search
        )

        print(f"\n{args.address}")
        print("-" * 70)

        if result["is_known_whale"]:
            print(f"KNOWN WHALE: {result['whale_name']}")
            print(f"Source: {result['source']}")
            print(f"Confidence: {result['confidence']}")
            if result.get("notes"):
                print(f"Notes: {result['notes']}")
        else:
            print("Not found in whale tracking databases")
            print()
            print("Try checking manually:")
            for name, handle in WHALE_TRACKERS.items():
                print(f"  {name}: Search {handle} on X for this address")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_whales.csv')
        process_csv(args.input, output_path, aggregator, args.column, include_arkham=args.arkham)

    else:
        # List known whales
        print("Known Whale Database:")
        print("-" * 70)
        by_source = {}
        for addr, (name, source, notes) in sorted(KNOWN_WHALES.items(), key=lambda x: x[1][0]):
            if source not in by_source:
                by_source[source] = []
            by_source[source].append((addr, name, notes))

        for source in sorted(by_source.keys()):
            print(f"\n{source}:")
            for addr, name, notes in by_source[source]:
                print(f"  {name}")
                print(f"    {addr}")

        print(f"\nTotal: {len(KNOWN_WHALES)} known whales")
        print()
        print("Usage:")
        print("  python3 whale_tracker_aggregator.py --address 0x1234...")
        print("  python3 whale_tracker_aggregator.py addresses.csv -o output.csv")


if __name__ == "__main__":
    main()
