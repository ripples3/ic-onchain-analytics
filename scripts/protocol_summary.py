#!/usr/bin/env python3
"""
Protocol Summary - Query lending positions across Aave, Spark, Morpho.

Reveals DeFi activity patterns for whale research.
Uses on-chain calls to protocol contracts.

Usage:
    # Single address
    python3 scripts/protocol_summary.py --address 0x1234...

    # Batch from CSV
    python3 scripts/protocol_summary.py addresses.csv -o positions.csv

    # Specific protocols
    python3 scripts/protocol_summary.py --address 0x1234... --protocols aave,spark

Based on: ZachXBT methodology - protocol activity as identity signal
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

# Protocol configurations
PROTOCOLS = {
    "aave_v3_ethereum": {
        "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "chain": "ethereum",
        "rpc_env": "ETH_RPC_URL",
        "name": "Aave V3 Ethereum",
    },
    "aave_v3_arbitrum": {
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "chain": "arbitrum",
        "rpc_env": "ARB_RPC_URL",
        "name": "Aave V3 Arbitrum",
    },
    "aave_v3_base": {
        "pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
        "chain": "base",
        "rpc_env": "BASE_RPC_URL",
        "name": "Aave V3 Base",
    },
    "spark_ethereum": {
        "pool": "0xC13e21B648A5Ee794902342038FF3aDAB66BE987",
        "chain": "ethereum",
        "rpc_env": "ETH_RPC_URL",
        "name": "Spark Ethereum",
    },
}

# Default RPCs
DEFAULT_RPCS = {
    "ethereum": "https://eth.llamarpc.com",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "base": "https://mainnet.base.org",
}


class ProtocolSummary:
    """Query lending positions across DeFi protocols."""

    def __init__(self, protocols: Optional[list[str]] = None):
        self.protocols = protocols or list(PROTOCOLS.keys())
        self.rpcs = {}

        # Set up RPCs
        for protocol_id, config in PROTOCOLS.items():
            chain = config["chain"]
            rpc = os.getenv(config["rpc_env"], DEFAULT_RPCS.get(chain, ""))
            self.rpcs[chain] = rpc

    _ADDRESS_RE = re.compile(r'^0x[a-fA-F0-9]{40}$')

    def _call_contract(self, chain: str, contract: str, signature: str, args: list = None) -> Optional[str]:
        """Make a contract call using cast."""
        if not self._ADDRESS_RE.match(contract):
            raise ValueError(f"Invalid contract address: {contract}")
        rpc = self.rpcs.get(chain)
        if not rpc:
            return None

        cmd = ["cast", "call", contract, signature]
        if args:
            cmd.extend(args)
        cmd.extend(["--rpc-url", rpc])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # cast not installed, try RPC
            pass

        return None

    def _rpc_call(self, chain: str, to: str, data: str) -> Optional[str]:
        """Make an RPC eth_call."""
        rpc = self.rpcs.get(chain)
        if not rpc:
            return None

        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": to, "data": data}, "latest"],
                "id": 1
            }
            response = requests.post(rpc, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json().get("result")
                return result
        except Exception:
            pass

        return None

    def get_aave_position(self, address: str, protocol_id: str) -> Optional[dict]:
        """
        Get Aave V3 position using getUserAccountData.

        Returns:
            Dict with totalCollateralBase, totalDebtBase, availableBorrowsBase,
            currentLiquidationThreshold, ltv, healthFactor
        """
        config = PROTOCOLS.get(protocol_id)
        if not config:
            return None

        chain = config["chain"]
        pool = config["pool"]

        # getUserAccountData(address) returns 6 uint256 values
        result = self._call_contract(
            chain,
            pool,
            "getUserAccountData(address)(uint256,uint256,uint256,uint256,uint256,uint256)",
            [address]
        )

        if result:
            try:
                # Parse the output (cast returns space-separated values)
                values = result.split("\n")
                if len(values) >= 6:
                    # Values are in base units (8 decimals for USD)
                    collateral = int(values[0]) / 1e8
                    debt = int(values[1]) / 1e8
                    available = int(values[2]) / 1e8
                    liq_threshold = int(values[3]) / 100  # basis points
                    ltv = int(values[4]) / 100  # basis points
                    health_factor = int(values[5]) / 1e18

                    return {
                        "protocol": config["name"],
                        "collateral_usd": collateral,
                        "debt_usd": debt,
                        "available_usd": available,
                        "liq_threshold": liq_threshold,
                        "ltv": ltv,
                        "health_factor": health_factor if health_factor < 1e10 else None,  # Infinity check
                    }
            except (ValueError, IndexError):
                pass

        # Fallback: try RPC call with encoded data
        # getUserAccountData(address) selector: 0xbf92857c
        try:
            # Encode the call data
            selector = "0xbf92857c"  # keccak256("getUserAccountData(address)")[:4]
            padded_address = address.lower().replace("0x", "").zfill(64)
            data = selector + padded_address

            result = self._rpc_call(chain, pool, data)
            if result and len(result) >= 386:  # 0x + 6 * 64 hex chars
                hex_data = result[2:]  # Remove 0x

                collateral = int(hex_data[0:64], 16) / 1e8
                debt = int(hex_data[64:128], 16) / 1e8
                available = int(hex_data[128:192], 16) / 1e8
                liq_threshold = int(hex_data[192:256], 16) / 100
                ltv = int(hex_data[256:320], 16) / 100
                health_factor = int(hex_data[320:384], 16) / 1e18

                return {
                    "protocol": config["name"],
                    "collateral_usd": collateral,
                    "debt_usd": debt,
                    "available_usd": available,
                    "liq_threshold": liq_threshold,
                    "ltv": ltv,
                    "health_factor": health_factor if health_factor < 1e10 else None,
                }
        except Exception:
            pass

        return None

    def check_address(self, address: str) -> dict:
        """
        Check an address across all configured protocols.

        Returns:
            Dict with protocol positions and aggregates
        """
        results = {
            "address": address,
            "positions": [],
            "total_collateral_usd": 0,
            "total_debt_usd": 0,
            "protocols_used": [],
        }

        for protocol_id in self.protocols:
            if not protocol_id.startswith(("aave", "spark")):
                continue  # Only handle Aave/Spark for now

            position = self.get_aave_position(address, protocol_id)

            if position and (position["collateral_usd"] > 0 or position["debt_usd"] > 0):
                results["positions"].append(position)
                results["total_collateral_usd"] += position["collateral_usd"]
                results["total_debt_usd"] += position["debt_usd"]
                results["protocols_used"].append(position["protocol"])

            # Rate limit
            time.sleep(0.1)

        return results

    def check_batch(self, addresses: list[str], show_progress: bool = True) -> list[dict]:
        """Check multiple addresses."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            result = self.check_address(address)
            results.append(result)

            if show_progress and (i + 1) % 10 == 0:
                active = sum(1 for r in results if r["positions"])
                print(f"  Progress: {i + 1}/{total} ({active} with positions)")

        return results


