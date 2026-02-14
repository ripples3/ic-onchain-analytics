#!/usr/bin/env python3
"""
Cleanup over-aggressive label propagation in the knowledge graph.

Fixes:
1. Demote propagated-only labels involved in cross-cluster correlations
2. Strip labels with 3+ conflicting entity labels via temporal correlations
3. Fix Cluster #3 timezone spread - remove members with non-majority timezone
4. Log all changes
"""

import sqlite3
import json
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "knowledge_graph.db"
LOG_ENTRIES: list[str] = []


def log(msg: str) -> None:
    LOG_ENTRIES.append(msg)
    print(msg)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def normalize_identity(identity: str | None) -> str | None:
    """Strip the base identity from a propagated label."""
    if identity is None:
        return None
    # Handle double-propagated: "X (propagated) (propagated)" -> "X"
    base = identity.replace(" (propagated)", "")
    return base.strip() if base else None


def find_propagated_in_cross_cluster(conn: sqlite3.Connection) -> list[dict]:
    """
    Find all propagated entities that have temporal_correlation relationships
    with entities that have a DIFFERENT identity.
    Returns list of dicts with address, identity, and conflicting identities.
    """
    cur = conn.cursor()

    # Get all propagated entities
    cur.execute("SELECT address, identity, confidence FROM entities WHERE identity LIKE '%propagated%'")
    propagated = {row["address"]: dict(row) for row in cur.fetchall()}

    results = []
    for addr, entity in propagated.items():
        # Find all temporal_correlation partners with different identities
        cur.execute("""
            SELECT e2.identity
            FROM relationships r
            JOIN entities e2 ON (
                CASE WHEN r.source = ? THEN r.target ELSE r.source END
            ) = e2.address
            WHERE r.relationship_type = 'temporal_correlation'
            AND (r.source = ? OR r.target = ?)
            AND e2.identity IS NOT NULL
            AND e2.identity != 'Unknown'
        """, (addr, addr, addr))

        partner_identities = [row["identity"] for row in cur.fetchall()]

        # Normalize identities for comparison (strip "propagated" suffix)
        my_base = normalize_identity(entity["identity"])
        conflicting = set()
        for pid in partner_identities:
            partner_base = normalize_identity(pid)
            if partner_base and partner_base != my_base:
                conflicting.add(pid)

        if conflicting:
            results.append({
                "address": addr,
                "identity": entity["identity"],
                "confidence": entity["confidence"],
                "conflicting_identities": conflicting,
                "conflict_count": len(conflicting),
            })

    return results


def has_original_evidence(conn: sqlite3.Connection, address: str) -> bool:
    """
    Check if an address has any non-propagation evidence sources
    (Arkham, OSINT, ENS, Snapshot, Etherscan label, etc.)
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as cnt FROM evidence
        WHERE entity_address = ?
        AND source NOT IN ('Propagation', 'Pattern Match', 'Behavioral', 'CIO', 'CrossChain')
    """, (address,))
    row = cur.fetchone()
    return row["cnt"] > 0


def count_distinct_conflicting_labels(conflicting_identities: set[str]) -> int:
    """
    Count how many distinct base entity labels are in the conflicting set.
    E.g., "Binance User" and "Binance User (propagated)" count as 1.
    But "Binance User", "FTX User", "Celsius Network" count as 3.
    """
    base_labels = set()
    for identity in conflicting_identities:
        base = normalize_identity(identity)
        if base:
            base_labels.add(base)
    return len(base_labels)


def step1_demote_propagated_only(conn: sqlite3.Connection) -> int:
    """
    For addresses with ONLY propagated labels (no original evidence),
    demote identity to 'Unverified (previously: [old_label])' with confidence 0.35.
    Only applies to those involved in cross-cluster correlations.
    """
    log("\n" + "=" * 60)
    log("STEP 1: Demote propagated-only labels in cross-cluster correlations")
    log("=" * 60)

    cross_cluster = find_propagated_in_cross_cluster(conn)
    changes = 0
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    for entity in cross_cluster:
        addr = entity["address"]
        old_identity = entity["identity"]
        old_confidence = entity["confidence"]

        # Skip if this will be handled by step 2 (3+ conflicting labels)
        distinct_conflicts = count_distinct_conflicting_labels(entity["conflicting_identities"])
        if distinct_conflicts >= 3:
            continue

        # Check if it has original (non-propagation) evidence
        if has_original_evidence(conn, addr):
            log(f"  SKIP {addr[:16]}... has original evidence, keeping label")
            continue

        # Demote
        base_label = normalize_identity(old_identity)
        new_identity = f"Unverified (previously: {base_label})"
        new_confidence = 0.35

        cur.execute("""
            UPDATE entities
            SET identity = ?, confidence = ?, last_updated = ?
            WHERE address = ?
        """, (new_identity, new_confidence, now, addr))

        # Add evidence entry for the change
        cur.execute("""
            INSERT INTO evidence (entity_address, source, claim, confidence, raw_data, created_at)
            VALUES (?, 'Cleanup', ?, ?, ?, ?)
        """, (
            addr,
            f"Demoted from '{old_identity}' (conf={old_confidence:.3f}) - cross-cluster conflict with {distinct_conflicts} other label(s)",
            new_confidence,
            json.dumps({"old_identity": old_identity, "old_confidence": old_confidence,
                        "conflicting": list(entity["conflicting_identities"]),
                        "reason": "propagated_only_cross_cluster"}),
            now,
        ))

        changes += 1
        log(f"  DEMOTED {addr[:16]}...")
        log(f"    FROM: {old_identity} (conf={old_confidence:.3f})")
        log(f"    TO:   {new_identity} (conf={new_confidence})")
        log(f"    Conflicts with: {', '.join(sorted(entity['conflicting_identities']))}")

    log(f"\n  Total demoted: {changes}")
    return changes


