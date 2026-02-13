#!/usr/bin/env python3
"""
Hub-First Investigation Strategy - 15:1 ROI methodology.

Key insight: Identify ONE hub address → unlock 15+ related addresses automatically.

Workflow:
1. PROFILE FIRST: Classify addresses to choose right investigation methods
2. HUB IDENTIFICATION: Find temporal correlation hubs (network analysis)
3. DEEP INVESTIGATE HUBS: Only 5-10 addresses get full pipeline
4. PROPAGATE: Use hub identities to label 30+ spoke addresses

Usage:
    # Find hubs in a set of addresses
    python3 scripts/investigate_hubs.py addresses.csv --find-hubs

    # Deep investigate specific hubs
    python3 scripts/investigate_hubs.py --hubs 0x1234...,0x5678...

    # Full pipeline: profile -> hubs -> investigate -> propagate
    python3 scripts/investigate_hubs.py addresses.csv --full

Based on: Phase 2 retrospective - Hub identification has 15:1 ROI
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import other investigation modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_graph.db")


def find_hubs_from_temporal(addresses: List[str], min_connections: int = 5) -> List[Dict]:
    """Find hub addresses based on temporal correlation network."""
    conn = sqlite3.connect(KG_PATH)
    cursor = conn.cursor()

    # Get temporal correlations for these addresses
    placeholders = ",".join(["?" for _ in addresses])
    cursor.execute(f"""
        SELECT source, target, confidence
        FROM relationships
        WHERE relationship_type = 'temporal_correlation'
        AND (source IN ({placeholders}) OR target IN ({placeholders}))
        AND confidence >= 0.8
    """, addresses + addresses)

    # Count connections per address
    connections = defaultdict(lambda: {"count": 0, "total_conf": 0.0, "partners": []})
    for source, target, conf in cursor.fetchall():
        connections[source]["count"] += 1
        connections[source]["total_conf"] += conf
        connections[source]["partners"].append(target)

        connections[target]["count"] += 1
        connections[target]["total_conf"] += conf
        connections[target]["partners"].append(source)

    conn.close()

    # Filter to hubs (many connections)
    hubs = []
    for addr, data in connections.items():
        if data["count"] >= min_connections:
            hubs.append({
                "address": addr,
                "connection_count": data["count"],
                "avg_confidence": data["total_conf"] / data["count"],
                "partners": list(set(data["partners"])),
            })

    # Sort by connection count
    hubs.sort(key=lambda x: x["connection_count"], reverse=True)
    return hubs


def get_hub_cluster(hub_address: str) -> List[str]:
    """Get all addresses connected to a hub."""
    conn = sqlite3.connect(KG_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT CASE WHEN source = ? THEN target ELSE source END as partner
        FROM relationships
        WHERE (source = ? OR target = ?)
        AND confidence >= 0.7
    """, (hub_address, hub_address, hub_address))

    partners = [row[0] for row in cursor.fetchall()]
    conn.close()

    return partners


def get_borrowed_amounts(addresses: List[str]) -> Dict[str, float]:
    """Get borrowed amounts for addresses from CSV."""
    borrowed = {}
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "top100_unidentified.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("borrower", "").lower()
                amount = float(row.get("total_borrowed_m", 0))
                borrowed[addr] = amount

    return {addr: borrowed.get(addr.lower(), 0) for addr in addresses}


