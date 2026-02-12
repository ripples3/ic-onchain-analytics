#!/usr/bin/env python3
"""
Temporal Correlation Engine

Detects wallets that act within seconds of each other, repeatedly.
This is one of the strongest signals for same-operator detection because:
1. It's nearly impossible to fake while maintaining operational efficiency
2. Even privacy-conscious operators slip into timing patterns
3. Coordinated actions (deposit A → borrow B) create unavoidable correlation

Signal Strength:
- 3+ correlations within 30s window = 70% confidence (possible coincidence)
- 5+ correlations within 30s window = 85% confidence (likely same operator)
- 10+ correlations within 30s window = 95% confidence (almost certain)
- Correlations within 10s window = +10% confidence boost

Based on Chainalysis and ZachXBT methodologies for operator fingerprinting.

Usage:
    # Analyze correlations for a set of addresses
    python3 temporal_correlation.py addresses.csv -o correlations.csv

    # Analyze specific address against a pool
    python3 temporal_correlation.py addresses.csv --target 0x1234...

    # Integration with knowledge graph
    from temporal_correlation import process_addresses
    process_addresses(knowledge_graph, addresses)
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
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

# Rate limiting
RATE_LIMIT = 5.0
last_request_time = 0

# Correlation thresholds
WINDOW_TIGHT = 10      # seconds - very strong signal
WINDOW_NORMAL = 30     # seconds - strong signal
WINDOW_LOOSE = 60      # seconds - moderate signal

# Confidence thresholds
MIN_CORRELATIONS = 3   # minimum to consider
HIGH_CONFIDENCE = 5    # high confidence threshold
VERY_HIGH_CONFIDENCE = 10  # very high confidence threshold


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


def get_all_activity(address: str, chain_id: int = 1, limit: int = 1000) -> List[dict]:
    """
    Get all activity (transactions + token transfers) for an address.
    Returns unified list with timestamps.
    """
    activities = []

    # Get normal transactions
    txs = etherscan_request({
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }, chain_id)

    for tx in txs:
        activities.append({
            'timestamp': int(tx.get('timeStamp', 0)),
            'hash': tx.get('hash'),
            'type': 'tx',
            'from': tx.get('from', '').lower(),
            'to': tx.get('to', '').lower(),
            'value': tx.get('value', '0'),
            'method': tx.get('functionName', '')[:50] if tx.get('functionName') else 'transfer'
        })

    # Get token transfers
    token_txs = etherscan_request({
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }, chain_id)

    for tx in token_txs:
        activities.append({
            'timestamp': int(tx.get('timeStamp', 0)),
            'hash': tx.get('hash'),
            'type': 'token',
            'from': tx.get('from', '').lower(),
            'to': tx.get('to', '').lower(),
            'value': tx.get('value', '0'),
            'token': tx.get('tokenSymbol', 'UNKNOWN')
        })

    # Sort by timestamp
    activities.sort(key=lambda x: x['timestamp'])

    return activities


# ============================================================================
# Time Bucketing for Efficient Comparison
# ============================================================================

def build_time_index(activities: List[dict], bucket_size: int = 60) -> Dict[int, List[dict]]:
    """
    Index activities by time bucket for efficient comparison.
    bucket_size in seconds.
    """
    index = defaultdict(list)
    for activity in activities:
        bucket = activity['timestamp'] // bucket_size
        index[bucket].append(activity)
    return index


def find_temporal_correlations_pair(
    addr1: str,
    activities1: List[dict],
    addr2: str,
    activities2: List[dict],
    window: int = WINDOW_NORMAL
) -> List[dict]:
    """
    Find temporally correlated activities between two addresses.

    Returns list of correlation events:
    {
        'timestamp1': int,
        'timestamp2': int,
        'delta': int (seconds),
        'activity1': dict,
        'activity2': dict
    }
    """
    if not activities1 or not activities2:
        return []

    correlations = []

    # Build time index for addr2 with bucket size = window
    index2 = build_time_index(activities2, bucket_size=window)

    for act1 in activities1:
        ts1 = act1['timestamp']
        bucket = ts1 // window

        # Check current bucket and adjacent buckets
        for b in [bucket - 1, bucket, bucket + 1]:
            for act2 in index2.get(b, []):
                ts2 = act2['timestamp']
                delta = abs(ts1 - ts2)

                if delta <= window and delta > 0:  # Exclude same transaction
                    # Skip if same transaction hash
                    if act1.get('hash') == act2.get('hash'):
                        continue

                    correlations.append({
                        'timestamp1': ts1,
                        'timestamp2': ts2,
                        'delta': delta,
                        'activity1': act1,
                        'activity2': act2,
                        'addr1': addr1,
                        'addr2': addr2
                    })

    return correlations


def deduplicate_correlations(correlations: List[dict]) -> List[dict]:
    """
    Remove duplicate correlations (same pair of transactions).
    Keep the one with smallest delta.
    """
    seen = {}  # (hash1, hash2) -> correlation

    for corr in correlations:
        h1 = corr['activity1'].get('hash', '')
        h2 = corr['activity2'].get('hash', '')
        key = tuple(sorted([h1, h2]))

        if key not in seen or corr['delta'] < seen[key]['delta']:
            seen[key] = corr

    return list(seen.values())


def calculate_correlation_confidence(correlations: List[dict]) -> float:
    """
    Calculate confidence score based on correlation patterns.

    Factors:
    - Number of correlations
    - Tightness of timing (smaller delta = higher confidence)
    - Consistency of pattern
    """
    if not correlations:
        return 0.0

    n = len(correlations)

    # Base confidence from count
    if n >= VERY_HIGH_CONFIDENCE:
        base_confidence = 0.90
    elif n >= HIGH_CONFIDENCE:
        base_confidence = 0.80
    elif n >= MIN_CORRELATIONS:
        base_confidence = 0.65
    else:
        return 0.0  # Below threshold

    # Boost for tight timing
    avg_delta = sum(c['delta'] for c in correlations) / n
    if avg_delta <= WINDOW_TIGHT:
        timing_boost = 0.10
    elif avg_delta <= WINDOW_NORMAL:
        timing_boost = 0.05
    else:
        timing_boost = 0.0

    # Boost for consistency (low variance in deltas)
    if n >= 3:
        deltas = [c['delta'] for c in correlations]
        mean_delta = sum(deltas) / n
        variance = sum((d - mean_delta) ** 2 for d in deltas) / n
        std_dev = variance ** 0.5

        # Low std dev = consistent pattern = higher confidence
        if mean_delta > 0:
            cv = std_dev / mean_delta  # coefficient of variation
            if cv < 0.3:  # Very consistent
                consistency_boost = 0.05
            elif cv < 0.6:
                consistency_boost = 0.02
            else:
                consistency_boost = 0.0
        else:
            consistency_boost = 0.0
    else:
        consistency_boost = 0.0

    return min(0.98, base_confidence + timing_boost + consistency_boost)


def analyze_correlation_pattern(correlations: List[dict]) -> dict:
    """
    Analyze the pattern of correlations to understand the relationship.
    """
    if not correlations:
        return {}

    # Determine who acts first
    addr1_first = sum(1 for c in correlations if c['timestamp1'] < c['timestamp2'])
    addr2_first = len(correlations) - addr1_first

    # Analyze activity types
    types1 = defaultdict(int)
    types2 = defaultdict(int)
    for c in correlations:
        types1[c['activity1'].get('type', 'unknown')] += 1
        types2[c['activity2'].get('type', 'unknown')] += 1

    # Analyze methods (for tx type)
    methods1 = defaultdict(int)
    methods2 = defaultdict(int)
    for c in correlations:
        if c['activity1'].get('method'):
            methods1[c['activity1']['method'][:30]] += 1
        if c['activity2'].get('method'):
            methods2[c['activity2']['method'][:30]] += 1

    # Calculate timing statistics
    deltas = [c['delta'] for c in correlations]
    avg_delta = sum(deltas) / len(deltas)
    min_delta = min(deltas)
    max_delta = max(deltas)

    return {
        'correlation_count': len(correlations),
        'addr1_acts_first': addr1_first,
        'addr2_acts_first': addr2_first,
        'timing': {
            'avg_delta_seconds': round(avg_delta, 1),
            'min_delta_seconds': min_delta,
            'max_delta_seconds': max_delta
        },
        'activity_types': {
            'addr1': dict(types1),
            'addr2': dict(types2)
        },
        'top_methods': {
            'addr1': dict(sorted(methods1.items(), key=lambda x: -x[1])[:3]),
            'addr2': dict(sorted(methods2.items(), key=lambda x: -x[1])[:3])
        },
        'pattern_description': describe_pattern(correlations, addr1_first, addr2_first)
    }


def describe_pattern(correlations: List[dict], addr1_first: int, addr2_first: int) -> str:
    """Generate human-readable description of the correlation pattern."""
    n = len(correlations)

    if addr1_first > addr2_first * 2:
        leader = "addr1 leads"
    elif addr2_first > addr1_first * 2:
        leader = "addr2 leads"
    else:
        leader = "bidirectional"

    avg_delta = sum(c['delta'] for c in correlations) / n

    if avg_delta <= 10:
        timing = "near-simultaneous"
    elif avg_delta <= 30:
        timing = "rapid succession"
    else:
        timing = "close timing"

    return f"{n} correlations, {leader}, {timing} (avg {avg_delta:.0f}s)"


# ============================================================================
# Batch Processing
# ============================================================================

def find_all_correlations(
    addresses: List[str],
    chain_id: int = 1,
    window: int = WINDOW_NORMAL,
    min_correlations: int = MIN_CORRELATIONS,
    progress_callback=None
) -> Dict[Tuple[str, str], dict]:
    """
    Find temporal correlations across all address pairs.

    Uses caching and time-bucketing for efficiency.

    Returns:
        {(addr1, addr2): {
            'correlations': [...],
            'confidence': float,
            'pattern': {...}
        }}
    """
    print(f"  Fetching activity for {len(addresses)} addresses...")

    # Fetch all activity (with caching)
    activity_cache: Dict[str, List[dict]] = {}

    for i, addr in enumerate(addresses):
        if progress_callback:
            progress_callback(i, len(addresses), "Fetching")
        elif (i + 1) % 20 == 0:
            print(f"    Fetched {i + 1}/{len(addresses)}...")

        activity_cache[addr.lower()] = get_all_activity(addr.lower(), chain_id)

    print(f"  Comparing {len(addresses) * (len(addresses) - 1) // 2} address pairs...")

    # Compare all pairs
    results = {}
    pair_count = 0
    total_pairs = len(addresses) * (len(addresses) - 1) // 2

    for i, addr1 in enumerate(addresses):
        for addr2 in addresses[i + 1:]:
            pair_count += 1

            if pair_count % 500 == 0:
                print(f"    Compared {pair_count}/{total_pairs} pairs...")

            addr1_lower = addr1.lower()
            addr2_lower = addr2.lower()

            correlations = find_temporal_correlations_pair(
                addr1_lower,
                activity_cache.get(addr1_lower, []),
                addr2_lower,
                activity_cache.get(addr2_lower, []),
                window
            )

            # Deduplicate
            correlations = deduplicate_correlations(correlations)

            if len(correlations) >= min_correlations:
                confidence = calculate_correlation_confidence(correlations)
                pattern = analyze_correlation_pattern(correlations)

                results[(addr1_lower, addr2_lower)] = {
                    'correlations': correlations,
                    'confidence': confidence,
                    'pattern': pattern
                }

    return results


def find_correlations_for_target(
    target: str,
    pool: List[str],
    chain_id: int = 1,
    window: int = WINDOW_NORMAL,
    min_correlations: int = MIN_CORRELATIONS
) -> Dict[str, dict]:
    """
    Find temporal correlations between a target address and a pool of addresses.
    More efficient than all-pairs when investigating a specific address.
    """
    target = target.lower()
    print(f"  Fetching activity for target {target[:10]}...")
    target_activity = get_all_activity(target, chain_id)

    if not target_activity:
        print(f"  No activity found for target")
        return {}

    print(f"  Comparing against {len(pool)} addresses...")

    results = {}

    for i, addr in enumerate(pool):
        if (i + 1) % 50 == 0:
            print(f"    Compared {i + 1}/{len(pool)}...")

        addr_lower = addr.lower()
        if addr_lower == target:
            continue

        addr_activity = get_all_activity(addr_lower, chain_id)

        correlations = find_temporal_correlations_pair(
            target,
            target_activity,
            addr_lower,
            addr_activity,
            window
        )

        correlations = deduplicate_correlations(correlations)

        if len(correlations) >= min_correlations:
            confidence = calculate_correlation_confidence(correlations)
            pattern = analyze_correlation_pattern(correlations)

            results[addr_lower] = {
                'correlations': correlations,
                'confidence': confidence,
                'pattern': pattern
            }

    return results


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_single_address(kg: 'KnowledgeGraph', addr: str):
    """
    Process temporal correlations for a single address against known entities.
    Called by build_knowledge_graph.py for per-address processing.
    """
    if not ETHERSCAN_API_KEY:
        raise ValueError("ETHERSCAN_API_KEY not set")

    # Get all addresses in knowledge graph
    conn = kg.connect()
    all_entities = conn.execute("SELECT address FROM entities LIMIT 500").fetchall()
    pool = [e[0] for e in all_entities if e[0].lower() != addr.lower()]

    if len(pool) < 2:
        return {'address': addr, 'correlations_found': 0}

    # Find correlations
    results = find_correlations_for_target(
        addr,
        pool[:100],  # Limit pool size for per-address processing
        min_correlations=MIN_CORRELATIONS
    )

    # Store results
    for other_addr, data in results.items():
        kg.add_relationship(
            addr,
            other_addr,
            'temporal_correlation',
            confidence=data['confidence'],
            evidence={
                'method': 'temporal_correlation',
                'correlation_count': data['pattern']['correlation_count'],
                'avg_delta': data['pattern']['timing']['avg_delta_seconds'],
                'description': data['pattern']['pattern_description']
            }
        )

        kg.add_evidence(
            addr,
            source='Temporal',
            claim=f"Correlated with {other_addr[:10]}...: {data['pattern']['pattern_description']}",
            confidence=data['confidence'],
            raw_data={
                'other_address': other_addr,
                'pattern': data['pattern']
            }
        )

    return {
        'address': addr,
        'correlations_found': len(results)
    }


def process_addresses(kg: 'KnowledgeGraph', addresses: List[str], window: int = WINDOW_NORMAL):
    """
    Process temporal correlations for a batch of addresses.
    Integrates with knowledge graph for storage.
    """
    print(f"\n  Running temporal correlation analysis on {len(addresses)} addresses...")

    if not ETHERSCAN_API_KEY:
        print("  Warning: ETHERSCAN_API_KEY not set", file=sys.stderr)
        return

    # Find all correlations
    results = find_all_correlations(
        addresses,
        window=window,
        min_correlations=MIN_CORRELATIONS
    )

    print(f"\n  Found {len(results)} correlated address pairs")

    # Store in knowledge graph
    high_confidence_count = 0

    for (addr1, addr2), data in results.items():
        confidence = data['confidence']
        pattern = data['pattern']

        # Add relationship
        kg.add_relationship(
            addr1,
            addr2,
            'temporal_correlation',
            confidence=confidence,
            evidence={
                'method': 'temporal_correlation',
                'correlation_count': pattern['correlation_count'],
                'avg_delta': pattern['timing']['avg_delta_seconds'],
                'description': pattern['pattern_description']
            }
        )

        # Add evidence to both addresses
        for addr in [addr1, addr2]:
            other = addr2 if addr == addr1 else addr1
            kg.add_evidence(
                addr,
                source='Temporal',
                claim=f"Correlated with {other[:10]}...: {pattern['pattern_description']}",
                confidence=confidence,
                raw_data={
                    'other_address': other,
                    'pattern': pattern
                }
            )

        if confidence >= 0.85:
            high_confidence_count += 1
            print(f"    HIGH: {addr1[:10]}... ↔ {addr2[:10]}... ({confidence:.0%}) - {pattern['pattern_description']}")

    # Create clusters from high-confidence correlations
    if high_confidence_count > 0:
        print(f"\n  Creating clusters from {high_confidence_count} high-confidence correlations...")

        # Build graph of high-confidence correlations
        from collections import defaultdict
        graph = defaultdict(set)

        for (addr1, addr2), data in results.items():
            if data['confidence'] >= 0.85:
                graph[addr1].add(addr2)
                graph[addr2].add(addr1)

        # Find connected components
        visited = set()
        clusters = []

        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)

        for addr in graph:
            if addr not in visited:
                component = set()
                dfs(addr, component)
                if len(component) >= 2:
                    clusters.append(component)

        # Create clusters in knowledge graph
        for i, members in enumerate(clusters):
            cluster_id = kg.create_cluster(
                addresses=list(members),
                name=f"Temporal Cluster {i + 1}",
                methods=['temporal_correlation'],
                confidence=0.85
            )
            print(f"    Created cluster {cluster_id} with {len(members)} members")

    print(f"\n  Temporal correlation analysis complete")
    print(f"    Total correlated pairs: {len(results)}")
    print(f"    High confidence (>=85%): {high_confidence_count}")


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Temporal Correlation Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze all addresses in a CSV
    python3 temporal_correlation.py addresses.csv -o correlations.csv

    # Analyze a specific target against a pool
    python3 temporal_correlation.py addresses.csv --target 0x1234...

    # Use tighter timing window (10s instead of 30s)
    python3 temporal_correlation.py addresses.csv --window 10
        """
    )

    parser.add_argument("input", nargs="?", help="Input CSV with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--target", help="Analyze specific address against pool")
    parser.add_argument("--window", type=int, default=WINDOW_NORMAL,
                        help=f"Correlation window in seconds (default: {WINDOW_NORMAL})")
    parser.add_argument("--min-correlations", type=int, default=MIN_CORRELATIONS,
                        help=f"Minimum correlations to report (default: {MIN_CORRELATIONS})")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID (default: 1 = Ethereum)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--kg", action="store_true", help="Store results in knowledge graph")

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
    print(f"Correlation window: {args.window}s")
    print(f"Minimum correlations: {args.min_correlations}")

    # Run analysis
    if args.target:
        print(f"\nAnalyzing target: {args.target}")
        results = find_correlations_for_target(
            args.target,
            addresses,
            chain_id=args.chain_id,
            window=args.window,
            min_correlations=args.min_correlations
        )

        # Convert to pair format for consistent output
        results = {(args.target.lower(), addr): data for addr, data in results.items()}
    else:
        print(f"\nAnalyzing all pairs...")
        results = find_all_correlations(
            addresses,
            chain_id=args.chain_id,
            window=args.window,
            min_correlations=args.min_correlations
        )

    # Store in knowledge graph if requested
    if args.kg:
        from build_knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.connect()

        for (addr1, addr2), data in results.items():
            kg.add_relationship(
                addr1, addr2, 'temporal_correlation',
                confidence=data['confidence'],
                evidence={
                    'method': 'temporal_correlation',
                    'pattern': data['pattern']
                }
            )

        kg.close()
        print(f"\nStored {len(results)} correlations in knowledge graph")

    # Output
    if args.json:
        # Convert for JSON serialization
        json_results = {}
        for (addr1, addr2), data in results.items():
            key = f"{addr1}|{addr2}"
            json_results[key] = {
                'addr1': addr1,
                'addr2': addr2,
                'confidence': data['confidence'],
                'pattern': data['pattern'],
                'sample_correlations': data['correlations'][:5]  # First 5 only
            }
        print(json.dumps(json_results, indent=2, default=str))
    else:
        # Print summary
        print(f"\n{'='*80}")
        print(f"TEMPORAL CORRELATION RESULTS")
        print(f"{'='*80}")
        print(f"\nFound {len(results)} correlated address pairs\n")

        # Sort by confidence
        sorted_results = sorted(results.items(), key=lambda x: -x[1]['confidence'])

        for (addr1, addr2), data in sorted_results[:20]:  # Top 20
            conf = data['confidence']
            pattern = data['pattern']

            conf_label = "🔴 HIGH" if conf >= 0.85 else "🟡 MEDIUM" if conf >= 0.70 else "🟢 LOW"

            print(f"{conf_label} [{conf:.0%}] {addr1[:16]}... ↔ {addr2[:16]}...")
            print(f"    {pattern['pattern_description']}")
            print(f"    Timing: avg {pattern['timing']['avg_delta_seconds']:.1f}s, "
                  f"range {pattern['timing']['min_delta_seconds']}-{pattern['timing']['max_delta_seconds']}s")
            print()

        if len(results) > 20:
            print(f"... and {len(results) - 20} more pairs")

    # Save to CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "addr1", "addr2", "confidence", "correlation_count",
                "avg_delta_seconds", "min_delta_seconds", "max_delta_seconds",
                "pattern_description"
            ])

            for (addr1, addr2), data in sorted_results:
                pattern = data['pattern']
                writer.writerow([
                    addr1,
                    addr2,
                    f"{data['confidence']:.3f}",
                    pattern['correlation_count'],
                    pattern['timing']['avg_delta_seconds'],
                    pattern['timing']['min_delta_seconds'],
                    pattern['timing']['max_delta_seconds'],
                    pattern['pattern_description']
                ])

        print(f"\nSaved to {args.output}")

    # Summary statistics
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    high_conf = sum(1 for _, d in results.items() if d['confidence'] >= 0.85)
    medium_conf = sum(1 for _, d in results.items() if 0.70 <= d['confidence'] < 0.85)
    low_conf = len(results) - high_conf - medium_conf

    print(f"\nConfidence Distribution:")
    print(f"  High (>=85%):    {high_conf}")
    print(f"  Medium (70-84%): {medium_conf}")
    print(f"  Low (<70%):      {low_conf}")

    if results:
        all_deltas = []
        for data in results.values():
            all_deltas.append(data['pattern']['timing']['avg_delta_seconds'])

        print(f"\nTiming Statistics:")
        print(f"  Avg delta across pairs: {sum(all_deltas)/len(all_deltas):.1f}s")
        print(f"  Tightest correlation:   {min(all_deltas):.1f}s avg")

    # Identify addresses appearing in multiple correlations
    addr_counts = defaultdict(int)
    for (addr1, addr2), data in results.items():
        if data['confidence'] >= 0.70:
            addr_counts[addr1] += 1
            addr_counts[addr2] += 1

    if addr_counts:
        print(f"\nMost Connected Addresses (>=70% confidence):")
        for addr, count in sorted(addr_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"  {addr[:20]}... - {count} correlations")


if __name__ == "__main__":
    main()
