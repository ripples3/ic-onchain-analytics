#!/usr/bin/env python3
"""
DEX Analyzer - Track DEX swap patterns and trading behavior.

Identifies trading patterns for whale research:
- Preferred DEXs (Uniswap, Sushiswap, Curve, etc.)
- Token preferences (what they trade)
- Trading frequency and volume
- MEV patterns (sandwich attacks, arbitrage)

Usage:
    # Single address
    python3 scripts/dex_analyzer.py --address 0x1234...

    # Batch from CSV
    python3 scripts/dex_analyzer.py addresses.csv -o dex_patterns.csv

    # Specific chain
    python3 scripts/dex_analyzer.py --address 0x1234... --chain arbitrum

Based on: Trading pattern analysis for identity clustering
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

# Known DEX router addresses
DEX_ROUTERS = {
    "ethereum": {
        # Uniswap
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router 2",
        "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
        # Sushiswap
        "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "Sushiswap Router",
        # Curve
        "0x99a58482bd75cbab83b27ec03ca68ff489b5788f": "Curve Router",
        "0xf0d4c12a5768d806021f80a262b4d39d26c58b8d": "Curve Router 2",
        # 1inch
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router V5",
        "0x111111125421ca6dc452d289314280a0f8842a65": "1inch Router V6",
        # 0x
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange Proxy",
        # Balancer
        "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
        # CoW Protocol
        "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Protocol",
        # Paraswap
        "0xdef171fe48cf0115b1d80b88dc8eab59176fee57": "Paraswap V5",
    },
    "arbitrum": {
        "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506": "Sushiswap Router",
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router 2",
        "0x5e325eda8064b456f4781070c0738d849c824258": "Camelot Router",
        "0xc873fecbd354f5a56e00e710b90ef4201db2448d": "Camelot Router V2",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router V5",
    },
    "base": {
        "0x2626664c2603336e57b271c5c0b26f421741e481": "Uniswap V3 Router",
        "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router V5",
        "0x327df1e6de05895d2ab08513aadd9313fe505d86": "Baseswap Router",
        "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43": "Aerodrome Router",
    },
}

# Swap event signatures
SWAP_EVENTS = {
    # Uniswap V2
    "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822": "Swap(address,uint256,uint256,uint256,uint256,address)",
    # Uniswap V3
    "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67": "Swap(address,address,int256,int256,uint160,uint128,int24)",
    # Curve
    "0x8b3e96f2b889fa771c53c981b40daf005f63f637f1869f707052d15a3dd97140": "TokenExchange(address,int128,uint256,int128,uint256)",
}

# Explorer API configurations
EXPLORER_APIS = {
    "ethereum": {
        "api": "https://api.etherscan.io/api",
        "api_key_env": "ETHERSCAN_API_KEY",
    },
    "arbitrum": {
        "api": "https://api.arbiscan.io/api",
        "api_key_env": "ARBISCAN_API_KEY",
    },
    "base": {
        "api": "https://api.basescan.org/api",
        "api_key_env": "BASESCAN_API_KEY",
    },
}


class DEXAnalyzer:
    """Analyze DEX trading patterns."""

    def __init__(self, chain: str = "ethereum"):
        self.chain = chain
        self.api_config = EXPLORER_APIS.get(chain, EXPLORER_APIS["ethereum"])
        self.api_key = os.getenv(
            self.api_config.get("api_key_env", "ETHERSCAN_API_KEY"),
            os.getenv("ETHERSCAN_API_KEY", "")
        )
        self.dex_routers = DEX_ROUTERS.get(chain, DEX_ROUTERS["ethereum"])

    def get_transactions(self, address: str, max_txs: int = 1000) -> list[dict]:
        """Get transaction history."""
        try:
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "page": 1,
                "offset": max_txs,
                "apikey": self.api_key
            }

            response = requests.get(self.api_config["api"], params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])

        except Exception as e:
            print(f"  Error fetching transactions: {e}")

        return []

    def get_token_transfers(self, address: str, max_txs: int = 500) -> list[dict]:
        """Get ERC20 token transfers."""
        try:
            params = {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "page": 1,
                "offset": max_txs,
                "apikey": self.api_key
            }

            response = requests.get(self.api_config["api"], params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])

        except Exception:
            pass

        return []

    def analyze_address(self, address: str) -> dict:
        """
        Analyze DEX trading patterns for an address.

        Returns:
            Dict with trading statistics and patterns
        """
        address = address.lower()
        results = {
            "address": address,
            "chain": self.chain,
            "dex_interactions": defaultdict(int),
            "tokens_traded": defaultdict(int),
            "total_swaps": 0,
            "total_volume_eth": 0,
            "first_swap": None,
            "last_swap": None,
            "avg_swap_size_eth": 0,
            "trading_frequency": None,  # swaps per day
            "preferred_dex": None,
            "top_tokens": [],
        }

        # Get transactions
        txs = self.get_transactions(address)
        token_transfers = self.get_token_transfers(address)

        # Analyze DEX interactions
        swap_timestamps = []
        for tx in txs:
            to_addr = tx.get("to", "").lower()
            value_eth = int(tx.get("value", 0)) / 1e18

            # Check if interacting with known DEX
            if to_addr in self.dex_routers:
                dex_name = self.dex_routers[to_addr]
                results["dex_interactions"][dex_name] += 1
                results["total_swaps"] += 1
                results["total_volume_eth"] += value_eth

                timestamp = int(tx.get("timeStamp", 0))
                swap_timestamps.append(timestamp)

        # Analyze token transfers for trading patterns
        for transfer in token_transfers:
            token_symbol = transfer.get("tokenSymbol", "UNKNOWN")
            results["tokens_traded"][token_symbol] += 1

        # Calculate statistics
        if swap_timestamps:
            swap_timestamps.sort()
            results["first_swap"] = swap_timestamps[0]
            results["last_swap"] = swap_timestamps[-1]

            if results["total_swaps"] > 0:
                results["avg_swap_size_eth"] = results["total_volume_eth"] / results["total_swaps"]

            # Trading frequency (swaps per day)
            if len(swap_timestamps) > 1:
                time_span_days = (swap_timestamps[-1] - swap_timestamps[0]) / 86400
                if time_span_days > 0:
                    results["trading_frequency"] = results["total_swaps"] / time_span_days

        # Determine preferred DEX
        if results["dex_interactions"]:
            results["preferred_dex"] = max(
                results["dex_interactions"].items(),
                key=lambda x: x[1]
            )[0]

        # Top 5 tokens
        results["top_tokens"] = sorted(
            results["tokens_traded"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Convert defaultdicts for JSON serialization
        results["dex_interactions"] = dict(results["dex_interactions"])
        results["tokens_traded"] = dict(results["tokens_traded"])

        return results

    def analyze_batch(self, addresses: list[str], show_progress: bool = True) -> list[dict]:
        """Analyze multiple addresses."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            result = self.analyze_address(address)
            results.append(result)

            if show_progress and (i + 1) % 10 == 0:
                active = sum(1 for r in results if r["total_swaps"] > 0)
                print(f"  Progress: {i + 1}/{total} ({active} with DEX activity)")

            # Rate limit
            time.sleep(0.25)

        return results


