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
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

# ============================================================================
# Configuration
# ============================================================================

# Relationship type weights - how much confidence decays per hop
# UPDATED based on cluster contamination audit - reduced CIO weights
RELATIONSHIP_WEIGHTS = {
    'same_entity': 0.95,        # Verified same entity
    'same_signer': 0.95,        # Same Safe signer (very strong)
    'shared_deposits': 0.90,    # Same exchange deposit addresses
    'same_cluster': 0.85,       # Part of detected cluster (reduced from 0.90)
    'temporal_correlation': 0.85,  # Same-operator timing
    'counterparty_overlap': 0.70,  # Similar counterparties (reduced from 0.80)
    'cio_common_funder': 0.50,  # CIO via common funder (NEW - low weight)
    'funded_by': 0.50,          # Funding relationship (reduced from 0.75)
    'delegated_to': 0.70,       # Governance delegation
    'traded_with': 0.40,        # Just transacted (weak)
}

# Minimum confidence to continue propagation
MIN_PROPAGATION_CONFIDENCE = 0.30

# Maximum hops from seed
MAX_HOPS = 4

# Minimum confidence to apply a label
MIN_LABEL_CONFIDENCE = 0.40

# ============================================================================
# Timezone Validation Gate (Phase 2 Improvement)
# ============================================================================
# Prevents cluster contamination by validating timezone compatibility
# before propagating labels. Key insight: UK fund can't operate from UTC+7.

# Known entity expected timezones (for validation)
KNOWN_ENTITY_TIMEZONES = {
    'Abraxas Capital': ['UTC+0', 'UTC+1'],  # UK-based
    'Celsius Network': ['UTC-5', 'UTC-4', 'UTC-3', 'UTC-6'],  # US-based (NJ)
    'Trend Research': ['UTC+8', 'UTC+7'],  # Asia-Pacific (Jack Yi)
    'Coinbase': ['UTC-8', 'UTC-7', 'UTC-5'],  # US-based
    'Binance': ['UTC+8', 'UTC+0'],  # Global, HQ in various locations
    'FTX': ['UTC-5', 'UTC-4'],  # Was Bahamas-based
}

# Timezone tolerance for validation (hours)
# Based on cluster contamination audit: UTC+7 addresses wrongly labeled as UK funds
# Tightened to prevent regional mismatches (UK fund can't operate from South America)
TIMEZONE_TOLERANCE_STRICT = 1   # Same region (UK/EU, East Coast US, etc.)
TIMEZONE_TOLERANCE_LOOSE = 2    # Adjacent regions (still likely same operator)


def parse_timezone_offset(tz_str: str) -> Optional[int]:
    """Parse timezone string like 'UTC+8' or 'UTC-5' to integer offset."""
    if not tz_str:
        return None
    match = re.match(r'UTC([+-]?\d+)', tz_str)
    if match:
        return int(match.group(1))
    return None


def get_timezone_from_evidence(kg: 'KnowledgeGraph', address: str) -> Optional[str]:
    """Get timezone from behavioral evidence in knowledge graph."""
    conn = kg.connect()
    # Don't limit to 1 - iterate through all behavioral evidence to find timezone
    cursor = conn.execute(
        """SELECT claim, raw_data FROM evidence
           WHERE entity_address = ?
           AND (source = 'Behavioral' OR source LIKE '%timezone%' OR source LIKE '%fingerprint%')
           ORDER BY confidence DESC LIMIT 10""",
        (address.lower(),)
    )

    for row in cursor.fetchall():
        claim, raw_data = row

        # Try to extract from raw_data JSON first (most reliable)
        if raw_data:
            try:
                data = json.loads(raw_data)
                if 'timing' in data and 'timezone_signal' in data['timing']:
                    return data['timing']['timezone_signal']
                if 'timezone_signal' in data:
                    return data['timezone_signal']
            except (json.JSONDecodeError, TypeError):
                pass

        # Try to extract from claim text as fallback
        if claim:
            # Match "Timezone: UTC+X" or "UTC-X timezone"
            match = re.search(r'Timezone:\s*(UTC[+-]?\d+)', claim)
            if match:
                return match.group(1)
            match = re.search(r'(UTC[+-]?\d+)\s+timezone', claim)
            if match:
                return match.group(1)

    return None


