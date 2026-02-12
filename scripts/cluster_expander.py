#!/usr/bin/env python3
"""
Cluster Expander - On-Chain Layer

Expands from seed addresses to full clusters using:
1. CIO Detection - Common Input Ownership heuristics (94.85% accuracy)
2. Cross-Chain Correlation - Same address on multiple chains
3. Change Address Detection - Dust patterns and related wallets
4. Bridge Transaction Tracking - Follow funds across chains

Integrates with the Knowledge Graph for persistent storage.

Usage:
    # Standalone mode
    python3 cluster_expander.py addresses.csv -o expanded.csv

    # With knowledge graph integration (called from build_knowledge_graph.py)
    from cluster_expander import process_addresses
    process_addresses(knowledge_graph, addresses)
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# API Configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# Chain configurations
CHAINS = {
    'ethereum': {'chain_id': 1, 'api_base': 'https://api.etherscan.io/v2/api'},
    'arbitrum': {'chain_id': 42161, 'api_base': 'https://api.etherscan.io/v2/api'},
    'base': {'chain_id': 8453, 'api_base': 'https://api.etherscan.io/v2/api'},
    'optimism': {'chain_id': 10, 'api_base': 'https://api.etherscan.io/v2/api'},
    'polygon': {'chain_id': 137, 'api_base': 'https://api.etherscan.io/v2/api'},
}

# Known bridge contracts
BRIDGE_CONTRACTS = {
    # Arbitrum
    '0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a': 'Arbitrum Bridge',
    '0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f': 'Arbitrum Inbox',
    # Optimism
    '0x99c9fc46f92e8a1c0dec1b1747d010903e884be1': 'Optimism Gateway',
    '0x4200000000000000000000000000000000000010': 'Optimism L2 Bridge',
    # Base
    '0x49048044d57e1c92a77f79988d21fa8faf74e97e': 'Base Bridge',
    # Polygon
    '0xa0c68c638235ee32657e8f720a23cec1bfc77c77': 'Polygon Bridge',
}

# Rate limiting
RATE_LIMIT = 5.0  # requests per second
last_request_time = 0


def rate_limit():
    """Enforce rate limiting."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / RATE_LIMIT:
        time.sleep(1 / RATE_LIMIT - elapsed)
    last_request_time = time.time()


def etherscan_request(params: dict, chain_id: int = 1) -> Any:
    """Make a rate-limited request to Etherscan V2 API."""
    rate_limit()
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = chain_id

    try:
        response = requests.get(
            "https://api.etherscan.io/v2/api",
            params=params,
            timeout=30
        )
        data = response.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"  API Error: {e}", file=sys.stderr)
        return []


def get_transactions(address: str, chain_id: int = 1, limit: int = 1000) -> List[dict]:
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


def get_token_transfers(address: str, chain_id: int = 1, limit: int = 500) -> List[dict]:
    """Get ERC20 token transfers for an address."""
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }
    return etherscan_request(params, chain_id)


# ============================================================================
# CIO Detection (Common Input Ownership)
# ============================================================================

def detect_circular_funding(addresses: List[str], chain_id: int = 1) -> Dict[str, Set[str]]:
    """
    Detect circular funding patterns (A → B → C → A).
    If wallets fund each other in a cycle, likely same entity.
    """
    print("  Detecting circular funding patterns...")

    # Build funding graph
    funding_graph: Dict[str, Set[str]] = defaultdict(set)
    address_set = set(addr.lower() for addr in addresses)

    for i, addr in enumerate(addresses):
        if i % 50 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        txs = get_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            # Only consider ETH transfers within our address set
            if value > 0 and from_addr in address_set and to_addr in address_set:
                funding_graph[from_addr].add(to_addr)

    # Find cycles using iterative DFS (avoids recursion limit)
    clusters: Dict[str, Set[str]] = {}
    globally_visited = set()
    cluster_id = 0

    def find_cycle_iterative(start: str) -> Optional[Set[str]]:
        """Find a cycle starting from 'start' using iterative DFS."""
        # Stack: (current_node, path_list, visited_in_path)
        stack = [(start, [start], {start})]

        while stack:
            current, path, path_set = stack.pop()

            for next_addr in funding_graph.get(current, []):
                # Found cycle back to start
                if next_addr == start and len(path) > 1:
                    return set(path)

                # Skip if already in current path (not a cycle to start)
                # or if we've exceeded max depth
                if next_addr in path_set or len(path) >= 10:
                    continue

                # Skip globally visited (already in a cluster)
                if next_addr in globally_visited:
                    continue

                new_path = path + [next_addr]
                new_path_set = path_set | {next_addr}
                stack.append((next_addr, new_path, new_path_set))

        return None

    for addr in addresses:
        addr_lower = addr.lower()
        if addr_lower in globally_visited:
            continue
        if addr_lower not in funding_graph:
            continue

        cycle = find_cycle_iterative(addr_lower)
        if cycle and len(cycle) > 1:
            clusters[f"circular_{cluster_id}"] = cycle
            globally_visited.update(cycle)
            cluster_id += 1
            print(f"    Found circular cluster: {len(cycle)} addresses")

    return clusters