def deep_investigate_hub(hub_address: str) -> Dict:
    """Run full investigation pipeline on a hub address."""
    result = {
        "address": hub_address,
        "profile": None,
        "funding_origin": None,
        "cluster_size": 0,
        "cluster_borrowed": 0.0,
        "identity": None,
        "confidence": 0.0,
    }

    # Get cluster
    cluster = get_hub_cluster(hub_address)
    result["cluster_size"] = len(cluster) + 1  # Include hub

    # Get borrowed amounts
    borrowed = get_borrowed_amounts([hub_address] + cluster)
    result["cluster_borrowed"] = sum(borrowed.values())

    # Check knowledge graph for existing identity
    conn = sqlite3.connect(KG_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT identity, confidence, entity_type
        FROM entities
        WHERE address = ?
    """, (hub_address,))
    row = cursor.fetchone()

    if row and row[0]:
        result["identity"] = row[0]
        result["confidence"] = row[1] or 0.5
        result["profile"] = row[2]

    # Check for funding evidence
    cursor.execute("""
        SELECT claim, confidence
        FROM evidence
        WHERE entity_address = ?
        AND (source LIKE '%funding%' OR source LIKE '%trace%' OR claim LIKE '%funded%')
        ORDER BY confidence DESC
        LIMIT 1
    """, (hub_address,))
    funding_row = cursor.fetchone()
    if funding_row:
        result["funding_origin"] = funding_row[0]

    conn.close()

    # If no identity yet, try to infer from cluster size
    if not result["identity"]:
        if result["cluster_size"] >= 10:
            result["identity"] = "Large Coordinated Entity"
            result["confidence"] = 0.50
        elif result["cluster_size"] >= 5:
            result["identity"] = "Coordinated Wallet Cluster"
            result["confidence"] = 0.45

    return result


def propagate_from_hub(hub_address: str, identity: str, confidence: float) -> int:
    """Propagate identity from hub to all connected addresses."""
    conn = sqlite3.connect(KG_PATH)
    cursor = conn.cursor()

    # Get partners
    partners = get_hub_cluster(hub_address)

    propagated = 0
    for partner in partners:
        # Calculate decayed confidence
        cursor.execute("""
            SELECT confidence FROM relationships
            WHERE (source = ? AND target = ?) OR (source = ? AND target = ?)
        """, (hub_address, partner, partner, hub_address))
        row = cursor.fetchone()
        rel_conf = row[0] if row else 0.7

        decayed_conf = confidence * rel_conf * 0.85  # Decay factor

        # Update entity if no higher confidence identity exists
        cursor.execute("""
            UPDATE entities
            SET identity = ?, confidence = ?, last_updated = ?
            WHERE address = ?
            AND (identity IS NULL OR confidence < ?)
        """, (f"{identity} (propagated)", decayed_conf, datetime.now().isoformat(),
              partner, decayed_conf))

        if cursor.rowcount > 0:
            propagated += 1

    conn.commit()
    conn.close()

    return propagated


def main():
    parser = argparse.ArgumentParser(description="Hub-first investigation strategy")
    parser.add_argument("input", nargs="?", help="CSV file with addresses")
    parser.add_argument("--find-hubs", action="store_true", help="Find hub addresses")
    parser.add_argument("--hubs", help="Comma-separated hub addresses to investigate")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--min-connections", type=int, default=5, help="Min connections for hub")
    parser.add_argument("-o", "--output", help="Output file")
    args = parser.parse_args()

    # Load addresses
    addresses = []
    if args.input and args.input.endswith(".csv"):
        with open(args.input, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("address") or row.get("borrower") or list(row.values())[0]
                addresses.append(addr.lower())

    if args.find_hubs or args.full:
        print(f"\n{'='*60}")
        print("FINDING HUB ADDRESSES")
        print(f"{'='*60}")

        hubs = find_hubs_from_temporal(addresses, args.min_connections)

        print(f"\nFound {len(hubs)} hub addresses:\n")
        for i, hub in enumerate(hubs[:10]):
            borrowed = get_borrowed_amounts([hub["address"]])
            cluster_addrs = hub["partners"]
            cluster_borrowed = sum(get_borrowed_amounts(cluster_addrs).values())

            print(f"{i+1}. {hub['address']}")
            print(f"   Connections: {hub['connection_count']}")
            print(f"   Avg confidence: {hub['avg_confidence']*100:.1f}%")
            print(f"   Hub borrowed: ${borrowed.get(hub['address'], 0):.1f}M")
            print(f"   Cluster total: ${cluster_borrowed:.1f}M ({len(cluster_addrs)} addresses)")
            print()

        if args.full and hubs:
            print(f"\n{'='*60}")
            print("DEEP INVESTIGATING TOP 5 HUBS")
            print(f"{'='*60}")

            results = []
            for hub in hubs[:5]:
                print(f"\nInvestigating {hub['address'][:16]}...")
                result = deep_investigate_hub(hub["address"])
                results.append(result)

                if result["identity"]:
                    print(f"  Identity: {result['identity']} ({result['confidence']*100:.0f}%)")
                    print(f"  Cluster: {result['cluster_size']} addresses, ${result['cluster_borrowed']:.1f}M")

                    # Propagate
                    propagated = propagate_from_hub(
                        hub["address"],
                        result["identity"],
                        result["confidence"]
                    )
                    print(f"  Propagated to: {propagated} addresses")

            print(f"\n{'='*60}")
            print("SUMMARY")
            print(f"{'='*60}")
            identified = sum(1 for r in results if r["identity"])
            total_propagated = sum(r.get("propagated", 0) for r in results)
            print(f"Hubs identified: {identified}/5")
            print(f"Total propagated: {total_propagated}")

    elif args.hubs:
        hub_list = [h.strip() for h in args.hubs.split(",")]
        print(f"\nDeep investigating {len(hub_list)} specified hubs...")

        for hub in hub_list:
            print(f"\n{'='*60}")
            result = deep_investigate_hub(hub)
            print(f"Hub: {hub}")
            print(f"Profile: {result.get('profile', {}).get('primary_profile', 'unknown')}")
            print(f"Cluster size: {result['cluster_size']}")
            print(f"Cluster borrowed: ${result['cluster_borrowed']:.1f}M")
            if result["identity"]:
                print(f"Identity: {result['identity']} ({result['confidence']*100:.0f}%)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
