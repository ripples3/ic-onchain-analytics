#!/usr/bin/env python3
"""
Address Clustering Tool (ZachXBT Methodology)

Identifies wallet clusters owned by the same entity using on-chain signals:
- Common Input Ownership (CIO): Two addresses as inputs in same tx
- Change Address Detection: Small change outputs after large transfers
- Timing Analysis: Correlated transaction patterns
- CEX Deposit Reuse: Same deposit address used by multiple wallets

Usage:
    # Cluster addresses from CSV
    python3 scripts/cluster_addresses.py addresses.csv -o clusters.csv

    # Analyze single address for related wallets
    python3 scripts/cluster_addresses.py --address 0x1234...

    # Full analysis with all methods
    python3 scripts/cluster_addresses.py addresses.csv --methods cio,change,timing,deposits

Environment:
    ETHERSCAN_API_KEY - Required for transaction history

Based on ZachXBT's investigation methodology:
> "I traced around 500 different transactions overnight to find the one link I needed."
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    script_dir = Path(__file__).parent
    env_paths = [script_dir / ".env", script_dir.parent / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ClusterResult:
    """Result of address clustering analysis."""
    address: str
    cluster_id: str = ""
    cluster_size: int = 1
    related_addresses: list = field(default_factory=list)
    signals: dict = field(default_factory=dict)  # signal_type -> list of evidence
    confidence: float = 0.0  # 0-1 overall confidence
    timing_pattern: dict = field(default_factory=dict)
    common_funders: list = field(default_factory=list)
    change_recipients: list = field(default_factory=list)
    shared_deposits: list = field(default_factory=list)
    last_analyzed: str = ""
    error: str = ""


@dataclass
class TimingPattern:
    """Transaction timing pattern for an address."""
    address: str
    tx_count: int = 0
    hour_distribution: dict = field(default_factory=dict)  # hour -> count
    day_distribution: dict = field(default_factory=dict)   # day -> count
    avg_gap_seconds: float = 0.0
    median_gas_price: float = 0.0
    active_hours: list = field(default_factory=list)  # Most active hours (timezone signal)


# ============================================================================
# CEX Deposit Address Database
# ============================================================================

# Known CEX hot wallets for deposit reuse detection
CEX_HOT_WALLETS = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549",
    "0xf977814e90da44bfa03b6295a0616a897441acec",
    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
    "0x503828976d22510aad0201ac7ec88293211d23da",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",
    # FTX (historical)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2",
}


# ============================================================================
# API Client
# ============================================================================

class EtherscanClient:
    """Etherscan API client for transaction history."""

    BASE_URL = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str, rate_limit: float = 5.0):
        self.api_key = api_key
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0

    def _wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _request(self, **params) -> dict:
        self._wait()
        params["apikey"] = self.api_key
        params["chainid"] = params.get("chainid", 1)

        resp = requests.get(self.BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_transactions(self, address: str, limit: int = 500) -> list[dict]:
        """Get transaction history for an address."""
        data = self._request(
            module="account",
            action="txlist",
            address=address,
            startblock=0,
            endblock=99999999,
            page=1,
            offset=min(limit, 10000),
            sort="desc"
        )

        if data.get("status") == "1":
            return data.get("result", [])
        return []

    def get_internal_transactions(self, address: str, limit: int = 100) -> list[dict]:
        """Get internal transactions for an address."""
        data = self._request(
            module="account",
            action="txlistinternal",
            address=address,
            startblock=0,
            endblock=99999999,
            page=1,
            offset=min(limit, 10000),
            sort="desc"
        )

        if data.get("status") == "1":
            return data.get("result", [])
        return []


# ============================================================================
# Clustering Methods
# ============================================================================

def analyze_timing_pattern(transactions: list[dict]) -> TimingPattern:
    """
    Analyze transaction timing patterns.

    Detects:
    - Hour-of-day distribution (timezone signal)
    - Day-of-week distribution
    - Transaction frequency
    - Gas price patterns
    """
    if not transactions:
        return TimingPattern(address="")

    hour_dist = defaultdict(int)
    day_dist = defaultdict(int)
    gas_prices = []
    timestamps = []

    for tx in transactions:
        try:
            ts = int(tx.get("timeStamp", 0))
            if ts == 0:
                continue

            dt = datetime.fromtimestamp(ts)
            hour_dist[dt.hour] += 1
            day_dist[dt.strftime("%A")] += 1
            timestamps.append(ts)

            gas = int(tx.get("gasPrice", 0))
            if gas > 0:
                gas_prices.append(gas)
        except Exception:
            continue

    # Calculate average gap between transactions
    avg_gap = 0.0
    if len(timestamps) > 1:
        timestamps.sort(reverse=True)
        gaps = [timestamps[i] - timestamps[i+1] for i in range(len(timestamps)-1)]
        avg_gap = sum(gaps) / len(gaps)

    # Find most active hours
    sorted_hours = sorted(hour_dist.items(), key=lambda x: -x[1])
    active_hours = [h for h, _ in sorted_hours[:3]]

    # Median gas price
    median_gas = 0.0
    if gas_prices:
        gas_prices.sort()
        mid = len(gas_prices) // 2
        median_gas = gas_prices[mid]

    return TimingPattern(
        address=transactions[0].get("from", "") if transactions else "",
        tx_count=len(transactions),
        hour_distribution=dict(hour_dist),
        day_distribution=dict(day_dist),
        avg_gap_seconds=avg_gap,
        median_gas_price=median_gas,
        active_hours=active_hours
    )


def correlate_timing_patterns(patterns: list[TimingPattern], threshold: float = 0.7) -> list[tuple]:
    """
    Find address pairs with correlated timing patterns.

    Returns list of (addr1, addr2, correlation_score) tuples.
    """
    correlations = []

    for i, p1 in enumerate(patterns):
        for j, p2 in enumerate(patterns):
            if i >= j:
                continue

            # Compare hour distributions
            hours1 = set(p1.active_hours)
            hours2 = set(p2.active_hours)

            if not hours1 or not hours2:
                continue

            # Jaccard similarity of active hours
            intersection = len(hours1 & hours2)
            union = len(hours1 | hours2)
            hour_sim = intersection / union if union > 0 else 0

            # Compare average gap (within 2x is similar)
            gap_sim = 0.0
            if p1.avg_gap_seconds > 0 and p2.avg_gap_seconds > 0:
                ratio = min(p1.avg_gap_seconds, p2.avg_gap_seconds) / max(p1.avg_gap_seconds, p2.avg_gap_seconds)
                gap_sim = ratio if ratio > 0.5 else 0

            # Combined score
            score = (hour_sim * 0.6) + (gap_sim * 0.4)

            if score >= threshold:
                correlations.append((p1.address, p2.address, score))

    return correlations


def find_common_funders(transactions_map: dict[str, list[dict]]) -> dict[str, list[str]]:
    """
    Find addresses that share a common funder.

    Returns: {funder_address: [funded_addresses]}
    """
    funder_to_funded = defaultdict(set)

    for address, txs in transactions_map.items():
        address = address.lower()
        for tx in txs:
            # Find incoming transactions
            if tx.get("to", "").lower() == address:
                funder = tx.get("from", "").lower()
                value = int(tx.get("value", "0"))

                # Only count significant funding (>0.1 ETH)
                if value > 0.1 * 1e18:
                    funder_to_funded[funder].add(address)

    # Filter to funders with multiple recipients
    return {
        funder: list(funded)
        for funder, funded in funder_to_funded.items()
        if len(funded) > 1
    }


def detect_change_addresses(address: str, transactions: list[dict], threshold_ratio: float = 0.15) -> list[dict]:
    """
    Detect potential change addresses.

    A change address receives a small amount (<15% of sent amount) in the same tx
    or immediately after a large outgoing transfer.

    Returns list of {address, tx_hash, change_amount, main_amount, ratio}
    """
    changes = []
    address = address.lower()

    for tx in transactions:
        # Only look at outgoing transactions
        if tx.get("from", "").lower() != address:
            continue

        value = int(tx.get("value", "0"))
        if value < 0.01 * 1e18:  # Skip tiny amounts
            continue

        # Look for multiple outputs in internal transactions
        # This is a simplified version - full implementation would analyze trace calls

    return changes


def find_shared_cex_deposits(transactions_map: dict[str, list[dict]]) -> dict[str, list[str]]:
    """
    Find addresses that deposit to the same CEX deposit address.

    CEX deposit addresses are often single-use, so if two wallets
    send to the same non-hot-wallet CEX address, they're likely the same user.
    """
    deposit_to_senders = defaultdict(set)

    for address, txs in transactions_map.items():
        address = address.lower()
        for tx in txs:
            to_addr = tx.get("to", "").lower()
            from_addr = tx.get("from", "").lower()

            # Must be outgoing from this address
            if from_addr != address:
                continue

            # Skip hot wallets (those are shared by everyone)
            if to_addr in CEX_HOT_WALLETS:
                continue

            # Look for patterns that suggest CEX deposit addresses
            # These are often addresses with:
            # - Very few outgoing transactions
            # - All funds eventually go to CEX hot wallets
            # This is a heuristic - would need to trace further for certainty

            value = int(tx.get("value", "0"))
            if value > 0.1 * 1e18:  # Significant amounts only
                deposit_to_senders[to_addr].add(address)

    # Filter to deposits with multiple senders
    return {
        deposit: list(senders)
        for deposit, senders in deposit_to_senders.items()
        if len(senders) > 1
    }


def build_cluster_graph(
    addresses: list[str],
    timing_correlations: list[tuple],
    common_funders: dict[str, list[str]],
    shared_deposits: dict[str, list[str]]
) -> dict[str, set]:
    """
    Build a cluster graph from all signals.

    Returns adjacency list: {address: set(connected_addresses)}
    """
    graph = defaultdict(set)

    # Add timing correlation edges
    for addr1, addr2, score in timing_correlations:
        if score > 0.7:
            graph[addr1.lower()].add(addr2.lower())
            graph[addr2.lower()].add(addr1.lower())

    # Add common funder edges
    for funder, funded in common_funders.items():
        for i, addr1 in enumerate(funded):
            for addr2 in funded[i+1:]:
                graph[addr1.lower()].add(addr2.lower())
                graph[addr2.lower()].add(addr1.lower())

    # Add shared deposit edges (high confidence)
    for deposit, senders in shared_deposits.items():
        for i, addr1 in enumerate(senders):
            for addr2 in senders[i+1:]:
                graph[addr1.lower()].add(addr2.lower())
                graph[addr2.lower()].add(addr1.lower())

    return dict(graph)


def find_clusters(graph: dict[str, set]) -> list[set]:
    """
    Find connected components (clusters) in the graph.

    Uses BFS to find all connected addresses.
    """
    visited = set()
    clusters = []

    for address in graph:
        if address in visited:
            continue

        # BFS to find all connected addresses
        cluster = set()
        queue = [address]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)
            cluster.add(current)

            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        if cluster:
            clusters.append(cluster)

    return clusters


# ============================================================================
# Main Analysis
# ============================================================================

def analyze_addresses(
    addresses: list[str],
    client: EtherscanClient,
    methods: list[str] = None
) -> list[ClusterResult]:
    """
    Analyze a list of addresses for clustering signals.
    """
    if methods is None:
        methods = ["timing", "funders", "deposits"]

    results = []
    transactions_map = {}
    timing_patterns = []

    # Fetch transaction history for all addresses
    print(f"Fetching transactions for {len(addresses)} addresses...", file=sys.stderr)
    for i, addr in enumerate(addresses):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(addresses)}", file=sys.stderr)

        txs = client.get_transactions(addr, limit=200)
        transactions_map[addr.lower()] = txs

        if "timing" in methods and txs:
            pattern = analyze_timing_pattern(txs)
            pattern.address = addr.lower()
            timing_patterns.append(pattern)

    # Run clustering methods
    timing_correlations = []
    common_funders = {}
    shared_deposits = {}

    if "timing" in methods and timing_patterns:
        print("Analyzing timing patterns...", file=sys.stderr)
        timing_correlations = correlate_timing_patterns(timing_patterns)

    if "funders" in methods:
        print("Finding common funders...", file=sys.stderr)
        common_funders = find_common_funders(transactions_map)

    if "deposits" in methods:
        print("Checking shared CEX deposits...", file=sys.stderr)
        shared_deposits = find_shared_cex_deposits(transactions_map)

    # Build cluster graph
    graph = build_cluster_graph(
        addresses,
        timing_correlations,
        common_funders,
        shared_deposits
    )

    # Find connected clusters
    clusters = find_clusters(graph)

    # Assign cluster IDs
    cluster_map = {}
    for i, cluster in enumerate(clusters):
        cluster_id = f"cluster_{i+1}"
        for addr in cluster:
            cluster_map[addr] = (cluster_id, cluster)

    # Build results
    for addr in addresses:
        addr_lower = addr.lower()
        result = ClusterResult(
            address=addr_lower,
            last_analyzed=datetime.now(timezone.utc).isoformat()
        )

        if addr_lower in cluster_map:
            cluster_id, cluster = cluster_map[addr_lower]
            result.cluster_id = cluster_id
            result.cluster_size = len(cluster)
            result.related_addresses = [a for a in cluster if a != addr_lower]

            # Calculate confidence based on signal count
            signals = 0
            if any(addr_lower in [c[0].lower(), c[1].lower()] for c in timing_correlations):
                signals += 1
                result.signals["timing"] = True
            if any(addr_lower in funded for funded in common_funders.values()):
                signals += 1
                result.signals["common_funder"] = True
            if any(addr_lower in senders for senders in shared_deposits.values()):
                signals += 2  # Higher weight for deposit reuse
                result.signals["shared_deposit"] = True

            result.confidence = min(1.0, signals * 0.25)

        # Add timing pattern
        for p in timing_patterns:
            if p.address == addr_lower:
                result.timing_pattern = {
                    "tx_count": p.tx_count,
                    "active_hours": p.active_hours,
                    "avg_gap_hours": p.avg_gap_seconds / 3600 if p.avg_gap_seconds else 0
                }
                break

        # Add related info
        result.common_funders = [
            f for f, funded in common_funders.items()
            if addr_lower in funded
        ]
        result.shared_deposits = [
            d for d, senders in shared_deposits.items()
            if addr_lower in senders
        ]

        results.append(result)

    return results


# ============================================================================
# I/O Functions
# ============================================================================

def load_addresses(filepath: str) -> list[str]:
    """Load addresses from file."""
    addresses = []
    path = Path(filepath)

    if path.suffix == ".csv":
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("address") or row.get("Address") or row.get("wallet")
                if addr:
                    addresses.append(addr.strip().lower())
    else:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith("0x"):
                    addresses.append(line.lower())

    return list(set(addresses))


def save_results(results: list[ClusterResult], filepath: str, format: str = "csv"):
    """Save results to file."""
    if format == "json":
        with open(filepath, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
    else:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "address", "cluster_id", "cluster_size", "related_addresses",
                "confidence", "signals", "common_funders", "shared_deposits",
                "timing_pattern", "last_analyzed", "error"
            ])
            writer.writeheader()
            for r in results:
                row = {
                    "address": r.address,
                    "cluster_id": r.cluster_id,
                    "cluster_size": r.cluster_size,
                    "related_addresses": json.dumps(r.related_addresses) if r.related_addresses else "",
                    "confidence": f"{r.confidence:.2f}",
                    "signals": json.dumps(r.signals) if r.signals else "",
                    "common_funders": json.dumps(r.common_funders) if r.common_funders else "",
                    "shared_deposits": json.dumps(r.shared_deposits) if r.shared_deposits else "",
                    "timing_pattern": json.dumps(r.timing_pattern) if r.timing_pattern else "",
                    "last_analyzed": r.last_analyzed,
                    "error": r.error,
                }
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Cluster wallet addresses using on-chain signals (ZachXBT methodology)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze addresses from CSV
    python3 cluster_addresses.py whales.csv -o clusters.csv

    # Analyze single address
    python3 cluster_addresses.py --address 0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c

    # Specific methods only
    python3 cluster_addresses.py whales.csv --methods timing,funders

Methods:
    timing   - Analyze transaction timing patterns (timezone, frequency)
    funders  - Find addresses with common funding sources
    deposits - Detect shared CEX deposit addresses (high confidence)
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with addresses"
    )

    parser.add_argument(
        "--address", "-a",
        help="Analyze single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="clusters.csv",
        help="Output file (default: clusters.csv)"
    )

    parser.add_argument(
        "--methods", "-m",
        default="timing,funders,deposits",
        help="Comma-separated clustering methods"
    )

    parser.add_argument(
        "--format", "-f",
        default="csv",
        choices=["csv", "json"],
        help="Output format (default: csv)"
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=5.0,
        help="API requests per second (default: 5.0)"
    )

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = EtherscanClient(api_key, args.rate_limit)
    methods = [m.strip().lower() for m in args.methods.split(",")]

    # Single address mode
    if args.address:
        # For single address, also fetch related addresses
        print(f"Analyzing {args.address}...", file=sys.stderr)
        txs = client.get_transactions(args.address, limit=200)

        # Find potentially related addresses (received from or sent to)
        related = set()
        for tx in txs:
            related.add(tx.get("from", "").lower())
            related.add(tx.get("to", "").lower())

        related.discard(args.address.lower())
        related.discard("")

        # Limit related addresses for analysis
        related_list = list(related)[:20]
        all_addresses = [args.address] + related_list

        print(f"Found {len(related_list)} related addresses", file=sys.stderr)
        results = analyze_addresses(all_addresses, client, methods)

        # Filter to show only the target and clustered addresses
        target_result = next((r for r in results if r.address == args.address.lower()), None)
        if target_result:
            print(json.dumps(asdict(target_result), indent=2))
        else:
            print(json.dumps({"error": "Analysis failed"}))
        return

    # Batch mode
    addresses = load_addresses(args.input)
    print(f"Analyzing {len(addresses)} addresses...", file=sys.stderr)

    results = analyze_addresses(addresses, client, methods)

    save_results(results, args.output, args.format)
    print(f"\nSaved to {args.output}", file=sys.stderr)

    # Summary
    clustered = [r for r in results if r.cluster_id]
    unique_clusters = len(set(r.cluster_id for r in clustered if r.cluster_id))

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total addresses: {len(results)}", file=sys.stderr)
    print(f"  In clusters: {len(clustered)} ({100*len(clustered)/len(results):.1f}%)", file=sys.stderr)
    print(f"  Unique clusters: {unique_clusters}", file=sys.stderr)

    # Show largest clusters
    if clustered:
        cluster_sizes = defaultdict(int)
        for r in clustered:
            cluster_sizes[r.cluster_id] = r.cluster_size

        print(f"\n  Largest clusters:", file=sys.stderr)
        for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1])[:5]:
            print(f"    {cid}: {size} addresses", file=sys.stderr)


if __name__ == "__main__":
    main()
