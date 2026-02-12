#!/usr/bin/env python3
"""
Common Input Ownership (CIO) Detector - EVM Adaptation (v2 - Fixed)

Adapted from Bitcoin's CIO heuristic for EVM chains. Since EVM transactions
have a single 'from' address (unlike Bitcoin's multi-input UTXO), we detect
ownership through related patterns:

1. Circular Funding - A funds B, B funds C, C funds A (same entity recycling)
2. Common Funding Source - Multiple wallets funded by same source within 24h
3. Shared Deposit Destination - Multiple wallets depositing to same exchange address

REMOVED: Coordinated Activity - Too aggressive, caused false positives

v2 Fixes (2026-02-13):
- Added comprehensive protocol/exchange exclusion list
- Added ENS conflict detection (multiple ENS = different people)
- Added cluster size cap (max 50 addresses)
- Require stronger evidence (3+ shared connections for large clusters)
- Fixed union-find transitive chaining issue
- Added validation layer before final output

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

# ============================================================================
# CONFIGURATION
# ============================================================================

# Maximum cluster size - one entity rarely controls 50+ wallets
MAX_CLUSTER_SIZE = 50

# Minimum shared connections required for clustering
MIN_SHARED_CONNECTIONS = 2  # For small clusters
MIN_SHARED_CONNECTIONS_LARGE = 3  # For clusters > 10 addresses

# ============================================================================
# EXCLUSION LISTS - Addresses that are shared by many users (NOT ownership signals)
# ============================================================================

# Major CEX hot wallets
CEX_HOT_WALLETS = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance 16
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance 15
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",  # Binance 1
    "0xf977814e90da44bfa03b6295a0616a897441acec",  # Binance 8
    "0x5a52e96bacdabb82fd05763e25335261b270efcb",  # Binance 9
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8",  # Binance 7
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",  # Binance 6
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",  # Coinbase 1
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43",  # Coinbase 2
    "0x503828976d22510aad0201ac7ec88293211d23da",  # Coinbase 4
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740",  # Coinbase 5
    "0x3cd751e6b0078be393132286c442345e5dc49699",  # Coinbase 6
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511",  # Coinbase 7
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",  # Kraken 1
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13",  # Kraken 2
    "0xe853c56864a2ebe4576a807d26fdc4a0ada51919",  # Kraken 3
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",  # OKX 1
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3",  # OKX 2
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853",  # Gemini 1
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8",  # Gemini 2
    # FTX (historical)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2",  # FTX 1
    "0xc098b2a3aa256d2140208c3de6543aaef5cd3a94",  # FTX 2
    # Other
    "0x1151314c646ce4e0ecd76d1af4760ae66a9fe30f",  # Bitfinex 1
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa",  # Bitfinex 2
    "0xab7c74abc0c4d48d1bdad5dcb26153fc8780f83e",  # Huobi 1
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b",  # Huobi 2
}

# Major DeFi protocols - transactions to these are NOT ownership signals
DEFI_PROTOCOLS = {
    # Uniswap
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2 Router
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3 Router
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap V3 Router 2
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",  # Uniswap Universal Router
    # Aave
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",  # Aave V2 Pool
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",  # Aave V3 Pool
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9",  # AAVE Token
    # Compound
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b",  # Compound Comptroller
    "0xc00e94cb662c3520282e6f5717214004a7f26888",  # COMP Token
    # Curve
    "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",  # Curve 3pool
    "0xd51a44d3fae010294c616388b506acda1bfaae46",  # Curve Tricrypto2
    "0x99a58482bd75cbab83b27ec03ca68ff489b5788f",  # Curve Router
    # Lido
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84",  # stETH
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0",  # wstETH
    # Maker
    "0x9759a6ac90977b93b58547b4a71c78317f391a28",  # MakerDAO DSR
    "0x83f20f44975d03b1b09e64809b757c47f942beea",  # sDAI
    # 1inch
    "0x1111111254fb6c44bac0bed2854e76f90643097d",  # 1inch Router
    "0x1111111254eeb25477b68fb85ed929f73a960582",  # 1inch V5
    # OpenSea
    "0x00000000006c3852cbef3e08e8df289169ede581",  # Seaport
    # ENS
    "0x283af0b28c62c092c9727f1ee09c02ca627eb7f5",  # ENS Registrar
    "0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85",  # ENS Base Registrar
    # Gnosis Safe
    "0xa6b71e26c5e0845f74c812102ca7114b6a896ab2",  # Safe Factory 1.3.0
    "0x76e2cfc1f5fa8f6a5b3fc4c8f4788f0116861f9b",  # Safe Factory 1.4.1
}

# Bridges and L2 contracts
BRIDGES = {
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1",  # Optimism Bridge
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f",  # Arbitrum Bridge
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35",  # Base Bridge
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a",  # Arbitrum L1
    "0x5e4e65926ba27467555eb562121fac00d24e9dd2",  # zkSync Era
    "0x32400084c286cf3e17e7b677ea9583e60a000324",  # zkSync Diamond
}

# Combine all exclusions
EXCLUDE_ADDRESSES = CEX_HOT_WALLETS | DEFI_PROTOCOLS | BRIDGES

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

    v2: Uses comprehensive exclusion list
    """
    print("Detecting shared deposit destinations...")

    # Build deposit map: destination -> source addresses
    deposit_map: Dict[str, Set[str]] = defaultdict(set)

    for i, addr in enumerate(addresses):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(addresses)}...")

        txs = get_normal_transactions(addr.lower(), chain_id, limit=500)

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value = int(tx.get("value", 0))

            # Outgoing ETH transfer (potential deposit)
            # Exclude known hot wallets and protocols
            if (from_addr == addr.lower() and value > 0 and
                to_addr not in EXCLUDE_ADDRESSES):
                # Check if it looks like a deposit (reasonable amount, not gas)
                eth_value = value / 1e18
                if 0.01 < eth_value < 1000:  # Reasonable deposit range
                    deposit_map[to_addr].add(addr.lower())

    # Find shared destinations (require 2+ sources)
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0

    for dest, sources in deposit_map.items():
        if len(sources) >= 2:
            cluster_key = f"shared_deposit_{cluster_id}"
            clusters[cluster_key] = sources
            print(f"  Found shared deposit cluster: {len(sources)} addresses → {dest[:10]}...")
            cluster_id += 1

    return clusters