def get_expected_timezone_for_identity(identity: str) -> Optional[List[str]]:
    """Get expected timezone(s) for a known entity identity."""
    if not identity:
        return None

    # Check exact matches first
    for entity, timezones in KNOWN_ENTITY_TIMEZONES.items():
        if entity.lower() in identity.lower():
            return timezones

    # Check for region hints in identity
    identity_lower = identity.lower()
    if 'uk' in identity_lower or 'british' in identity_lower or 'london' in identity_lower:
        return ['UTC+0', 'UTC+1']
    if 'asia' in identity_lower or 'singapore' in identity_lower or 'hong kong' in identity_lower:
        return ['UTC+8', 'UTC+7', 'UTC+9']
    if 'europe' in identity_lower or 'eu' in identity_lower:
        return ['UTC+0', 'UTC+1', 'UTC+2']
    if 'us' in identity_lower or 'america' in identity_lower or 'new york' in identity_lower:
        return ['UTC-5', 'UTC-4', 'UTC-6', 'UTC-7', 'UTC-8']

    return None


def calculate_timezone_difference(tz1: str, tz2: str) -> int:
    """Calculate absolute hour difference between two timezones."""
    offset1 = parse_timezone_offset(tz1)
    offset2 = parse_timezone_offset(tz2)

    if offset1 is None or offset2 is None:
        return 999  # Unknown - assume incompatible

    diff = abs(offset1 - offset2)
    # Handle wraparound (e.g., UTC+12 and UTC-12 are close)
    if diff > 12:
        diff = 24 - diff
    return diff


