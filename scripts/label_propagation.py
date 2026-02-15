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

    # Show confidence tier for an address
    python3 label_propagation.py --tier 0x5678...

    # Integration with knowledge graph
    from label_propagation import propagate_identity, run_full_propagation, calculate_confidence_tier
    propagate_identity(kg, seed_address, identity, confidence)
    tier_name, score = calculate_confidence_tier(address, kg)
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
    'change_address': 0.80,     # Change address pattern (same operator splitting funds)
    'deployed_by': 0.90,        # Contract deployer (very strong - same operator)
}

# Minimum confidence to continue propagation
MIN_PROPAGATION_CONFIDENCE = 0.30

# Maximum hops from seed
MAX_HOPS = 4

# Minimum confidence to apply a label
MIN_LABEL_CONFIDENCE = 0.35

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
    """Get expected timezone(s) for a known entity identity.

    Only returns timezone expectations for SPECIFIC KNOWN entities (Abraxas,
    Celsius, etc.) where we have independent confirmation of physical location.

    Does NOT infer timezone from generic region labels like "Asia-Pacific
    VC/Investment Fund" -- those labels WERE DERIVED FROM the timezone signal,
    so validating timezone against them is circular reasoning.
    """
    if not identity:
        return None

    # Check exact matches against known entities only
    for entity, timezones in KNOWN_ENTITY_TIMEZONES.items():
        if entity.lower() in identity.lower():
            return timezones

    # Do NOT infer from region keywords in identity names.
    # These identities (e.g., "Asia-Pacific DeFi Fund (UTC+7)") were themselves
    # derived from behavioral timezone analysis. Using them to validate timezone
    # is circular: the identity IS the timezone observation, not independent data.
    return None


def calculate_timezone_difference(tz1: str, tz2: str) -> int:
    """Calculate absolute hour difference between two timezones.
    Returns -1 if either timezone is unparseable (caller should treat as unknown,
    not as maximally incompatible)."""
    offset1 = parse_timezone_offset(tz1)
    offset2 = parse_timezone_offset(tz2)

    if offset1 is None or offset2 is None:
        return -1  # Unknown -- caller decides how to handle

    diff = abs(offset1 - offset2)
    # Handle wraparound (e.g., UTC+12 and UTC-12 are close)
    if diff > 12:
        diff = 24 - diff
    return diff


