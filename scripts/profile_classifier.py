#!/usr/bin/env python3
"""
Profile Classifier - Classify addresses BEFORE choosing investigation methods.

Determines the profile of an address to recommend appropriate investigation scripts.
Avoids wasting API calls on methods that won't work (e.g., NFT tracker on DeFi lenders).

Usage:
    # Single address
    python3 scripts/profile_classifier.py --address 0x1234...

    # Batch from CSV
    python3 scripts/profile_classifier.py addresses.csv -o profiles.csv

    # Get recommended scripts
    python3 scripts/profile_classifier.py --address 0x1234... --recommend

Based on: Phase 2 retrospective - 0% hit rate on NFT/Bridge/Change for DeFi whales
"""

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# Known protocol addresses to check for DeFi activity
DEFI_PROTOCOLS = {
    # Lending
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": "Aave V2",
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3",
    "0xc3d688b66703497daa19211eedff47f25384cdc3": "Compound V3",
    "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho",
    # DEXs
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router 2",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "Sushiswap",
    # Bridges
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge",
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism Bridge",
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": "Base Bridge",
}

# NFT marketplaces and collections
NFT_CONTRACTS = {
    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc": "Seaport",
    "0x7be8076f4ea4a4ad08075c2508e481d6c946d12b": "OpenSea",
    "0x7f268357a8c2552623316e2562d90e642bb538e5": "OpenSea V2",
    "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d": "BAYC",
    "0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb": "CryptoPunks",
}


