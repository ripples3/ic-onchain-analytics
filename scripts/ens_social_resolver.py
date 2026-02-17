#!/usr/bin/env python3
"""
ENS-to-Social Identity Resolver

Resolves ENS names to real-world social identities using free APIs:
1. web3.bio batch API (aggregates ENS + Farcaster + Lens + Twitter + GitHub)
2. ensdata.net (ENS text records + Farcaster)
3. Neynar (Farcaster lookup by address)

Usage:
    # Resolve all ENS holders from knowledge graph
    python3 scripts/ens_social_resolver.py

    # Resolve from CSV (columns: address, ens_name)
    python3 scripts/ens_social_resolver.py input.csv -o results.csv

    # Single ENS name
    python3 scripts/ens_social_resolver.py --ens vitalik.eth

    # Single address
    python3 scripts/ens_social_resolver.py --address 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

    # Update knowledge graph with findings
    python3 scripts/ens_social_resolver.py --update-kg

    # Dry run (show what would be resolved, don't call APIs)
    python3 scripts/ens_social_resolver.py --dry-run
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
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "knowledge_graph.db"

# Rate limiting
WEB3BIO_DELAY = 1.0      # seconds between batch requests
ENSDATA_DELAY = 1.5       # seconds between requests (72h cache)
NEYNAR_DELAY = 0.5        # seconds between requests
REQUEST_TIMEOUT = 15      # seconds


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SocialProfile:
    """Resolved social identity for an address."""
    address: str
    ens_name: str
    # Social handles
    twitter: str = ""
    farcaster: str = ""
    github: str = ""
    lens: str = ""
    # Contact / identity
    email: str = ""
    website: str = ""
    display_name: str = ""
    bio: str = ""
    # Metadata
    sources: list = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

    @property
    def has_identity(self) -> bool:
        return bool(self.twitter or self.farcaster or self.github
                    or self.email or self.website)

    @property
    def identity_summary(self) -> str:
        parts = []
        if self.display_name:
            parts.append(self.display_name)
        if self.twitter:
            parts.append(f"@{self.twitter}")
        if self.farcaster:
            parts.append(f"fc:{self.farcaster}")
        if self.github:
            parts.append(f"gh:{self.github}")
        if self.email:
            parts.append(self.email)
        if self.website:
            parts.append(self.website)
        return " | ".join(parts) if parts else ""


# ============================================================================
# API Clients
# ============================================================================

def query_web3bio_single(identity: str) -> list[dict]:
    """Query web3.bio for a single identity (ENS name or address)."""
    url = f"https://api.web3.bio/profile/{identity}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "IndexCoop-Whale-Research/1.0"
        })
        if resp.status_code == 429:
            print("  ⚠️  web3.bio rate limited, waiting 10s...")
            time.sleep(10)
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
                "User-Agent": "IndexCoop-Whale-Research/1.0"
            })
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else [data]
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  web3.bio error: {e}")
        return []


def query_ensdata(ens_name: str) -> Optional[dict]:
    """Query ensdata.net for ENS text records + Farcaster."""
    url = f"https://ensdata.net/{ens_name}?farcaster=true"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "IndexCoop-Whale-Research/1.0"
        })
        if resp.status_code == 429:
            print(f"  ⚠️  ensdata.net rate limited")
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.exceptions.RequestException:
        return None


def query_neynar_by_address(address: str, api_key: str = None) -> Optional[dict]:
    """Query Neynar Farcaster API by custody address."""
    url = f"https://api.neynar.com/v2/farcaster/user/by_verification?address={address}"
    headers = {"User-Agent": "IndexCoop-Whale-Research/1.0"}
    if api_key:
        headers["api_key"] = api_key
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("result", {}).get("user"):
            return data["result"]["user"]
    except requests.exceptions.RequestException:
        pass
    return None


# ============================================================================
# Profile Extraction
# ============================================================================

def extract_from_web3bio(profiles: list[dict], profile: SocialProfile) -> None:
    """Extract social data from web3.bio response into SocialProfile."""
    for p in profiles:
        platform = p.get("platform", "").lower()
        identity = p.get("identity", "")
        display = p.get("displayName", "") or p.get("display_name", "")
        bio_text = p.get("description", "") or ""

        if display and not profile.display_name:
            profile.display_name = display
        if bio_text and not profile.bio:
            profile.bio = bio_text[:200]

        # Extract platform-specific handles
        if platform == "farcaster" and not profile.farcaster:
            profile.farcaster = identity.replace("@", "")
        elif platform == "lens" and not profile.lens:
            profile.lens = identity
        elif platform == "ens" or platform == "basenames":
            # ENS profiles may contain social links
            pass

        # Check links dict (keyed by platform name like "twitter", "github", etc.)
        links = p.get("links", {}) or {}
        if isinstance(links, dict):
            for link_platform, link_data in links.items():
                handle = link_data.get("handle", "") if isinstance(link_data, dict) else ""
                if link_platform == "twitter" and handle and not profile.twitter:
                    profile.twitter = handle.replace("@", "")
                elif link_platform == "github" and handle and not profile.github:
                    profile.github = handle
                elif link_platform == "farcaster" and handle and not profile.farcaster:
                    profile.farcaster = handle
                elif link_platform == "website" and handle and not profile.website:
                    profile.website = handle

        # Also check top-level social fields
        if p.get("email") and not profile.email:
            profile.email = p["email"]
        if p.get("website") and not profile.website:
            profile.website = p["website"]

    if profiles:
        profile.sources.append("web3.bio")
        profile.raw_data["web3bio"] = profiles


def extract_from_ensdata(data: dict, profile: SocialProfile) -> None:
    """Extract social data from ensdata.net response (flat fields)."""
    if not data:
        return

    has_data = False
    if data.get("twitter") and not profile.twitter:
        profile.twitter = data["twitter"].replace("@", "")
        has_data = True
    if data.get("github") and not profile.github:
        profile.github = data["github"]
        has_data = True
    if data.get("email") and not profile.email:
        profile.email = data["email"]
        has_data = True
    if data.get("url") and not profile.website:
        profile.website = data["url"]
        has_data = True
    if data.get("description") and not profile.bio:
        profile.bio = data["description"][:200]
        has_data = True
    if data.get("ens_primary") and not profile.display_name:
        profile.display_name = data.get("ens_primary", "")

    # Farcaster data from ensdata
    fc = data.get("farcaster", {}) or {}
    if fc.get("username") and not profile.farcaster:
        profile.farcaster = fc["username"]
        has_data = True
    if fc.get("displayName") and not profile.display_name:
        profile.display_name = fc["displayName"]
    if fc.get("bio") and not profile.bio:
        profile.bio = fc["bio"][:200]

    if has_data:
        profile.sources.append("ensdata.net")
        profile.raw_data["ensdata"] = data


def extract_from_neynar(data: dict, profile: SocialProfile) -> None:
    """Extract social data from Neynar Farcaster response."""
    if not data:
        return
    if data.get("username") and not profile.farcaster:
        profile.farcaster = data["username"]
    if data.get("display_name") and not profile.display_name:
        profile.display_name = data["display_name"]
    if data.get("profile", {}).get("bio", {}).get("text") and not profile.bio:
        profile.bio = data["profile"]["bio"]["text"][:200]

    profile.sources.append("neynar")
    profile.raw_data["neynar"] = data


# ============================================================================
# Pipeline
# ============================================================================

def resolve_batch(entries: list[dict], skip_ensdata: bool = False,
                  neynar_api_key: str = None) -> list[SocialProfile]:
    """
    Resolve a batch of {address, ens_name} dicts to social profiles.

    Pipeline:
    1. web3.bio batch (30 at a time) — covers ENS + Farcaster + Lens
    2. ensdata.net for misses — ENS text records + Farcaster
    3. Neynar for remaining misses — Farcaster by address
    """
    profiles = {}
    for entry in entries:
        addr = entry["address"].lower()
        ens = entry.get("ens_name", "")
        profiles[addr] = SocialProfile(address=addr, ens_name=ens)

    # --- Step 1: web3.bio ---
    # Prefer ENS names (better hit rate), fall back to addresses
    lookup_list = []  # (lookup_key, address)
    for addr, p in profiles.items():
        key = p.ens_name if p.ens_name else addr
        lookup_list.append((key, addr))

    print(f"\n📡 Step 1: web3.bio ({len(lookup_list)} identities)")

    hits_web3bio = 0
    for idx, (key, addr) in enumerate(lookup_list):
        print(f"  [{idx+1}/{len(lookup_list)}] {key[:40]}...", end=" ", flush=True)
        data = query_web3bio_single(key)
        if data:
            extract_from_web3bio(data, profiles[addr])
            if profiles[addr].has_identity:
                hits_web3bio += 1
                print(f"✅ {profiles[addr].identity_summary[:50]}")
            else:
                print("—")
        else:
            print("—")
        if idx + 1 < len(lookup_list):
            time.sleep(WEB3BIO_DELAY)

    print(f"  ✅ web3.bio: {hits_web3bio}/{len(profiles)} resolved")

    # --- Step 2: ensdata.net for misses with ENS names ---
    if not skip_ensdata:
        misses_with_ens = [p for p in profiles.values()
                          if not p.has_identity and p.ens_name]
        if misses_with_ens:
            print(f"\n📡 Step 2: ensdata.net ({len(misses_with_ens)} misses with ENS)")
            hits_ensdata = 0
            for idx, p in enumerate(misses_with_ens):
                print(f"  [{idx+1}/{len(misses_with_ens)}] {p.ens_name}...", end=" ", flush=True)
                data = query_ensdata(p.ens_name)
                extract_from_ensdata(data, p)
                if p.has_identity:
                    hits_ensdata += 1
                    print("✅")
                else:
                    print("—")
                time.sleep(ENSDATA_DELAY)
            print(f"  ✅ ensdata.net: {hits_ensdata} additional resolved")
        else:
            print("\n📡 Step 2: ensdata.net — no misses with ENS names, skipping")

    # --- Step 3: Neynar for remaining misses ---
    if neynar_api_key:
        misses = [p for p in profiles.values() if not p.farcaster]
        if misses:
            print(f"\n📡 Step 3: Neynar Farcaster ({len(misses)} remaining)")
            hits_neynar = 0
            for idx, p in enumerate(misses):
                data = query_neynar_by_address(p.address, neynar_api_key)
                extract_from_neynar(data, p)
                if p.farcaster:
                    hits_neynar += 1
                time.sleep(NEYNAR_DELAY)
            print(f"  ✅ Neynar: {hits_neynar} Farcaster profiles found")
    else:
        print("\n📡 Step 3: Neynar — no API key, skipping (set NEYNAR_API_KEY)")

    # --- Summary ---
    resolved = [p for p in profiles.values() if p.has_identity]
    print(f"\n{'='*60}")
    print(f"📊 Results: {len(resolved)}/{len(profiles)} resolved ({100*len(resolved)//max(len(profiles),1)}%)")
    if resolved:
        print(f"\n{'Address':<44} {'ENS':<20} {'Identity'}")
        print("-" * 100)
        for p in sorted(resolved, key=lambda x: x.ens_name):
            print(f"{p.address[:42]:<44} {p.ens_name:<20} {p.identity_summary[:60]}")

    return list(profiles.values())


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def update_knowledge_graph(profiles: list[SocialProfile]) -> int:
    """Update KG with resolved social profiles. Returns count updated."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from build_knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph(str(DB_PATH))
    updated = 0

    for p in profiles:
        if not p.has_identity:
            continue

        # Build identity string
        identity = p.display_name or p.twitter or p.farcaster or p.github or ""
        if not identity:
            continue

        # Update entity
        kwargs = {"ens_name": p.ens_name} if p.ens_name else {}
        if identity:
            kwargs["identity"] = identity
        kg.add_entity(p.address, **kwargs)

        # Add evidence
        confidence = 0.0
        if p.twitter:
            confidence = max(confidence, 0.70)
        if p.display_name:
            confidence = max(confidence, 0.60)
        if p.farcaster:
            confidence = max(confidence, 0.55)
        if p.github:
            confidence = max(confidence, 0.50)

        claim_parts = []
        if p.twitter:
            claim_parts.append(f"Twitter: @{p.twitter}")
        if p.farcaster:
            claim_parts.append(f"Farcaster: {p.farcaster}")
        if p.github:
            claim_parts.append(f"GitHub: {p.github}")
        if p.email:
            claim_parts.append(f"Email: {p.email}")
        if p.website:
            claim_parts.append(f"Website: {p.website}")
        if p.display_name:
            claim_parts.append(f"Name: {p.display_name}")

        kg.add_evidence(
            address=p.address,
            source=f"ens_social_resolver ({', '.join(p.sources)})",
            claim="; ".join(claim_parts),
            confidence=confidence,
            raw_data={"social_profile": asdict(p)}
        )
        updated += 1

    print(f"\n🗄️  Knowledge graph: {updated} entities updated")
    return updated


