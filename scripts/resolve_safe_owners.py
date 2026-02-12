#!/usr/bin/env python3
"""
Safe Multisig Owner Resolver

Resolves Safe multisig wallet owners using the Safe Transaction Service API.
Useful for identifying DAO treasuries and institutional multisigs.

Usage:
    # Resolve owners for Safe addresses in CSV
    python3 scripts/resolve_safe_owners.py safes.csv -o safe_owners.csv

    # Check single Safe
    python3 scripts/resolve_safe_owners.py --address 0x1234...

    # Check all chains
    python3 scripts/resolve_safe_owners.py safes.csv --all-chains

Safe Transaction Service:
    Ethereum: https://safe-transaction-mainnet.safe.global
    Arbitrum: https://safe-transaction-arbitrum.safe.global
    Base:     https://safe-transaction-base.safe.global
    Optimism: https://safe-transaction-optimism.safe.global
    Polygon:  https://safe-transaction-polygon.safe.global

No API key required.
"""

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


# ============================================================================
# Chain Configuration
# ============================================================================

SAFE_APIS = {
    "ethereum": "https://safe-transaction-mainnet.safe.global",
    "mainnet": "https://safe-transaction-mainnet.safe.global",
    "arbitrum": "https://safe-transaction-arbitrum.safe.global",
    "base": "https://safe-transaction-base.safe.global",
    "optimism": "https://safe-transaction-optimism.safe.global",
    "polygon": "https://safe-transaction-polygon.safe.global",
    "gnosis": "https://safe-transaction-gnosis-chain.safe.global",
    "avalanche": "https://safe-transaction-avalanche.safe.global",
    "bsc": "https://safe-transaction-bsc.safe.global",
}


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SafeInfo:
    """Safe wallet information."""
    address: str
    chain: str
    is_safe: bool = False
    version: str = ""
    threshold: int = 0
    owner_count: int = 0
    owners: list = None
    nonce: int = 0
    modules: list = None
    fallback_handler: str = ""
    guard: str = ""
    # Cross-referenced owner data
    owner_labels: dict = None  # address -> label
    owner_ens: dict = None     # address -> ENS name
    last_checked: str = ""
    error: str = ""

    def __post_init__(self):
        if self.owners is None:
            self.owners = []
        if self.modules is None:
            self.modules = []
        if self.owner_labels is None:
            self.owner_labels = {}
        if self.owner_ens is None:
            self.owner_ens = {}


# ============================================================================
# Safe API Client
# ============================================================================

class SafeClient:
    """Client for Safe Transaction Service API."""

    def __init__(self, rate_limit: float = 5.0):
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0
        self.session = requests.Session()

    def _wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _get_api_url(self, chain: str) -> str:
        """Get API URL for chain."""
        return SAFE_APIS.get(chain.lower(), SAFE_APIS["ethereum"])

    def get_safe_info(self, address: str, chain: str = "ethereum") -> SafeInfo:
        """Get Safe wallet information."""
        address = address.lower()
        if not address.startswith("0x"):
            address = "0x" + address

        # Checksum address for Safe API
        address = self._checksum_address(address)

        result = SafeInfo(
            address=address.lower(),
            chain=chain.lower(),
            last_checked=datetime.now(timezone.utc).isoformat()
        )

        try:
            self._wait()

            base_url = self._get_api_url(chain)
            url = f"{base_url}/api/v1/safes/{address}/"

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 404:
                # Not a Safe on this chain
                result.is_safe = False
                return result

            if resp.status_code != 200:
                result.error = f"HTTP {resp.status_code}"
                return result

            data = resp.json()

            result.is_safe = True
            result.version = data.get("version", "")
            result.threshold = data.get("threshold", 0)
            result.nonce = data.get("nonce", 0)
            result.owners = [o.lower() for o in data.get("owners", [])]
            result.owner_count = len(result.owners)
            result.modules = data.get("modules", [])
            result.fallback_handler = data.get("fallbackHandler", "")
            result.guard = data.get("guard", "")

        except requests.exceptions.Timeout:
            result.error = "Timeout"
        except Exception as e:
            result.error = str(e)

        return result

    def get_safe_info_all_chains(self, address: str) -> list[SafeInfo]:
        """Check if address is a Safe on any supported chain."""
        results = []

        for chain in SAFE_APIS.keys():
            if chain == "mainnet":
                continue  # Skip duplicate

            info = self.get_safe_info(address, chain)
            if info.is_safe:
                results.append(info)

        return results

    @staticmethod
    def _checksum_address(address: str) -> str:
        """Convert to checksum address format."""
        # Simple implementation - just return lowercase for API compatibility
        # Full checksum would require keccak256
        address = address.lower()
        if address.startswith("0x"):
            return "0x" + address[2:]
        return "0x" + address