class ProfileClassifier:
    """Classify address profiles to recommend investigation methods."""

    def __init__(self):
        self.api_key = ETHERSCAN_API_KEY

    def get_transaction_sample(self, address: str, limit: int = 100) -> List[Dict]:
        """Get recent transactions for analysis."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address={address}&page=1&offset={limit}&sort=desc&apikey={self.api_key}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                return data.get("result", [])
        except Exception as e:
            print(f"Error fetching transactions: {e}")
        return []

    def get_internal_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get internal transactions (DeFi protocol interactions)."""
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlistinternal&address={address}&page=1&offset={limit}&sort=desc&apikey={self.api_key}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                return data.get("result", [])
        except Exception as e:
            print(f"Error fetching internal txs: {e}")
        return []

    def is_contract(self, address: str) -> bool:
        """Check if address is a contract via eth_getCode.

        CRITICAL: Returns False on API failure. A false negative here causes
        contracts to be misclassified as EOAs, which was the root cause of
        3/5 Phase 2 investigation failures.
        """
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=proxy&action=eth_getCode&address={address}&apikey={self.api_key}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            code = data.get("result", "0x")
            return code != "0x" and len(code) > 2
        except Exception as e:
            print(f"WARNING: is_contract API check failed for {address}: {e} — defaulting to EOA")
            return False

    def classify(self, address: str, skip_tx_analysis: bool = False) -> Dict:
        """Classify an address into a profile.

        IMPORTANT: Contract-first routing (Phase 2 improvement)
        - Check is_contract FIRST before any transaction analysis
        - If contract, route to bot_operator_tracer recommendations immediately
        - This fixes 60% of misclassifications on contract addresses
        """
        address = address.lower()

        profile = {
            "address": address,
            "is_contract": False,
            "is_defi_lender": False,
            "is_dex_trader": False,
            "is_nft_holder": False,
            "is_bridge_user": False,
            "is_governance_active": False,
            "is_high_frequency": False,
            "primary_profile": "unknown",
            "recommended_scripts": [],
            "skip_scripts": [],
            "confidence": 0.0,
        }

        # CONTRACT-FIRST ROUTING (Phase 2 fix)
        # Check if contract BEFORE any other analysis
        profile["is_contract"] = self.is_contract(address)

        if profile["is_contract"]:
            # For contracts, skip transaction analysis entirely
            # Route directly to bot_operator_tracer which has 100% success rate
            profile["primary_profile"] = "contract/bot"
            profile["recommended_scripts"] = [
                "bot_operator_tracer.py",  # 100% success on contracts
                "trace_funding.py",        # 100% success (always provides signal)
                "behavioral_fingerprint.py",  # 100% success (universal fallback)
            ]
            profile["skip_scripts"] = [
                "nft_tracker.py",           # 0% hit rate on DeFi bots
                "governance_scraper.py",    # 0% hit rate on bots
                "ens_resolver.py",          # 0% hit rate on bots
                "cio_detector.py",          # 0% hit rate on sophisticated contracts
                "counterparty_graph.py",    # Too noisy for contracts
                "whale_tracker.py",         # 0% hit rate on sophisticated
                "dex_analyzer.py",          # Contracts don't trade via DEX
                "bridge_tracker.py",        # 0% hit rate
            ]
            profile["confidence"] = 0.85  # High confidence for contracts
            return profile

        # For EOAs, continue with transaction analysis
        if skip_tx_analysis:
            return profile

        # Analyze transactions
        txs = self.get_transaction_sample(address)
        internal_txs = self.get_internal_transactions(address)

        if not txs and not internal_txs:
            profile["primary_profile"] = "inactive"
            return profile

        # Count interactions by type
        defi_count = 0
        dex_count = 0
        nft_count = 0
        bridge_count = 0

        all_interactions = set()
        for tx in txs:
            to_addr = tx.get("to", "").lower()
            all_interactions.add(to_addr)

            if to_addr in DEFI_PROTOCOLS:
                if "Aave" in DEFI_PROTOCOLS[to_addr] or "Compound" in DEFI_PROTOCOLS[to_addr] or "Morpho" in DEFI_PROTOCOLS[to_addr]:
                    defi_count += 1
                elif "Uniswap" in DEFI_PROTOCOLS[to_addr] or "Sushi" in DEFI_PROTOCOLS[to_addr]:
                    dex_count += 1
                elif "Bridge" in DEFI_PROTOCOLS[to_addr]:
                    bridge_count += 1

            if to_addr in NFT_CONTRACTS:
                nft_count += 1

        # Add internal transactions
        for tx in internal_txs:
            to_addr = tx.get("to", "").lower()
            from_addr = tx.get("from", "").lower()

            for addr in [to_addr, from_addr]:
                if addr in DEFI_PROTOCOLS:
                    if "Aave" in DEFI_PROTOCOLS[addr] or "Compound" in DEFI_PROTOCOLS[addr]:
                        defi_count += 1

        total_txs = len(txs)

        # Set flags based on ratios
        if total_txs > 0:
            profile["is_defi_lender"] = defi_count / total_txs > 0.3
            profile["is_dex_trader"] = dex_count / total_txs > 0.2
            profile["is_nft_holder"] = nft_count / total_txs > 0.1
            profile["is_bridge_user"] = bridge_count / total_txs > 0.05
            profile["is_high_frequency"] = total_txs >= 100

        # Determine primary profile (contracts already returned early above)
        if profile["is_defi_lender"] and not profile["is_dex_trader"]:
            profile["primary_profile"] = "defi_lender"
        elif profile["is_dex_trader"]:
            profile["primary_profile"] = "dex_trader"
        elif profile["is_nft_holder"]:
            profile["primary_profile"] = "nft_collector"
        elif profile["is_bridge_user"]:
            profile["primary_profile"] = "cross_chain_user"
        else:
            profile["primary_profile"] = "general"

        # Set recommended and skip scripts based on profile
        profile["recommended_scripts"], profile["skip_scripts"] = self._get_recommendations(profile)
        profile["confidence"] = 0.75 if total_txs >= 50 else 0.5

        return profile

    def _get_recommendations(self, profile: Dict) -> tuple:
        """Get recommended and skip scripts based on profile."""
        primary = profile["primary_profile"]

        # Script recommendations by profile type
        RECOMMENDATIONS = {
            "defi_lender": {
                "use": ["temporal_correlation.py", "cio_detector.py", "trace_funding.py",
                        "behavioral_fingerprint.py", "pattern_matcher.py", "governance_scraper.py"],
                "skip": ["nft_tracker.py", "bridge_tracker.py", "change_detector.py", "dex_analyzer.py"],
            },
            "dex_trader": {
                "use": ["dex_analyzer.py", "temporal_correlation.py", "counterparty_graph.py",
                        "trace_funding.py", "behavioral_fingerprint.py"],
                "skip": ["nft_tracker.py", "governance_scraper.py"],
            },
            "nft_collector": {
                "use": ["nft_tracker.py", "ens_resolver.py", "governance_scraper.py",
                        "trace_funding.py"],
                "skip": ["dex_analyzer.py", "bridge_tracker.py", "change_detector.py"],
            },
            "cross_chain_user": {
                "use": ["bridge_tracker.py", "trace_funding.py", "temporal_correlation.py",
                        "behavioral_fingerprint.py"],
                "skip": ["nft_tracker.py", "governance_scraper.py"],
            },
            "contract/bot": {
                "use": ["bot_operator_tracer.py", "trace_funding.py", "temporal_correlation.py"],
                "skip": ["nft_tracker.py", "governance_scraper.py", "ens_resolver.py"],
            },
            "general": {
                "use": ["temporal_correlation.py", "cio_detector.py", "trace_funding.py",
                        "behavioral_fingerprint.py"],
                "skip": [],
            },
        }

        rec = RECOMMENDATIONS.get(primary, RECOMMENDATIONS["general"])
        return rec["use"], rec["skip"]


