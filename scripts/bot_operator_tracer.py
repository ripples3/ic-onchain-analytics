#!/usr/bin/env python3
"""
Bot Operator Tracer - For flash loan/MEV bots, trace the OPERATOR not the contract.

Key insight: Top DeFi borrowers include bots with billions in cumulative activity.
The bot itself isn't the BD target, but the OPERATOR is. This script traces:
1. Contract deployer
2. Other contracts deployed by same deployer (pattern of activity)
3. Profit destinations (where outflows go = operator's wallet)
4. MEV builder relationships

Usage:
    # Single address (contract or EOA)
    python3 scripts/bot_operator_tracer.py --address 0x1234...

    # Batch from CSV
    python3 scripts/bot_operator_tracer.py contracts.csv -o operators.csv

    # Deep trace with profit flow analysis
    python3 scripts/bot_operator_tracer.py --address 0x1234... --deep

Based on: Phase 2 retrospective - Top 3 addresses were flash loan bots
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# Known MEV builders and relays
MEV_BUILDERS = {
    "0x95222290dd7278aa3ddd389cc1e1d165cc4bafe5": "beaverbuild.org",
    "0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97": "Titan Builder",
    "0x1f9090aae28b8a3dceadf281b0f12828e676c326": "Flashbots Builder",
    "0x690b9a9e9aa1c9db991c7721a92d351db4fac990": "builder0x69",
    "0xdafea492d9c6733ae3d56b7ed1adb60692c98bc5": "Flashbots Relay",
}

# Known flash loan providers
FLASH_LOAN_PROVIDERS = {
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3",
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": "Aave V2",
    "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho Blue",
    "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f": "Uniswap V2 Factory",
    "0x1f98431c8ad98523631ae4a59f267346ea31f984": "Uniswap V3 Factory",
}


class BotOperatorTracer:
    """Trace operators behind bot contracts."""

    def __init__(self):
        self.api_key = ETHERSCAN_API_KEY
        self.rate_limit = 5.0
        self.last_request = 0

    def _rate_limited_request(self, url: str) -> Dict:
        """Make rate-limited API request."""
        elapsed = time.time() - self.last_request
        if elapsed < 1 / self.rate_limit:
            time.sleep(1 / self.rate_limit - elapsed)

        try:
            resp = requests.get(url, timeout=15)
            self.last_request = time.time()
            return resp.json()
        except Exception as e:
            print(f"Request error: {e}")
            return {}

    def is_contract(self, address: str) -> bool:
        """Check if address is a contract."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=proxy&action=eth_getCode&address={address}&apikey={self.api_key}"
        data = self._rate_limited_request(url)
        code = data.get("result", "0x")
        return code != "0x" and len(code) > 2

    def get_contract_creator(self, contract_address: str) -> Optional[Dict]:
        """Get the deployer of a contract."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getcontractcreation&contractaddresses={contract_address}&apikey={self.api_key}"
        data = self._rate_limited_request(url)

        if data.get("status") == "1" and data.get("result"):
            result = data["result"][0]
            return {
                "deployer": result.get("contractCreator", "").lower(),
                "creation_tx": result.get("txHash", ""),
            }
        return None

    def get_contracts_by_deployer(self, deployer: str, limit: int = 50) -> List[Dict]:
        """Get other contracts deployed by the same address."""
        # Get outgoing transactions that created contracts
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address={deployer}&page=1&offset={limit}&sort=desc&apikey={self.api_key}"
        data = self._rate_limited_request(url)

        contracts = []
        if data.get("status") == "1":
            for tx in data.get("result", []):
                # Contract creation has empty 'to' field
                if tx.get("to") == "" and tx.get("from", "").lower() == deployer.lower():
                    contract_addr = tx.get("contractAddress", "")
                    if contract_addr:
                        contracts.append({
                            "address": contract_addr.lower(),
                            "creation_tx": tx.get("hash", ""),
                            "timestamp": int(tx.get("timeStamp", 0)),
                        })

        return contracts

    def get_profit_destinations(self, address: str, limit: int = 100) -> List[Dict]:
        """Track where value flows OUT of the address (operator's wallet)."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address={address}&page=1&offset={limit}&sort=desc&apikey={self.api_key}"
        data = self._rate_limited_request(url)

        destinations = defaultdict(lambda: {"count": 0, "total_eth": 0.0})

        if data.get("status") == "1":
            for tx in data.get("result", []):
                if tx.get("from", "").lower() == address.lower():
                    to_addr = tx.get("to", "").lower()
                    value = int(tx.get("value", 0)) / 1e18

                    if value > 0.01:  # Ignore dust
                        destinations[to_addr]["count"] += 1
                        destinations[to_addr]["total_eth"] += value

        # Sort by total value
        sorted_dests = sorted(
            [(addr, data) for addr, data in destinations.items()],
            key=lambda x: x[1]["total_eth"],
            reverse=True
        )

        return [
            {"address": addr, "count": data["count"], "total_eth": data["total_eth"]}
            for addr, data in sorted_dests[:20]
        ]

    def check_mev_builder_funding(self, address: str) -> Optional[Dict]:
        """Check if address was funded by a known MEV builder."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address={address}&page=1&offset=10&sort=asc&apikey={self.api_key}"
        data = self._rate_limited_request(url)

        if data.get("status") == "1":
            for tx in data.get("result", []):
                from_addr = tx.get("from", "").lower()
                if from_addr in MEV_BUILDERS:
                    return {
                        "builder": MEV_BUILDERS[from_addr],
                        "address": from_addr,
                        "tx": tx.get("hash", ""),
                    }
        return None

    def analyze_flash_loan_usage(self, address: str) -> Dict:
        """Analyze flash loan provider interactions."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlistinternal&address={address}&page=1&offset=200&sort=desc&apikey={self.api_key}"
        data = self._rate_limited_request(url)

        providers_used = defaultdict(int)

        if data.get("status") == "1":
            for tx in data.get("result", []):
                for addr in [tx.get("from", "").lower(), tx.get("to", "").lower()]:
                    if addr in FLASH_LOAN_PROVIDERS:
                        providers_used[FLASH_LOAN_PROVIDERS[addr]] += 1

        return dict(providers_used)

    def analyze_profit_flow(self, address: str) -> Dict:
        """Analyze profit flow concentration to identify operator structure.

        Phase 2 improvement: Profit concentration reveals operator type.

        Key insight from 0xdb7030be investigation:
        - $45M profit → single beneficiary → single operator
        - 80%+ concentration = Single operator
        - 50-80% = Primary operator with partners
        - <50% = Distributed operation (team/DAO)
        """
        destinations = self.get_profit_destinations(address, limit=200)

        if not destinations:
            return {
                "concentration": 0.0,
                "operator_type": "unknown",
                "top_recipient": None,
                "total_eth": 0.0,
                "recipient_count": 0,
            }

        total_eth = sum(d["total_eth"] for d in destinations)
        if total_eth == 0:
            return {
                "concentration": 0.0,
                "operator_type": "no_outflow",
                "top_recipient": None,
                "total_eth": 0.0,
                "recipient_count": len(destinations),
            }

        # Calculate concentration
        top_recipient = destinations[0] if destinations else None
        top_eth = top_recipient["total_eth"] if top_recipient else 0
        concentration = top_eth / total_eth if total_eth > 0 else 0

        # Classify operator structure
        if concentration >= 0.8:
            operator_type = "single_operator"
        elif concentration >= 0.5:
            operator_type = "primary_with_partners"
        elif concentration >= 0.3:
            operator_type = "small_team"
        else:
            operator_type = "distributed_operation"

        return {
            "concentration": concentration,
            "operator_type": operator_type,
            "top_recipient": top_recipient["address"] if top_recipient else None,
            "top_recipient_eth": top_eth,
            "total_eth": total_eth,
            "recipient_count": len(destinations),
        }

    def trace_operator(self, address: str, deep: bool = False) -> Dict:
        """Full operator trace for a bot/contract address."""
        address = address.lower()

        result = {
            "address": address,
            "is_contract": False,
            "deployer": None,
            "related_contracts": [],
            "profit_destinations": [],
            "profit_flow": {},  # Phase 2: profit concentration analysis
            "mev_builder": None,
            "flash_loan_providers": {},
            "likely_operator": None,
            "confidence": 0.0,
            "operator_type": "unknown",
        }

        # Check if contract
        result["is_contract"] = self.is_contract(address)

        if result["is_contract"]:
            # Get deployer
            creator = self.get_contract_creator(address)
            if creator:
                result["deployer"] = creator["deployer"]

                # Get other contracts by deployer
                if deep:
                    result["related_contracts"] = self.get_contracts_by_deployer(creator["deployer"])

                # Check if deployer is the operator (EOA)
                if not self.is_contract(creator["deployer"]):
                    result["likely_operator"] = creator["deployer"]
                    result["confidence"] = 0.85

            # Get profit destinations
            result["profit_destinations"] = self.get_profit_destinations(address)

            # If no deployer found, operator might be in profit destinations
            if not result["likely_operator"] and result["profit_destinations"]:
                top_dest = result["profit_destinations"][0]
                if not self.is_contract(top_dest["address"]) and top_dest["total_eth"] > 1.0:
                    result["likely_operator"] = top_dest["address"]
                    result["confidence"] = 0.70

            # Check for flash loan usage
            result["flash_loan_providers"] = self.analyze_flash_loan_usage(address)
            if result["flash_loan_providers"]:
                result["operator_type"] = "flash_loan_bot"

            # Phase 2: Analyze profit flow concentration
            result["profit_flow"] = self.analyze_profit_flow(address)

            # If profit flow shows single operator and we don't have one yet,
            # use top recipient as likely operator
            if not result["likely_operator"] and result["profit_flow"].get("concentration", 0) >= 0.5:
                top_recipient = result["profit_flow"].get("top_recipient")
                if top_recipient and not self.is_contract(top_recipient):
                    result["likely_operator"] = top_recipient
                    # Confidence based on concentration
                    concentration = result["profit_flow"]["concentration"]
                    result["confidence"] = max(result["confidence"], 0.6 + (concentration * 0.3))

        else:
            # It's an EOA, check if it deployed contracts
            related = self.get_contracts_by_deployer(address)
            if related:
                result["related_contracts"] = related
                result["operator_type"] = "bot_deployer"
                result["confidence"] = 0.80

            # Check MEV builder funding
            mev = self.check_mev_builder_funding(address)
            if mev:
                result["mev_builder"] = mev
                result["operator_type"] = "mev_operator"
                result["confidence"] = max(result["confidence"], 0.75)

            result["likely_operator"] = address

        return result


def main():
    parser = argparse.ArgumentParser(description="Trace bot operators")
    parser.add_argument("input", nargs="?", help="Address or CSV file")
    parser.add_argument("--address", "-a", help="Single address to trace")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--deep", "-d", action="store_true", help="Deep trace with related contracts")
    args = parser.parse_args()

    tracer = BotOperatorTracer()

    addresses = []
    if args.address:
        addresses = [args.address]
    elif args.input and args.input.endswith(".csv"):
        with open(args.input, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("address") or row.get("borrower") or list(row.values())[0]
                addresses.append(addr)
    elif args.input:
        addresses = [args.input]
    else:
        parser.print_help()
        sys.exit(1)

    results = []
    for i, addr in enumerate(addresses):
        print(f"\nTracing {i+1}/{len(addresses)}: {addr[:10]}...")
        result = tracer.trace_operator(addr, deep=args.deep)
        results.append(result)

        # Print results
        print(f"\n{'='*60}")
        print(f"Address: {addr}")
        print(f"Type: {'CONTRACT' if result['is_contract'] else 'EOA'}")

        if result["deployer"]:
            print(f"Deployer: {result['deployer']}")

        if result["likely_operator"]:
            print(f"Likely Operator: {result['likely_operator']}")
            print(f"Confidence: {result['confidence']*100:.0f}%")
            print(f"Operator Type: {result['operator_type']}")

        if result["mev_builder"]:
            print(f"MEV Builder: {result['mev_builder']['builder']}")

        if result["flash_loan_providers"]:
            print(f"Flash Loan Providers:")
            for provider, count in result["flash_loan_providers"].items():
                print(f"  - {provider}: {count} interactions")

        if result["related_contracts"]:
            print(f"Related Contracts ({len(result['related_contracts'])}):")
            for c in result["related_contracts"][:5]:
                print(f"  - {c['address'][:16]}...")

        if result["profit_destinations"]:
            print(f"Top Profit Destinations:")
            for d in result["profit_destinations"][:5]:
                print(f"  - {d['address'][:16]}... ({d['total_eth']:.2f} ETH, {d['count']} txs)")

        print(f"{'='*60}")

    if args.output:
        with open(args.output, "w", newline="") as f:
            fieldnames = ["address", "is_contract", "deployer", "likely_operator",
                         "confidence", "operator_type", "mev_builder", "related_contract_count"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "address": r["address"],
                    "is_contract": r["is_contract"],
                    "deployer": r["deployer"],
                    "likely_operator": r["likely_operator"],
                    "confidence": r["confidence"],
                    "operator_type": r["operator_type"],
                    "mev_builder": r["mev_builder"]["builder"] if r["mev_builder"] else "",
                    "related_contract_count": len(r["related_contracts"]),
                })
        print(f"\nResults saved to {args.output}")

    # Summary
    contracts = sum(1 for r in results if r["is_contract"])
    operators_found = sum(1 for r in results if r["likely_operator"])
    flash_bots = sum(1 for r in results if r["operator_type"] == "flash_loan_bot")
    mev_ops = sum(1 for r in results if r["operator_type"] == "mev_operator")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total addresses: {len(results)}")
    print(f"Contracts: {contracts}")
    print(f"Operators identified: {operators_found}")
    print(f"Flash loan bots: {flash_bots}")
    print(f"MEV operators: {mev_ops}")


if __name__ == "__main__":
    main()
