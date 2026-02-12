#!/usr/bin/env python3
"""
Pattern Matcher - Entity Recognition

Applies learned patterns from known entities to identify unknowns:
1. Entity Templates - VC funds, protocols, exchanges, individuals
2. Cluster Patterns - Similar cluster structure to known entities
3. Behavioral Matching - Similar fingerprints to identified addresses
4. Evidence Aggregation - Combine all sources for final identification

The key insight: once we identify one entity (e.g., Trend Research),
we can find more like it by matching their patterns.

Usage:
    # With knowledge graph (called from build_knowledge_graph.py)
    from pattern_matcher import match_patterns
    match_patterns(knowledge_graph)

    # Standalone: analyze a single address against known patterns
    python3 pattern_matcher.py --address 0x1234...

    # Create a new template from a known entity
    python3 pattern_matcher.py --create-template "Trend Research" --addresses addr1,addr2,addr3
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

# ============================================================================
# Entity Templates
# ============================================================================

# Pre-defined entity templates based on known patterns
ENTITY_TEMPLATES = {
    "vc_fund": {
        "name": "VC/Investment Fund",
        "description": "Venture capital or crypto investment fund",
        "patterns": {
            "cluster_size": {"min": 10, "max": 100},
            "entity_type": "fund",
            "funding_pattern": "common_funder",  # Usually funded from same source
            "trading_style": ["spot", "none"],  # Not MEV/arbitrage
            "risk_profile": ["conservative", "moderate"],
            "has_ens": False,  # VCs often don't use ENS
            "snapshot_activity": False,  # Usually don't vote
            "cross_chain": True,  # Active on multiple chains
        },
        "examples": [
            "0x85e67feb76596f08a4dbebfdcbed3d0e9bf60ae9",  # Trend Research
        ],
        "confidence": 0.75
    },

    "protocol_treasury": {
        "name": "Protocol Treasury",
        "description": "DeFi protocol treasury or multisig",
        "patterns": {
            "contract_type": "Safe",
            "entity_type": "protocol",
            "has_ens": True,  # Usually has protocol.eth
            "snapshot_activity": True,  # Active in governance
            "trading_style": "none",  # Treasuries don't trade
            "risk_profile": "conservative",
        },
        "examples": [],
        "confidence": 0.8
    },

    "exchange_hot_wallet": {
        "name": "Exchange Hot Wallet",
        "description": "Centralized exchange hot wallet",
        "patterns": {
            "entity_type": "exchange",
            "trading_style": "none",  # Receives/sends, doesn't DEX trade
            "high_tx_volume": True,  # Many transactions
            "activity_pattern": "always_on",  # 24/7 activity
            "cross_chain": True,
        },
        "examples": [
            "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14
        ],
        "confidence": 0.9
    },

    "mev_bot": {
        "name": "MEV Bot",
        "description": "MEV extraction or arbitrage bot",
        "patterns": {
            "contract_type": "Contract",  # Usually a smart contract
            "entity_type": "bot",
            "trading_style": ["mev", "arbitrage"],
            "activity_pattern": "always_on",
            "gas_strategy": ["high", "very_high"],
            "high_tx_volume": True,
        },
        "examples": [],
        "confidence": 0.85
    },

    "whale_individual": {
        "name": "Whale Individual",
        "description": "High net worth individual trader",
        "patterns": {
            "contract_type": "EOA",
            "entity_type": "individual",
            "has_ens": True,  # Often has personal ENS
            "snapshot_activity": True,  # Often votes
            "trading_style": "spot",
            "activity_pattern": "business_hours",  # Human hours
        },
        "examples": [],
        "confidence": 0.7
    },

    "7_siblings_pattern": {
        "name": "7 Siblings Pattern",
        "description": "Large cluster with coordinated activity",
        "patterns": {
            "cluster_size": {"min": 5, "max": 20},
            "funding_pattern": "common_funder",
            "activity_pattern": "coordinated",  # Same timing
            "gas_strategy": "same",  # Same gas patterns
        },
        "examples": [],
        "confidence": 0.8
    },
}


# ============================================================================
# Pattern Matching Functions
# ============================================================================

def match_template(entity_data: dict, template: dict) -> Tuple[bool, float, List[str]]:
    """
    Check if an entity matches a template.

    Returns:
        (matches, score, matched_criteria)
    """
    patterns = template.get("patterns", {})
    matched = []
    total_weight = 0
    matched_weight = 0

    # Contract type check
    if "contract_type" in patterns:
        total_weight += 1
        if entity_data.get("contract_type") and patterns["contract_type"] in entity_data["contract_type"]:
            matched.append(f"contract_type={patterns['contract_type']}")
            matched_weight += 1

    # Entity type check
    if "entity_type" in patterns:
        total_weight += 1
        if entity_data.get("entity_type") == patterns["entity_type"]:
            matched.append(f"entity_type={patterns['entity_type']}")
            matched_weight += 1

    # Cluster size check
    if "cluster_size" in patterns:
        total_weight += 1
        cluster_size = entity_data.get("cluster_size", 0)
        size_range = patterns["cluster_size"]
        if size_range.get("min", 0) <= cluster_size <= size_range.get("max", float('inf')):
            matched.append(f"cluster_size={cluster_size}")
            matched_weight += 1

    # ENS check
    if "has_ens" in patterns:
        total_weight += 0.5
        has_ens = bool(entity_data.get("ens_name"))
        if has_ens == patterns["has_ens"]:
            matched.append(f"has_ens={has_ens}")
            matched_weight += 0.5

    # Snapshot activity check
    if "snapshot_activity" in patterns:
        total_weight += 0.5
        has_votes = entity_data.get("snapshot_votes", 0) > 0
        if has_votes == patterns["snapshot_activity"]:
            matched.append(f"snapshot_activity={has_votes}")
            matched_weight += 0.5

    # Trading style check
    if "trading_style" in patterns:
        total_weight += 1
        style = entity_data.get("trading_style")
        expected = patterns["trading_style"]
        if isinstance(expected, list):
            if style in expected:
                matched.append(f"trading_style={style}")
                matched_weight += 1
        elif style == expected:
            matched.append(f"trading_style={style}")
            matched_weight += 1

    # Risk profile check
    if "risk_profile" in patterns:
        total_weight += 0.5
        profile = entity_data.get("risk_profile")
        expected = patterns["risk_profile"]
        if isinstance(expected, list):
            if profile in expected:
                matched.append(f"risk_profile={profile}")
                matched_weight += 0.5
        elif profile == expected:
            matched.append(f"risk_profile={profile}")
            matched_weight += 0.5

    # Activity pattern check
    if "activity_pattern" in patterns:
        total_weight += 0.5
        pattern = entity_data.get("activity_pattern")
        if pattern and patterns["activity_pattern"] in pattern:
            matched.append(f"activity_pattern={pattern}")
            matched_weight += 0.5

    # Gas strategy check
    if "gas_strategy" in patterns:
        total_weight += 0.5
        gas = entity_data.get("gas_strategy")
        expected = patterns["gas_strategy"]
        if isinstance(expected, list):
            if gas in expected:
                matched.append(f"gas_strategy={gas}")
                matched_weight += 0.5
        elif gas == expected:
            matched.append(f"gas_strategy={gas}")
            matched_weight += 0.5

    # Calculate score
    score = matched_weight / total_weight if total_weight > 0 else 0

    # Determine if it's a match (>50% of criteria matched)
    matches = score >= 0.5

    return matches, score, matched


def find_cluster_pattern_matches(kg: 'KnowledgeGraph') -> List[dict]:
    """
    Find clusters that match patterns of known identified clusters.
    """
    results = []

    # Get all clusters
    conn = kg.connect()
    clusters = conn.execute("SELECT * FROM clusters").fetchall()

    # Get identified clusters as templates
    identified_clusters = []
    for cluster in clusters:
        cluster = dict(cluster)
        members = conn.execute(
            "SELECT * FROM entities WHERE cluster_id = ?", (cluster['id'],)
        ).fetchall()

        # Check if any member is identified
        identified_member = None
        for m in members:
            m = dict(m)
            if m.get('identity'):
                identified_member = m
                break

        if identified_member:
            identified_clusters.append({
                'cluster': cluster,
                'identity': identified_member['identity'],
                'size': len(members),
                'methods': json.loads(cluster.get('detection_methods', '[]'))
            })

    # Compare unidentified clusters to identified ones
    for cluster in clusters:
        cluster = dict(cluster)
        members = conn.execute(
            "SELECT * FROM entities WHERE cluster_id = ?", (cluster['id'],)
        ).fetchall()

        # Skip if already identified
        has_identified = any(dict(m).get('identity') for m in members)
        if has_identified:
            continue

        cluster_size = len(members)
        cluster_methods = json.loads(cluster.get('detection_methods', '[]'))

        # Compare to identified clusters
        for ic in identified_clusters:
            # Check size similarity (within 50%)
            size_ratio = min(cluster_size, ic['size']) / max(cluster_size, ic['size'])
            if size_ratio < 0.5:
                continue

            # Check method overlap
            method_overlap = len(set(cluster_methods) & set(ic['methods']))
            if method_overlap == 0:
                continue

            # Calculate similarity score
            similarity = (size_ratio * 0.4 + (method_overlap / max(len(cluster_methods), 1)) * 0.6)

            if similarity >= 0.6:
                results.append({
                    'cluster_id': cluster['id'],
                    'matched_to': ic['identity'],
                    'similarity': similarity,
                    'evidence': f"Similar to {ic['identity']} cluster (size: {cluster_size} vs {ic['size']}, methods: {cluster_methods})"
                })

    return results


def aggregate_evidence_score(kg: 'KnowledgeGraph', address: str) -> Tuple[float, List[str]]:
    """
    Aggregate all evidence for an address to compute final confidence.
    """
    evidence = kg.get_evidence(address)

    if not evidence:
        return 0.0, []

    # Weight by source
    source_weights = {
        'CIO': 0.9,
        'CrossChain': 0.8,
        'Behavioral': 0.6,
        'ENS': 0.9,
        'Snapshot': 0.7,
        'OSINT': 0.5,
        'Known Whales DB': 0.95,
        'Pattern Match': 0.7,
    }

    # Use MAX confidence per source to prevent low-confidence items from diluting
    # high-confidence evidence (e.g., 50 behavioral signals shouldn't drown out 1 CIO)
    source_max_conf = {}  # source -> max confidence seen
    claims = []

    for ev in evidence:
        source = ev.get('source', 'Unknown')
        conf = ev.get('confidence', 0.5)
        claims.append(f"[{source}] {ev.get('claim', '')[:50]}...")

        # Keep only the highest confidence per source
        if source not in source_max_conf or conf > source_max_conf[source]:
            source_max_conf[source] = conf

    # Calculate weighted average using max confidence per source
    total_weight = 0
    weighted_confidence = 0

    for source, conf in source_max_conf.items():
        weight = source_weights.get(source, 0.5)
        total_weight += weight
        weighted_confidence += conf * weight

    final_confidence = weighted_confidence / total_weight if total_weight > 0 else 0

    return final_confidence, claims


# ============================================================================
# Main Pattern Matching
# ============================================================================

def match_patterns(kg: 'KnowledgeGraph'):
    """
    Run pattern matching on all unidentified entities.
    """
    print("\n  Running pattern matching...")

    conn = kg.connect()

    # Get unidentified entities
    unidentified = conn.execute(
        """SELECT e.*, bf.timezone_signal, bf.gas_strategy, bf.trading_style,
                  bf.risk_profile, bf.activity_pattern
           FROM entities e
           LEFT JOIN behavioral_fingerprints bf ON e.address = bf.address
           WHERE e.identity IS NULL OR e.identity = ''"""
    ).fetchall()

    print(f"    Found {len(unidentified)} unidentified entities")

    matched_count = 0

    for row in unidentified:
        entity = dict(row)
        address = entity['address']

        # Get cluster info
        cluster_id = entity.get('cluster_id')
        if cluster_id:
            cluster = conn.execute(
                "SELECT COUNT(*) as size FROM entities WHERE cluster_id = ?", (cluster_id,)
            ).fetchone()
            entity['cluster_size'] = cluster[0] if cluster else 0
        else:
            entity['cluster_size'] = 0

        # Get snapshot info
        snapshot_evidence = conn.execute(
            "SELECT * FROM evidence WHERE entity_address = ? AND source = 'Snapshot'",
            (address,)
        ).fetchone()
        entity['snapshot_votes'] = 1 if snapshot_evidence else 0

        # Match against templates
        best_match = None
        best_score = 0

        for template_id, template in ENTITY_TEMPLATES.items():
            matches, score, criteria = match_template(entity, template)

            if matches and score > best_score:
                best_match = {
                    'template_id': template_id,
                    'template_name': template['name'],
                    'score': score,
                    'criteria': criteria,
                    'confidence': template['confidence'] * score
                }
                best_score = score

        if best_match and best_match['confidence'] >= 0.5:
            # Record the match
            kg.add_evidence(
                address,
                source='Pattern Match',
                claim=f"Matches {best_match['template_name']} pattern ({best_match['score']:.0%})",
                confidence=best_match['confidence'],
                raw_data=best_match
            )

            # Update entity type if not set
            if not entity.get('entity_type') or entity['entity_type'] == 'unknown':
                entity_type = ENTITY_TEMPLATES[best_match['template_id']].get('patterns', {}).get('entity_type')
                if entity_type:
                    kg.add_entity(address, entity_type=entity_type)

            matched_count += 1

    print(f"    Matched {matched_count} entities to templates")

    # Find cluster pattern matches
    print("\n    Matching cluster patterns...")
    cluster_matches = find_cluster_pattern_matches(kg)

    if cluster_matches:
        print(f"    Found {len(cluster_matches)} potential cluster matches")
        for match in cluster_matches:
            # Get cluster members
            members = conn.execute(
                "SELECT address FROM entities WHERE cluster_id = ?",
                (match['cluster_id'],)
            ).fetchall()

            for m in members:
                kg.add_evidence(
                    m[0],
                    source='Pattern Match',
                    claim=f"Cluster similar to {match['matched_to']}",
                    confidence=match['similarity'] * 0.7,
                    raw_data=match
                )

    # Final confidence aggregation
    print("\n    Aggregating evidence for final scores...")
    all_entities = conn.execute("SELECT address FROM entities").fetchall()

    identified_count = 0
    high_conf_count = 0

    for row in all_entities:
        address = row[0]
        final_confidence, claims = aggregate_evidence_score(kg, address)

        if final_confidence > 0:
            # Update entity confidence
            kg.add_entity(address, confidence=final_confidence)

            if final_confidence >= 0.7:
                high_conf_count += 1

            # Check if we can infer identity from cluster
            entity = kg.get_entity(address)
            if not entity.get('identity') and entity.get('cluster_id'):
                # Check if any cluster member is identified
                cluster_identity = conn.execute(
                    """SELECT identity FROM entities
                       WHERE cluster_id = ? AND identity IS NOT NULL AND identity != ''
                       LIMIT 1""",
                    (entity['cluster_id'],)
                ).fetchone()

                if cluster_identity:
                    # Avoid duplicating "(cluster member)" suffix
                    base_identity = cluster_identity[0]
                    if base_identity.endswith(" (cluster member)"):
                        new_identity = base_identity
                    else:
                        new_identity = f"{base_identity} (cluster member)"
                    kg.set_identity(
                        address,
                        identity=new_identity,
                        confidence=final_confidence * 0.9
                    )
                    identified_count += 1

    print(f"\n  Pattern matching complete:")
    print(f"    Template matches: {matched_count}")
    print(f"    Cluster pattern matches: {len(cluster_matches)}")
    print(f"    High confidence entities: {high_conf_count}")
    print(f"    Newly identified: {identified_count}")


# ============================================================================
# Template Creation
# ============================================================================

def create_template_from_entity(kg: 'KnowledgeGraph', identity: str, addresses: List[str]) -> dict:
    """
    Create a new template from identified entity addresses.
    """
    template = {
        "name": identity,
        "description": f"Pattern learned from {identity}",
        "patterns": {},
        "examples": addresses,
        "confidence": 0.7
    }

    # Aggregate patterns from addresses
    contract_types = Counter()
    entity_types = Counter()
    trading_styles = Counter()
    risk_profiles = Counter()
    gas_strategies = Counter()

    for addr in addresses:
        entity = kg.get_entity(addr)
        fp = kg.get_fingerprint(addr)

        if entity:
            if entity.get('contract_type'):
                contract_types[entity['contract_type']] += 1
            if entity.get('entity_type'):
                entity_types[entity['entity_type']] += 1

        if fp:
            if fp.get('trading_style'):
                trading_styles[fp['trading_style']] += 1
            if fp.get('risk_profile'):
                risk_profiles[fp['risk_profile']] += 1
            if fp.get('gas_strategy'):
                gas_strategies[fp['gas_strategy']] += 1

    # Set patterns based on most common values
    if contract_types:
        template['patterns']['contract_type'] = contract_types.most_common(1)[0][0]
    if entity_types:
        template['patterns']['entity_type'] = entity_types.most_common(1)[0][0]
    if trading_styles:
        template['patterns']['trading_style'] = trading_styles.most_common(1)[0][0]
    if risk_profiles:
        template['patterns']['risk_profile'] = risk_profiles.most_common(1)[0][0]
    if gas_strategies:
        template['patterns']['gas_strategy'] = gas_strategies.most_common(1)[0][0]

    # Cluster size
    if len(addresses) > 1:
        template['patterns']['cluster_size'] = {
            "min": max(2, len(addresses) - 5),
            "max": len(addresses) + 10
        }

    return template


def save_template(template: dict, kg: 'KnowledgeGraph'):
    """Save a template to the knowledge graph."""
    conn = kg.connect()
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO entity_templates (name, description, patterns, examples, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            template['name'],
            template['description'],
            json.dumps(template['patterns']),
            json.dumps(template['examples']),
            template['confidence'],
            now
        )
    )
    conn.commit()


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pattern Matcher - Entity Recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--address", help="Match patterns for single address")
    parser.add_argument("--create-template", help="Create template from identity name")
    parser.add_argument("--addresses", help="Comma-separated addresses for template creation")
    parser.add_argument("--list-templates", action="store_true", help="List all templates")

    args = parser.parse_args()

    # Import knowledge graph
    from build_knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    kg.connect()

    if args.list_templates:
        print("\n" + "="*60)
        print("ENTITY TEMPLATES")
        print("="*60)

        for tid, template in ENTITY_TEMPLATES.items():
            print(f"\n{tid}: {template['name']}")
            print(f"  Description: {template['description']}")
            print(f"  Confidence: {template['confidence']:.0%}")
            print(f"  Patterns: {json.dumps(template['patterns'], indent=4)}")
        return

    if args.create_template and args.addresses:
        addresses = [a.strip() for a in args.addresses.split(',')]
        template = create_template_from_entity(kg, args.create_template, addresses)
        print(json.dumps(template, indent=2))

        # Save to database
        save_template(template, kg)
        print(f"\nTemplate saved for: {args.create_template}")
        return

    if args.address:
        # Match single address
        entity = kg.get_entity(args.address)
        fp = kg.get_fingerprint(args.address)

        if not entity:
            print(f"Address not found: {args.address}")
            return

        # Merge data
        entity_data = {**entity}
        if fp:
            entity_data.update({
                'trading_style': fp.get('trading_style'),
                'risk_profile': fp.get('risk_profile'),
                'gas_strategy': fp.get('gas_strategy'),
                'activity_pattern': fp.get('activity_pattern')
            })

        # Get cluster size
        if entity.get('cluster_id'):
            conn = kg.connect()
            cluster = conn.execute(
                "SELECT COUNT(*) FROM entities WHERE cluster_id = ?",
                (entity['cluster_id'],)
            ).fetchone()
            entity_data['cluster_size'] = cluster[0] if cluster else 0

        print(f"\nMatching patterns for: {args.address}")
        print("="*60)

        for template_id, template in ENTITY_TEMPLATES.items():
            matches, score, criteria = match_template(entity_data, template)
            if matches:
                print(f"\n{template['name']} ({template_id})")
                print(f"  Score: {score:.0%}")
                print(f"  Confidence: {template['confidence'] * score:.0%}")
                print(f"  Matched criteria: {criteria}")

        # Show evidence
        evidence = kg.get_evidence(args.address)
        if evidence:
            print("\nEvidence:")
            for ev in evidence:
                print(f"  [{ev['source']}] {ev['claim']} ({ev['confidence']:.0%})")

        final_conf, _ = aggregate_evidence_score(kg, args.address)
        print(f"\nFinal confidence: {final_conf:.0%}")
        return

    # Default: run full pattern matching
    match_patterns(kg)
    kg.close()


if __name__ == "__main__":
    main()