def format_timestamp(ts: Optional[int]) -> str:
    """Format Unix timestamp."""
    from datetime import datetime
    if ts:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return "N/A"


def process_csv(input_path: str, output_path: str, analyzer: DEXAnalyzer, address_column: str = "address"):
    """Process CSV file and add DEX analysis."""
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

    print(f"Analyzing {len(addresses)} addresses for DEX activity on {analyzer.chain}")

    # Add columns
    new_columns = ["total_swaps", "preferred_dex", "top_tokens", "trading_frequency", "total_volume_eth"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    # Analyze
    results = analyzer.analyze_batch(addresses)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        row["total_swaps"] = result.get("total_swaps", 0)
        row["preferred_dex"] = result.get("preferred_dex", "")
        row["top_tokens"] = ",".join([t[0] for t in result.get("top_tokens", [])])
        row["trading_frequency"] = f"{result.get('trading_frequency', 0):.2f}" if result.get("trading_frequency") else ""
        row["total_volume_eth"] = f"{result.get('total_volume_eth', 0):.4f}" if result.get("total_volume_eth") else ""

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    active_traders = sum(1 for r in results if r["total_swaps"] > 0)
    total_swaps = sum(r["total_swaps"] for r in results)

    print(f"\nResults:")
    print(f"  Active DEX traders: {active_traders}/{len(results)}")
    print(f"  Total swaps analyzed: {total_swaps}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="DEX trading pattern analyzer")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--chain", default="ethereum", help="Chain to analyze (ethereum, arbitrum, base)")
    parser.add_argument("--column", default="address", help="Column containing addresses")

    args = parser.parse_args()

    analyzer = DEXAnalyzer(chain=args.chain)

    if args.address:
        # Single address
        print(f"Analyzing {args.address} on {args.chain}...")
        result = analyzer.analyze_address(args.address)

        print(f"\n{args.address}")
        print("-" * 70)

        if result["total_swaps"] > 0:
            print(f"Total Swaps: {result['total_swaps']}")
            print(f"Total Volume: {result['total_volume_eth']:.4f} ETH")
            print(f"Avg Swap Size: {result['avg_swap_size_eth']:.4f} ETH")
            print(f"First Swap: {format_timestamp(result['first_swap'])}")
            print(f"Last Swap: {format_timestamp(result['last_swap'])}")
            if result["trading_frequency"]:
                print(f"Trading Frequency: {result['trading_frequency']:.2f} swaps/day")
            print()

            print("DEX Usage:")
            for dex, count in sorted(result["dex_interactions"].items(), key=lambda x: -x[1]):
                print(f"  {dex}: {count} txs")
            print()

            print("Top Tokens Traded:")
            for token, count in result["top_tokens"]:
                print(f"  {token}: {count} transfers")
        else:
            print("  No DEX activity found")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', f'_dex_{args.chain}.csv')
        process_csv(args.input, output_path, analyzer, args.column)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
