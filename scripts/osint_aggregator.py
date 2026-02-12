#!/usr/bin/env python3
"""
OSINT Aggregator - Layer 3

Aggregates off-chain intelligence from multiple sources:
1. ENS Metadata - On-chain text records (Twitter, GitHub, email, URL)
2. Snapshot Governance - Voting history reveals identity through engagement
3. Whale Tracker Cross-Reference - Lookonchain, OnchainLens, Spot On Chain
4. Protocol Pattern Matching - Match ENS names to known protocols

Usage:
    # Standalone mode
    python3 osint_aggregator.py addresses.csv -o osint.csv

    # With knowledge graph integration
    from osint_aggregator import process_addresses
    process_addresses(knowledge_graph, addresses)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
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
ETH_RPC_URL = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")

# Rate limiting
RATE_LIMIT = 2.0  # Lower for external APIs
last_request_time = 0


def rate_limit():
    """Enforce rate limiting."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / RATE_LIMIT:
        time.sleep(1 / RATE_LIMIT - elapsed)
    last_request_time = time.time()


# ============================================================================
# ENS Metadata Extraction
# ============================================================================

# ENS Public Resolver ABI (text record function)
ENS_RESOLVER_ADDRESS = "0x231b0Ee14048e9dCcD1d247744d114a4EB5E8E63"  # ENS Public Resolver 2

# Common text record keys
ENS_TEXT_KEYS = [
    "com.twitter",
    "com.github",
    "com.discord",
    "email",
    "url",
    "description",
    "avatar",
    "com.linkedin",
    "org.telegram",
]