# ============================================================================
# Input Loading
# ============================================================================

def load_from_csv(filepath: str) -> list[dict]:
    """Load addresses from CSV. Expects 'address' column, optional 'ens_name'."""
    entries = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get("address", "").strip()
            ens = row.get("ens_name", "").strip()
            if addr:
                entries.append({"address": addr, "ens_name": ens})
    return entries


def load_from_kg() -> list[dict]:
    """Load ENS holders from knowledge graph."""
    import sqlite3
    if not DB_PATH.exists():
        print("⚠️  Knowledge graph not found. Use --ens or provide CSV input.")
        return []

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT address, ens_name FROM entities WHERE ens_name IS NOT NULL AND ens_name != ''"
    ).fetchall()
    conn.close()
    return [{"address": r["address"], "ens_name": r["ens_name"]} for r in rows]


# ============================================================================
# Output
# ============================================================================

def write_csv(profiles: list[SocialProfile], filepath: str) -> None:
    """Write results to CSV."""
    fieldnames = [
        "address", "ens_name", "display_name", "twitter", "farcaster",
        "github", "lens", "email", "website", "bio", "sources", "has_identity"
    ]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in sorted(profiles, key=lambda x: (not x.has_identity, x.ens_name)):
            writer.writerow({
                "address": p.address,
                "ens_name": p.ens_name,
                "display_name": p.display_name,
                "twitter": p.twitter,
                "farcaster": p.farcaster,
                "github": p.github,
                "lens": p.lens,
                "email": p.email,
                "website": p.website,
                "bio": p.bio,
                "sources": "|".join(p.sources),
                "has_identity": p.has_identity,
            })
    print(f"\n💾 Results written to {filepath}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="ENS-to-Social Identity Resolver")
    parser.add_argument("input", nargs="?", help="CSV file with address,ens_name columns")
    parser.add_argument("-o", "--output", help="Output CSV path")
    parser.add_argument("--ens", help="Resolve single ENS name")
    parser.add_argument("--address", help="Resolve single address")
    parser.add_argument("--update-kg", action="store_true", help="Update knowledge graph")
    parser.add_argument("--dry-run", action="store_true", help="Show inputs, don't call APIs")
    parser.add_argument("--skip-ensdata", action="store_true", help="Skip ensdata.net (step 2)")
    args = parser.parse_args()

    neynar_key = os.environ.get("NEYNAR_API_KEY")

    # Determine input
    if args.ens:
        entries = [{"address": "", "ens_name": args.ens}]
    elif args.address:
        entries = [{"address": args.address, "ens_name": ""}]
    elif args.input:
        entries = load_from_csv(args.input)
    else:
        # Default: load from KG
        entries = load_from_kg()

    if not entries:
        print("No entries to resolve. Provide CSV, --ens, or --address.")
        sys.exit(1)

    print(f"🔍 ENS Social Resolver")
    print(f"   Entries: {len(entries)}")
    ens_count = sum(1 for e in entries if e.get("ens_name"))
    print(f"   With ENS: {ens_count}")
    print(f"   Neynar API: {'✅' if neynar_key else '❌ (set NEYNAR_API_KEY)'}")

    if args.dry_run:
        print("\n📋 Dry run — entries to resolve:")
        for e in entries[:20]:
            print(f"  {e['address'][:42]}  {e.get('ens_name', '')}")
        if len(entries) > 20:
            print(f"  ... and {len(entries) - 20} more")
        return

    profiles = resolve_batch(
        entries,
        skip_ensdata=args.skip_ensdata,
        neynar_api_key=neynar_key,
    )

    if args.output:
        write_csv(profiles, args.output)

    if args.update_kg:
        update_knowledge_graph(profiles)

    # Default output if no CSV specified
    if not args.output:
        resolved = [p for p in profiles if p.has_identity]
        if resolved:
            print(f"\nTip: use -o results.csv to save, --update-kg to update knowledge graph")


if __name__ == "__main__":
    main()
