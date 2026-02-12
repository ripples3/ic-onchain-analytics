#!/usr/bin/env python3
"""
Label Propagation Algorithm

When you identify one wallet, propagate that identity through the relationship
graph with confidence decay. This is how Chainalysis scales - one identification
unlocks many more.

Key insight: If wallet A is identified as "Trend Research" and wallet B has:
- 90% temporal correlation with A
- 75% counterparty overlap with A
- Same cluster as A

Then B should inherit the "Trend Research" label with combined confidence.

Relationship Weights (confidence decay per hop):
- same_cluster: 0.90 (very strong - same entity cluster)
- temporal_correlation: 0.85 (strong - same operator timing)
- counterparty_overlap: 0.80 (strong - same counterparties)
- shared_deposits: 0.90 (very strong - same exchange user)
- funded_by: 0.75 (moderate - could be same entity or just funder)
- same_entity: 0.95 (verified same entity)
- traded_with: 0.40 (weak - just transacted)

Propagation Modes:
1. Forward: Start from identified → find related unknowns
2. Backward: Start from unknown → check if connected to identified
3. Full: Propagate all known identities through entire graph

Usage:
    # Propagate from a newly identified address
    python3 label_propagation.py --seed 0x1234... --identity "Trend Research"

    # Run full propagation on entire knowledge graph
    python3 label_propagation.py --full

    # Check what identities an unknown might inherit
    python3 label_propagation.py --check 0x5678...

    # Integration with knowledge graph
    from label_propagation import propagate_identity, run_full_propagation
    propagate_identity(kg, seed_address, identity, confidence)
"""

import argparse
import json
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

# ============================================================================
# Configuration
# ============================================================================

# Relationship type weights - how much confidence decays per hop
RELATIONSHIP_WEIGHTS = {
    'same_entity': 0.95,        # Verified same entity
    'same_cluster': 0.90,       # Part of detected cluster
    'shared_deposits': 0.90,    # Same exchange deposit addresses
    'temporal_correlation': 0.85,  # Same-operator timing
    'counterparty_overlap': 0.80,  # Similar counterparties
    'funded_by': 0.75,          # Funding relationship
    'delegated_to': 0.70,       # Governance delegation
    'traded_with': 0.40,        # Just transacted (weak)
}

# Minimum confidence to continue propagation
MIN_PROPAGATION_CONFIDENCE = 0.30

# Maximum hops from seed
MAX_HOPS = 4

# Minimum confidence to apply a label
MIN_LABEL_CONFIDENCE = 0.40


@dataclass
class PropagationResult:
    """Result of propagating a label to an address."""
    address: str
    identity: str
    confidence: float
    source_address: str
    hops: int
    path: List[str]
    relationship_chain: List[str]
    combined_weight: float


@dataclass
class PropagationStats:
    """Statistics from a propagation run."""
    seed_address: str
    seed_identity: str
    seed_confidence: float
    addresses_reached: int
    labels_applied: int
    max_hops_used: int
    propagation_paths: List[PropagationResult] = field(default_factory=list)


# ============================================================================
# Core Propagation Algorithm
# ============================================================================