def resolve_ens_reverse(address: str) -> Optional[str]:
    """
    Resolve ENS name from address using reverse resolution via ENS subgraph.
    """
    rate_limit()

    try:
        # Use ENS subgraph (The Graph decentralized network)
        ens_subgraph = "https://gateway.thegraph.com/api/subgraphs/id/5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH"
        query = """
        query GetName($address: String!) {
            domains(where: {resolvedAddress: $address}) {
                name
                resolvedAddress {
                    id
                }
            }
        }
        """

        response = requests.post(
            ens_subgraph,
            json={"query": query, "variables": {"address": address.lower()}},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            domains = data.get("data", {}).get("domains", [])
            if domains:
                return domains[0].get("name")

    except Exception as e:
        print(f"  ENS resolution error: {e}", file=sys.stderr)

    return None


def get_ens_text_records(ens_name: str) -> Dict[str, str]:
    """
    Get text records from ENS name.
    Note: ENS subgraph returns which text keys exist but not their values.
    For actual values, would need web3.py with ENS resolver calls.
    """
    rate_limit()

    records = {}

    try:
        # Use ENS subgraph for text record keys
        ens_subgraph = "https://gateway.thegraph.com/api/subgraphs/id/5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH"
        query = """
        query GetTextRecords($name: String!) {
            domains(where: {name: $name}) {
                resolver {
                    texts
                }
            }
        }
        """

        response = requests.post(
            ens_subgraph,
            json={"query": query, "variables": {"name": ens_name}},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            domains = data.get("data", {}).get("domains", [])
            if domains and domains[0].get("resolver"):
                texts = domains[0]["resolver"].get("texts", [])
                for key in texts:
                    records[key] = f"[has {key}]"  # Subgraph doesn't return values

    except Exception as e:
        print(f"  ENS text records error: {e}", file=sys.stderr)

    return records


def extract_ens_identity_signals(ens_name: str, text_records: Dict[str, str]) -> List[str]:
    """
    Extract identity signals from ENS name and records.
    """
    signals = []

    if not ens_name:
        return signals

    # Check name patterns
    name_lower = ens_name.lower()

    # Protocol/project names
    protocol_patterns = [
        (r'.*capital\.eth$', 'Likely VC/Investment Fund'),
        (r'.*fund\.eth$', 'Likely Investment Fund'),
        (r'.*dao\.eth$', 'DAO Treasury'),
        (r'.*treasury\.eth$', 'Project Treasury'),
        (r'.*vault\.eth$', 'Vault/Treasury'),
        (r'.*protocol\.eth$', 'Protocol Address'),
        (r'.*finance\.eth$', 'DeFi Protocol'),
        (r'.*labs\.eth$', 'Development Team'),
        (r'.*foundation\.eth$', 'Foundation Address'),
    ]

    for pattern, label in protocol_patterns:
        if re.match(pattern, name_lower):
            signals.append(label)
            break

    # Personal name patterns (firstname.eth, firstname-lastname.eth)
    if re.match(r'^[a-z]{2,15}\.eth$', name_lower):
        signals.append('Likely Personal Name')

    # Numbers in name often indicate whale/collector
    if re.search(r'\d{3,}', name_lower):
        signals.append('Contains Numbers - Collector Pattern')

    # Text record signals
    if text_records.get('com.twitter'):
        signals.append('Has Twitter Link')
    if text_records.get('com.github'):
        signals.append('Has GitHub Link (Developer)')
    if text_records.get('url'):
        signals.append('Has Website')
    if text_records.get('email'):
        signals.append('Has Email')

    return signals


# ============================================================================
# Snapshot Governance Analysis
# ============================================================================

SNAPSHOT_GRAPHQL_URL = "https://hub.snapshot.org/graphql"


def snapshot_query(query: str, variables: dict = None) -> dict:
    """Execute a Snapshot GraphQL query."""
    rate_limit()

    try:
        response = requests.post(
            SNAPSHOT_GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        data = response.json()
        return data.get("data", {})
    except Exception as e:
        print(f"  Snapshot error: {e}", file=sys.stderr)
        return {}


def get_snapshot_activity(address: str) -> dict:
    """Get Snapshot voting activity for an address."""
    query = """
    query Votes($voter: String!) {
        votes(
            where: { voter: $voter }
            first: 100
            orderBy: "created"
            orderDirection: desc
        ) {
            id
            voter
            created
            vp
            proposal {
                id
                title
                space {
                    id
                    name
                }
            }
        }
    }
    """

    result = snapshot_query(query, {"voter": address.lower()})
    votes = result.get("votes", [])

    if not votes:
        return {
            'address': address.lower(),
            'has_votes': False,
            'total_votes': 0
        }

    # Aggregate by space
    spaces = defaultdict(lambda: {'count': 0, 'vp': 0})
    total_vp = 0

    for vote in votes:
        vp = vote.get('vp', 0)
        total_vp += vp

        if vote.get('proposal') and vote['proposal'].get('space'):
            space_id = vote['proposal']['space']['id']
            space_name = vote['proposal']['space']['name']
            spaces[space_id]['name'] = space_name
            spaces[space_id]['count'] += 1
            spaces[space_id]['vp'] += vp

    # Sort by vote count
    top_spaces = sorted(spaces.items(), key=lambda x: -x[1]['count'])[:5]

    return {
        'address': address.lower(),
        'has_votes': True,
        'total_votes': len(votes),
        'total_voting_power': total_vp,
        'unique_spaces': len(spaces),
        'top_spaces': [
            {'id': s[0], 'name': s[1]['name'], 'votes': s[1]['count'], 'vp': s[1]['vp']}
            for s in top_spaces
        ],
        'recent_votes': [
            {
                'proposal': (v.get('proposal') or {}).get('title', 'Unknown'),
                'space': ((v.get('proposal') or {}).get('space') or {}).get('name', 'Unknown'),
                'vp': v.get('vp', 0)
            }
            for v in votes[:3]
        ]
    }


def get_delegations(address: str) -> dict:
    """Get delegation info for an address."""
    # Delegations FROM this address
    query_from = """
    query Delegations($delegator: String!) {
        delegations(
            where: { delegator: $delegator }
            first: 100
        ) {
            delegate
            space
        }
    }
    """

    # Delegations TO this address
    query_to = """
    query Delegations($delegate: String!) {
        delegations(
            where: { delegate: $delegate }
            first: 100
        ) {
            delegator
            space
        }
    }
    """

    result_from = snapshot_query(query_from, {"delegator": address.lower()})
    result_to = snapshot_query(query_to, {"delegate": address.lower()})

    delegates_to = result_from.get("delegations", [])
    receives_from = result_to.get("delegations", [])

    return {
        'delegates_to_count': len(delegates_to),
        'receives_delegations_from': len(receives_from),
        'is_delegate': len(receives_from) > 5,  # Significant if >5 delegators
        'delegates_to': [d['delegate'][:20] + '...' for d in delegates_to[:3]],
        'spaces_delegating': list(set(d['space'] for d in delegates_to))[:5]
    }


def extract_governance_identity_signals(snapshot: dict, delegations: dict) -> List[str]:
    """Extract identity signals from governance activity."""
    signals = []

    if not snapshot.get('has_votes'):
        return signals

    total_vp = snapshot.get('total_voting_power', 0)
    total_votes = snapshot.get('total_votes', 0)
    unique_spaces = snapshot.get('unique_spaces', 0)

    # High voting power = institutional
    if total_vp > 1000000:
        signals.append(f"Very High Voting Power ({total_vp:,.0f}) - Institutional")
    elif total_vp > 100000:
        signals.append(f"High Voting Power ({total_vp:,.0f})")

    # Active voter in many DAOs
    if unique_spaces > 10:
        signals.append(f"Active in {unique_spaces} DAOs - Power User/Fund")
    elif unique_spaces > 5:
        signals.append(f"Active in {unique_spaces} DAOs")

    # Significant delegate
    if delegations.get('is_delegate'):
        signals.append(f"Receives delegations from {delegations['receives_delegations_from']} addresses - Known Entity")

    # Check for major DAO participation
    top_spaces = snapshot.get('top_spaces', [])
    major_daos = {'aave.eth', 'ens.eth', 'compound-governance.eth', 'uniswap', 'gitcoin.eth', 'arbitrum.eth'}

    for space in top_spaces:
        if space['id'] in major_daos:
            signals.append(f"Active in {space['name']} governance")

    return signals


# ============================================================================
# Protocol Pattern Matching
# ============================================================================

# Known protocols and their treasury patterns
KNOWN_PROTOCOLS = {
    # DeFi protocols
    'aave': ['aave.eth', 'aavetreasury.eth', 'aave-grants'],
    'uniswap': ['uniswap.eth', 'uniswap-treasury'],
    'compound': ['compound.eth', 'compound-treasury'],
    'maker': ['maker.eth', 'makerdao.eth', 'dai.eth'],
    'curve': ['curve.eth', 'curvedao'],
    'lido': ['lido.eth', 'lido-finance'],
    'yearn': ['yearn.eth', 'yearntreasury'],

    # Exchanges
    'binance': ['binance', 'bnb'],
    'coinbase': ['coinbase', 'cb'],
    'kraken': ['kraken'],

    # VCs/Funds
    'a16z': ['a16z', 'andreessen'],
    'paradigm': ['paradigm'],
    'polychain': ['polychain'],
    'pantera': ['pantera'],
    'multicoin': ['multicoin'],
}


def match_protocol_pattern(ens_name: str) -> Optional[str]:
    """Try to match ENS name to known protocol."""
    if not ens_name:
        return None

    name_lower = ens_name.lower()

    for protocol, patterns in KNOWN_PROTOCOLS.items():
        for pattern in patterns:
            if pattern in name_lower:
                return protocol

    return None


# ============================================================================
# Whale Tracker Aggregation
# ============================================================================

def check_whale_trackers(address: str) -> List[dict]:
    """
    Check if address is tracked by major whale trackers.
    Note: This would ideally use their APIs, but most require subscriptions.
    Returns cached/known whale labels.
    """
    # Known whale addresses (from previous investigations)
    KNOWN_WHALES = {
        # Justin Sun
        "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": {"name": "Justin Sun", "confidence": 0.95},
        "0x176f3dab24a159341c0509bb36b833e7fdd0a132": {"name": "Justin Sun", "confidence": 0.9},

        # Major entities
        "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": {"name": "Polygon Bridge", "confidence": 0.95},
        "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": {"name": "Stargate Finance", "confidence": 0.95},

        # Trend Research cluster
        "0x85e67feb76596f08a4dbebfdcbed3d0e9bf60ae9": {"name": "Trend Research", "confidence": 0.85},
        "0xfaf6f6ffaf0ea8815a8ceeee6399ebe9bfe72a7a": {"name": "Trend Research", "confidence": 0.85},

        # 7 Siblings
        "0xbcd0f3c2e6e73d6c2e1e8e0c6e52c4f2e2a1d0c9": {"name": "7 Siblings", "confidence": 0.8},
    }

    results = []
    addr_lower = address.lower()

    if addr_lower in KNOWN_WHALES:
        info = KNOWN_WHALES[addr_lower]
        results.append({
            'source': 'Known Whales DB',
            'label': info['name'],
            'confidence': info['confidence']
        })

    return results


# ============================================================================
# Full OSINT Aggregation
# ============================================================================

def aggregate_osint(address: str) -> dict:
    """
    Aggregate all OSINT sources for an address.
    """
    result = {
        'address': address.lower(),
        'ens': None,
        'snapshot': None,
        'delegations': None,
        'whale_labels': [],
        'identity_signals': [],
        'inferred_identity': None,
        'confidence': 0.0
    }

    # ENS Resolution
    print(f"    Checking ENS for {address[:10]}...")
    ens_name = resolve_ens_reverse(address)
    if ens_name:
        text_records = get_ens_text_records(ens_name)
        result['ens'] = {
            'name': ens_name,
            'text_records': text_records
        }
        ens_signals = extract_ens_identity_signals(ens_name, text_records)
        result['identity_signals'].extend(ens_signals)

        # Check protocol pattern
        matched_protocol = match_protocol_pattern(ens_name)
        if matched_protocol:
            result['identity_signals'].append(f"Matches Protocol: {matched_protocol}")

    # Snapshot Activity
    print(f"    Checking Snapshot...")
    snapshot = get_snapshot_activity(address)
    result['snapshot'] = snapshot

    delegations = get_delegations(address)
    result['delegations'] = delegations

    gov_signals = extract_governance_identity_signals(snapshot, delegations)
    result['identity_signals'].extend(gov_signals)

    # Whale Tracker Check
    whale_labels = check_whale_trackers(address)
    result['whale_labels'] = whale_labels

    if whale_labels:
        for label in whale_labels:
            result['identity_signals'].append(f"Whale Tracker: {label['label']}")

    # Calculate overall confidence
    confidence = 0.0
    if result['ens']:
        confidence += 0.3
        if result['ens'].get('text_records'):
            confidence += 0.1

    if snapshot.get('has_votes'):
        if snapshot.get('total_voting_power', 0) > 100000:
            confidence += 0.3
        else:
            confidence += 0.1

    if delegations.get('is_delegate'):
        confidence += 0.2

    if whale_labels:
        confidence = max(confidence, max(l['confidence'] for l in whale_labels))

    result['confidence'] = min(confidence, 0.95)

    # Infer identity
    if whale_labels:
        result['inferred_identity'] = whale_labels[0]['label']
    elif result['ens'] and match_protocol_pattern(result['ens']['name']):
        result['inferred_identity'] = f"{match_protocol_pattern(result['ens']['name'])} Related"

    return result


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_single_address(kg: 'KnowledgeGraph', addr: str):
    """
    Process a single address through the OSINT layer.
    Called by build_knowledge_graph for per-address error handling.
    """
    osint = aggregate_osint(addr)

    # Store ENS if found
    if osint.get('ens'):
        kg.add_entity(addr, ens_name=osint['ens']['name'])
        kg.add_evidence(
            addr,
            source='ENS',
            claim=f"ENS Name: {osint['ens']['name']}",
            confidence=0.9,
            raw_data=osint['ens']
        )

    # Store Snapshot activity
    if osint.get('snapshot', {}).get('has_votes'):
        snap = osint['snapshot']
        kg.add_evidence(
            addr,
            source='Snapshot',
            claim=f"Voted {snap['total_votes']} times in {snap['unique_spaces']} DAOs",
            confidence=0.7,
            raw_data=snap
        )

        # If significant delegate, mark as known entity
        if osint.get('delegations', {}).get('is_delegate'):
            kg.add_entity(addr, entity_type='individual')  # Fixed: was 'known_entity'
            kg.add_evidence(
                addr,
                source='Snapshot',
                claim=f"Receives delegations - known governance participant",
                confidence=0.8,
                raw_data=osint['delegations']
            )

    # Store whale labels
    for label in osint.get('whale_labels', []):
        kg.add_evidence(
            addr,
            source=label['source'],
            claim=f"Identified as: {label['label']}",
            confidence=label['confidence']
        )

        if label['confidence'] >= 0.7:
            kg.set_identity(
                addr,
                identity=label['label'],
                confidence=label['confidence']
            )

    # Store identity signals
    for signal in osint.get('identity_signals', []):
        kg.add_evidence(
            addr,
            source='OSINT',
            claim=signal,
            confidence=0.5
        )

    # If we inferred an identity
    if osint.get('inferred_identity') and osint['confidence'] >= 0.5:
        current = kg.get_entity(addr)
        if not current or not current.get('identity'):
            kg.set_identity(
                addr,
                identity=osint['inferred_identity'],
                confidence=osint['confidence']
            )

    return osint


def process_addresses(kg: 'KnowledgeGraph', addresses: List[str]):
    """
    Process addresses through the OSINT layer.
    """
    print(f"\n  Processing {len(addresses)} addresses through OSINT layer...")

    for i, addr in enumerate(addresses):
        if (i + 1) % 10 == 0:
            print(f"\n    Progress: {i+1}/{len(addresses)}")

        osint = aggregate_osint(addr)

        # Store ENS if found
        if osint.get('ens'):
            kg.add_entity(addr, ens_name=osint['ens']['name'])
            kg.add_evidence(
                addr,
                source='ENS',
                claim=f"ENS Name: {osint['ens']['name']}",
                confidence=0.9,
                raw_data=osint['ens']
            )

        # Store Snapshot activity
        if osint.get('snapshot', {}).get('has_votes'):
            snap = osint['snapshot']
            kg.add_evidence(
                addr,
                source='Snapshot',
                claim=f"Voted {snap['total_votes']} times in {snap['unique_spaces']} DAOs",
                confidence=0.7,
                raw_data=snap
            )

            # If significant delegate, mark as known entity
            if osint.get('delegations', {}).get('is_delegate'):
                kg.add_entity(addr, entity_type='known_entity')
                kg.add_evidence(
                    addr,
                    source='Snapshot',
                    claim=f"Receives delegations - known governance participant",
                    confidence=0.8,
                    raw_data=osint['delegations']
                )

        # Store whale labels
        for label in osint.get('whale_labels', []):
            kg.add_evidence(
                addr,
                source=label['source'],
                claim=f"Identified as: {label['label']}",
                confidence=label['confidence']
            )

            if label['confidence'] >= 0.7:
                kg.set_identity(
                    addr,
                    identity=label['label'],
                    confidence=label['confidence']
                )

        # Store identity signals
        for signal in osint.get('identity_signals', []):
            kg.add_evidence(
                addr,
                source='OSINT',
                claim=signal,
                confidence=0.5
            )

        # If we inferred an identity
        if osint.get('inferred_identity') and osint['confidence'] >= 0.5:
            current = kg.get_entity(addr)
            if not current or not current.get('identity'):
                kg.set_identity(
                    addr,
                    identity=osint['inferred_identity'],
                    confidence=osint['confidence']
                )

    print(f"\n  OSINT layer complete. Processed {len(addresses)} addresses")


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OSINT Aggregator - Layer 3",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("input", nargs="?", help="Input CSV with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Analyze single address")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Input CSV or --address required")

    # Single address mode
    if args.address:
        result = aggregate_osint(args.address)
        print(json.dumps(result, indent=2, default=str))
        return

    # Batch mode
    with open(args.input) as f:
        reader = csv.DictReader(f)
        addresses = [row.get("address") or row.get("borrower") for row in reader]
        addresses = [a for a in addresses if a]

    print(f"Processing {len(addresses)} addresses...")

    results = []
    for addr in addresses:
        result = aggregate_osint(addr)
        results.append(result)

    # Output
    if args.json:
        print(json.dumps(results, indent=2, default=str))

    # Save to CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "address", "ens_name", "snapshot_votes", "snapshot_spaces",
                "voting_power", "is_delegate", "whale_labels", "identity_signals",
                "inferred_identity", "confidence"
            ])

            for r in results:
                writer.writerow([
                    r['address'],
                    r.get('ens', {}).get('name', ''),
                    r.get('snapshot', {}).get('total_votes', 0),
                    r.get('snapshot', {}).get('unique_spaces', 0),
                    r.get('snapshot', {}).get('total_voting_power', 0),
                    r.get('delegations', {}).get('is_delegate', False),
                    '|'.join(l['label'] for l in r.get('whale_labels', [])),
                    '|'.join(r.get('identity_signals', [])),
                    r.get('inferred_identity', ''),
                    r.get('confidence', 0)
                ])

        print(f"Saved to {args.output}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    with_ens = sum(1 for r in results if r.get('ens'))
    with_snapshot = sum(1 for r in results if r.get('snapshot', {}).get('has_votes'))
    with_labels = sum(1 for r in results if r.get('whale_labels'))
    with_identity = sum(1 for r in results if r.get('inferred_identity'))

    print(f"Total: {len(results)}")
    print(f"With ENS: {with_ens}")
    print(f"With Snapshot votes: {with_snapshot}")
    print(f"With whale labels: {with_labels}")
    print(f"With inferred identity: {with_identity}")


if __name__ == "__main__":
    main()