def step2_strip_high_conflict(conn: sqlite3.Connection) -> int:
    """
    For addresses where propagated label conflicts with 3+ other distinct entity
    labels via temporal correlations, strip entirely and set to
    'Unknown (cluster conflict)' with confidence 0.20.
    """
    log("\n" + "=" * 60)
    log("STEP 2: Strip propagated labels with 3+ conflicting entity labels")
    log("=" * 60)

    cross_cluster = find_propagated_in_cross_cluster(conn)
    changes = 0
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    for entity in cross_cluster:
        addr = entity["address"]
        old_identity = entity["identity"]
        old_confidence = entity["confidence"]

        distinct_conflicts = count_distinct_conflicting_labels(entity["conflicting_identities"])
        if distinct_conflicts < 3:
            continue

        new_identity = "Unknown (cluster conflict)"
        new_confidence = 0.20

        cur.execute("""
            UPDATE entities
            SET identity = ?, confidence = ?, last_updated = ?
            WHERE address = ?
        """, (new_identity, new_confidence, now, addr))

        # Add evidence entry for the change
        cur.execute("""
            INSERT INTO evidence (entity_address, source, claim, confidence, raw_data, created_at)
            VALUES (?, 'Cleanup', ?, ?, ?, ?)
        """, (
            addr,
            f"Stripped '{old_identity}' (conf={old_confidence:.3f}) - conflicts with {distinct_conflicts} distinct entity labels",
            new_confidence,
            json.dumps({"old_identity": old_identity, "old_confidence": old_confidence,
                        "conflicting": list(entity["conflicting_identities"]),
                        "distinct_conflict_count": distinct_conflicts,
                        "reason": "high_conflict_propagated"}),
            now,
        ))

        changes += 1
        log(f"  STRIPPED {addr[:16]}...")
        log(f"    FROM: {old_identity} (conf={old_confidence:.3f})")
        log(f"    TO:   {new_identity} (conf={new_confidence})")
        log(f"    Conflicting labels ({distinct_conflicts}): {', '.join(sorted(entity['conflicting_identities']))}")

    log(f"\n  Total stripped: {changes}")
    return changes


