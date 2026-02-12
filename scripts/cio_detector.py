#!/usr/bin/env python3
"""
Common Input Ownership (CIO) Detector - EVM Adaptation

Adapted from Bitcoin's CIO heuristic for EVM chains. Since EVM transactions
have a single 'from' address (unlike Bitcoin's multi-input UTXO), we detect
ownership through related patterns:

1. Circular Funding - A funds B, B funds C, C funds A (same entity recycling)
2. Common Funding Source - Multiple wallets funded by same source within 24h
3. Coordinated Activity - Multiple wallets interacting in same block/timeframe
4. Shared Deposit Destination - Multiple wallets depositing to same exchange address

Based on ZachXBT methodology and Chainalysis academic research.

Usage:
    python3 cio_detector.py addresses.csv -o clusters.csv
    python3 cio_detector.py --address 0x1234...
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"

# Rate limiting
RATE_LIMIT = 5  # requests per second
last_request_time = 0

def rate_limit():
    """Enforce rate limiting."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / RATE_LIMIT:
        time.sleep(1 / RATE_LIMIT - elapsed)
    last_request_time = time.time()

def etherscan_request(params: dict, chain_id: int = 1) -> dict:
    """Make a rate-limited request to Etherscan V2 API."""
    rate_limit()
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = chain_id

    try:
        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)
        data = response.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return []

def get_normal_transactions(address: str, chain_id: int = 1, limit: int = 1000) -> List[dict]:
    """Get normal transactions for an address."""
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }
    return etherscan_request(params, chain_id)

def get_internal_transactions(address: str, chain_id: int = 1, limit: int = 1000) -> List[dict]:
    """Get internal transactions for an address."""
    params = {
        "module": "account",
        "action": "txlistinternal",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }
    return etherscan_request(params, chain_id)

def detect_circular_funding(addresses: List[str], chain_id: int = 1) -> Dict[str, Set[str]]:
    """
    Detect circular funding patterns where wallets fund each other.

    If A → B → C → A, they're likely the same entity.
    """
    print("Detecting circular funding patterns...")

    # Build funding graph
    funding_graph: Dict[str, Set[str]] = defaultdict(set)  # funder -> funded
    funded_by: Dict[str, Set[str]] = defaultdict(set)  # funded -> funders

    address_set = set(addr.lower() for addr in addresses)

    for i, addr in enumerate(addresses):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(addresses)}...")

        txs = get_normal_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            # Only consider ETH transfers (not contract calls)
            if value > 0:
                if from_addr in address_set and to_addr in address_set:
                    funding_graph[from_addr].add(to_addr)
                    funded_by[to_addr].add(from_addr)

    # Find cycles (circular funding)
    clusters: Dict[str, Set[str]] = {}
    visited = set()

    def find_cycle(start: str, current: str, path: Set[str]) -> Optional[Set[str]]:
        if current in path and current == start and len(path) > 1:
            return path
        if current in visited:
            return None

        path.add(current)
        for next_addr in funding_graph.get(current, []):
            result = find_cycle(start, next_addr, path.copy())
            if result:
                return result
        return None

    cluster_id = 0
    for addr in addresses:
        addr_lower = addr.lower()
        if addr_lower in visited:
            continue

        cycle = find_cycle(addr_lower, addr_lower, set())
        if cycle and len(cycle) > 1:
            cluster_key = f"circular_{cluster_id}"
            clusters[cluster_key] = cycle
            visited.update(cycle)
            cluster_id += 1
            print(f"  Found circular cluster: {len(cycle)} addresses")

    return clusters