def detect_common_funder(addresses: List[str], chain_id: int = 1,
                         time_window_hours: int = 48) -> Dict[str, Set[str]]:
    """
    Detect addresses funded by the same source within a time window.
    If A, B, C all received first funding from X within 48 hours, same entity.
    """
    print("  Detecting common funding sources...")

    # Get first funder for each address
    first_funders: Dict[str, Tuple[str, int]] = {}

    for i, addr in enumerate(addresses):
        if i % 50 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        txs = get_transactions(addr.lower(), chain_id, limit=50)

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
                    print(f"    Found common funder cluster: {len(current_cluster)} addresses from {funder[:10]}...")
                    cluster_id += 1
                current_cluster = [(addr, ts)]

        # Don't forget last cluster
        if len(current_cluster) >= 2:
            cluster_key = f"common_funder_{cluster_id}"
            clusters[cluster_key] = set(a for a, _ in current_cluster)
            print(f"    Found common funder cluster: {len(current_cluster)} addresses")
            cluster_id += 1

    return clusters


def detect_shared_deposits(addresses: List[str], chain_id: int = 1) -> Dict[str, Set[str]]:
    """
    Detect addresses depositing to the same exchange address.
    Exchange deposit addresses are typically unique per user.
    """
    print("  Detecting shared deposit destinations...")

    # Known exchange hot wallets to EXCLUDE
    EXCLUDE_ADDRESSES = {
        "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance 16
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance 15
        "0xf977814e90da44bfa03b6295a0616a897441acec",  # Binance 8
        "0x5a52e96bacdabb82fd05763e25335261b270efcb",  # Binance 20
        "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",  # OKX
    }

    deposit_map: Dict[str, Set[str]] = defaultdict(set)

    for i, addr in enumerate(addresses):
        if i % 50 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        txs = get_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            # Outgoing ETH transfer (potential deposit)
            if from_addr == addr.lower() and value > 0 and to_addr not in EXCLUDE_ADDRESSES:
                eth_value = value / 1e18
                if 0.01 < eth_value < 1000:
                    deposit_map[to_addr].add(addr.lower())

    # Find shared destinations
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0

    for dest, sources in deposit_map.items():
        if len(sources) >= 2:
            clusters[f"shared_deposit_{cluster_id}"] = sources
            print(f"    Found shared deposit cluster: {len(sources)} addresses → {dest[:10]}...")
            cluster_id += 1

    return clusters


# ============================================================================
# Cross-Chain Correlation
# ============================================================================

def detect_cross_chain_presence(addresses: List[str]) -> Dict[str, Dict[str, bool]]:
    """
    Check if addresses exist on multiple chains.
    Same address active on multiple chains = strong identity signal.
    """
    print("  Detecting cross-chain presence...")

    results: Dict[str, Dict[str, bool]] = {}

    for i, addr in enumerate(addresses):
        if i % 20 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        results[addr.lower()] = {}

        for chain_name, chain_info in CHAINS.items():
            # Check for any transaction on this chain
            txs = get_transactions(addr.lower(), chain_info['chain_id'], limit=1)
            has_activity = len(txs) > 0
            results[addr.lower()][chain_name] = has_activity

            if has_activity:
                time.sleep(0.2)  # Additional rate limiting for cross-chain

    return results


def detect_bridge_transactions(addresses: List[str], chain_id: int = 1) -> Dict[str, List[dict]]:
    """
    Detect bridge transactions to find cross-chain movements.
    """
    print("  Detecting bridge transactions...")

    bridge_txs: Dict[str, List[dict]] = defaultdict(list)

    for i, addr in enumerate(addresses):
        if i % 50 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        txs = get_transactions(addr.lower(), chain_id, limit=1000)

        for tx in txs:
            to_addr = tx.get("to", "").lower()

            if to_addr in BRIDGE_CONTRACTS:
                bridge_txs[addr.lower()].append({
                    'hash': tx.get('hash'),
                    'bridge': BRIDGE_CONTRACTS[to_addr],
                    'value': int(tx.get('value', 0)) / 1e18,
                    'timestamp': int(tx.get('timeStamp', 0))
                })

    return bridge_txs


# ============================================================================
# Change Address Detection
# ============================================================================

