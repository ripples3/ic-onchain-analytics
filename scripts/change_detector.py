#!/usr/bin/env python3
"""
Change Address Detector - Detect "change" patterns in EVM transactions.

Adapts Bitcoin change address heuristic (AUC 0.9986) for EVM.
Identifies related addresses through fund flow patterns.

EVM Adaptation:
- Bitcoin: UTXO model has explicit change outputs
- EVM: Account model, but similar patterns emerge:
  - Small amounts sent to new addresses after large transfers
  - Dust sweeping to new addresses
  - Split transactions with "leftover" going to new address

Usage:
    # Single address
    python3 scripts/change_detector.py --address 0x1234...

    # Batch from CSV
    python3 scripts/change_detector.py addresses.csv -o change_patterns.csv

Based on: Academic research - Change address detection (AUC 0.9986)
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

# Configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETH_RPC_URL = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")

# Thresholds for change detection
SMALL_AMOUNT_ETH = 0.1  # Below this is considered "small" (potential change)
LARGE_AMOUNT_ETH = 1.0  # Above this is considered "large" (main payment)
TIME_WINDOW_SECONDS = 3600  # 1 hour window for related transactions
DUST_THRESHOLD_ETH = 0.01  # Below this is dust


class ChangeDetector:
    """Detect change address patterns in EVM transactions."""

    def __init__(self):
        self.api_key = ETHERSCAN_API_KEY
        self.known_contracts = set()  # Cache of known contract addresses

    def get_transactions(self, address: str, max_txs: int = 500) -> list[dict]:
        """Get transaction history for an address."""
        try:
            url = "https://api.etherscan.io/v2/api"
            params = {
                "chainid": 1,  # Ethereum mainnet
                "module": "account",
                "action": "txlist",
                "address": address,
                "apikey": self.api_key
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])[:max_txs]

        except Exception as e:
            print(f"  Error fetching transactions: {e}")

        return []

    def get_internal_transactions(self, address: str, max_txs: int = 100) -> list[dict]:
        """Get internal (contract) transactions."""
        try:
            url = "https://api.etherscan.io/v2/api"
            params = {
                "chainid": 1,  # Ethereum mainnet
                "module": "account",
                "action": "txlistinternal",
                "address": address,
                "apikey": self.api_key
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])[:max_txs]

        except Exception:
            pass

        return []

    def is_contract(self, address: str) -> bool:
        """Check if an address is a contract."""
        if not address:
            return False

        address = address.lower()
        if address in self.known_contracts:
            return True

        try:
            url = "https://api.etherscan.io/v2/api"
            params = {
                "chainid": 1,  # Ethereum mainnet
                "module": "proxy",
                "action": "eth_getCode",
                "address": address,
                "tag": "latest",
                "apikey": self.api_key
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json().get("result", "0x")
                is_contract = result != "0x" and len(result) > 2
                if is_contract:
                    self.known_contracts.add(address)
                return is_contract

        except Exception:
            pass

        return False

    def detect_change_patterns(self, address: str) -> dict:
        """
        Detect change address patterns for a given address.

        Patterns detected:
        1. Split transactions: Large outgoing + small "change" to new address
        2. Dust sweeping: Multiple small amounts sent to same new address
        3. Sequential withdrawals: Series of transactions to new address before main activity

        Returns:
            Dict with detected patterns and potential related addresses
        """
        address = address.lower()
        results = {
            "address": address,
            "patterns": [],
            "potential_related": [],
            "confidence_scores": {},
        }

        # Get transactions
        txs = self.get_transactions(address)
        if not txs:
            return results

        # Filter outgoing ETH transfers from this address
        outgoing_txs = []
        for tx in txs:
            if tx.get("from", "").lower() == address:
                value_eth = int(tx.get("value", 0)) / 1e18
                to_addr = tx.get("to", "").lower()
                timestamp = int(tx.get("timeStamp", 0))

                if value_eth > 0 and to_addr:
                    outgoing_txs.append({
                        "hash": tx.get("hash"),
                        "to": to_addr,
                        "value": value_eth,
                        "timestamp": timestamp,
                        "gas_used": int(tx.get("gasUsed", 0)),
                    })

        if len(outgoing_txs) < 2:
            return results

        # Pattern 1: Split transactions
        # Look for large transfer followed by small transfer within time window
        for i, tx1 in enumerate(outgoing_txs):
            if tx1["value"] < LARGE_AMOUNT_ETH:
                continue

            # Look for small transfers within time window
            for tx2 in outgoing_txs[i+1:]:
                time_diff = tx2["timestamp"] - tx1["timestamp"]
                if time_diff > TIME_WINDOW_SECONDS:
                    break

                if tx2["value"] < SMALL_AMOUNT_ETH and tx2["to"] != tx1["to"]:
                    # Check if the small transfer recipient is a new address (EOA, not contract)
                    if not self.is_contract(tx2["to"]):
                        pattern = {
                            "type": "split_transaction",
                            "main_tx": tx1["hash"],
                            "main_value": tx1["value"],
                            "main_recipient": tx1["to"],
                            "change_tx": tx2["hash"],
                            "change_value": tx2["value"],
                            "change_recipient": tx2["to"],
                            "time_diff_seconds": time_diff,
                        }
                        results["patterns"].append(pattern)

                        if tx2["to"] not in results["potential_related"]:
                            results["potential_related"].append(tx2["to"])
                            results["confidence_scores"][tx2["to"]] = 0.6  # Medium confidence

        # Pattern 2: Dust sweeping
        # Multiple small transfers to the same new address
        recipient_counts = defaultdict(list)
        for tx in outgoing_txs:
            if tx["value"] < SMALL_AMOUNT_ETH:
                recipient_counts[tx["to"]].append(tx)

        for recipient, dust_txs in recipient_counts.items():
            if len(dust_txs) >= 3:  # At least 3 dust transactions
                total_dust = sum(tx["value"] for tx in dust_txs)
                if not self.is_contract(recipient):
                    pattern = {
                        "type": "dust_sweeping",
                        "recipient": recipient,
                        "tx_count": len(dust_txs),
                        "total_value": total_dust,
                    }
                    results["patterns"].append(pattern)

                    if recipient not in results["potential_related"]:
                        results["potential_related"].append(recipient)
                        results["confidence_scores"][recipient] = 0.7  # Higher confidence

        # Pattern 3: Sequential funding
        # Check if address received funds and then split to multiple addresses in sequence
        incoming_txs = [tx for tx in txs if tx.get("to", "").lower() == address]
        if incoming_txs and outgoing_txs:
            first_incoming = int(incoming_txs[0].get("timeStamp", 0))
            early_outgoing = [tx for tx in outgoing_txs
                            if tx["timestamp"] - first_incoming < 86400]  # Within 24h

            if len(early_outgoing) >= 2:
                # Check for pattern: receive → split to multiple addresses
                early_recipients = list(set(tx["to"] for tx in early_outgoing))
                if len(early_recipients) >= 2:
                    pattern = {
                        "type": "initial_split",
                        "recipients": early_recipients,
                        "total_split": sum(tx["value"] for tx in early_outgoing),
                    }
                    results["patterns"].append(pattern)

                    for recipient in early_recipients:
                        if not self.is_contract(recipient) and recipient not in results["potential_related"]:
                            results["potential_related"].append(recipient)
                            results["confidence_scores"][recipient] = 0.5  # Lower confidence

        return results

    def analyze_batch(self, addresses: list[str], show_progress: bool = True) -> list[dict]:
        """Analyze multiple addresses for change patterns."""
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            result = self.detect_change_patterns(address)
            results.append(result)

            if show_progress and (i + 1) % 10 == 0:
                with_patterns = sum(1 for r in results if r["patterns"])
                print(f"  Progress: {i + 1}/{total} ({with_patterns} with patterns)")

            # Rate limit
            time.sleep(0.25)

        return results


def process_csv(input_path: str, output_path: str, detector: ChangeDetector, address_column: str = "address"):
    """Process CSV file and add change pattern detection."""
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

    print(f"Analyzing {len(addresses)} addresses for change patterns")

    # Add columns
    new_columns = ["change_patterns", "related_addresses", "highest_confidence"]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)

    # Analyze
    results = detector.analyze_batch(addresses)

    # Map results by address
    result_map = {r["address"].lower(): r for r in results}

    # Update rows
    for row in rows:
        addr = row.get(address_column, row.get('borrower', '')).lower()
        result = result_map.get(addr, {})

        patterns = result.get("patterns", [])
        row["change_patterns"] = len(patterns)

        related = result.get("potential_related", [])
        row["related_addresses"] = ",".join(related[:5])  # First 5

        scores = result.get("confidence_scores", {})
        row["highest_confidence"] = f"{max(scores.values()):.2f}" if scores else ""

    # Write output
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    with_patterns = sum(1 for r in results if r["patterns"])
    total_related = sum(len(r["potential_related"]) for r in results)

    print(f"\nResults:")
    print(f"  Addresses with change patterns: {with_patterns}/{len(results)}")
    print(f"  Total related addresses found: {total_related}")
    print(f"Output written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Change address pattern detector")
    parser.add_argument("input", nargs="?", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--column", default="address", help="Column containing addresses")

    args = parser.parse_args()

    detector = ChangeDetector()

    if args.address:
        # Single address
        print(f"Analyzing {args.address} for change patterns...")
        result = detector.detect_change_patterns(args.address)

        print(f"\n{args.address}")
        print("-" * 70)

        if result["patterns"]:
            print(f"Patterns detected: {len(result['patterns'])}")
            print()

            for pattern in result["patterns"]:
                ptype = pattern["type"]
                if ptype == "split_transaction":
                    print(f"  Split Transaction:")
                    print(f"    Main: {pattern['main_value']:.4f} ETH → {pattern['main_recipient'][:16]}...")
                    print(f"    Change: {pattern['change_value']:.4f} ETH → {pattern['change_recipient'][:16]}...")
                    print(f"    Time diff: {pattern['time_diff_seconds']}s")
                elif ptype == "dust_sweeping":
                    print(f"  Dust Sweeping:")
                    print(f"    Recipient: {pattern['recipient'][:16]}...")
                    print(f"    Transactions: {pattern['tx_count']}")
                    print(f"    Total: {pattern['total_value']:.6f} ETH")
                elif ptype == "initial_split":
                    print(f"  Initial Split:")
                    print(f"    Recipients: {len(pattern['recipients'])}")
                    print(f"    Total: {pattern['total_split']:.4f} ETH")
                print()

            if result["potential_related"]:
                print("-" * 70)
                print("Potential Related Addresses:")
                for addr in result["potential_related"]:
                    conf = result["confidence_scores"].get(addr, 0)
                    print(f"  {addr} (confidence: {conf:.2f})")
        else:
            print("  No change patterns detected")

    elif args.input:
        # Batch processing
        output_path = args.output or args.input.replace('.csv', '_change.csv')
        process_csv(args.input, output_path, detector, args.column)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