def validate_timezone_compatibility(
    source_identity: str,
    source_timezone: Optional[str],
    target_timezone: Optional[str],
    relationship_type: str,
    relationship_confidence: float = 0.5,
) -> Tuple[bool, float, str]:
    """
    Validate if target timezone is compatible with source identity.

    Returns:
        (is_valid, confidence_multiplier, warning_message)

    Confidence multipliers:
        1.0 = timezone matches expected
        0.85 = timezone unknown (no data to validate)
        0.7 = timezone close (within tolerance)
        0.5 = timezone mismatch but relationship is very strong (>=90%)
        0.3 = timezone mismatch with weak relationship (contamination risk)

    Key design decision (2026-02-15): timezone mismatch is a confidence
    penalty, NOT a hard block. Strong temporal correlations (>=90%) can
    overcome timezone mismatch because sophisticated operators use VPNs,
    travel, or run bots across timezones. The previous hard-block approach
    was rejecting 90% of propagation candidates and applying 0 new labels.
    """
    # If we can't determine target timezone, allow with mild penalty
    # Previously returned 0.6 -- too harsh for missing data
    if not target_timezone or target_timezone == 'unknown':
        return True, 0.85, "Target timezone unknown"

    # Get expected timezones for the source identity
    expected_timezones = get_expected_timezone_for_identity(source_identity)

    if not expected_timezones:
        # No expected timezone for this identity - use source timezone if available
        if source_timezone:
            diff = calculate_timezone_difference(source_timezone, target_timezone)
            if diff < 0:
                return True, 0.85, "Cannot compare timezones"
            if diff <= TIMEZONE_TOLERANCE_STRICT:
                return True, 1.0, ""
            elif diff <= TIMEZONE_TOLERANCE_LOOSE:
                return True, 0.7, f"Timezone {target_timezone} is {diff}h from source {source_timezone}"
            else:
                # Mismatch: penalize but allow if relationship is strong
                if relationship_confidence >= 0.90:
                    return True, 0.5, f"TZ mismatch ({target_timezone} vs {source_timezone}, diff={diff}h) overridden by strong relationship ({relationship_confidence:.0%})"
                else:
                    return True, 0.3, f"TZ mismatch: {target_timezone} vs {source_timezone} (diff={diff}h)"
        else:
            return True, 0.85, "No timezone validation possible"

    # Check if target timezone matches any expected
    target_offset = parse_timezone_offset(target_timezone)
    if target_offset is None:
        return True, 0.85, "Cannot parse target timezone"

    # Check against all expected timezones
    min_diff = 999
    for expected_tz in expected_timezones:
        diff = calculate_timezone_difference(expected_tz, target_timezone)
        if diff >= 0:
            min_diff = min(min_diff, diff)

    if min_diff == 999:
        # Could not compute any valid diff
        return True, 0.85, "Cannot compare timezones"

    if min_diff <= TIMEZONE_TOLERANCE_STRICT:
        return True, 1.0, ""
    elif min_diff <= TIMEZONE_TOLERANCE_LOOSE:
        return True, 0.7, f"Timezone {target_timezone} close to expected {expected_timezones}"
    else:
        # Timezone mismatch -- penalty depends on relationship strength
        warning = f"TZ mismatch: {target_timezone} vs expected {expected_timezones} for {source_identity}"
        if relationship_confidence >= 0.90:
            return True, 0.5, f"{warning} (overridden by strong relationship {relationship_confidence:.0%})"
        else:
            return True, 0.3, f"{warning}"


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
            # TIMEZONE VALIDATION GATE (Phase 2 Improvement, relaxed Phase 2.5)
            # ================================================================
            # Validates timezone compatibility and applies confidence penalty.
            # Key change (2026-02-15): mismatch is a penalty, NOT a hard block.
            # Strong relationships (>=90%) get a smaller penalty (0.5x vs 0.3x).
            #
            # Temporal correlations are EXEMPT from timezone validation because
            # they prove same-operator by definition (actions within seconds).
            # Behavioral timezone signals are noisy and the same operator can
            # show different peak-activity times across wallets.

            timezone_warning = ""
            tz_exempt_types = ('temporal_correlation', 'same_entity', 'same_signer',
                               'shared_deposits', 'deployed_by', 'change_address')

            if validate_timezone and new_confidence >= MIN_LABEL_CONFIDENCE and rel_type not in tz_exempt_types:
                target_timezone = get_timezone_from_evidence(kg, other)

                is_valid, tz_multiplier, tz_warning = validate_timezone_compatibility(
                    source_identity=identity,
                    source_timezone=seed_timezone,
                    target_timezone=target_timezone,
                    relationship_type=rel_type,
                    relationship_confidence=rel_conf,
                )

                # Always apply the multiplier (even on mismatch)
                if tz_multiplier < 1.0:
                    new_confidence *= tz_multiplier
                    timezone_warning = tz_warning

                    if tz_multiplier <= 0.3:
                        labels_rejected_timezone += 1
                        if verbose:
                            print(f"    ⚠️  {other[:16]}... TZ penalty {tz_multiplier}x: {tz_warning}")

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
                existing_confidence = entity.get('confidence', 0) if entity else 0

                # Determine if we should apply the new label:
                # 1. No existing identity
                # 2. Existing identity is a conflict/unverified/unknown placeholder
                # 3. Existing identity is a propagated label with lower confidence
                should_apply = False
                if not existing_identity:
                    should_apply = True
                elif 'cluster conflict' in existing_identity.lower():
                    should_apply = True  # Always overwrite conflicts
                elif 'unverified' in existing_identity.lower():
                    should_apply = new_confidence > existing_confidence
                elif '(propagated)' in existing_identity:
                    should_apply = new_confidence > existing_confidence

                if should_apply:
                    # Apply propagated label
                    propagated_identity = f"{identity} (propagated)"
                    kg.set_identity(other, propagated_identity, new_confidence)
                    labels_applied += 1

                    if verbose:
                        prev = f" [was: {existing_identity[:30]}]" if existing_identity else ""
                        tz_note = f" [{timezone_warning}]" if timezone_warning else ""
                        print(f"    → {other[:16]}... = '{propagated_identity}' ({new_confidence:.0%}){tz_note}{prev}")

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

    # Get all identified entities suitable as seeds.
    # Excludes: propagated labels, cluster conflicts, unverified placeholders.
    # These are not real identities and should not be used as propagation seeds.
    identified = conn.execute(
        """SELECT address, identity, confidence
           FROM entities
           WHERE identity IS NOT NULL
             AND identity != ''
             AND identity NOT LIKE '%(propagated)%'
             AND identity NOT LIKE '%Unknown%'
             AND identity NOT LIKE '%Unverified%'
             AND confidence >= 0.50
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
# Confidence Tier System (Improvement #3 from Cluster Contamination Retrospective)
# ============================================================================
# Replaces binary HIGH/MEDIUM/LOW with a 5-tier system that accounts for:
# 1. Source quality (Arkham/Nansen = highest trust)
# 2. Timezone consistency (prevents cross-region contamination)
# 3. Cross-cluster conflicts (detects label collisions)
#
# Tiers:
#   VERIFIED   (90-100%): Arkham/Nansen confirmed + behavioral match
#   VALIDATED  (70-89%):  Propagated + timezone match + no cross-cluster conflicts
#   CANDIDATE  (50-69%):  CIO/temporal link only, needs validation
#   UNVERIFIED (30-49%):  Propagated but timezone mismatch or conflicts
#   UNKNOWN    (0-29%):   No signals

# Trusted external verification sources
VERIFIED_SOURCES = {'Arkham', 'Nansen', 'arkham', 'nansen'}


def _has_verified_source(kg: 'KnowledgeGraph', address: str) -> bool:
    """Check if address has evidence from a trusted external source (Arkham/Nansen)."""
    conn = kg.connect()
    rows = conn.execute(
        """SELECT source FROM evidence
           WHERE entity_address = ?""",
        (address.lower(),)
    ).fetchall()

    for row in rows:
        source = row[0] if row[0] else ''
        # Match exact source or source containing the name (e.g., "Arkham Intelligence")
        for verified in VERIFIED_SOURCES:
            if verified.lower() in source.lower():
                return True
    return False


def _has_behavioral_match(kg: 'KnowledgeGraph', address: str) -> bool:
    """Check if address has behavioral evidence (timezone, fingerprint, etc.)."""
    conn = kg.connect()
    row = conn.execute(
        """SELECT COUNT(*) FROM evidence
           WHERE entity_address = ?
           AND (source = 'Behavioral' OR source LIKE '%fingerprint%'
                OR source LIKE '%timezone%')""",
        (address.lower(),)
    ).fetchone()
    return row[0] > 0 if row else False


def _check_cross_cluster_conflicts(kg: 'KnowledgeGraph', address: str) -> bool:
    """
    Check if an address has relationships to entities in different identity clusters.

    A conflict exists when an address is connected (via temporal correlation or
    other strong links) to entities that have different non-propagated identities.
    This is a strong signal of label contamination.

    Returns True if conflicts exist, False otherwise.
    """
    address = address.lower()
    conn = kg.connect()

    # Get all addresses related to this one via strong relationship types
    strong_types = ('temporal_correlation', 'same_cluster', 'same_entity',
                    'same_signer', 'shared_deposits')
    placeholders = ','.join(['?'] * len(strong_types))

    related = conn.execute(
        f"""SELECT DISTINCT
                CASE WHEN source = ? THEN target ELSE source END as other_addr
            FROM relationships
            WHERE (source = ? OR target = ?)
              AND relationship_type IN ({placeholders})
              AND confidence >= 0.7""",
        (address, address, address, *strong_types)
    ).fetchall()

    # Collect non-propagated identities from related addresses
    identities = set()
    for row in related:
        other = row[0]
        entity = conn.execute(
            """SELECT identity FROM entities
               WHERE address = ?
               AND identity IS NOT NULL
               AND identity != ''
               AND identity NOT LIKE '%(propagated)%'""",
            (other,)
        ).fetchone()
        if entity and entity[0]:
            # Normalize: strip suffixes like " (cluster member)" for comparison
            base_identity = entity[0].split(' (')[0].strip()
            identities.add(base_identity)

    # Also check the address's own identity
    own_entity = conn.execute(
        """SELECT identity FROM entities
           WHERE address = ?
           AND identity IS NOT NULL
           AND identity != ''
           AND identity NOT LIKE '%(propagated)%'""",
        (address,)
    ).fetchone()
    if own_entity and own_entity[0]:
        base_identity = own_entity[0].split(' (')[0].strip()
        identities.add(base_identity)

    # More than one distinct identity in the cluster = conflict
    return len(identities) > 1


def _check_timezone_consistency(kg: 'KnowledgeGraph', address: str) -> Optional[bool]:
    """
    Check if the address's timezone is consistent with its assigned identity.

    Returns:
        True  - timezone matches expected for identity
        False - timezone mismatch detected
        None  - cannot determine (no timezone data or no identity)
    """
    address = address.lower()
    conn = kg.connect()

    # Get the address's identity
    entity = conn.execute(
        "SELECT identity FROM entities WHERE address = ?",
        (address,)
    ).fetchone()

    if not entity or not entity[0]:
        return None

    identity = entity[0]
    # Strip propagated suffix for lookup
    base_identity = identity.replace(' (propagated)', '').strip()

    # Get the address's timezone
    target_tz = get_timezone_from_evidence(kg, address)
    if not target_tz:
        return None  # Can't validate without timezone data

    # Get expected timezone for the identity
    expected_timezones = get_expected_timezone_for_identity(base_identity)
    if not expected_timezones:
        return None  # Can't validate without expected timezone

    # Check if target timezone is within tolerance of any expected timezone
    target_offset = parse_timezone_offset(target_tz)
    if target_offset is None:
        return None

    for expected_tz in expected_timezones:
        diff = calculate_timezone_difference(expected_tz, target_tz)
        if diff >= 0 and diff <= TIMEZONE_TOLERANCE_LOOSE:
            return True

    return False


def calculate_confidence_tier(
    address: str,
    kg: 'KnowledgeGraph'
) -> Tuple[str, float]:
    """
    Calculate the confidence tier for an address based on multi-signal analysis.

    Replaces binary HIGH/MEDIUM/LOW with a 5-tier system:

    | Tier       | Confidence | Requirements                                     |
    |------------|------------|--------------------------------------------------|
    | VERIFIED   | 90-100%    | Arkham/Nansen confirmed + behavioral match        |
    | VALIDATED  | 70-89%     | Propagated + timezone match + no cross-cluster    |
    | CANDIDATE  | 50-69%     | CIO/temporal link only, needs validation           |
    | UNVERIFIED | 30-49%     | Propagated but timezone mismatch or conflicts      |
    | UNKNOWN    | 0-29%      | No signals                                         |

    Args:
        address: The Ethereum address to evaluate
        kg: KnowledgeGraph instance (must be connected)

    Returns:
        Tuple of (tier_name, confidence_score) e.g. ("VERIFIED", 0.95)
    """
    address = address.lower()
    conn = kg.connect()

    # Step 1: Check if entity exists and has any identity
    entity = conn.execute(
        "SELECT identity, confidence FROM entities WHERE address = ?",
        (address,)
    ).fetchone()

    has_identity = entity is not None and entity[0] is not None and entity[0] != ''
    existing_confidence = entity[1] if entity and entity[1] else 0.0

    if not has_identity:
        # No identity at all - check if there are any signals
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE entity_address = ?",
            (address,)
        ).fetchone()[0]

        if evidence_count == 0:
            return ("UNKNOWN", 0.0)
        else:
            # Has evidence but no identity assigned yet
            return ("UNKNOWN", min(0.29, existing_confidence))

    # Step 2: Check for Arkham/Nansen verification
    has_verified_source = _has_verified_source(kg, address)

    # Step 3: Check behavioral match
    has_behavioral = _has_behavioral_match(kg, address)

    # Step 4: Check timezone consistency
    tz_consistent = _check_timezone_consistency(kg, address)

    # Step 5: Check for cross-cluster conflicts
    has_conflicts = _check_cross_cluster_conflicts(kg, address)

    # ================================================================
    # Tier Assignment Logic
    # ================================================================

    # VERIFIED (90-100%): Arkham/Nansen confirmed + behavioral match
    if has_verified_source and has_behavioral:
        score = max(0.90, min(1.0, existing_confidence))
        return ("VERIFIED", score)

    # VERIFIED (90-95%): Arkham/Nansen confirmed even without behavioral
    # (Arkham alone is highly reliable)
    if has_verified_source:
        score = max(0.90, min(0.95, existing_confidence))
        return ("VERIFIED", score)

    # UNVERIFIED (30-49%): Any conflicts detected - demote regardless of other signals
    if has_conflicts:
        score = max(0.30, min(0.49, existing_confidence * 0.5))
        return ("UNVERIFIED", score)

    # UNVERIFIED (30-49%): Timezone mismatch detected
    if tz_consistent is False:  # Explicitly False, not None
        score = max(0.30, min(0.49, existing_confidence * 0.6))
        return ("UNVERIFIED", score)

    # VALIDATED (70-89%): Timezone matches + no conflicts
    if tz_consistent is True and not has_conflicts:
        score = max(0.70, min(0.89, existing_confidence))
        return ("VALIDATED", score)

    # CANDIDATE (50-69%): Has identity but can't fully validate
    # This covers: propagated labels without timezone data, CIO/temporal links
    # where timezone is unknown
    score = max(0.50, min(0.69, existing_confidence))
    return ("CANDIDATE", score)


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

    # Show confidence tier for an address
    python3 label_propagation.py --tier 0x5678...
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
    parser.add_argument("--tier", help="Show confidence tier for an address")
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

        elif args.tier:
            tier_name, tier_score = calculate_confidence_tier(args.tier, kg)

            # Tier display colors/indicators
            tier_indicators = {
                'VERIFIED':   '[++++]',
                'VALIDATED':  '[+++ ]',
                'CANDIDATE':  '[++  ]',
                'UNVERIFIED': '[+   ]',
                'UNKNOWN':    '[    ]',
            }
            indicator = tier_indicators.get(tier_name, '[    ]')

            print(f"\n{'='*60}")
            print("CONFIDENCE TIER ASSESSMENT")
            print("="*60)
            print(f"\nAddress: {args.tier.lower()}")

            # Show identity if available
            entity = kg.get_entity(args.tier)
            if entity and entity.get('identity'):
                print(f"Identity: {entity['identity']}")
                print(f"Stored confidence: {entity.get('confidence', 0.0):.0%}")

            print(f"\n{indicator} Tier: {tier_name}")
            print(f"     Score: {tier_score:.0%}")

            # Show tier explanation
            tier_explanations = {
                'VERIFIED':   'Confirmed by Arkham/Nansen with behavioral match',
                'VALIDATED':  'Propagated label with timezone match, no cross-cluster conflicts',
                'CANDIDATE':  'CIO/temporal link only - needs further validation',
                'UNVERIFIED': 'Timezone mismatch or cross-cluster conflicts detected',
                'UNKNOWN':    'No identity signals found',
            }
            print(f"     Basis: {tier_explanations.get(tier_name, 'N/A')}")

            # Show signal details
            print(f"\nSignal Details:")
            has_verified = _has_verified_source(kg, args.tier)
            has_behavioral = _has_behavioral_match(kg, args.tier)
            tz_consistent = _check_timezone_consistency(kg, args.tier)
            has_conflicts = _check_cross_cluster_conflicts(kg, args.tier)

            tz_display = {True: 'MATCH', False: 'MISMATCH', None: 'Unknown'}

            print(f"  Arkham/Nansen source: {'Yes' if has_verified else 'No'}")
            print(f"  Behavioral evidence:  {'Yes' if has_behavioral else 'No'}")
            print(f"  Timezone consistency: {tz_display[tz_consistent]}")
            print(f"  Cross-cluster conflicts: {'YES (contamination risk)' if has_conflicts else 'None'}")

            # Show tier table for reference
            print(f"\nTier Reference:")
            print(f"  VERIFIED   (90-100%): Arkham/Nansen confirmed + behavioral match")
            print(f"  VALIDATED  (70-89%):  Propagated + timezone match + no conflicts")
            print(f"  CANDIDATE  (50-69%):  CIO/temporal link only, needs validation")
            print(f"  UNVERIFIED (30-49%):  Timezone mismatch or conflicts")
            print(f"  UNKNOWN    (0-29%):   No signals")

        else:
            parser.print_help()

    finally:
        kg.close()


if __name__ == "__main__":
    main()
