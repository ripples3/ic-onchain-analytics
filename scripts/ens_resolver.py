#!/usr/bin/env python3
"""
ENS Resolver - Batch resolve ENS names for wallet addresses.

Uses Etherscan API to reverse-resolve addresses to ENS names.
Also resolves ENS names to addresses for forward lookup.

Usage:
    # Batch reverse resolve (address → ENS)
    python3 scripts/ens_resolver.py addresses.csv -o resolved.csv

    # Single address
    python3 scripts/ens_resolver.py --address 0x7a16ff8270133f063aab6c9977183d9e72835428

    # Forward resolve (ENS → address)
    python3 scripts/ens_resolver.py --ens vitalik.eth

Based on: ZachXBT methodology - ENS as identity signal
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

# Rate limiting
RATE_LIMIT = 5  # requests per second
MIN_REQUEST_INTERVAL = 1.0 / RATE_LIMIT


class ENSResolver:
    """Batch ENS resolution using Etherscan API and on-chain calls."""

    def __init__(self, etherscan_api_key: Optional[str] = None, rpc_url: Optional[str] = None):
        self.etherscan_api_key = etherscan_api_key or os.getenv("ETHERSCAN_API_KEY")
        self.rpc_url = rpc_url or os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")
        self.last_request_time = 0
        self.cache: dict = {}

        if not self.etherscan_api_key:
            print("Warning: ETHERSCAN_API_KEY not set. Some features may not work.")

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def reverse_resolve(self, address: str) -> Optional[str]:
        """
        Reverse resolve address to ENS name using on-chain call.

        Args:
            address: Ethereum address (0x...)

        Returns:
            ENS name or None
        """
        address = address.lower()

        # Check cache
        if address in self.cache:
            return self.cache[address]

        self._rate_limit()

        # ENS reverse resolver contract
        # Call: node(address) on 0x084b1c3c81545d370f3634392de611caabff8148 (ENS Reverse Registrar)
        # Or use the simpler approach via RPC

        try:
            # Use Etherscan API for reverse ENS lookup
            url = f"https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 1,
                "sort": "asc",
                "apikey": self.etherscan_api_key
            }

            # Actually, Etherscan doesn't have a direct ENS API
            # We need to use the ENS subgraph or direct contract call

            # Use ENS subgraph (The Graph)
            subgraph_url = "https://api.thegraph.com/subgraphs/name/ensdomains/ens"
            query = """
            query($address: String!) {
                domains(where: {resolvedAddress: $address}, first: 1) {
                    name
                    resolvedAddress {
                        id
                    }
                }
            }
            """

            response = requests.post(
                subgraph_url,
                json={"query": query, "variables": {"address": address.lower()}},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                domains = data.get("data", {}).get("domains", [])
                if domains:
                    ens_name = domains[0].get("name")
                    self.cache[address] = ens_name
                    return ens_name

            self.cache[address] = None
            return None

        except Exception as e:
            print(f"  Error resolving {address[:10]}...: {e}")
            self.cache[address] = None
            return None

    def forward_resolve(self, ens_name: str) -> Optional[str]:
        """
        Forward resolve ENS name to address.

        Args:
            ens_name: ENS name (e.g., vitalik.eth)

        Returns:
            Address or None
        """
        ens_name = ens_name.lower()

        # Check cache
        cache_key = f"forward:{ens_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        self._rate_limit()

        try:
            # Use ENS subgraph
            subgraph_url = "https://api.thegraph.com/subgraphs/name/ensdomains/ens"
            query = """
            query($name: String!) {
                domains(where: {name: $name}, first: 1) {
                    name
                    resolvedAddress {
                        id
                    }
                }
            }
            """

            response = requests.post(
                subgraph_url,
                json={"query": query, "variables": {"name": ens_name}},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                domains = data.get("data", {}).get("domains", [])
                if domains and domains[0].get("resolvedAddress"):
                    address = domains[0]["resolvedAddress"]["id"]
                    self.cache[cache_key] = address
                    return address

            self.cache[cache_key] = None
            return None

        except Exception as e:
            print(f"  Error resolving {ens_name}: {e}")
            self.cache[cache_key] = None
            return None

    def batch_reverse_resolve(self, addresses: list[str], show_progress: bool = True) -> dict[str, Optional[str]]:
        """
        Batch reverse resolve multiple addresses.

        Args:
            addresses: List of Ethereum addresses
            show_progress: Whether to show progress bar

        Returns:
            Dict mapping address → ENS name (or None)
        """
        results = {}
        total = len(addresses)
        resolved_count = 0

        for i, address in enumerate(addresses):
            ens_name = self.reverse_resolve(address)
            results[address.lower()] = ens_name

            if ens_name:
                resolved_count += 1

            if show_progress and (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{total} ({resolved_count} resolved)")

        return results

    def save_cache(self, path: str):
        """Save cache to file."""
        with open(path, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def load_cache(self, path: str):
        """Load cache from file."""
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.cache = json.load(f)


def process_csv(input_path: str, output_path: str, resolver: ENSResolver, address_column: str = "address"):
    """Process CSV file and add ENS resolution."""
    rows = []
    addresses = []

    # Read input
    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        # Add ens_name column if not present
        if 'ens_name' not in fieldnames:
            fieldnames.append('ens_name')

        for row in reader:
            rows.append(row)
            addr = row.get(address_column, row.get('borrower', ''))
            if addr:
                addresses.append(addr)

    print(f"Found {len(addresses)} addresses to resolve")

    # Resolve
    results = resolver.batch_reverse_resolve(addresses)

    # Update rows
    resolved_count = 0
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        ens_name = results.get(addr)

        # Only update if we found a name and field is empty
        if ens_name and not row.get('ens_name'):
            row['ens_name'] = ens_name
            resolved_count += 1
        elif not row.get('ens_name'):
            row['ens_name'] = ''

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResolved {resolved_count} ENS names")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch ENS resolution")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to resolve")
    parser.add_argument("--ens", help="ENS name to forward resolve")
    parser.add_argument("--column", default="address", help="Column containing addresses")
    parser.add_argument("--cache", help="Cache file path")

    args = parser.parse_args()

    resolver = ENSResolver()

    # Load cache if specified
    if args.cache:
        resolver.load_cache(args.cache)

    if args.ens:
        # Forward resolve ENS → address
        print(f"Resolving {args.ens}...")
        address = resolver.forward_resolve(args.ens)
        if address:
            print(f"  {args.ens} → {address}")
        else:
            print(f"  {args.ens} → Not found")

    elif args.address:
        # Single reverse resolve
        print(f"Resolving {args.address}...")
        ens_name = resolver.reverse_resolve(args.address)
        if ens_name:
            print(f"  {args.address} → {ens_name}")
        else:
            print(f"  {args.address} → No ENS name found")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_ens.csv')
        process_csv(args.input, output_path, resolver, args.column)

    else:
        parser.print_help()

    # Save cache if specified
    if args.cache:
        resolver.save_cache(args.cache)


if __name__ == "__main__":
    main()
