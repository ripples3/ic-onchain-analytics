#!/usr/bin/env python3
"""
Arkham Intelligence Address Resolver

Batch-resolves wallet addresses to real-world entity identities using Arkham's API.
Uses batch endpoint (up to 1,000 addresses per request) for efficiency.

Usage:
    # Resolve from CSV (needs 'address' or 'borrower' column)
    python3 scripts/arkham_resolver.py data/raw/whale_addresses_full.csv -o results.csv

    # Single address
    python3 scripts/arkham_resolver.py --address 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

    # Update knowledge graph with findings
    python3 scripts/arkham_resolver.py data/raw/whale_addresses_full.csv --update-kg

    # Dry run
    python3 scripts/arkham_resolver.py data/raw/whale_addresses_full.csv --dry-run

Environment:
    ARKHAM_API_KEY - Required. Get from https://intel.arkm.com/api
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    script_dir = Path(__file__).parent
    for env_path in [script_dir / ".env", script_dir.parent / ".env"]:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "knowledge_graph.db"

API_BASE = "https://api.arkhamintelligence.com"
BATCH_SIZE = 1000
BATCH_DELAY = 2.0  # seconds between batch requests
REQUEST_TIMEOUT = 30


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ArkhamProfile:
    """Resolved identity from Arkham."""
    address: str
    entity_name: str = ""
    entity_id: str = ""
    entity_type: str = ""  # individual, organization, service, etc.
    label_name: str = ""
    twitter: str = ""
    linkedin: str = ""
    crunchbase: str = ""
    website: str = ""
    note: str = ""
    is_contract: bool = False

    @property
    def has_identity(self) -> bool:
        return bool(self.entity_name)

    @property
    def identity_summary(self) -> str:
        parts = [self.entity_name]
        if self.entity_type:
            parts[0] += f" ({self.entity_type})"
        if self.twitter:
            parts.append(f"@{self.twitter}")
        if self.linkedin:
            parts.append("LinkedIn")
        return " | ".join(parts)


# ============================================================================
# API Client
# ============================================================================

def resolve_batch(addresses: list[str], api_key: str) -> dict[str, ArkhamProfile]:
    """Resolve a batch of addresses via Arkham batch API (max 1000)."""
    profiles = {}
    headers = {"API-Key": api_key, "Content-Type": "application/json"}

    url = f"{API_BASE}/intelligence/address/batch"
    try:
        resp = requests.post(url, headers=headers, json={"addresses": addresses},
                             timeout=REQUEST_TIMEOUT)

        if resp.status_code == 429:
            print("  ⚠️  Rate limited, waiting 30s...")
            time.sleep(30)
            resp = requests.post(url, headers=headers, json={"addresses": addresses},
                                 timeout=REQUEST_TIMEOUT)

        if resp.status_code == 401:
            print("❌ Invalid API key. Check ARKHAM_API_KEY in .env")
            sys.exit(1)

        if resp.status_code != 200:
            print(f"  ⚠️  Arkham returned {resp.status_code}: {resp.text[:200]}")
            return profiles

        data = resp.json()
        addr_data = data.get("addresses", data)  # handle both formats

        for addr_key, info in addr_data.items():
            addr = info.get("address", addr_key).lower()
            entity = info.get("arkhamEntity") or {}
            label = info.get("arkhamLabel") or {}

            twitter = entity.get("twitter", "") or ""
            # Extract handle from URL
            if "twitter.com/" in twitter:
                twitter = twitter.rstrip("/").split("/")[-1]
            elif "x.com/" in twitter:
                twitter = twitter.rstrip("/").split("/")[-1]

            linkedin = entity.get("linkedin", "") or ""
            crunchbase = entity.get("crunchbase", "") or ""
            website = entity.get("website", "") or ""

            profile = ArkhamProfile(
                address=addr,
                entity_name=entity.get("name", ""),
                entity_id=entity.get("id", ""),
                entity_type=entity.get("type", ""),
                label_name=label.get("name", ""),
                twitter=twitter,
                linkedin=linkedin,
                crunchbase=crunchbase,
                website=website,
                note=entity.get("note", ""),
                is_contract=info.get("contract", False),
            )
            profiles[addr] = profile

    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  Arkham API error: {e}")

    return profiles


# ============================================================================
# Pipeline
# ============================================================================

def resolve_all(addresses: list[str], api_key: str) -> list[ArkhamProfile]:
    """Resolve all addresses in batches of 1000."""
    all_profiles = {}
    unique_addrs = list(set(addresses))
    total_batches = (len(unique_addrs) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n📡 Arkham batch API ({len(unique_addrs)} addresses, {total_batches} batches)")

    total_hits = 0
    for i in range(0, len(unique_addrs), BATCH_SIZE):
        batch = unique_addrs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} addresses)...", end=" ", flush=True)

        profiles = resolve_batch(batch, api_key)
        hits = sum(1 for p in profiles.values() if p.has_identity)
        total_hits += hits
        all_profiles.update(profiles)
        print(f"{hits} identified")

        if i + BATCH_SIZE < len(unique_addrs):
            time.sleep(BATCH_DELAY)

    # Create profiles for addresses not in response
    for addr in unique_addrs:
        if addr.lower() not in all_profiles:
            all_profiles[addr.lower()] = ArkhamProfile(address=addr.lower())

    resolved = [p for p in all_profiles.values() if p.has_identity]
    print(f"\n{'='*60}")
    print(f"📊 Results: {len(resolved)}/{len(unique_addrs)} identified ({100*len(resolved)//max(len(unique_addrs),1)}%)")

    if resolved:
        print(f"\n{'Address':<44} {'Entity':<30} {'Type':<15} {'Twitter'}")
        print("-" * 110)
        for p in sorted(resolved, key=lambda x: x.entity_name.lower()):
            tw = f"@{p.twitter}" if p.twitter else ""
            print(f"{p.address[:42]:<44} {p.entity_name[:28]:<30} {p.entity_type:<15} {tw}")

    return list(all_profiles.values())


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def update_knowledge_graph(profiles: list[ArkhamProfile]) -> int:
    """Update KG with Arkham identities."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from build_knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph(str(DB_PATH))
    updated = 0

    for p in profiles:
        if not p.has_identity:
            continue

        kg.add_entity(p.address, identity=p.entity_name)

        # Arkham is high confidence
        confidence = 0.85
        if p.entity_type == "individual" and p.twitter:
            confidence = 0.95
        elif p.entity_type == "organization":
            confidence = 0.90

        claim_parts = [f"Arkham entity: {p.entity_name}"]
        if p.entity_type:
            claim_parts.append(f"Type: {p.entity_type}")
        if p.twitter:
            claim_parts.append(f"Twitter: @{p.twitter}")
        if p.linkedin:
            claim_parts.append(f"LinkedIn: {p.linkedin}")
        if p.label_name:
            claim_parts.append(f"Label: {p.label_name}")

        kg.add_evidence(
            address=p.address,
            source="arkham_resolver",
            claim="; ".join(claim_parts),
            confidence=confidence,
            raw_data=asdict(p),
        )
        updated += 1

    print(f"\n🗄️  Knowledge graph: {updated} entities updated")
    return updated