def format_usd(value: float) -> str:
    """Format USD value."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.1f}K"
    else:
        return f"${value:.2f}"


def process_csv(input_path: str, output_path: str, checker: ProtocolSummary, address_column: str = "address"):
    """Process CSV file and add protocol positions."""
    rows = []
    addresses = []

    # Read input
    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        for row in reader:
            rows.append(row)
            addr = row.get(address_column, row.get('borrower', ''))
            if addr:
                addresses.append(addr)

    print(f"Checking {len(addresses)} addresses across {len(checker.protocols)} protocols")

    # Add columns
    new_columns = ["total_collateral_usd", "total_debt_usd", "health_factor_min", "protocols_used", "protocol_count"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    # Check positions
    results = checker.check_batch(addresses)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        row["total_collateral_usd"] = format_usd(result.get("total_collateral_usd", 0)) if result.get("total_collateral_usd", 0) > 0 else ""
        row["total_debt_usd"] = format_usd(result.get("total_debt_usd", 0)) if result.get("total_debt_usd", 0) > 0 else ""

        # Min health factor across positions
        health_factors = [p["health_factor"] for p in result.get("positions", []) if p.get("health_factor")]
        row["health_factor_min"] = f"{min(health_factors):.2f}" if health_factors else ""

        row["protocols_used"] = ",".join(result.get("protocols_used", []))
        row["protocol_count"] = len(result.get("protocols_used", []))

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    with_positions = sum(1 for r in results if r["positions"])
    total_collateral = sum(r["total_collateral_usd"] for r in results)
    total_debt = sum(r["total_debt_usd"] for r in results)

    print(f"\nResults:")
    print(f"  Addresses with positions: {with_positions}/{len(results)}")
    print(f"  Total collateral: {format_usd(total_collateral)}")
    print(f"  Total debt: {format_usd(total_debt)}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="DeFi protocol position checker")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to check")
    parser.add_argument("--protocols", help="Comma-separated list of protocols (default: all)")
    parser.add_argument("--column", default="address", help="Column containing addresses")

    args = parser.parse_args()

    protocols = args.protocols.split(",") if args.protocols else None
    checker = ProtocolSummary(protocols=protocols)

    if args.address:
        # Single address
        print(f"Checking {args.address} across {len(checker.protocols)} protocols...")
        result = checker.check_address(args.address)

        print(f"\n{args.address}")
        print("-" * 70)

        if result["positions"]:
            for pos in result["positions"]:
                print(f"  {pos['protocol']}")
                print(f"    Collateral: {format_usd(pos['collateral_usd']):>12}")
                print(f"    Debt:       {format_usd(pos['debt_usd']):>12}")
                if pos.get("health_factor"):
                    print(f"    Health:     {pos['health_factor']:>12.2f}")
                print()

            print("-" * 70)
            print(f"Total Collateral: {format_usd(result['total_collateral_usd'])}")
            print(f"Total Debt:       {format_usd(result['total_debt_usd'])}")
            print(f"Protocols:        {', '.join(result['protocols_used'])}")
        else:
            print("  No lending positions found")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_protocols.csv')
        process_csv(args.input, output_path, checker, args.column)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