def propagate_identity(
    kg: 'KnowledgeGraph',
    seed_address: str,
    identity: str,
    seed_confidence: float = 1.0,
    max_hops: int = MAX_HOPS,
    min_confidence: float = MIN_PROPAGATION_CONFIDENCE,
    apply_labels: bool = True,
    verbose: bool = True
) -> PropagationStats:
    """
    Propagate an identity from a seed address through the relationship graph.

    Uses BFS with confidence decay based on relationship type.

    Args:
        kg: Knowledge graph instance
        seed_address: Starting address with known identity
        identity: The identity to propagate
        seed_confidence: Confidence of the seed identity (default 1.0)
        max_hops: Maximum hops from seed
        min_confidence: Stop propagating when confidence drops below this
        apply_labels: Whether to actually apply labels to the knowledge graph
        verbose: Print progress

    Returns:
        PropagationStats with results
    """
    seed_address = seed_address.lower()

    if verbose:
        print(f"\n  Propagating '{identity}' from {seed_address[:16]}...")
        print(f"  Seed confidence: {seed_confidence:.0%}, Max hops: {max_hops}")

    # BFS queue: (address, confidence, hops, path, relationship_chain)
    queue = deque([(seed_address, seed_confidence, 0, [seed_address], [])])

    # Track visited with best confidence seen
    visited: Dict[str, float] = {seed_address: seed_confidence}

    # Results
    results: List[PropagationResult] = []
    labels_applied = 0
    max_hops_used = 0

    conn = kg.connect()

    while queue:
        current, confidence, hops, path, rel_chain = queue.popleft()

        if hops > max_hops:
            continue

        if confidence < min_confidence:
            continue

        max_hops_used = max(max_hops_used, hops)

        # Get all relationships for current address
        relationships = conn.execute(
            """SELECT source, target, relationship_type, confidence as rel_confidence, evidence
               FROM relationships
               WHERE source = ? OR target = ?""",
            (current, current)
        ).fetchall()

        for row in relationships:
            source, target, rel_type, rel_confidence, evidence = row

            # Determine the other address
            other = target if source == current else source

            # Skip if already visited with higher confidence
            if other in visited and visited[other] >= confidence:
                continue

            # Calculate new confidence
            rel_weight = RELATIONSHIP_WEIGHTS.get(rel_type, 0.5)
            rel_conf = rel_confidence if rel_confidence else 0.5

            # Combined decay: relationship weight * relationship confidence * current confidence
            new_confidence = confidence * rel_weight * rel_conf

            if new_confidence < min_confidence:
                continue

            # Update visited
            visited[other] = new_confidence

            # Create result
            result = PropagationResult(
                address=other,
                identity=identity,
                confidence=new_confidence,
                source_address=seed_address,
                hops=hops + 1,
                path=path + [other],
                relationship_chain=rel_chain + [rel_type],
                combined_weight=new_confidence / seed_confidence
            )
            results.append(result)

            # Apply label if confidence is sufficient and it's not the seed
            if apply_labels and new_confidence >= MIN_LABEL_CONFIDENCE and other != seed_address:
                # Check if address already has an identity
                entity = kg.get_entity(other)
                existing_identity = entity.get('identity') if entity else None

                if not existing_identity:
                    # Apply propagated label
                    propagated_identity = f"{identity} (propagated)"
                    kg.set_identity(other, propagated_identity, new_confidence)
                    labels_applied += 1

                    if verbose:
                        print(f"    → {other[:16]}... = '{propagated_identity}' ({new_confidence:.0%})")

                # Add evidence regardless
                kg.add_evidence(
                    other,
                    source='Propagation',
                    claim=f"Connected to {identity} via {' → '.join(rel_chain + [rel_type])}",
                    confidence=new_confidence,
                    raw_data={
                        'source_identity': identity,
                        'source_address': seed_address,
                        'hops': hops + 1,
                        'path': path + [other],
                        'relationship_chain': rel_chain + [rel_type]
                    }
                )

            # Add to queue for further propagation
            queue.append((other, new_confidence, hops + 1, path + [other], rel_chain + [rel_type]))

    stats = PropagationStats(
        seed_address=seed_address,
        seed_identity=identity,
        seed_confidence=seed_confidence,
        addresses_reached=len(visited) - 1,  # Exclude seed
        labels_applied=labels_applied,
        max_hops_used=max_hops_used,
        propagation_paths=results
    )

    if verbose:
        print(f"\n  Propagation complete:")
        print(f"    Addresses reached: {stats.addresses_reached}")
        print(f"    Labels applied: {stats.labels_applied}")
        print(f"    Max hops used: {stats.max_hops_used}")

    return stats