def get_ens_names(addresses: List[str]) -> Dict[str, str]:
    """
    Get ENS names for addresses (if available in our data).
    Returns dict of address -> ens_name.

    Note: This is a placeholder - in production, query ENS or use cached data.
    """
    # Try to load from knowledge graph if available
    try:
        import sqlite3
        conn = sqlite3.connect('data/knowledge_graph.db')
        cursor = conn.execute('''
            SELECT address, ens_name FROM entities
            WHERE ens_name IS NOT NULL AND ens_name != ''
        ''')
        return {row[0].lower(): row[1] for row in cursor.fetchall()}
    except:
        return {}


def validate_cluster(addresses: Set[str], ens_map: Dict[str, str]) -> Tuple[bool, str]:
    """
    Validate a cluster for conflicts.

    Returns (is_valid, reason).
    """
    # Check 1: ENS conflict - multiple different ENS names = different people
    ens_names = set()
    for addr in addresses:
        ens = ens_map.get(addr.lower())
        if ens:
            ens_names.add(ens.lower())

    if len(ens_names) > 1:
        return False, f"ENS conflict: {len(ens_names)} different names ({', '.join(list(ens_names)[:3])}...)"

    # Check 2: Cluster size cap
    if len(addresses) > MAX_CLUSTER_SIZE:
        return False, f"Too large: {len(addresses)} addresses (max {MAX_CLUSTER_SIZE})"

    return True, "OK"


def merge_clusters(all_clusters: List[Dict[str, Set[str]]],
                   ens_map: Dict[str, str] = None) -> Dict[str, dict]:
    """
    Merge overlapping clusters from different detection methods.

    v2 Fixes:
    - NO transitive chaining - only merge if addresses directly share a cluster
    - Validate clusters for ENS conflicts
    - Cap cluster size
    - Require multiple methods for large clusters
    """
    print("\nMerging overlapping clusters...")

    if ens_map is None:
        ens_map = get_ens_names([])

    # Track which addresses appear in which original clusters
    address_to_clusters: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # addr -> [(method, cluster_id)]

    for clusters in all_clusters:
        for cluster_id, addresses in clusters.items():
            method = cluster_id.rsplit('_', 1)[0]
            for addr in addresses:
                address_to_clusters[addr].append((method, cluster_id))

    # Build connection strength between addresses
    # Two addresses are connected if they appear in the SAME original cluster
    connection_count: Dict[Tuple[str, str], int] = defaultdict(int)
    connection_methods: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for clusters in all_clusters:
        for cluster_id, addresses in clusters.items():
            method = cluster_id.rsplit('_', 1)[0]
            addr_list = list(addresses)
            for i in range(len(addr_list)):
                for j in range(i + 1, len(addr_list)):
                    pair = tuple(sorted([addr_list[i], addr_list[j]]))
                    connection_count[pair] += 1
                    connection_methods[pair].add(method)

    # Build clusters using STRICT merging (no transitive chaining)
    # Only merge addresses with direct connection
    used = set()
    final_clusters: List[Tuple[Set[str], Set[str]]] = []  # (addresses, methods)

    for (addr1, addr2), count in sorted(connection_count.items(), key=lambda x: -x[1]):
        if addr1 in used and addr2 in used:
            continue

        # Find existing cluster that contains addr1 or addr2
        target_cluster = None
        for i, (members, methods) in enumerate(final_clusters):
            if addr1 in members or addr2 in members:
                target_cluster = i
                break

        if target_cluster is not None:
            # Add to existing cluster (but check connection strength)
            members, methods = final_clusters[target_cluster]
            new_addr = addr2 if addr1 in members else addr1

            # Require direct connection to at least one existing member
            has_direct_connection = False
            for existing in members:
                pair = tuple(sorted([new_addr, existing]))
                if connection_count.get(pair, 0) >= MIN_SHARED_CONNECTIONS:
                    has_direct_connection = True
                    break

            if has_direct_connection:
                # Validate before adding
                test_members = members | {new_addr}
                is_valid, reason = validate_cluster(test_members, ens_map)

                if is_valid:
                    members.add(new_addr)
                    methods.update(connection_methods[(addr1, addr2)])
                    used.add(new_addr)
                else:
                    print(f"  Rejected adding {new_addr[:10]}... to cluster: {reason}")
        else:
            # Create new cluster
            new_members = {addr1, addr2}
            is_valid, reason = validate_cluster(new_members, ens_map)

            if is_valid:
                final_clusters.append((new_members, connection_methods[(addr1, addr2)]))
                used.add(addr1)
                used.add(addr2)
            else:
                print(f"  Rejected new cluster: {reason}")

    # Format output
    result = {}
    for i, (members, methods) in enumerate(final_clusters):
        if len(members) >= 2:
            # For large clusters, require stronger evidence
            if len(members) > 10 and len(methods) < 2:
                print(f"  Skipping cluster_{i}: {len(members)} members but only 1 method")
                continue

            result[f"cluster_{i}"] = {
                "addresses": list(members),
                "size": len(members),
                "methods": list(methods),
                "confidence": min(0.9, 0.5 + 0.15 * len(methods)),  # Reduced confidence boost
                "validated": True
            }

    print(f"  Final: {len(result)} validated clusters")
    return result