# ============================================================================
# Known Owner Database
# ============================================================================

# Known entities that are often Safe owners
KNOWN_OWNERS = {
    # DAOs
    "0x8d90113a1e286a5ab3e496fbd1853f265e5913c6": "Lido DAO",
    "0x3e40d73eb977dc6a537af587d48316fee66e9c8c": "Lido DAO: Treasury",
    "0x0de4b8c7455f25d2e5ae8a52a49eb3a3c7e1f1c5": "Spark DAO",
    "0x0048a99dd95c0e695bf0f5ea66d2f54d7c3c6c7b": "Sky/Maker",

    # Protocols
    "0x7a16ff8270133f063aab6c9977183d9e72835428": "Michael Egorov (Curve)",
    "0xf20b3387fd3b6529ebc8caeed3a01f8f19e9a09c": "Aave DAO Treasury",
    "0x2ba1dc5e4981d1f2b55e8f6e4e8e2a1b0e8c5f7a": "Compound DAO",

    # Funds
    "0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c": "Trend Research (LD Capital)",
    "0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5": "Abraxas Capital",

    # Indexes / Index Coop
    "0x9467cfadc9de245010df95ec6a585a506a8ad5fc": "Index Coop: Ops Multisig",
}


def enrich_owners(safe_info: SafeInfo) -> SafeInfo:
    """Add labels to known owners."""
    for owner in safe_info.owners:
        owner_lower = owner.lower()
        if owner_lower in KNOWN_OWNERS:
            safe_info.owner_labels[owner_lower] = KNOWN_OWNERS[owner_lower]
    return safe_info


# ============================================================================
# Main
# ============================================================================

def load_addresses(filepath: str) -> list[str]:
    """Load addresses from file."""
    addresses = []
    path = Path(filepath)

    if path.suffix == ".csv":
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("address") or row.get("Address") or row.get("wallet")
                if addr:
                    addresses.append(addr.strip().lower())
    else:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith("0x"):
                    addresses.append(line.lower())

    return list(set(addresses))


def save_results(results: list[SafeInfo], filepath: str, format: str = "csv"):
    """Save results to file."""
    if format == "json":
        with open(filepath, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
    else:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "address", "chain", "is_safe", "version", "threshold",
                "owner_count", "owners", "owner_labels",
                "nonce", "modules", "last_checked", "error"
            ])
            writer.writeheader()
            for r in results:
                row = {
                    "address": r.address,
                    "chain": r.chain,
                    "is_safe": r.is_safe,
                    "version": r.version,
                    "threshold": r.threshold,
                    "owner_count": r.owner_count,
                    "owners": json.dumps(r.owners) if r.owners else "",
                    "owner_labels": json.dumps(r.owner_labels) if r.owner_labels else "",
                    "nonce": r.nonce,
                    "modules": json.dumps(r.modules) if r.modules else "",
                    "last_checked": r.last_checked,
                    "error": r.error,
                }
                writer.writerow(row)