def validate_timezone_compatibility(
    source_identity: str,
    source_timezone: Optional[str],
    target_timezone: Optional[str],
    relationship_type: str
) -> Tuple[bool, float, str]:
    """
    Validate if target timezone is compatible with source identity.

    Returns:
        (is_valid, confidence_multiplier, warning_message)

    Confidence multipliers:
        1.0 = timezone matches expected
        0.7 = timezone close (within tolerance)
        0.3 = timezone mismatch (contamination risk)
        0.0 = reject propagation
    """
    # If we can't determine timezones, allow with reduced confidence
    if not target_timezone or target_timezone == 'unknown':
        return True, 0.6, "Target timezone unknown - reduced confidence"

    # Get expected timezones for the source identity
    expected_timezones = get_expected_timezone_for_identity(source_identity)

    if not expected_timezones:
        # No expected timezone for this identity - use source timezone if available
        if source_timezone:
            diff = calculate_timezone_difference(source_timezone, target_timezone)
            if diff <= TIMEZONE_TOLERANCE_STRICT:
                return True, 1.0, ""
            elif diff <= TIMEZONE_TOLERANCE_LOOSE:
                return True, 0.7, f"Timezone {target_timezone} is {diff}h from source {source_timezone}"
            else:
                return False, 0.3, f"TIMEZONE MISMATCH: {target_timezone} vs expected {source_timezone} (diff={diff}h)"
        else:
            return True, 0.8, "No timezone validation possible"

    # Check if target timezone matches any expected
    target_offset = parse_timezone_offset(target_timezone)
    if target_offset is None:
        return True, 0.6, "Cannot parse target timezone"

    # Check against all expected timezones
    min_diff = 999
    for expected_tz in expected_timezones:
        diff = calculate_timezone_difference(expected_tz, target_timezone)
        min_diff = min(min_diff, diff)

    if min_diff <= TIMEZONE_TOLERANCE_STRICT:
        return True, 1.0, ""
    elif min_diff <= TIMEZONE_TOLERANCE_LOOSE:
        return True, 0.7, f"Timezone {target_timezone} close to expected {expected_timezones}"
    else:
        # TIMEZONE MISMATCH - this is likely contamination
        warning = f"TIMEZONE MISMATCH: {target_timezone} vs expected {expected_timezones} for {source_identity}"
        return False, 0.3, warning


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
    labels_rejected_timezone: int  # NEW: labels rejected due to timezone mismatch
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
    validate_timezone: bool = True,
    verbose: bool = True
) -> PropagationStats:
    """
    Propagate an identity from a seed address through the relationship graph.

    Uses BFS with confidence decay based on relationship type.
    INCLUDES TIMEZONE VALIDATION GATE (Phase 2 improvement).

    Args:
        kg: Knowledge graph instance
        seed_address: Starting address with known identity
        identity: The identity to propagate
        seed_confidence: Confidence of the seed identity (default 1.0)
        max_hops: Maximum hops from seed
        min_confidence: Stop propagating when confidence drops below this
        apply_labels: Whether to actually apply labels to the knowledge graph
        validate_timezone: Whether to validate timezone compatibility (default True)
        verbose: Print progress

    Returns:
        PropagationStats with results
    """
    seed_address = seed_address.lower()

    if verbose:
        print(f"\n  Propagating '{identity}' from {seed_address[:16]}...")
        print(f"  Seed confidence: {seed_confidence:.0%}, Max hops: {max_hops}")
        if validate_timezone:
            print(f"  Timezone validation: ENABLED")

    # Get seed timezone for validation
    seed_timezone = get_timezone_from_evidence(kg, seed_address) if validate_timezone else None

    # BFS queue: (address, confidence, hops, path, relationship_chain)
    queue = deque([(seed_address, seed_confidence, 0, [seed_address], [])])

    # Track visited with best confidence seen
    visited: Dict[str, float] = {seed_address: seed_confidence}

    # Results
    results: List[PropagationResult] = []
    labels_applied = 0
    labels_rejected_timezone = 0
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

            # ================================================================
            # TIMEZONE VALIDATION GATE (Phase 2 Improvement)
            # ================================================================
            # Before applying a label, validate timezone compatibility.
            # This prevents cluster contamination (e.g., UK fund labeled on UTC+7 address)

            timezone_warning = ""
            if validate_timezone and new_confidence >= MIN_LABEL_CONFIDENCE:
                target_timezone = get_timezone_from_evidence(kg, other)

                is_valid, tz_multiplier, tz_warning = validate_timezone_compatibility(
                    source_identity=identity,
                    source_timezone=seed_timezone,
                    target_timezone=target_timezone,
                    relationship_type=rel_type
                )

                if not is_valid:
                    # TIMEZONE MISMATCH - reduce confidence significantly
                    new_confidence *= tz_multiplier
                    timezone_warning = tz_warning
                    labels_rejected_timezone += 1

                    if verbose:
                        print(f"    ⚠️  {other[:16]}... TIMEZONE REJECTED: {tz_warning}")

                    # Don't apply label, but still add to visited and continue propagation
                    # (in case there are other paths)
                    visited[other] = new_confidence
                    continue

                elif tz_multiplier < 1.0:
                    # Timezone close but not exact - apply multiplier
                    new_confidence *= tz_multiplier
                    timezone_warning = tz_warning

            # ================================================================

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
                        tz_note = f" [{timezone_warning}]" if timezone_warning else ""
                        print(f"    → {other[:16]}... = '{propagated_identity}' ({new_confidence:.0%}){tz_note}")

                # Add evidence regardless
                evidence_data = {
                    'source_identity': identity,
                    'source_address': seed_address,
                    'hops': hops + 1,
                    'path': path + [other],
                    'relationship_chain': rel_chain + [rel_type]
                }
                if timezone_warning:
                    evidence_data['timezone_warning'] = timezone_warning

                kg.add_evidence(
                    other,
                    source='Propagation',
                    claim=f"Connected to {identity} via {' → '.join(rel_chain + [rel_type])}",
                    confidence=new_confidence,
                    raw_data=evidence_data
                )

            # Add to queue for further propagation
            queue.append((other, new_confidence, hops + 1, path + [other], rel_chain + [rel_type]))

    stats = PropagationStats(
        seed_address=seed_address,
        seed_identity=identity,
        seed_confidence=seed_confidence,
        addresses_reached=len(visited) - 1,  # Exclude seed
        labels_applied=labels_applied,
        labels_rejected_timezone=labels_rejected_timezone,
        max_hops_used=max_hops_used,
        propagation_paths=results
    )

    if verbose:
        print(f"\n  Propagation complete:")
        print(f"    Addresses reached: {stats.addresses_reached}")
        print(f"    Labels applied: {stats.labels_applied}")
        if stats.labels_rejected_timezone > 0:
            print(f"    Labels rejected (timezone): {stats.labels_rejected_timezone}")
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
    total_labels_rejected_tz = 0

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
            validate_timezone=True,
            verbose=False  # Suppress individual output
        )

        all_stats[address] = stats
        total_labels_applied += stats.labels_applied
        total_labels_rejected_tz += stats.labels_rejected_timezone

        if verbose and stats.labels_applied > 0:
            tz_note = f" ({stats.labels_rejected_timezone} tz rejected)" if stats.labels_rejected_timezone > 0 else ""
            print(f"  {identity[:30]}: propagated to {stats.labels_applied} addresses{tz_note}")

    if verbose:
        print(f"\n" + "="*60)
        print(f"PROPAGATION COMPLETE")
        print(f"  Seeds processed: {len(identified)}")
        print(f"  Labels applied: {total_labels_applied}")
        if total_labels_rejected_tz > 0:
            print(f"  Labels rejected (timezone): {total_labels_rejected_tz}")
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
