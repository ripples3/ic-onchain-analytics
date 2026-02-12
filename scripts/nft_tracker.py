#!/usr/bin/env python3
"""
NFT Tracker - Track NFT holdings and trading patterns.

Identifies identity through NFT collections:
- Blue chip holdings (BAYC, Punks, Azuki, etc.)
- PFP usage patterns
- Collection preferences
- Trading activity

Usage:
    # Single address
    python3 scripts/nft_tracker.py --address 0x1234...

    # Batch from CSV
    python3 scripts/nft_tracker.py addresses.csv -o nft_holdings.csv

    # Include trading history
    python3 scripts/nft_tracker.py --address 0x1234... --trades

Based on: NFT identity signals - blue chip holders often have public presence
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

# Known blue chip NFT collections
BLUE_CHIP_COLLECTIONS = {
    # Ethereum
    "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d": {"name": "Bored Ape Yacht Club", "symbol": "BAYC", "tier": 1},
    "0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb": {"name": "CryptoPunks", "symbol": "PUNK", "tier": 1},
    "0x60e4d786628fea6478f785a6d7e704777c86a7c6": {"name": "Mutant Ape Yacht Club", "symbol": "MAYC", "tier": 1},
    "0xed5af388653567af2f388e6224dc7c4b3241c544": {"name": "Azuki", "symbol": "AZUKI", "tier": 1},
    "0x49cf6f5d44e70224e2e23fdcdd2c053f30ada28b": {"name": "Clone X", "symbol": "CLONEX", "tier": 1},
    "0x8a90cab2b38dba80c64b7734e58ee1db38b8992e": {"name": "Doodles", "symbol": "DOODLE", "tier": 2},
    "0x23581767a106ae21c074b2276d25e5c3e136a68b": {"name": "Moonbirds", "symbol": "MOONBIRD", "tier": 2},
    "0x34d85c9cdeb23fa97cb08333b511ac86e1c4e258": {"name": "Otherdeed", "symbol": "OTHR", "tier": 2},
    "0x79fcdef22feed20eddacbb2587640e45491b757f": {"name": "mfers", "symbol": "MFER", "tier": 3},
    "0x1a92f7381b9f03921564a437210bb9396471050c": {"name": "Cool Cats", "symbol": "COOL", "tier": 3},
    "0x7bd29408f11d2bfc23c34f18275bbf23bb716bc7": {"name": "Meebits", "symbol": "MEEBIT", "tier": 2},
    "0x5cc5b05a8a13e3fbdb0bb9fccd98d38e50f90c38": {"name": "Sandbox LAND", "symbol": "LAND", "tier": 2},
    "0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85": {"name": "ENS Domains", "symbol": "ENS", "tier": 1},
    "0xa7d8d9ef8d8ce8992df33d8b8cf4aebabd5bd270": {"name": "Art Blocks", "symbol": "BLOCKS", "tier": 1},
    "0x059edd72cd353df5106d2b9cc5ab83a52287ac3a": {"name": "Art Blocks Curated", "symbol": "ABC", "tier": 1},
    "0x306b1ea3ecdf94ab739f1910bbda052ed4a9f949": {"name": "Beanz", "symbol": "BEANZ", "tier": 3},
    "0xba30e5f9bb24caa003e9f2f0497ad287fdf95623": {"name": "Bored Ape Kennel Club", "symbol": "BAKC", "tier": 2},
    "0x8821bee2ba0df28761afff119d66390d594cd280": {"name": "DeGods", "symbol": "DEGODS", "tier": 2},
    "0x524cab2ec69124574082676e6f654a18df49a048": {"name": "Lil Pudgys", "symbol": "LILPUDGY", "tier": 3},
    "0xbd3531da5cf5857e7cfaa92426877b022e612cf8": {"name": "Pudgy Penguins", "symbol": "PPG", "tier": 2},
}

# NFT marketplaces for trade detection
NFT_MARKETPLACES = {
    "0x00000000006c3852cbef3e08e8df289169ede581": "OpenSea Seaport",
    "0x00000000000001ad428e4906ae43d8f9852d0dd6": "OpenSea Seaport 1.4",
    "0x0000000000000ad24e80fd803c6ac37206a45f15": "OpenSea Seaport 1.5",
    "0x74312363e45dcaba76c59ec49a7aa8a65a67eed3": "X2Y2",
    "0x59728544b08ab483533076417fbbb2fd0b17ce3a": "LooksRare",
    "0x000000000000ad05ccc4f10045630fb830b95127": "Blur",
    "0x29469395eaf6f95920e59f858042f0e28d98a20b": "Blur Blend",
    "0x39da41747a83aee658334415666f3ef92dd0d541": "Blur Pool",
}


class NFTTracker:
    """Track NFT holdings and trading patterns."""

    def __init__(self):
        self.api_key = os.getenv("ETHERSCAN_API_KEY", "")

    def get_nft_transfers(self, address: str, max_txs: int = 1000) -> list[dict]:
        """Get NFT (ERC721) transfers for an address."""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "tokennfttx",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "page": 1,
                "offset": max_txs,
                "apikey": self.api_key
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])

        except Exception as e:
            print(f"  Error fetching NFT transfers: {e}")

        return []

    def get_erc1155_transfers(self, address: str, max_txs: int = 500) -> list[dict]:
        """Get ERC1155 transfers for an address."""
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "token1155tx",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "page": 1,
                "offset": max_txs,
                "apikey": self.api_key
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])

        except Exception:
            pass

        return []

    def get_transactions(self, address: str, max_txs: int = 500) -> list[dict]:
        """Get regular transactions for marketplace detection."""
        try:
            url = "https://api.etherscan.io/api"
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

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])

        except Exception:
            pass

        return []

    def analyze_holdings(self, address: str, include_trades: bool = False) -> dict:
        """
        Analyze NFT holdings and patterns.

        Returns:
            Dict with holdings, blue chips, and trading patterns
        """
        address = address.lower()
        results = {
            "address": address,
            "collections": defaultdict(lambda: {"held": 0, "bought": 0, "sold": 0, "tokens": []}),
            "blue_chip_count": 0,
            "blue_chip_collections": [],
            "total_nfts_held": 0,
            "total_bought": 0,
            "total_sold": 0,
            "marketplace_activity": defaultdict(int),
            "is_trader": False,
            "is_collector": False,
            "first_nft_tx": None,
            "last_nft_tx": None,
        }

        # Get NFT transfers
        nft_transfers = self.get_nft_transfers(address)
        erc1155_transfers = self.get_erc1155_transfers(address)

        all_transfers = nft_transfers + erc1155_transfers

        if not all_transfers:
            return results

        # Analyze transfers
        timestamps = []
        for transfer in all_transfers:
            contract = transfer.get("contractAddress", "").lower()
            token_id = transfer.get("tokenID", "")
            from_addr = transfer.get("from", "").lower()
            to_addr = transfer.get("to", "").lower()
            timestamp = int(transfer.get("timeStamp", 0))

            timestamps.append(timestamp)

            # Get collection info
            collection_name = transfer.get("tokenName", "Unknown")
            collection_symbol = transfer.get("tokenSymbol", "???")

            # Check blue chip
            blue_chip_info = BLUE_CHIP_COLLECTIONS.get(contract)
            if blue_chip_info:
                collection_name = blue_chip_info["name"]
                collection_symbol = blue_chip_info["symbol"]

            # Track holdings
            if to_addr == address:
                # Received/bought
                results["collections"][contract]["bought"] += 1
                results["collections"][contract]["held"] += 1
                results["collections"][contract]["tokens"].append(token_id)
                results["collections"][contract]["name"] = collection_name
                results["collections"][contract]["symbol"] = collection_symbol
                results["total_bought"] += 1

            if from_addr == address:
                # Sent/sold
                results["collections"][contract]["sold"] += 1
                results["collections"][contract]["held"] -= 1
                if token_id in results["collections"][contract]["tokens"]:
                    results["collections"][contract]["tokens"].remove(token_id)
                results["total_sold"] += 1

        # Get marketplace activity
        if include_trades:
            txs = self.get_transactions(address)
            for tx in txs:
                to_addr = tx.get("to", "").lower()
                if to_addr in NFT_MARKETPLACES:
                    results["marketplace_activity"][NFT_MARKETPLACES[to_addr]] += 1

        # Calculate blue chip holdings
        for contract, data in results["collections"].items():
            if data["held"] > 0:
                results["total_nfts_held"] += data["held"]

                if contract in BLUE_CHIP_COLLECTIONS:
                    blue_chip_info = BLUE_CHIP_COLLECTIONS[contract]
                    results["blue_chip_count"] += data["held"]
                    results["blue_chip_collections"].append({
                        "name": blue_chip_info["name"],
                        "symbol": blue_chip_info["symbol"],
                        "tier": blue_chip_info["tier"],
                        "count": data["held"],
                    })

        # Sort blue chips by tier
        results["blue_chip_collections"].sort(key=lambda x: (x["tier"], -x["count"]))

        # Timestamps
        if timestamps:
            timestamps.sort()
            results["first_nft_tx"] = timestamps[0]
            results["last_nft_tx"] = timestamps[-1]

        # Classify behavior
        results["is_trader"] = results["total_bought"] > 10 and results["total_sold"] > 5
        results["is_collector"] = results["total_nfts_held"] > 20 or results["blue_chip_count"] >= 3

        # Convert for JSON
        results["collections"] = {k: dict(v) for k, v in results["collections"].items() if v["held"] > 0 or v["bought"] > 0}
        results["marketplace_activity"] = dict(results["marketplace_activity"])

        return results

    def analyze_batch(self, addresses: list[str], show_progress: bool = True) -> list[dict]:
        """Analyze multiple addresses."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            result = self.analyze_holdings(address)
            results.append(result)

            if show_progress and (i + 1) % 10 == 0:
                collectors = sum(1 for r in results if r["blue_chip_count"] > 0)
                print(f"  Progress: {i + 1}/{total} ({collectors} blue chip holders)")

            # Rate limit
            time.sleep(0.25)

        return results


