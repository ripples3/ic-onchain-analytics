#!/usr/bin/env python3
"""
Etherscan Labels Fetcher

Batch-fetches labels and contract information from Etherscan API.
Rate limit: 5 requests/second (free tier), 100K requests/day.

Usage:
    # Fetch labels for addresses in CSV
    python3 scripts/etherscan_labels.py addresses.csv -o labeled.csv

    # Check single address
    python3 scripts/etherscan_labels.py --address 0x1234...

    # Different chain
    python3 scripts/etherscan_labels.py addresses.csv --chain base

Environment:
    ETHERSCAN_API_KEY - Required. Get from https://etherscan.io/apis
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    script_dir = Path(__file__).parent
    env_paths = [script_dir / ".env", script_dir.parent / ".env"]
    for env_path in env_paths:
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


# ============================================================================
# Chain Configuration
# ============================================================================

CHAINS = {
    "ethereum": {"chainid": 1, "name": "Ethereum"},
    "arbitrum": {"chainid": 42161, "name": "Arbitrum One"},
    "base": {"chainid": 8453, "name": "Base"},
    "optimism": {"chainid": 10, "name": "Optimism"},
    "polygon": {"chainid": 137, "name": "Polygon"},
}


# ============================================================================
# Contract Type Patterns
# ============================================================================

CONTRACT_PATTERNS = {
    # Gnosis Safe variants
    "GnosisSafe": "Safe",
    "GnosisSafeProxy": "Safe Proxy",
    "Safe": "Safe",
    "SafeProxy": "Safe Proxy",

    # MakerDAO DSProxy
    "DSProxy": "DSProxy",
    "DsProxy": "DSProxy",

    # Instadapp
    "InstaAccountV2": "Instadapp DSA V2",
    "InstaAccount": "Instadapp DSA",

    # Summer.fi
    "AccountGuard": "Summer.fi Account",
    "AccountFactory": "Summer.fi Factory",

    # Other DeFi primitives
    "Vault": "Vault",
    "Strategy": "Strategy",
    "Pool": "Pool",
}


@dataclass
class AddressInfo:
    """Information about an Ethereum address."""
    address: str
    chain: str
    is_contract: bool
    contract_name: str = ""
    contract_type: str = ""  # Categorized type
    is_verified: bool = False
    implementation: str = ""  # For proxies
    label: str = ""
    creator: str = ""
    creation_tx: str = ""
    error: str = ""


class EtherscanClient:
    """Client for Etherscan V2 API."""

    BASE_URL = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str, rate_limit: float = 5.0):
        self.api_key = api_key
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0

    def _wait(self):
        """Respect rate limit."""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _request(self, chainid: int, module: str, action: str, **params) -> dict:
        """Make API request."""
        self._wait()

        all_params = {
            "chainid": chainid,
            "module": module,
            "action": action,
            "apikey": self.api_key,
            **params
        }

        resp = requests.get(self.BASE_URL, params=all_params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_code(self, address: str, chainid: int = 1) -> str:
        """Check if address is a contract."""
        data = self._request(
            chainid,
            "proxy",
            "eth_getCode",
            address=address
        )
        return data.get("result", "0x")

    def get_source_code(self, address: str, chainid: int = 1) -> Optional[dict]:
        """Get contract source code and metadata."""
        data = self._request(
            chainid,
            "contract",
            "getsourcecode",
            address=address
        )

        if data.get("status") == "1" and data.get("result"):
            return data["result"][0]
        return None

    def get_contract_creation(self, addresses: list[str], chainid: int = 1) -> dict:
        """
        Get contract creation info for multiple addresses.
        Max 5 addresses per call.
        """
        results = {}

        for i in range(0, len(addresses), 5):
            batch = addresses[i:i+5]
            data = self._request(
                chainid,
                "contract",
                "getcontractcreation",
                contractaddresses=",".join(batch)
            )

            if data.get("status") == "1" and data.get("result"):
                for item in data["result"]:
                    addr = item.get("contractAddress", "").lower()
                    results[addr] = {
                        "creator": item.get("contractCreator", ""),
                        "tx_hash": item.get("txHash", "")
                    }

        return results

    def get_address_info(self, address: str, chainid: int = 1) -> AddressInfo:
        """Get comprehensive info about an address."""
        address = address.lower()
        chain_name = next((c for c, v in CHAINS.items() if v["chainid"] == chainid), "ethereum")

        info = AddressInfo(
            address=address,
            chain=chain_name,
            is_contract=False
        )

        try:
            # Check if contract
            code = self.get_code(address, chainid)
            info.is_contract = code != "0x" and len(code) > 2

            if not info.is_contract:
                info.contract_type = "EOA"
                return info

            # Get contract details
            source = self.get_source_code(address, chainid)
            if source:
                info.contract_name = source.get("ContractName", "")
                info.is_verified = bool(source.get("SourceCode"))
                info.implementation = source.get("Implementation", "")

                # Categorize contract type
                for pattern, cat_type in CONTRACT_PATTERNS.items():
                    if pattern.lower() in info.contract_name.lower():
                        info.contract_type = cat_type
                        break

                if not info.contract_type:
                    if info.contract_name:
                        info.contract_type = f"Contract ({info.contract_name})"
                    elif info.is_verified:
                        info.contract_type = "Contract (verified)"
                    else:
                        info.contract_type = "Contract (unverified)"

            # Get creation info
            creation = self.get_contract_creation([address], chainid)
            if address in creation:
                info.creator = creation[address]["creator"]
                info.creation_tx = creation[address]["tx_hash"]

        except Exception as e:
            info.error = str(e)

        return info


def load_addresses(filepath: str) -> list[str]:
    """Load addresses from CSV or text file."""
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

    return list(set(addresses))  # Dedupe


def save_results(results: list[AddressInfo], filepath: str, format: str = "csv"):
    """Save results to file."""
    if format == "json":
        with open(filepath, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
    else:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "address", "chain", "is_contract", "contract_name",
                "contract_type", "is_verified", "implementation",
                "label", "creator", "creation_tx", "error"
            ])
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Etherscan labels and contract info",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with addresses (CSV or text)"
    )

    parser.add_argument(
        "--address", "-a",
        help="Check single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="etherscan_labels.csv",
        help="Output file (default: etherscan_labels.csv)"
    )

    parser.add_argument(
        "--chain", "-c",
        default="ethereum",
        choices=list(CHAINS.keys()),
        help="Blockchain to query (default: ethereum)"
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

    # Validate
    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = EtherscanClient(api_key, args.rate_limit)
    chainid = CHAINS[args.chain]["chainid"]

    # Single address mode
    if args.address:
        info = client.get_address_info(args.address, chainid)
        print(json.dumps(asdict(info), indent=2))
        return

    # Batch mode
    addresses = load_addresses(args.input)
    print(f"Processing {len(addresses)} addresses on {args.chain}...", file=sys.stderr)

    results = []
    for i, addr in enumerate(addresses):
        if (i + 1) % 20 == 0:
            print(f"Progress: {i + 1}/{len(addresses)}", file=sys.stderr)

        info = client.get_address_info(addr, chainid)
        results.append(info)

    # Save results
    save_results(results, args.output, args.format)
    print(f"Saved to {args.output}", file=sys.stderr)

    # Summary
    contracts = sum(1 for r in results if r.is_contract)
    safes = sum(1 for r in results if "Safe" in r.contract_type)
    dsproxies = sum(1 for r in results if "DSProxy" in r.contract_type)
    verified = sum(1 for r in results if r.is_verified)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total: {len(results)}", file=sys.stderr)
    print(f"  EOAs: {len(results) - contracts}", file=sys.stderr)
    print(f"  Contracts: {contracts}", file=sys.stderr)
    print(f"  - Safe wallets: {safes}", file=sys.stderr)
    print(f"  - DSProxy: {dsproxies}", file=sys.stderr)
    print(f"  - Verified: {verified}", file=sys.stderr)


if __name__ == "__main__":
    main()