def detect_common_funder(addresses: List[str], chain_id: int = 1,
                         time_window_hours: int = 24) -> Dict[str, Set[str]]:
    """
    Detect wallets funded by the same source within a time window.

    If A,B,C all received first funding from X within 24 hours, same entity.
    """
    print("Detecting common funding sources...")

    # Get first funder for each address
    first_funders: Dict[str, Tuple[str, int]] = {}  # address -> (funder, timestamp)

    for i, addr in enumerate(addresses):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(addresses)}...")

        txs = get_normal_transactions(addr.lower(), chain_id, limit=100)

        # Find first incoming ETH transfer
        for tx in txs:
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            if to_addr == addr.lower() and value > 0:
                funder = tx.get("from", "").lower()
                timestamp = int(tx.get("timeStamp", 0))
                first_funders[addr.lower()] = (funder, timestamp)
                break

    # Group by common funder within time window
    funder_groups: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for addr, (funder, ts) in first_funders.items():
        funder_groups[funder].append((addr, ts))

    # Find clusters within time window
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0

    for funder, funded_list in funder_groups.items():
        if len(funded_list) < 2:
            continue

        # Sort by timestamp
        funded_list.sort(key=lambda x: x[1])

        # Group addresses funded within time window
        current_cluster = [funded_list[0]]
        for i in range(1, len(funded_list)):
            addr, ts = funded_list[i]
            prev_ts = current_cluster[-1][1]

            if ts - prev_ts <= time_window_hours * 3600:
                current_cluster.append((addr, ts))
            else:
                if len(current_cluster) >= 2:
                    cluster_key = f"common_funder_{cluster_id}"
                    clusters[cluster_key] = set(a for a, _ in current_cluster)
                    print(f"  Found common funder cluster: {len(current_cluster)} addresses from {funder[:10]}...")
                    cluster_id += 1
                current_cluster = [(addr, ts)]

        # Don't forget last cluster
        if len(current_cluster) >= 2:
            cluster_key = f"common_funder_{cluster_id}"
            clusters[cluster_key] = set(a for a, _ in current_cluster)
            print(f"  Found common funder cluster: {len(current_cluster)} addresses from {funder[:10]}...")
            cluster_id += 1

    return clusters

def detect_coordinated_activity(addresses: List[str], chain_id: int = 1,
                                block_window: int = 5) -> Dict[str, Set[str]]:
    """
    Detect wallets with coordinated activity (same block/timeframe).

    Multiple wallets interacting with same contract in same block = coordinated.
    """
    print("Detecting coordinated activity...")

    # Build activity map: (contract, block_range) -> addresses
    activity_map: Dict[Tuple[str, int], Set[str]] = defaultdict(set)

    for i, addr in enumerate(addresses):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(addresses)}...")

        txs = get_normal_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            to_addr = tx.get("to", "").lower()
            block = int(tx.get("blockNumber", 0))

            # Round block to window
            block_group = block // block_window * block_window

            if to_addr:  # Contract interaction
                activity_map[(to_addr, block_group)].add(addr.lower())

    # Find clusters with 3+ addresses
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0
    seen_addresses = set()

    for (contract, block), addrs in activity_map.items():
        if len(addrs) >= 3 and not addrs.issubset(seen_addresses):
            cluster_key = f"coordinated_{cluster_id}"
            clusters[cluster_key] = addrs
            seen_addresses.update(addrs)
            print(f"  Found coordinated cluster: {len(addrs)} addresses at block ~{block}")
            cluster_id += 1

    return clusters

def detect_shared_deposits(addresses: List[str], chain_id: int = 1) -> Dict[str, Set[str]]:
    """
    Detect wallets that deposit to the same exchange address.

    Exchange deposit addresses are typically single-use per user.
    If two wallets deposit to same address, likely same user.
    """
    print("Detecting shared deposit destinations...")

    # Build deposit map: destination -> source addresses
    deposit_map: Dict[str, Set[str]] = defaultdict(set)

    # Known exchange hot wallets to EXCLUDE (these are shared)
    EXCLUDE_ADDRESSES = {
        "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance 16
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance 15
        "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",  # Binance 1
        "0xd24400ae8bfebb18ca49be86258a3c749cf46853",  # Gemini 1
        "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",  # OKX
        # Add more known hot wallets as needed
    }

    for i, addr in enumerate(addresses):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(addresses)}...")

        txs = get_normal_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            # Outgoing ETH transfer (potential deposit)
            if from_addr == addr.lower() and value > 0 and to_addr not in EXCLUDE_ADDRESSES:
                # Check if it looks like a deposit (reasonable amount, not gas)
                eth_value = value / 1e18
                if 0.01 < eth_value < 1000:  # Reasonable deposit range
                    deposit_map[to_addr].add(addr.lower())

    # Find shared destinations
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0

    for dest, sources in deposit_map.items():
        if len(sources) >= 2:
            cluster_key = f"shared_deposit_{cluster_id}"
            clusters[cluster_key] = sources
            print(f"  Found shared deposit cluster: {len(sources)} addresses → {dest[:10]}...")
            cluster_id += 1

    return clusters