def detect_change_addresses(addresses: List[str], chain_id: int = 1) -> Dict[str, List[str]]:
    """
    Detect potential change addresses from transaction patterns.
    Look for:
    - Small amounts sent immediately after large transactions
    - New addresses receiving from our addresses
    """
    print("  Detecting change addresses...")

    change_candidates: Dict[str, List[str]] = defaultdict(list)

    for i, addr in enumerate(addresses):
        if i % 50 == 0 and i > 0:
            print(f"    Processing {i}/{len(addresses)}...")

        txs = get_transactions(addr.lower(), chain_id, limit=500)

        # Track outgoing transactions
        outgoing = [tx for tx in txs if tx.get('from', '').lower() == addr.lower()]

        for tx in outgoing:
            to_addr = tx.get('to', '').lower()
            value = int(tx.get('value', 0)) / 1e18
            timestamp = int(tx.get('timeStamp', 0))

            # Skip if to a known contract or same address
            if to_addr == addr.lower() or not to_addr:
                continue

            # Check if this looks like a change pattern
            # Small value + new address
            if 0 < value < 1:  # Less than 1 ETH
                # Check if this address has few transactions (likely new)
                target_txs = get_transactions(to_addr, chain_id, limit=10)
                if len(target_txs) <= 5:
                    change_candidates[addr.lower()].append(to_addr)

    return change_candidates


# ============================================================================
# Cluster Merging
# ============================================================================

def merge_all_clusters(cluster_sets: List[Dict[str, Set[str]]]) -> Dict[str, dict]:
    """Merge overlapping clusters from different detection methods."""
    print("\n  Merging overlapping clusters...")

    # Build address -> clusters mapping
    address_clusters: Dict[str, List[str]] = defaultdict(list)

    for clusters in cluster_sets:
        for cluster_id, addresses in clusters.items():
            for addr in addresses:
                address_clusters[addr].append(cluster_id)

    # Union-find for merging
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

    # Union addresses in same clusters
    for clusters in cluster_sets:
        for addresses in clusters.values():
            addr_list = list(addresses)
            for i in range(1, len(addr_list)):
                union(addr_list[0], addr_list[i])

    # Build final clusters
    final_clusters: Dict[str, Set[str]] = defaultdict(set)
    for addr in address_clusters:
        root = find(addr)
        final_clusters[root].add(addr)

    # Format output with metadata
    result = {}
    for i, (root, members) in enumerate(final_clusters.items()):
        if len(members) >= 2:
            # Collect detection methods
            methods = set()
            for clusters in cluster_sets:
                for cluster_id, addresses in clusters.items():
                    if members & addresses:
                        method = cluster_id.rsplit('_', 1)[0]
                        methods.add(method)

            result[f"cluster_{i}"] = {
                "addresses": list(members),
                "size": len(members),
                "methods": list(methods),
                "confidence": min(0.95, 0.5 + 0.15 * len(methods))
            }

    return result


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_single_address(kg: 'KnowledgeGraph', addr: str):
    """
    Process a single address through the on-chain layer.
    Fetches transactions and adds basic evidence.
    CIO clustering requires batch processing and is done separately.
    """
    if not ETHERSCAN_API_KEY:
        raise ValueError("ETHERSCAN_API_KEY not set")

    # Fetch transactions
    txs = get_transactions(addr, chain_id=1, limit=500)

    if not txs:
        kg.add_evidence(
            addr,
            source='CIO',
            claim='No transaction history found',
            confidence=0.3
        )
        return {'address': addr, 'tx_count': 0}

    # Analyze transaction patterns
    unique_senders = set()
    unique_recipients = set()
    total_value_in = 0
    total_value_out = 0

    for tx in txs:
        if tx.get('to', '').lower() == addr.lower():
            unique_senders.add(tx.get('from', '').lower())
            total_value_in += int(tx.get('value', 0))
        if tx.get('from', '').lower() == addr.lower():
            unique_recipients.add(tx.get('to', '').lower())
            total_value_out += int(tx.get('value', 0))

    # Add evidence
    kg.add_evidence(
        addr,
        source='CIO',
        claim=f"Transaction analysis: {len(txs)} txs, {len(unique_senders)} senders, {len(unique_recipients)} recipients",
        confidence=0.5,
        raw_data={
            'tx_count': len(txs),
            'unique_senders': len(unique_senders),
            'unique_recipients': len(unique_recipients),
            'first_tx': txs[-1].get('timeStamp') if txs else None,
            'last_tx': txs[0].get('timeStamp') if txs else None
        }
    )

    return {
        'address': addr,
        'tx_count': len(txs),
        'unique_senders': list(unique_senders)[:10],  # Keep top 10 for potential clustering
        'unique_recipients': list(unique_recipients)[:10]
    }