# ============================================================================
# Input / Output
# ============================================================================

def load_addresses_from_csv(filepath: str) -> list[str]:
    """Load addresses from CSV. Checks 'address' then 'borrower' column."""
    addresses = []
    with open(filepath) as f:
        # Skip non-header lines (dune metadata)
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if "address" in line.lower() or "borrower" in line.lower():
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    seen = set()
    for row in reader:
        addr = (row.get("address") or row.get("borrower") or "").strip()
        if addr and addr.startswith("0x") and addr.lower() not in seen:
            addresses.append(addr)
            seen.add(addr.lower())
    return addresses


def write_csv(profiles: list[ArkhamProfile], filepath: str) -> None:
    """Write results to CSV."""
    fieldnames = [
        "address", "entity_name", "entity_id", "entity_type", "label_name",
        "twitter", "linkedin", "crunchbase", "website", "note", "is_contract",
        "has_identity",
    ]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in sorted(profiles, key=lambda x: (not x.has_identity, x.entity_name.lower() if x.entity_name else "zzz")):
            writer.writerow({
                "address": p.address,
                "entity_name": p.entity_name,
                "entity_id": p.entity_id,
                "entity_type": p.entity_type,
                "label_name": p.label_name,
                "twitter": p.twitter,
                "linkedin": p.linkedin,
                "crunchbase": p.crunchbase,
                "website": p.website,
                "note": p.note,
                "is_contract": p.is_contract,
                "has_identity": p.has_identity,
            })
    print(f"\n💾 Results written to {filepath}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Arkham Intelligence Address Resolver")
    parser.add_argument("input", nargs="?", help="CSV file with addresses")
    parser.add_argument("-o", "--output", help="Output CSV path")
    parser.add_argument("--address", help="Resolve single address")
    parser.add_argument("--update-kg", action="store_true", help="Update knowledge graph")
    parser.add_argument("--dry-run", action="store_true", help="Show inputs only")
    args = parser.parse_args()

    api_key = os.environ.get("ARKHAM_API_KEY", "")
    if not api_key:
        print("❌ ARKHAM_API_KEY not set. Add it to .env")
        sys.exit(1)

    # Load addresses
    if args.address:
        addresses = [args.address]
    elif args.input:
        addresses = load_addresses_from_csv(args.input)
    else:
        print("Provide a CSV file or --address")
        sys.exit(1)

    if not addresses:
        print("No addresses found in input.")
        sys.exit(1)

    print(f"🔍 Arkham Resolver")
    print(f"   Addresses: {len(addresses)}")

    if args.dry_run:
        print(f"\n📋 Dry run — first 20 addresses:")
        for a in addresses[:20]:
            print(f"  {a}")
        if len(addresses) > 20:
            print(f"  ... and {len(addresses) - 20} more")
        return

    profiles = resolve_all(addresses, api_key)

    if args.output:
        write_csv(profiles, args.output)

    if args.update_kg:
        update_knowledge_graph(profiles)

    if not args.output:
        resolved = [p for p in profiles if p.has_identity]
        if resolved:
            print(f"\nTip: use -o results.csv to save, --update-kg to update knowledge graph")


if __name__ == "__main__":
    main()