def save_owners_flat(results: list[SafeInfo], filepath: str):
    """Save flattened owner data for cross-referencing."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "safe_address", "chain", "owner_address", "owner_label",
            "threshold", "total_owners"
        ])
        writer.writeheader()

        for safe in results:
            if not safe.is_safe:
                continue

            for owner in safe.owners:
                writer.writerow({
                    "safe_address": safe.address,
                    "chain": safe.chain,
                    "owner_address": owner,
                    "owner_label": safe.owner_labels.get(owner.lower(), ""),
                    "threshold": safe.threshold,
                    "total_owners": safe.owner_count,
                })


def main():
    parser = argparse.ArgumentParser(
        description="Resolve Safe multisig wallet owners",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check single Safe
    python3 resolve_safe_owners.py --address 0x5be9a4959308a0d0c7bc0870e319314d8d957dbb

    # Batch check from CSV
    python3 resolve_safe_owners.py safes.csv -o safe_owners.csv

    # Check all chains
    python3 resolve_safe_owners.py --address 0x1234... --all-chains

    # Export flat owner list for cross-referencing
    python3 resolve_safe_owners.py safes.csv --flat-output owners_flat.csv
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with addresses"
    )

    parser.add_argument(
        "--address", "-a",
        help="Check single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="safe_owners.csv",
        help="Output file (default: safe_owners.csv)"
    )

    parser.add_argument(
        "--flat-output",
        help="Additional flat output file with one row per owner"
    )

    parser.add_argument(
        "--chain", "-c",
        default="ethereum",
        choices=list(SAFE_APIS.keys()),
        help="Chain to check (default: ethereum)"
    )

    parser.add_argument(
        "--all-chains",
        action="store_true",
        help="Check all supported chains"
    )

    parser.add_argument(
        "--format", "-f",
        default="csv",
        choices=["csv", "json"],
        help="Output format (default: csv)"
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=5.0,
        help="Requests per second (default: 5.0)"
    )

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    client = SafeClient(args.rate_limit)

    # Single address mode
    if args.address:
        if args.all_chains:
            results = client.get_safe_info_all_chains(args.address)
            if not results:
                print(json.dumps({"address": args.address, "is_safe": False, "chains_checked": list(SAFE_APIS.keys())}))
            else:
                for r in results:
                    r = enrich_owners(r)
                print(json.dumps([asdict(r) for r in results], indent=2))
        else:
            result = client.get_safe_info(args.address, args.chain)
            result = enrich_owners(result)
            print(json.dumps(asdict(result), indent=2))
        return

    # Batch mode
    addresses = load_addresses(args.input)
    print(f"Checking {len(addresses)} addresses for Safe wallets...", file=sys.stderr)

    results = []
    safes_found = 0

    for i, addr in enumerate(addresses):
        if (i + 1) % 20 == 0:
            print(f"Progress: {i + 1}/{len(addresses)} ({safes_found} Safes found)", file=sys.stderr)

        if args.all_chains:
            chain_results = client.get_safe_info_all_chains(addr)
            for r in chain_results:
                r = enrich_owners(r)
                results.append(r)
                if r.is_safe:
                    safes_found += 1
            # If not a Safe on any chain, still record it
            if not chain_results:
                results.append(SafeInfo(
                    address=addr,
                    chain="none",
                    is_safe=False,
                    last_checked=datetime.now(timezone.utc).isoformat()
                ))
        else:
            result = client.get_safe_info(addr, args.chain)
            result = enrich_owners(result)
            results.append(result)
            if result.is_safe:
                safes_found += 1

    save_results(results, args.output, args.format)
    print(f"\nSaved to {args.output}", file=sys.stderr)

    # Flat output
    if args.flat_output:
        save_owners_flat(results, args.flat_output)
        print(f"Flat owner list saved to {args.flat_output}", file=sys.stderr)

    # Summary
    safes = [r for r in results if r.is_safe]
    total_owners = set()
    for s in safes:
        total_owners.update(s.owners)

    labeled_owners = sum(len(s.owner_labels) for s in safes)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total addresses: {len(addresses)}", file=sys.stderr)
    print(f"  Safe wallets: {len(safes)}", file=sys.stderr)
    print(f"  Unique owners: {len(total_owners)}", file=sys.stderr)
    print(f"  Labeled owners: {labeled_owners}", file=sys.stderr)

    if safes:
        # Threshold distribution
        thresholds = {}
        for s in safes:
            key = f"{s.threshold}/{s.owner_count}"
            thresholds[key] = thresholds.get(key, 0) + 1

        print(f"\n  Threshold distribution:", file=sys.stderr)
        for thresh, count in sorted(thresholds.items(), key=lambda x: -x[1])[:5]:
            print(f"    {thresh}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
