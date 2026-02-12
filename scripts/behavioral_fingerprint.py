#!/usr/bin/env python3
"""
Behavioral Fingerprinting - Layer 2

Analyzes behavioral patterns to cluster and identify entities:
1. Timing Analysis - Activity patterns reveal timezone and habits
2. Gas Price Patterns - Gas strategy reveals wallet software/operator
3. DEX Trading Patterns - Trading style reveals entity type
4. Protocol Interaction Patterns - How they use DeFi protocols

Entities with similar behavioral fingerprints are likely related.

Usage:
    # Standalone mode
    python3 behavioral_fingerprint.py addresses.csv -o fingerprints.csv

    # With knowledge graph integration
    from behavioral_fingerprint import process_addresses
    process_addresses(knowledge_graph, addresses)
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
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
        "sort": "desc"  # Most recent first
    }
    return etherscan_request(params, chain_id)


# Known DEX routers
DEX_ROUTERS = {
    # Uniswap
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 SwapRouter",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    # 1inch
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch V5 Router",
    "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch V4 Router",
    # Cowswap
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Protocol",
    # Paraswap
    "0xdef171fe48cf0115b1d80b88dc8eab59176fee57": "Paraswap V5",
    # 0x
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange",
}

# Lending protocols
LENDING_PROTOCOLS = {
    # Aave V3
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3 Pool",
    # Spark
    "0xc13e21b648a5ee794902342038ff3adab66be987": "Spark Pool",
    # Compound V3
    "0xc3d688b66703497daa19211eedff47f25384cdc3": "Compound V3 USDC",
    "0xa17581a9e3356d9a858b789d68b4d866e593ae94": "Compound V3 WETH",
    # Morpho
    "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho Blue",
}


# ============================================================================
# Timing Analysis
# ============================================================================

def analyze_timing_patterns(txs: List[dict]) -> dict:
    """
    Analyze transaction timing to infer timezone and activity patterns.

    Returns:
        {
            'timezone_signal': 'UTC+8',
            'active_hours': [9, 10, 11, ...],
            'day_distribution': {'Monday': 0.15, ...},
            'activity_pattern': 'business_hours' | 'always_on' | 'irregular'
        }
    """
    if not txs:
        return {}

    # Convert timestamps to hours and days
    hour_counts = Counter()
    day_counts = Counter()
    timestamps = []

    for tx in txs:
        ts = int(tx.get('timeStamp', 0))
        if ts == 0:
            continue

        timestamps.append(ts)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        hour_counts[dt.hour] += 1
        day_counts[dt.strftime('%A')] += 1

    if not timestamps:
        return {}

    total_txs = len(timestamps)

    # Find peak hours
    sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])
    peak_hours = [h for h, c in sorted_hours[:6]]  # Top 6 hours

    # Infer timezone from peak activity
    # Assume peak activity is during business hours (9-17 local time)
    avg_peak_hour = sum(peak_hours) / len(peak_hours)
    assumed_work_midday = 13  # 1 PM local time is typical peak
    timezone_offset = int(round(assumed_work_midday - avg_peak_hour))
    if timezone_offset < -12:
        timezone_offset += 24
    if timezone_offset > 12:
        timezone_offset -= 24

    timezone_signal = f"UTC{'+' if timezone_offset >= 0 else ''}{timezone_offset}"

    # Determine activity pattern
    # Business hours: activity concentrated in 8-hour window
    hour_distribution = {h: c / total_txs for h, c in hour_counts.items()}
    top_8_hours = sum(c for h, c in sorted_hours[:8])
    concentration = top_8_hours / total_txs

    if concentration > 0.7:
        activity_pattern = 'business_hours'
    elif concentration < 0.4:
        activity_pattern = 'always_on'  # 24/7, likely bot or team
    else:
        activity_pattern = 'irregular'

    # Check for dormancy patterns (weekends off = human)
    weekend_pct = (day_counts.get('Saturday', 0) + day_counts.get('Sunday', 0)) / total_txs
    if weekend_pct < 0.1:
        activity_pattern += '_weekday_only'

    return {
        'timezone_signal': timezone_signal,
        'active_hours': sorted(peak_hours),
        'hour_distribution': hour_distribution,
        'day_distribution': {d: c / total_txs for d, c in day_counts.items()},
        'activity_pattern': activity_pattern,
        'weekend_activity_pct': weekend_pct
    }


# ============================================================================
# Gas Strategy Analysis
# ============================================================================

def analyze_gas_patterns(txs: List[dict]) -> dict:
    """
    Analyze gas price patterns to infer wallet software and operator behavior.

    Returns:
        {
            'gas_strategy': 'low' | 'medium' | 'high' | 'adaptive',
            'avg_gas_price_gwei': float,
            'gas_consistency': float,  # 0-1, higher = more consistent
            'uses_eip1559': bool
        }
    """
    if not txs:
        return {}

    gas_prices = []
    max_fees = []
    priority_fees = []

    for tx in txs:
        gas_price = int(tx.get('gasPrice', 0))
        if gas_price > 0:
            gas_prices.append(gas_price / 1e9)  # Convert to Gwei

        # Check for EIP-1559 transactions
        max_fee = tx.get('maxFeePerGas')
        priority_fee = tx.get('maxPriorityFeePerGas')
        if max_fee:
            max_fees.append(int(max_fee) / 1e9)
        if priority_fee:
            priority_fees.append(int(priority_fee) / 1e9)

    if not gas_prices:
        return {}

    avg_gas = sum(gas_prices) / len(gas_prices)

    # Calculate consistency (low std dev = consistent strategy)
    if len(gas_prices) > 1:
        variance = sum((g - avg_gas) ** 2 for g in gas_prices) / len(gas_prices)
        std_dev = variance ** 0.5
        # Cap the ratio to prevent instability with very small avg_gas
        # Minimum avg_gas of 1 Gwei and max ratio of 2.0
        if avg_gas >= 1:
            ratio = min(std_dev / avg_gas, 2.0)
            consistency = max(0, 1 - ratio)
        else:
            consistency = 0.5  # Unknown consistency for near-zero gas
    else:
        consistency = 1.0

    # Determine strategy based on average gas price
    # These thresholds assume normal mainnet conditions
    if avg_gas < 15:
        strategy = 'low'
    elif avg_gas < 50:
        strategy = 'medium'
    elif avg_gas < 150:
        strategy = 'high'
    else:
        strategy = 'very_high'

    # Check if they adapt to conditions (high variance = adaptive)
    if consistency < 0.5:
        strategy = 'adaptive'

    uses_eip1559 = len(max_fees) > len(gas_prices) * 0.5

    return {
        'gas_strategy': strategy,
        'avg_gas_price_gwei': round(avg_gas, 2),
        'gas_consistency': round(consistency, 2),
        'uses_eip1559': uses_eip1559,
        'max_fee_avg': round(sum(max_fees) / len(max_fees), 2) if max_fees else None,
        'priority_fee_avg': round(sum(priority_fees) / len(priority_fees), 2) if priority_fees else None
    }


# ============================================================================
# DEX Trading Pattern Analysis
# ============================================================================

def analyze_trading_patterns(txs: List[dict]) -> dict:
    """
    Analyze DEX trading patterns to infer entity type.

    Returns:
        {
            'trading_style': 'spot' | 'leverage' | 'arbitrage' | 'mev' | 'none',
            'preferred_dex': str,
            'trade_count': int,
            'uses_aggregators': bool
        }
    """
    if not txs:
        return {}

    dex_counts = Counter()
    trade_count = 0
    uses_aggregators = False
    trade_values = []

    for tx in txs:
        to_addr = tx.get('to', '').lower()

        if to_addr in DEX_ROUTERS:
            dex_name = DEX_ROUTERS[to_addr]
            dex_counts[dex_name] += 1
            trade_count += 1

            # Track if they use aggregators
            if 'inch' in dex_name.lower() or 'paraswap' in dex_name.lower() or 'cow' in dex_name.lower():
                uses_aggregators = True

            # Track trade values
            value = int(tx.get('value', 0)) / 1e18
            if value > 0:
                trade_values.append(value)

    if trade_count == 0:
        return {
            'trading_style': 'none',
            'trade_count': 0
        }

    # Determine preferred DEX
    preferred_dex = dex_counts.most_common(1)[0][0] if dex_counts else None

    # Analyze trading style based on patterns
    # High frequency + low variance = potential arbitrage/MEV
    # High value trades = institutional spot trading

    avg_trade_value = sum(trade_values) / len(trade_values) if trade_values else 0

    # Check for MEV patterns (many small trades in short time)
    timestamps = [int(tx.get('timeStamp', 0)) for tx in txs if tx.get('to', '').lower() in DEX_ROUTERS]
    if len(timestamps) > 10:
        timestamps.sort()
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        avg_interval = sum(intervals) / len(intervals) if intervals else float('inf')

        if avg_interval < 60:  # Less than 1 minute between trades on average
            trading_style = 'mev'
        elif avg_interval < 3600 and trade_count > 50:  # High frequency
            trading_style = 'arbitrage'
        else:
            trading_style = 'spot'
    else:
        trading_style = 'spot'

    return {
        'trading_style': trading_style,
        'preferred_dex': preferred_dex,
        'trade_count': trade_count,
        'uses_aggregators': uses_aggregators,
        'avg_trade_value_eth': round(avg_trade_value, 4),
        'dex_distribution': dict(dex_counts.most_common(5))
    }


# ============================================================================
# Protocol Interaction Analysis
# ============================================================================

def analyze_protocol_interactions(txs: List[dict]) -> dict:
    """
    Analyze how they interact with DeFi protocols to infer entity type.

    Returns:
        {
            'protocol_preferences': ['Aave V3', 'Spark'],
            'risk_profile': 'conservative' | 'moderate' | 'aggressive',
            'entity_type_signal': 'individual' | 'fund' | 'protocol' | 'bot'
        }
    """
    if not txs:
        return {}

    protocol_counts = Counter()
    lending_interactions = 0
    contract_deployments = 0

    for tx in txs:
        to_addr = tx.get('to', '').lower()

        # Track lending protocol usage
        if to_addr in LENDING_PROTOCOLS:
            protocol_name = LENDING_PROTOCOLS[to_addr]
            protocol_counts[protocol_name] += 1
            lending_interactions += 1

        # Track contract deployments
        if not to_addr:  # Contract creation
            contract_deployments += 1

    # Determine protocol preferences
    preferences = [p for p, _ in protocol_counts.most_common(5)]

    # Infer risk profile based on protocol usage
    # Heavy Aave/Compound usage = conservative
    # Spark/Morpho = moderate
    # Less-known protocols = aggressive
    conservative_protocols = {'Aave V3 Pool', 'Compound V3 USDC', 'Compound V3 WETH'}
    moderate_protocols = {'Spark Pool', 'Morpho Blue'}

    conservative_count = sum(protocol_counts.get(p, 0) for p in conservative_protocols)
    moderate_count = sum(protocol_counts.get(p, 0) for p in moderate_protocols)

    if lending_interactions == 0:
        risk_profile = 'unknown'
    elif conservative_count > moderate_count:
        risk_profile = 'conservative'
    elif moderate_count > conservative_count:
        risk_profile = 'moderate'
    else:
        risk_profile = 'aggressive'

    # Infer entity type
    if contract_deployments > 5:
        entity_type_signal = 'protocol'  # Likely a protocol or developer
    elif lending_interactions > 100:
        entity_type_signal = 'fund'  # Heavy DeFi usage
    elif len(protocol_counts) > 5:
        entity_type_signal = 'fund'  # Uses many protocols
    else:
        entity_type_signal = 'individual'

    return {
        'protocol_preferences': preferences,
        'lending_interactions': lending_interactions,
        'contract_deployments': contract_deployments,
        'risk_profile': risk_profile,
        'entity_type_signal': entity_type_signal
    }


# ============================================================================
# Full Fingerprint Generation
# ============================================================================

def generate_fingerprint(address: str, chain_id: int = 1) -> dict:
    """
    Generate complete behavioral fingerprint for an address.
    """
    txs = get_transactions(address.lower(), chain_id, limit=500)

    if not txs:
        return {
            'address': address.lower(),
            'tx_count': 0,
            'has_activity': False
        }

    timing = analyze_timing_patterns(txs)
    gas = analyze_gas_patterns(txs)
    trading = analyze_trading_patterns(txs)
    protocols = analyze_protocol_interactions(txs)

    return {
        'address': address.lower(),
        'tx_count': len(txs),
        'has_activity': True,
        'timing': timing,
        'gas': gas,
        'trading': trading,
        'protocols': protocols
    }


def compute_fingerprint_similarity(fp1: dict, fp2: dict) -> float:
    """
    Compute similarity between two fingerprints.
    Returns 0-1 score.
    """
    if not fp1.get('has_activity') or not fp2.get('has_activity'):
        return 0.0

    scores = []

    # Timing similarity
    t1 = fp1.get('timing', {})
    t2 = fp2.get('timing', {})
    if t1 and t2:
        # Same timezone
        if t1.get('timezone_signal') == t2.get('timezone_signal'):
            scores.append(0.8)
        # Same activity pattern
        if t1.get('activity_pattern') == t2.get('activity_pattern'):
            scores.append(0.6)
        # Similar active hours
        h1 = set(t1.get('active_hours', []))
        h2 = set(t2.get('active_hours', []))
        if h1 and h2:
            overlap = len(h1 & h2) / len(h1 | h2)
            scores.append(overlap)

    # Gas strategy similarity
    g1 = fp1.get('gas', {})
    g2 = fp2.get('gas', {})
    if g1 and g2:
        if g1.get('gas_strategy') == g2.get('gas_strategy'):
            scores.append(0.7)
        if g1.get('uses_eip1559') == g2.get('uses_eip1559'):
            scores.append(0.3)

    # Trading pattern similarity
    tr1 = fp1.get('trading', {})
    tr2 = fp2.get('trading', {})
    if tr1 and tr2:
        if tr1.get('trading_style') == tr2.get('trading_style'):
            scores.append(0.6)
        if tr1.get('preferred_dex') == tr2.get('preferred_dex'):
            scores.append(0.5)
        if tr1.get('uses_aggregators') == tr2.get('uses_aggregators'):
            scores.append(0.3)

    # Protocol similarity
    p1 = fp1.get('protocols', {})
    p2 = fp2.get('protocols', {})
    if p1 and p2:
        pref1 = set(p1.get('protocol_preferences', []))
        pref2 = set(p2.get('protocol_preferences', []))
        if pref1 and pref2:
            overlap = len(pref1 & pref2) / len(pref1 | pref2)
            scores.append(overlap)
        if p1.get('risk_profile') == p2.get('risk_profile'):
            scores.append(0.5)

    return sum(scores) / len(scores) if scores else 0.0


def cluster_by_behavior(fingerprints: List[dict], threshold: float = 0.7) -> Dict[str, List[str]]:
    """
    Cluster addresses by behavioral similarity.
    """
    clusters: Dict[str, List[str]] = {}
    assigned = set()

    # Simple greedy clustering
    for i, fp1 in enumerate(fingerprints):
        if fp1['address'] in assigned:
            continue

        cluster_members = [fp1['address']]
        assigned.add(fp1['address'])

        for j, fp2 in enumerate(fingerprints[i+1:], i+1):
            if fp2['address'] in assigned:
                continue

            similarity = compute_fingerprint_similarity(fp1, fp2)
            if similarity >= threshold:
                cluster_members.append(fp2['address'])
                assigned.add(fp2['address'])

        if len(cluster_members) >= 2:
            clusters[f"behavior_{len(clusters)}"] = cluster_members

    return clusters


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_single_address(kg: 'KnowledgeGraph', addr: str):
    """
    Process a single address through the behavioral layer.
    Called by build_knowledge_graph for per-address error handling.
    """
    if not ETHERSCAN_API_KEY:
        raise ValueError("ETHERSCAN_API_KEY not set")

    fp = generate_fingerprint(addr)

    if fp.get('has_activity'):
        kg.set_fingerprint(
            addr,
            timezone_signal=fp.get('timing', {}).get('timezone_signal'),
            gas_strategy=fp.get('gas', {}).get('gas_strategy'),
            trading_style=fp.get('trading', {}).get('trading_style'),
            protocol_preferences=fp.get('protocols', {}).get('protocol_preferences'),
            activity_pattern=fp.get('timing', {}).get('activity_pattern'),
            risk_profile=fp.get('protocols', {}).get('risk_profile')
        )

        # Update entity with inferred type
        entity_signal = fp.get('protocols', {}).get('entity_type_signal')
        if entity_signal:
            kg.add_entity(addr, entity_type=entity_signal)

        # Add evidence
        signals = []
        if fp.get('timing', {}).get('timezone_signal'):
            signals.append(f"Timezone: {fp['timing']['timezone_signal']}")
        if fp.get('trading', {}).get('trading_style') not in ('none', None):
            signals.append(f"Trading: {fp['trading']['trading_style']}")
        if fp.get('protocols', {}).get('risk_profile') not in ('unknown', None):
            signals.append(f"Risk: {fp['protocols']['risk_profile']}")

        if signals:
            kg.add_evidence(
                addr,
                source='Behavioral',
                claim=f"Fingerprint: {', '.join(signals)}",
                confidence=0.6,
                raw_data=fp
            )

    return fp


def process_addresses(kg: 'KnowledgeGraph', addresses: List[str]):
    """
    Process addresses through the behavioral layer.
    """
    print(f"\n  Processing {len(addresses)} addresses through behavioral layer...")

    if not ETHERSCAN_API_KEY:
        print("  Warning: ETHERSCAN_API_KEY not set", file=sys.stderr)
        return

    fingerprints = []

    for i, addr in enumerate(addresses):
        if (i + 1) % 20 == 0:
            print(f"    Processing {i+1}/{len(addresses)}...")

        fp = generate_fingerprint(addr)
        fingerprints.append(fp)

        # Store fingerprint in knowledge graph
        if fp.get('has_activity'):
            kg.set_fingerprint(
                addr,
                timezone_signal=fp.get('timing', {}).get('timezone_signal'),
                gas_strategy=fp.get('gas', {}).get('gas_strategy'),
                trading_style=fp.get('trading', {}).get('trading_style'),
                protocol_preferences=fp.get('protocols', {}).get('protocol_preferences'),
                activity_pattern=fp.get('timing', {}).get('activity_pattern'),
                risk_profile=fp.get('protocols', {}).get('risk_profile')
            )

            # Update entity with inferred type
            entity_signal = fp.get('protocols', {}).get('entity_type_signal')
            if entity_signal:
                kg.add_entity(addr, entity_type=entity_signal)

            # Add evidence
            signals = []
            if fp.get('timing', {}).get('timezone_signal'):
                signals.append(f"Timezone: {fp['timing']['timezone_signal']}")
            if fp.get('trading', {}).get('trading_style') not in ('none', None):
                signals.append(f"Trading: {fp['trading']['trading_style']}")
            if fp.get('protocols', {}).get('risk_profile') not in ('unknown', None):
                signals.append(f"Risk: {fp['protocols']['risk_profile']}")

            if signals:
                kg.add_evidence(
                    addr,
                    source='Behavioral',
                    claim=f"Fingerprint: {', '.join(signals)}",
                    confidence=0.6,
                    raw_data=fp
                )

    # Cluster by behavior
    print("\n    Clustering by behavioral similarity...")
    behavior_clusters = cluster_by_behavior(fingerprints, threshold=0.65)

    if behavior_clusters:
        print(f"    Found {len(behavior_clusters)} behavioral clusters")
        for cluster_id, members in behavior_clusters.items():
            # Add relationships between cluster members
            for i, addr1 in enumerate(members):
                for addr2 in members[i+1:]:
                    kg.add_relationship(
                        addr1, addr2, 'same_behavior',
                        confidence=0.6,
                        evidence={'method': 'behavioral_fingerprint'}
                    )

    print(f"\n  Behavioral layer complete. Processed {len(fingerprints)} fingerprints")


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Behavioral Fingerprinting - Layer 2",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input", nargs="?", help="Input CSV with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID")
    parser.add_argument("--address", help="Analyze single address")
    parser.add_argument("--cluster", action="store_true", help="Cluster by behavior")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Input CSV or --address required")

    if not ETHERSCAN_API_KEY:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Single address mode
    if args.address:
        fp = generate_fingerprint(args.address, args.chain_id)
        print(json.dumps(fp, indent=2, default=str))
        return

    # Batch mode
    with open(args.input) as f:
        reader = csv.DictReader(f)
        addresses = [row.get("address") or row.get("borrower") for row in reader]
        addresses = [a for a in addresses if a]

    print(f"Analyzing {len(addresses)} addresses...")

    fingerprints = []
    for i, addr in enumerate(addresses):
        if (i + 1) % 20 == 0:
            print(f"  Processing {i+1}/{len(addresses)}...")
        fp = generate_fingerprint(addr, args.chain_id)
        fingerprints.append(fp)

    # Cluster if requested
    clusters = {}
    if args.cluster:
        print("\nClustering by behavior...")
        clusters = cluster_by_behavior(fingerprints)
        print(f"Found {len(clusters)} behavioral clusters")

    # Output
    if args.json:
        output = {
            'fingerprints': fingerprints,
            'clusters': clusters
        }
        print(json.dumps(output, indent=2, default=str))

    # Save to CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "address", "tx_count", "timezone", "activity_pattern",
                "gas_strategy", "trading_style", "risk_profile", "entity_type_signal"
            ])

            for fp in fingerprints:
                writer.writerow([
                    fp['address'],
                    fp.get('tx_count', 0),
                    fp.get('timing', {}).get('timezone_signal', ''),
                    fp.get('timing', {}).get('activity_pattern', ''),
                    fp.get('gas', {}).get('gas_strategy', ''),
                    fp.get('trading', {}).get('trading_style', ''),
                    fp.get('protocols', {}).get('risk_profile', ''),
                    fp.get('protocols', {}).get('entity_type_signal', '')
                ])

        print(f"Saved to {args.output}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    with_activity = [fp for fp in fingerprints if fp.get('has_activity')]
    print(f"Total: {len(fingerprints)}")
    print(f"With activity: {len(with_activity)}")

    # Timezone distribution
    tz_dist = Counter(fp.get('timing', {}).get('timezone_signal') for fp in with_activity)
    if tz_dist:
        print(f"\nTimezone distribution:")
        for tz, count in tz_dist.most_common(5):
            print(f"  {tz}: {count}")

    # Trading style distribution
    style_dist = Counter(fp.get('trading', {}).get('trading_style') for fp in with_activity)
    if style_dist:
        print(f"\nTrading style:")
        for style, count in style_dist.most_common():
            print(f"  {style}: {count}")


if __name__ == "__main__":
    main()