def step3_fix_cluster3_timezones(conn: sqlite3.Connection) -> int:
    """
    Cluster #3 has 8 timezones across 13 members.
    Find the majority timezone and remove members that don't match.
    'Remove' means setting cluster_id to NULL (not deleting the entity).
    """
    log("\n" + "=" * 60)
    log("STEP 3: Fix Cluster #3 timezone spread")
    log("=" * 60)

    cur = conn.cursor()

    # Get cluster 3 members with their timezones
    cur.execute("""
        SELECT e.address, e.identity, e.confidence, b.timezone_signal
        FROM entities e
        LEFT JOIN behavioral_fingerprints b ON e.address = b.address
        WHERE e.cluster_id = 3
    """)
    members = [dict(row) for row in cur.fetchall()]

    # Count timezones
    tz_counts = Counter()
    for m in members:
        tz = m["timezone_signal"]
        if tz:
            tz_counts[tz] += 1

    log(f"  Cluster #3 members: {len(members)}")
    log(f"  Timezone distribution:")
    for tz, count in tz_counts.most_common():
        log(f"    {tz}: {count} members")

    # Majority timezone
    if not tz_counts:
        log("  ERROR: No timezone data for cluster #3")
        return 0

    majority_tz = tz_counts.most_common(1)[0][0]
    majority_count = tz_counts[majority_tz]
    log(f"  Majority timezone: {majority_tz} ({majority_count} members)")

    # Also consider identities: Trend Research is the dominant identity in this cluster
    identity_counts = Counter()
    for m in members:
        if m["identity"]:
            base = normalize_identity(m["identity"])
            identity_counts[base] += 1

    log(f"  Identity distribution:")
    for ident, count in identity_counts.most_common():
        log(f"    {ident}: {count} members")

    # The majority identity is "Trend Research (Jack Yi / LD Capital)" with
    # timezone spread across multiple zones. We keep the identity-based majority
    # and remove timezone outliers.
    # Strategy: Keep members whose identity is in the top identity group
    # AND whose timezone is within a reasonable range, OR remove by timezone mismatch.
    # Simplest approach: remove members whose timezone doesn't match majority.
    # But majority is only 3 (UTC-4). Let's be smarter: keep members whose
    # identity matches the dominant identity AND remove clearly wrong members.

    # Actually, let's look at this differently. The task says "remove members
    # whose timezone doesn't match the majority timezone". The majority tz
    # is the most common one. Let's find it.

    # With the data we have, UTC-4 has 3, UTC+2 has 3, etc.
    # Let's group by identity first and keep the dominant identity's members,
    # removing non-matching identities.
    dominant_identity = identity_counts.most_common(1)[0][0] if identity_counts else None
    log(f"\n  Dominant identity: {dominant_identity}")

    # Get timezones of the dominant identity members
    dominant_tzs = Counter()
    for m in members:
        base_ident = normalize_identity(m["identity"]) if m["identity"] else None
        if base_ident == dominant_identity and m["timezone_signal"]:
            dominant_tzs[m["timezone_signal"]] += 1

    log(f"  Timezones of '{dominant_identity}' members:")
    for tz, count in dominant_tzs.most_common():
        log(f"    {tz}: {count}")

    # The dominant identity has a wide tz spread itself. For the task requirement,
    # use the overall majority timezone.
    # Actually, the task simply says: "remove members whose timezone doesn't
    # match the majority timezone". Let's find THE majority (most common) tz.
    majority_tz = tz_counts.most_common(1)[0][0]
    log(f"\n  Using majority timezone: {majority_tz}")

    changes = 0
    now = datetime.now(timezone.utc).isoformat()

    for m in members:
        tz = m["timezone_signal"]
        if tz != majority_tz:
            addr = m["address"]
            cur.execute("""
                UPDATE entities SET cluster_id = NULL, last_updated = ? WHERE address = ?
            """, (now, addr))

            cur.execute("""
                INSERT INTO evidence (entity_address, source, claim, confidence, raw_data, created_at)
                VALUES (?, 'Cleanup', ?, ?, ?, ?)
            """, (
                addr,
                f"Removed from Cluster #3 - timezone {tz} doesn't match majority {majority_tz}",
                m["confidence"] if m["confidence"] else 0.0,
                json.dumps({"old_cluster": 3, "timezone": tz, "majority_tz": majority_tz,
                            "reason": "timezone_mismatch"}),
                now,
            ))

            changes += 1
            log(f"  REMOVED from Cluster #3: {addr[:16]}... | {m['identity']} | tz={tz}")

    # Log who remains
    log(f"\n  Removed {changes} members from Cluster #3")
    remaining = len(members) - changes
    log(f"  Remaining members: {remaining} (all {majority_tz})")

    return changes


def main() -> None:
    log("=" * 60)
    log("KNOWLEDGE GRAPH PROPAGATION CLEANUP")
    log(f"Started: {datetime.now(timezone.utc).isoformat()}")
    log(f"Database: {DB_PATH}")
    log("=" * 60)

    conn = get_conn()

    # Pre-cleanup stats
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM entities WHERE identity LIKE '%propagated%'")
    pre_propagated = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM entities")
    total_entities = cur.fetchone()[0]
    log(f"\nPre-cleanup: {pre_propagated} propagated labels out of {total_entities} entities")

    # Run steps (step 2 before step 1 so step 2 catches high-conflict first,
    # and step 1's skip logic works correctly)
    total_changes = 0
    stripped = step2_strip_high_conflict(conn)
    total_changes += stripped

    demoted = step1_demote_propagated_only(conn)
    total_changes += demoted

    cluster_removed = step3_fix_cluster3_timezones(conn)
    total_changes += cluster_removed

    # Post-cleanup stats
    cur.execute("SELECT COUNT(*) FROM entities WHERE identity LIKE '%propagated%'")
    post_propagated = cur.fetchone()[0]

    log("\n" + "=" * 60)
    log("CLEANUP SUMMARY")
    log("=" * 60)
    log(f"  Propagated labels stripped (3+ conflicts): {stripped}")
    log(f"  Propagated labels demoted (cross-cluster): {demoted}")
    log(f"  Cluster #3 members removed (timezone): {cluster_removed}")
    log(f"  Total changes: {total_changes}")
    log(f"  Propagated labels: {pre_propagated} -> {post_propagated}")
    log(f"  Reduction: {pre_propagated - post_propagated} labels cleaned")

    # Commit
    conn.commit()
    log("\nChanges committed to database.")

    # Write log file
    log_path = DB_PATH.parent / "cleanup_log.txt"
    with open(log_path, "w") as f:
        f.write("\n".join(LOG_ENTRIES))
    log(f"Log written to: {log_path}")

    conn.close()


if __name__ == "__main__":
    main()