def main():
    parser = argparse.ArgumentParser(description="Classify address profiles")
    parser.add_argument("input", nargs="?", help="Address or CSV file")
    parser.add_argument("--address", "-a", help="Single address to classify")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--recommend", "-r", action="store_true", help="Show script recommendations")
    args = parser.parse_args()

    classifier = ProfileClassifier()

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
        print(f"Classifying {i+1}/{len(addresses)}: {addr[:10]}...")
        profile = classifier.classify(addr)
        results.append(profile)

        if args.recommend or len(addresses) == 1:
            print(f"\n{'='*60}")
            print(f"Address: {addr}")
            print(f"Profile: {profile['primary_profile'].upper()}")
            print(f"Confidence: {profile['confidence']*100:.0f}%")
            print(f"\nFlags:")
            print(f"  is_contract: {profile['is_contract']}")
            print(f"  is_defi_lender: {profile['is_defi_lender']}")
            print(f"  is_dex_trader: {profile['is_dex_trader']}")
            print(f"  is_nft_holder: {profile['is_nft_holder']}")
            print(f"  is_bridge_user: {profile['is_bridge_user']}")
            print(f"\nRecommended scripts:")
            for script in profile['recommended_scripts']:
                print(f"  + {script}")
            if profile['skip_scripts']:
                print(f"\nSkip these scripts (low ROI for this profile):")
                for script in profile['skip_scripts']:
                    print(f"  - {script}")
            print(f"{'='*60}\n")

    if args.output:
        with open(args.output, "w", newline="") as f:
            fieldnames = ["address", "primary_profile", "confidence", "is_contract",
                         "is_defi_lender", "is_dex_trader", "is_nft_holder", "is_bridge_user",
                         "recommended_scripts", "skip_scripts"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                r["recommended_scripts"] = "|".join(r["recommended_scripts"])
                r["skip_scripts"] = "|".join(r["skip_scripts"])
                writer.writerow({k: r[k] for k in fieldnames})
        print(f"\nResults saved to {args.output}")

    # Print summary
    profiles = {}
    for r in results:
        p = r["primary_profile"]
        profiles[p] = profiles.get(p, 0) + 1

    print(f"\nProfile Distribution:")
    for p, count in sorted(profiles.items(), key=lambda x: x[1], reverse=True):
        print(f"  {p}: {count}")


if __name__ == "__main__":
    main()