def format_timestamp(ts: Optional[int]) -> str:
    """Format Unix timestamp."""
    from datetime import datetime
    if ts:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return "N/A"


def process_csv(input_path: str, output_path: str, tracker: NFTTracker, address_column: str = "address"):
    """Process CSV file and add NFT analysis."""
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

    print(f"Analyzing {len(addresses)} addresses for NFT holdings")

    # Add columns
    new_columns = ["nfts_held", "blue_chip_count", "blue_chip_collections", "is_collector", "is_trader"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    # Analyze
    results = tracker.analyze_batch(addresses)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        row["nfts_held"] = result.get("total_nfts_held", 0)
        row["blue_chip_count"] = result.get("blue_chip_count", 0)
        row["blue_chip_collections"] = ",".join([c["symbol"] for c in result.get("blue_chip_collections", [])])
        row["is_collector"] = "Yes" if result.get("is_collector") else ""
        row["is_trader"] = "Yes" if result.get("is_trader") else ""

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    collectors = sum(1 for r in results if r["is_collector"])
    blue_chip_holders = sum(1 for r in results if r["blue_chip_count"] > 0)
    total_blue_chips = sum(r["blue_chip_count"] for r in results)

    print(f"\nResults:")
    print(f"  NFT Collectors: {collectors}/{len(results)}")
    print(f"  Blue Chip Holders: {blue_chip_holders}")
    print(f"  Total Blue Chips: {total_blue_chips}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="NFT holdings tracker")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--trades", action="store_true", help="Include marketplace trading activity")
    parser.add_argument("--column", default="address", help="Column containing addresses")

    args = parser.parse_args()

    tracker = NFTTracker()

    if args.address:
        # Single address
        print(f"Analyzing {args.address}...")
        result = tracker.analyze_holdings(args.address, include_trades=args.trades)

        print(f"\n{args.address}")
        print("-" * 70)

        if result["total_nfts_held"] > 0 or result["total_bought"] > 0:
            print(f"NFTs Currently Held: {result['total_nfts_held']}")
            print(f"Total Bought: {result['total_bought']}")
            print(f"Total Sold: {result['total_sold']}")
            print(f"First NFT Activity: {format_timestamp(result['first_nft_tx'])}")
            print(f"Last NFT Activity: {format_timestamp(result['last_nft_tx'])}")
            print()

            if result["blue_chip_collections"]:
                print("Blue Chip Holdings:")
                for bc in result["blue_chip_collections"]:
                    tier_str = "★" * (4 - bc["tier"])
                    print(f"  {tier_str} {bc['name']} ({bc['symbol']}): {bc['count']}")
                print()

            if result["collections"]:
                print("All Collections (with holdings):")
                for contract, data in list(result["collections"].items())[:10]:
                    if data.get("held", 0) > 0:
                        name = data.get("name", contract[:10] + "...")
                        print(f"  {name}: {data['held']} held ({data.get('bought', 0)} bought, {data.get('sold', 0)} sold)")
                print()

            if result["marketplace_activity"]:
                print("Marketplace Activity:")
                for marketplace, count in sorted(result["marketplace_activity"].items(), key=lambda x: -x[1]):
                    print(f"  {marketplace}: {count} txs")

            print()
            print("-" * 70)
            print(f"Classification: {'Collector' if result['is_collector'] else ''} {'Trader' if result['is_trader'] else ''}")
        else:
            print("  No NFT activity found")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_nfts.csv')
        process_csv(args.input, output_path, tracker, args.column)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
