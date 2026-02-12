#!/usr/bin/env python3
"""
Multi-chain Balance Aggregator - Query same address across multiple chains.

Reveals total cross-chain holdings for whale research.
Uses public RPCs and block explorer APIs.

Usage:
    # Single address across all chains
    python3 scripts/multichain_balance.py --address 0x1234...

    # Batch from CSV
    python3 scripts/multichain_balance.py addresses.csv -o balances.csv

    # Specific chains only
    python3 scripts/multichain_balance.py --address 0x1234... --chains ethereum,arbitrum,base

Based on: ZachXBT methodology - cross-chain fund tracing
"""

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

# Chain configurations
CHAINS = {
    "ethereum": {
        "rpc": os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com"),
        "explorer_api": "https://api.etherscan.io/api",
        "api_key_env": "ETHERSCAN_API_KEY",
        "native_symbol": "ETH",
        "decimals": 18,
    },
    "arbitrum": {
        "rpc": os.getenv("ARB_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "explorer_api": "https://api.arbiscan.io/api",
        "api_key_env": "ARBISCAN_API_KEY",
        "native_symbol": "ETH",
        "decimals": 18,
    },
    "base": {
        "rpc": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
        "explorer_api": "https://api.basescan.org/api",
        "api_key_env": "BASESCAN_API_KEY",
        "native_symbol": "ETH",
        "decimals": 18,
    },
    "polygon": {
        "rpc": os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
        "explorer_api": "https://api.polygonscan.com/api",
        "api_key_env": "POLYGONSCAN_API_KEY",
        "native_symbol": "MATIC",
        "decimals": 18,
    },
    "optimism": {
        "rpc": os.getenv("OP_RPC_URL", "https://mainnet.optimism.io"),
        "explorer_api": "https://api-optimistic.etherscan.io/api",
        "api_key_env": "OPTIMISM_API_KEY",
        "native_symbol": "ETH",
        "decimals": 18,
    },
    "avalanche": {
        "rpc": os.getenv("AVAX_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
        "explorer_api": "https://api.snowtrace.io/api",
        "api_key_env": "SNOWTRACE_API_KEY",
        "native_symbol": "AVAX",
        "decimals": 18,
    },
    "bsc": {
        "rpc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org"),
        "explorer_api": "https://api.bscscan.com/api",
        "api_key_env": "BSCSCAN_API_KEY",
        "native_symbol": "BNB",
        "decimals": 18,
    },
}

# Common stablecoin addresses across chains
STABLECOINS = {
    "ethereum": {
        "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
    },
    "arbitrum": {
        "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
        "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
        "DAI": "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",
    },
    "base": {
        "USDC": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        "USDbC": "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca",
    },
    "polygon": {
        "USDC": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
        "USDT": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
        "DAI": "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063",
    },
}


class MultichainBalanceChecker:
    """Query balances across multiple chains."""

    def __init__(self, chains: Optional[list[str]] = None):
        self.chains = chains or list(CHAINS.keys())
        self.api_keys = {}

        # Load API keys
        for chain, config in CHAINS.items():
            key_env = config.get("api_key_env")
            if key_env:
                self.api_keys[chain] = os.getenv(key_env, os.getenv("ETHERSCAN_API_KEY", ""))

    def get_native_balance(self, address: str, chain: str) -> Optional[float]:
        """Get native token balance on a chain."""
        config = CHAINS.get(chain)
        if not config:
            return None

        try:
            # Try RPC call first
            rpc_url = config["rpc"]
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": 1
            }

            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json().get("result")
                if result:
                    balance_wei = int(result, 16)
                    return balance_wei / (10 ** config["decimals"])

        except Exception as e:
            # Fallback to explorer API
            pass

        try:
            api_url = config["explorer_api"]
            api_key = self.api_keys.get(chain, "")

            params = {
                "module": "account",
                "action": "balance",
                "address": address,
                "tag": "latest",
                "apikey": api_key
            }

            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    balance_wei = int(data.get("result", 0))
                    return balance_wei / (10 ** config["decimals"])

        except Exception as e:
            print(f"  Error getting {chain} balance: {e}")

        return None

    def get_token_balance(self, address: str, token_address: str, chain: str) -> Optional[float]:
        """Get ERC20 token balance."""
        config = CHAINS.get(chain)
        if not config:
            return None

        try:
            api_url = config["explorer_api"]
            api_key = self.api_keys.get(chain, "")

            params = {
                "module": "account",
                "action": "tokenbalance",
                "contractaddress": token_address,
                "address": address,
                "tag": "latest",
                "apikey": api_key
            }

            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    balance = int(data.get("result", 0))
                    # Assume 6 decimals for stablecoins, 18 for others
                    decimals = 6 if "USD" in token_address.upper() else 18
                    return balance / (10 ** decimals)

        except Exception as e:
            pass

        return None

    def get_tx_count(self, address: str, chain: str) -> Optional[int]:
        """Get transaction count on a chain."""
        config = CHAINS.get(chain)
        if not config:
            return None

        try:
            rpc_url = config["rpc"]
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionCount",
                "params": [address, "latest"],
                "id": 1
            }

            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json().get("result")
                if result:
                    return int(result, 16)

        except Exception:
            pass

        return None

    def check_address(self, address: str, include_stablecoins: bool = False) -> dict:
        """
        Check an address across all configured chains.

        Returns:
            Dict with chain → {native_balance, tx_count, stablecoins}
        """
        results = {
            "address": address,
            "chains": {},
            "total_native_usd": 0,
            "active_chains": [],
        }

        for chain in self.chains:
            chain_data = {
                "native_balance": None,
                "native_symbol": CHAINS[chain]["native_symbol"],
                "tx_count": None,
            }

            # Get native balance
            balance = self.get_native_balance(address, chain)
            chain_data["native_balance"] = balance

            # Get tx count
            tx_count = self.get_tx_count(address, chain)
            chain_data["tx_count"] = tx_count

            if tx_count and tx_count > 0:
                results["active_chains"].append(chain)

            # Get stablecoins if requested
            if include_stablecoins and chain in STABLECOINS:
                chain_data["stablecoins"] = {}
                for symbol, token_addr in STABLECOINS[chain].items():
                    token_balance = self.get_token_balance(address, token_addr, chain)
                    if token_balance and token_balance > 0:
                        chain_data["stablecoins"][symbol] = token_balance

            results["chains"][chain] = chain_data

            # Small delay to avoid rate limits
            time.sleep(0.2)

        return results

    def check_batch(self, addresses: list[str], show_progress: bool = True) -> list[dict]:
        """Check multiple addresses."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            result = self.check_address(address)
            results.append(result)

            if show_progress and (i + 1) % 5 == 0:
                print(f"  Progress: {i + 1}/{total}")

        return results


def format_balance(balance: Optional[float], decimals: int = 4) -> str:
    """Format balance for display."""
    if balance is None:
        return "N/A"
    if balance == 0:
        return "0"
    if balance < 0.0001:
        return "<0.0001"
    return f"{balance:,.{decimals}f}"


def process_csv(input_path: str, output_path: str, checker: MultichainBalanceChecker, address_column: str = "address"):
    """Process CSV file and add multichain balances."""
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

    print(f"Checking {len(addresses)} addresses across {len(checker.chains)} chains")

    # Add columns for each chain
    for chain in checker.chains:
        col_name = f"{chain}_balance"
        if col_name not in fieldnames:
            fieldnames.append(col_name)

    if "active_chains" not in fieldnames:
        fieldnames.append("active_chains")
    if "chain_count" not in fieldnames:
        fieldnames.append("chain_count")

    # Check balances
    results = checker.check_batch(addresses)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        for chain in checker.chains:
            chain_data = result.get("chains", {}).get(chain, {})
            balance = chain_data.get("native_balance")
            row[f"{chain}_balance"] = format_balance(balance) if balance else ""

        row["active_chains"] = ",".join(result.get("active_chains", []))
        row["chain_count"] = len(result.get("active_chains", []))

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    multi_chain = sum(1 for r in results if len(r.get("active_chains", [])) > 1)
    print(f"\nResults:")
    print(f"  Single-chain users: {len(results) - multi_chain}")
    print(f"  Multi-chain users: {multi_chain}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Multi-chain balance checker")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to check")
    parser.add_argument("--chains", help="Comma-separated list of chains (default: all)")
    parser.add_argument("--column", default="address", help="Column containing addresses")
    parser.add_argument("--stablecoins", action="store_true", help="Include stablecoin balances")

    args = parser.parse_args()

    chains = args.chains.split(",") if args.chains else None
    checker = MultichainBalanceChecker(chains=chains)

    if args.address:
        # Single address
        print(f"Checking {args.address} across {len(checker.chains)} chains...")
        result = checker.check_address(args.address, include_stablecoins=args.stablecoins)

        print(f"\n{args.address}")
        print("-" * 60)

        for chain, data in result["chains"].items():
            balance = data.get("native_balance")
            tx_count = data.get("tx_count")
            symbol = data.get("native_symbol")

            balance_str = format_balance(balance) if balance else "0"
            tx_str = str(tx_count) if tx_count else "0"

            print(f"  {chain:12} | {balance_str:>15} {symbol:5} | {tx_str:>6} txs")

            if data.get("stablecoins"):
                for symbol, amount in data["stablecoins"].items():
                    print(f"  {' ':12} | {format_balance(amount):>15} {symbol}")

        print("-" * 60)
        print(f"Active on {len(result['active_chains'])} chains: {', '.join(result['active_chains'])}")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_multichain.csv')
        process_csv(args.input, output_path, checker, args.column)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