def process_addresses(kg: 'KnowledgeGraph', addresses: List[str]):
    """
    Process addresses through the on-chain expansion layer.
    Integrates with the knowledge graph for storage.
    """
    print(f"\n  Processing {len(addresses)} addresses through on-chain layer...")

    if not ETHERSCAN_API_KEY:
        print("  Warning: ETHERSCAN_API_KEY not set", file=sys.stderr)
        return

    all_clusters = []

    # Run CIO detection methods
    print("\n  Running CIO detection...")
    circular = detect_circular_funding(addresses)
    if circular:
        all_clusters.append(circular)

    common_funder = detect_common_funder(addresses)
    if common_funder:
        all_clusters.append(common_funder)

    shared_deposits = detect_shared_deposits(addresses)
    if shared_deposits:
        all_clusters.append(shared_deposits)

    # Merge clusters
    merged = merge_all_clusters(all_clusters)

    print(f"\n  Found {len(merged)} clusters from CIO detection")

    # Store in knowledge graph
    for cluster_id, data in merged.items():
        cluster_db_id = kg.create_cluster(
            addresses=data['addresses'],
            name=None,  # Will be named when identified
            methods=data['methods'],
            confidence=data['confidence']
        )

        # Add evidence for each relationship
        for addr in data['addresses']:
            kg.add_evidence(
                addr,
                source='CIO',
                claim=f"Clustered via {', '.join(data['methods'])}",
                confidence=data['confidence'],
                raw_data={'cluster_size': data['size'], 'methods': data['methods']}
            )

    # Cross-chain correlation - SKIPPED for performance (adds 4x API calls)
    # To re-enable, uncomment below:
    # print("\n  Checking cross-chain presence...")
    # cross_chain = detect_cross_chain_presence(addresses[:50])
    # for addr, chains in cross_chain.items():
    #     active_chains = [c for c, active in chains.items() if active]
    #     if len(active_chains) > 1:
    #         kg.add_evidence(
    #             addr,
    #             source='CrossChain',
    #             claim=f"Active on {len(active_chains)} chains: {', '.join(active_chains)}",
    #             confidence=0.8,
    #             raw_data={'chains': active_chains}
    #         )

    # Look for expanded addresses (new addresses found through clustering)
    expanded = set()
    for data in merged.values():
        expanded.update(data['addresses'])

    original_set = set(a.lower() for a in addresses)
    potential_new = expanded - original_set

    # Filter out addresses already in knowledge graph to prevent re-queueing
    new_addresses = set()
    for addr in potential_new:
        existing = kg.get_entity(addr)
        if not existing:
            new_addresses.add(addr)

    if new_addresses:
        print(f"\n  Expansion: Found {len(new_addresses)} new related addresses")
        for addr in new_addresses:
            # Add to knowledge graph and queue for processing
            kg.add_entity(addr)
            for layer in ['onchain', 'behavioral', 'osint']:
                kg.queue_address(addr, layer, priority=-1)  # Lower priority

    print(f"\n  On-chain layer complete. {len(merged)} clusters, {len(new_addresses)} new addresses")


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cluster Expander - On-Chain Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input", nargs="?", help="Input CSV with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--methods", default="circular,common_funder,shared_deposits",
                        help="Detection methods (comma-separated)")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID (1=Ethereum)")
    parser.add_argument("--cross-chain", action="store_true", help="Check cross-chain presence")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.input:
        parser.error("Input CSV required")

    if not ETHERSCAN_API_KEY:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Load addresses
    with open(args.input) as f:
        reader = csv.DictReader(f)
        addresses = [row.get("address") or row.get("borrower") for row in reader]
        addresses = [a for a in addresses if a]

    print(f"Loaded {len(addresses)} addresses")

    # Run detection methods
    methods = args.methods.split(",")
    all_clusters = []

    if "circular" in methods:
        clusters = detect_circular_funding(addresses, args.chain_id)
        all_clusters.append(clusters)

    if "common_funder" in methods:
        clusters = detect_common_funder(addresses, args.chain_id)
        all_clusters.append(clusters)

    if "shared_deposits" in methods:
        clusters = detect_shared_deposits(addresses, args.chain_id)
        all_clusters.append(clusters)

    # Merge clusters
    merged = merge_all_clusters(all_clusters)

    # Cross-chain check
    if args.cross_chain:
        cross_chain = detect_cross_chain_presence(addresses)

    # Output
    if args.json:
        print(json.dumps(merged, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"RESULTS: Found {len(merged)} clusters")
        print(f"{'='*60}\n")

        for cluster_id, data in sorted(merged.items(), key=lambda x: -x[1]["size"]):
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

    # Save to CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["address", "cluster_id", "cluster_size", "methods", "confidence"])

            for cluster_id, data in merged.items():
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