def check_identity_inheritance(
    kg: 'KnowledgeGraph',
    address: str,
    max_hops: int = MAX_HOPS,
    min_confidence: float = MIN_PROPAGATION_CONFIDENCE,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Check what identities an unknown address might inherit from the graph.

    Performs backward propagation from the unknown to find connected
    identified entities.

    Args:
        kg: Knowledge graph instance
        address: Address to check
        max_hops: Maximum hops to search
        min_confidence: Minimum confidence to consider
        verbose: Print progress

    Returns:
        List of potential inherited identities with confidence
    """
    address = address.lower()

    if verbose:
        print(f"\n  Checking identity inheritance for {address[:16]}...")

    # BFS from the target address
    queue = deque([(address, 1.0, 0, [address], [])])
    visited = {address: 1.0}

    # Found identities
    found_identities: List[Dict[str, Any]] = []

    conn = kg.connect()

    while queue:
        current, confidence, hops, path, rel_chain = queue.popleft()

        if hops > max_hops:
            continue

        if confidence < min_confidence:
            continue

        # Check if current address has an identity
        entity = conn.execute(
            "SELECT identity, confidence FROM entities WHERE address = ?",
            (current,)
        ).fetchone()

        if entity and entity[0] and current != address:
            existing_identity = entity[0]
            existing_confidence = entity[1] or 0.5

            # Don't inherit from other propagated labels
            if "(propagated)" not in existing_identity:
                combined_confidence = confidence * existing_confidence

                found_identities.append({
                    'identity': existing_identity,
                    'source_address': current,
                    'confidence': combined_confidence,
                    'hops': hops,
                    'path': path,
                    'relationship_chain': rel_chain
                })

                if verbose:
                    print(f"    Found: '{existing_identity}' via {hops} hops ({combined_confidence:.0%})")

        # Get relationships
        relationships = conn.execute(
            """SELECT source, target, relationship_type, confidence as rel_confidence
               FROM relationships
               WHERE source = ? OR target = ?""",
            (current, current)
        ).fetchall()

        for row in relationships:
            source, target, rel_type, rel_confidence = row
            other = target if source == current else source

            if other in visited and visited[other] >= confidence:
                continue

            rel_weight = RELATIONSHIP_WEIGHTS.get(rel_type, 0.5)
            rel_conf = rel_confidence if rel_confidence else 0.5
            new_confidence = confidence * rel_weight * rel_conf

            if new_confidence < min_confidence:
                continue

            visited[other] = new_confidence
            queue.append((other, new_confidence, hops + 1, path + [other], rel_chain + [rel_type]))

    # Sort by confidence
    found_identities.sort(key=lambda x: -x['confidence'])

    if verbose:
        if found_identities:
            print(f"\n  Found {len(found_identities)} potential identities")
        else:
            print(f"\n  No connected identities found within {max_hops} hops")

    return found_identities


def run_full_propagation(
    kg: 'KnowledgeGraph',
    max_hops: int = MAX_HOPS,
    min_confidence: float = MIN_PROPAGATION_CONFIDENCE,
    verbose: bool = True
) -> Dict[str, PropagationStats]:
    """
    Run label propagation from ALL identified entities.

    This updates the entire knowledge graph by propagating known
    identities to connected unknowns.

    Args:
        kg: Knowledge graph instance
        max_hops: Maximum hops for propagation
        min_confidence: Minimum confidence threshold
        verbose: Print progress

    Returns:
        Dict mapping seed addresses to their propagation stats
    """
    if verbose:
        print("\n" + "="*60)
        print("FULL LABEL PROPAGATION")
        print("="*60)

    conn = kg.connect()

    # Get all identified entities (excluding propagated labels)
    identified = conn.execute(
        """SELECT address, identity, confidence
           FROM entities
           WHERE identity IS NOT NULL
             AND identity != ''
             AND identity NOT LIKE '%(propagated)%'
           ORDER BY confidence DESC"""
    ).fetchall()

    if verbose:
        print(f"\nFound {len(identified)} seed identities")

    all_stats: Dict[str, PropagationStats] = {}
    total_labels_applied = 0

    for address, identity, confidence in identified:
        confidence = confidence if confidence else 0.7

        stats = propagate_identity(
            kg,
            address,
            identity,
            seed_confidence=confidence,
            max_hops=max_hops,
            min_confidence=min_confidence,
            apply_labels=True,
            verbose=False  # Suppress individual output
        )

        all_stats[address] = stats
        total_labels_applied += stats.labels_applied

        if verbose and stats.labels_applied > 0:
            print(f"  {identity[:30]}: propagated to {stats.labels_applied} addresses")

    if verbose:
        print(f"\n" + "="*60)
        print(f"PROPAGATION COMPLETE")
        print(f"  Seeds processed: {len(identified)}")
        print(f"  Labels applied: {total_labels_applied}")
        print("="*60)

    return all_stats


# ============================================================================
# Inverse Propagation: Find Unknown's Potential Identity
# ============================================================================

def suggest_identity(
    kg: 'KnowledgeGraph',
    address: str,
    verbose: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Suggest an identity for an unknown address based on graph connections.

    Combines evidence from:
    1. Direct relationships to identified entities
    2. Cluster membership with identified entities
    3. Behavioral similarity to identified entities

    Returns the strongest identity suggestion with confidence.
    """
    address = address.lower()

    if verbose:
        print(f"\n  Suggesting identity for {address[:16]}...")

    # Check existing identity
    entity = kg.get_entity(address)
    if entity and entity.get('identity'):
        if verbose:
            print(f"  Already identified as: {entity['identity']}")
        return {
            'identity': entity['identity'],
            'confidence': entity.get('confidence', 0.5),
            'source': 'existing'
        }

    # Find inherited identities
    inherited = check_identity_inheritance(kg, address, verbose=False)

    if not inherited:
        if verbose:
            print("  No identity suggestions found")
        return None

    # Take the highest confidence suggestion
    best = inherited[0]

    # Aggregate if multiple paths lead to same identity
    identity_scores: Dict[str, float] = defaultdict(float)
    identity_sources: Dict[str, List[dict]] = defaultdict(list)

    for item in inherited:
        identity = item['identity']
        # Use max confidence, not sum (to avoid over-counting)
        if item['confidence'] > identity_scores[identity]:
            identity_scores[identity] = item['confidence']
        identity_sources[identity].append(item)

    # Best identity
    best_identity = max(identity_scores, key=identity_scores.get)
    best_confidence = identity_scores[best_identity]
    best_sources = identity_sources[best_identity]

    suggestion = {
        'identity': best_identity,
        'confidence': best_confidence,
        'sources': best_sources,
        'alternative_identities': [
            {'identity': k, 'confidence': v}
            for k, v in sorted(identity_scores.items(), key=lambda x: -x[1])
            if k != best_identity
        ][:3]
    }

    if verbose:
        print(f"\n  Best suggestion: '{best_identity}' ({best_confidence:.0%})")
        print(f"  Based on {len(best_sources)} connection path(s)")
        if suggestion['alternative_identities']:
            print(f"  Alternatives: {[a['identity'] for a in suggestion['alternative_identities']]}")

    return suggestion


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_new_identification(kg: 'KnowledgeGraph', address: str, identity: str, confidence: float = 0.9):
    """
    Process a new identification by propagating the label through the graph.

    Call this whenever you identify a new entity to automatically update
    related addresses.
    """
    print(f"\n  Processing new identification: {address[:16]}... = '{identity}'")

    # First, set the identity on the seed
    kg.set_identity(address, identity, confidence)

    # Then propagate
    stats = propagate_identity(
        kg,
        address,
        identity,
        seed_confidence=confidence,
        apply_labels=True,
        verbose=True
    )

    return stats


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Label Propagation Algorithm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Propagate from a newly identified address
    python3 label_propagation.py --seed 0x1234... --identity "Trend Research"

    # Run full propagation on entire knowledge graph
    python3 label_propagation.py --full

    # Check what identities an unknown might inherit
    python3 label_propagation.py --check 0x5678...

    # Suggest identity for unknown
    python3 label_propagation.py --suggest 0x5678...
        """
    )

    parser.add_argument("--seed", help="Seed address to propagate from")
    parser.add_argument("--identity", help="Identity to propagate (required with --seed)")
    parser.add_argument("--confidence", type=float, default=0.9,
                        help="Confidence of seed identity (default: 0.9)")
    parser.add_argument("--full", action="store_true",
                        help="Run full propagation from all identified entities")
    parser.add_argument("--check", help="Check what identities an address might inherit")
    parser.add_argument("--suggest", help="Suggest identity for an unknown address")
    parser.add_argument("--max-hops", type=int, default=MAX_HOPS,
                        help=f"Maximum hops for propagation (default: {MAX_HOPS})")
    parser.add_argument("--min-confidence", type=float, default=MIN_PROPAGATION_CONFIDENCE,
                        help=f"Minimum confidence threshold (default: {MIN_PROPAGATION_CONFIDENCE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't apply labels, just show what would be propagated")

    args = parser.parse_args()

    # Import knowledge graph
    from build_knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    kg.connect()

    try:
        if args.seed:
            if not args.identity:
                parser.error("--identity required with --seed")

            stats = propagate_identity(
                kg,
                args.seed,
                args.identity,
                seed_confidence=args.confidence,
                max_hops=args.max_hops,
                min_confidence=args.min_confidence,
                apply_labels=not args.dry_run,
                verbose=True
            )

            if args.dry_run:
                print("\n[DRY RUN - no labels applied]")

            # Show detailed results
            if stats.propagation_paths:
                print(f"\n{'='*60}")
                print("PROPAGATION PATHS")
                print("="*60)

                for result in sorted(stats.propagation_paths, key=lambda x: -x.confidence)[:20]:
                    print(f"\n{result.address}")
                    print(f"  Confidence: {result.confidence:.0%}")
                    print(f"  Hops: {result.hops}")
                    print(f"  Path: {' → '.join([p[:10] + '...' for p in result.path])}")
                    print(f"  Relationships: {' → '.join(result.relationship_chain)}")

        elif args.full:
            all_stats = run_full_propagation(
                kg,
                max_hops=args.max_hops,
                min_confidence=args.min_confidence,
                verbose=True
            )

            # Summary
            total_reached = sum(s.addresses_reached for s in all_stats.values())
            total_applied = sum(s.labels_applied for s in all_stats.values())

            print(f"\nTotal addresses reached: {total_reached}")
            print(f"Total labels applied: {total_applied}")

        elif args.check:
            inherited = check_identity_inheritance(
                kg,
                args.check,
                max_hops=args.max_hops,
                min_confidence=args.min_confidence,
                verbose=True
            )

            if inherited:
                print(f"\n{'='*60}")
                print("POTENTIAL INHERITED IDENTITIES")
                print("="*60)

                for item in inherited:
                    print(f"\n'{item['identity']}'")
                    print(f"  Confidence: {item['confidence']:.0%}")
                    print(f"  Source: {item['source_address'][:16]}...")
                    print(f"  Hops: {item['hops']}")
                    print(f"  Path: {' → '.join([p[:10] + '...' for p in item['path']])}")

        elif args.suggest:
            suggestion = suggest_identity(kg, args.suggest, verbose=True)

            if suggestion:
                print(f"\n{'='*60}")
                print("IDENTITY SUGGESTION")
                print("="*60)
                print(f"\nSuggested: '{suggestion['identity']}'")
                print(f"Confidence: {suggestion['confidence']:.0%}")

                if suggestion.get('sources'):
                    print(f"\nBased on {len(suggestion['sources'])} connection(s):")
                    for src in suggestion['sources'][:3]:
                        print(f"  - Via {src['source_address'][:16]}... ({src['hops']} hops)")

                if suggestion.get('alternative_identities'):
                    print(f"\nAlternatives:")
                    for alt in suggestion['alternative_identities']:
                        print(f"  - '{alt['identity']}' ({alt['confidence']:.0%})")

        else:
            parser.print_help()

    finally:
        kg.close()


if __name__ == "__main__":
    main()