def merge_clusters(all_clusters: List[Dict[str, Set[str]]]) -> Dict[str, dict]:
    """Merge overlapping clusters from different detection methods."""
    print("\nMerging overlapping clusters...")

    # Build address -> cluster mapping
    address_clusters: Dict[str, List[str]] = defaultdict(list)

    for clusters in all_clusters:
        for cluster_id, addresses in clusters.items():
            for addr in addresses:
                address_clusters[addr].append(cluster_id)

    # Union-find to merge overlapping clusters
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union addresses that appear in same cluster
    for clusters in all_clusters:
        for addresses in clusters.values():
            addr_list = list(addresses)
            for i in range(1, len(addr_list)):
                union(addr_list[0], addr_list[i])

    # Build final clusters
    final_clusters: Dict[str, Set[str]] = defaultdict(set)
    for addr in address_clusters:
        root = find(addr)
        final_clusters[root].add(addr)

    # Format output
    result = {}
    for i, (root, members) in enumerate(final_clusters.items()):
        if len(members) >= 2:
            # Collect detection methods
            methods = set()
            for clusters in all_clusters:
                for cluster_id, addresses in clusters.items():
                    if members & addresses:
                        method = cluster_id.rsplit('_', 1)[0]
                        methods.add(method)

            result[f"cluster_{i}"] = {
                "addresses": list(members),
                "size": len(members),
                "methods": list(methods),
                "confidence": min(0.9, 0.5 + 0.2 * len(methods))  # More methods = higher confidence
            }

    return result

def run_cio_detection(addresses: List[str], chain_id: int = 1,
                      methods: List[str] = None) -> Dict[str, dict]:
    """Run all CIO detection methods and merge results."""

    if methods is None:
        methods = ["circular", "common_funder", "coordinated", "shared_deposits"]

    all_clusters = []

    if "circular" in methods:
        clusters = detect_circular_funding(addresses, chain_id)
        all_clusters.append(clusters)

    if "common_funder" in methods:
        clusters = detect_common_funder(addresses, chain_id)
        all_clusters.append(clusters)

    if "coordinated" in methods:
        clusters = detect_coordinated_activity(addresses, chain_id)
        all_clusters.append(clusters)

    if "shared_deposits" in methods:
        clusters = detect_shared_deposits(addresses, chain_id)
        all_clusters.append(clusters)

    return merge_clusters(all_clusters)

def main():
    parser = argparse.ArgumentParser(description="CIO Detector - EVM Adaptation")
    parser.add_argument("input", nargs="?", help="Input CSV file with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--methods", default="circular,common_funder,coordinated,shared_deposits",
                        help="Detection methods (comma-separated)")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID (1=Ethereum)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not ETHERSCAN_API_KEY:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    methods = args.methods.split(",")

    # Get addresses
    if args.address:
        addresses = [args.address]
    elif args.input:
        with open(args.input) as f:
            reader = csv.DictReader(f)
            addresses = [row.get("address") or row.get("borrower") for row in reader]
            addresses = [a for a in addresses if a]
    else:
        print("Error: Provide input CSV or --address", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(addresses)} addresses...")
    print(f"Methods: {methods}")
    print(f"Chain ID: {args.chain_id}")
    print()

    # Run detection
    clusters = run_cio_detection(addresses, args.chain_id, methods)

    # Output
    if args.json:
        print(json.dumps(clusters, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"RESULTS: Found {len(clusters)} clusters")
        print(f"{'='*60}\n")

        for cluster_id, data in sorted(clusters.items(), key=lambda x: -x[1]["size"]):
            print(f"{cluster_id}:")
            print(f"  Size: {data['size']}")
            print(f"  Methods: {', '.join(data['methods'])}")
            print(f"  Confidence: {data['confidence']:.0%}")
            print(f"  Addresses:")
            for addr in data["addresses"][:5]:
                print(f"    - {addr}")
            if len(data["addresses"]) > 5:
                print(f"    ... and {len(data['addresses']) - 5} more")
            print()

    # Save to CSV if output specified
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["address", "cluster_id", "cluster_size", "methods", "confidence"])

            for cluster_id, data in clusters.items():
                for addr in data["addresses"]:
                    writer.writerow([
                        addr,
                        cluster_id,
                        data["size"],
                        "|".join(data["methods"]),
                        f"{data['confidence']:.2f}"
                    ])

        print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