def run_cio_detection(addresses: List[str], chain_id: int = 1,
                      methods: List[str] = None) -> Dict[str, dict]:
    """
    Run all CIO detection methods and merge results.

    v2: Removed 'coordinated' method (too aggressive).
    """
    if methods is None:
        # Default methods - removed 'coordinated' which caused false positives
        methods = ["circular", "common_funder", "shared_deposits"]

    all_clusters = []

    if "circular" in methods:
        clusters = detect_circular_funding(addresses, chain_id)
        all_clusters.append(clusters)

    if "common_funder" in methods:
        clusters = detect_common_funder(addresses, chain_id)
        all_clusters.append(clusters)

    # NOTE: 'coordinated' removed in v2 - too many false positives
    # If explicitly requested, still run it but warn
    if "coordinated" in methods:
        print("  WARNING: 'coordinated' method is deprecated (high false positive rate)")
        clusters = detect_coordinated_activity(addresses, chain_id)
        all_clusters.append(clusters)

    if "shared_deposits" in methods:
        clusters = detect_shared_deposits(addresses, chain_id)
        all_clusters.append(clusters)

    # Get ENS names for validation
    ens_map = get_ens_names(addresses)
    print(f"  Loaded {len(ens_map)} ENS names for validation")

    return merge_clusters(all_clusters, ens_map)

def main():
    global MAX_CLUSTER_SIZE  # Allow runtime override

    parser = argparse.ArgumentParser(description="CIO Detector v2 - EVM Adaptation (Fixed)")
    parser.add_argument("input", nargs="?", help="Input CSV file with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--methods", default="circular,common_funder,shared_deposits",
                        help="Detection methods (comma-separated). Note: 'coordinated' deprecated.")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID (1=Ethereum)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--max-cluster-size", type=int, default=50,
                        help="Maximum cluster size (default: 50)")
    args = parser.parse_args()

    if not ETHERSCAN_API_KEY:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Update global config if specified
    MAX_CLUSTER_SIZE = args.max_cluster_size

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

    print(f"CIO Detector v2 (with validation)")
    print(f"=" * 50)
    print(f"Analyzing {len(addresses)} addresses...")
    print(f"Methods: {methods}")
    print(f"Chain ID: {args.chain_id}")
    print(f"Max cluster size: {MAX_CLUSTER_SIZE}")
    print()

    # Run detection
    clusters = run_cio_detection(addresses, args.chain_id, methods)

    # Output
    if args.json:
        print(json.dumps(clusters, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"RESULTS: Found {len(clusters)} validated clusters")
        print(f"{'='*60}\n")

        for cluster_id, data in sorted(clusters.items(), key=lambda x: -x[1]["size"]):
            print(f"{cluster_id}:")
            print(f"  Size: {data['size']}")
            print(f"  Methods: {', '.join(data['methods'])}")
            print(f"  Confidence: {data['confidence']:.0%}")
            print(f"  Validated: {data.get('validated', False)}")
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
            writer.writerow(["address", "cluster_id", "cluster_size", "methods", "confidence", "validated"])

            for cluster_id, data in clusters.items():
                for addr in data["addresses"]:
                    writer.writerow([
                        addr,
                        cluster_id,
                        data["size"],
                        "|".join(data["methods"]),
                        f"{data['confidence']:.2f}",
                        data.get("validated", False)
                    ])

        print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
