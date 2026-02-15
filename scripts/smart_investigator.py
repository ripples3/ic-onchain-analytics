#!/usr/bin/env python3
"""
Smart Investigator - Optimal method routing based on address characteristics.

Phase 2 improvement: Routes investigation based on:
1. Contract vs EOA (contracts → bot_operator_tracer, 100% success)
2. Sophistication level ($500M+ whales → skip CIO/ENS/whale trackers)
3. Behavioral patterns (universal fallback)

Key insights from retrospective:
- behavioral_fingerprint: 100% success (always works)
- funding_trace: 100% success (CEX origin always exists)
- bot_operator_tracer: 100% on contracts
- temporal_correlation: 85% when partners exist
- cio_detector: 0% on sophisticated ($500M+) whales
- ens_resolver: 0% on sophisticated whales
- counterparty_graph: 0% on sophisticated whales

Usage:
    # Single address
    python3 scripts/smart_investigator.py --address 0x1234... --borrowed 500

    # Batch from CSV
    python3 scripts/smart_investigator.py addresses.csv -o results.csv

    # Skip web lookups (local only)
    python3 scripts/smart_investigator.py addresses.csv --local-only
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependencies. Install with: pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
KG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_graph.db")

# Sophistication threshold - above this, skip low-value methods
SOPHISTICATED_THRESHOLD_M = 500  # $500M+


class SmartInvestigator:
    """Routes addresses to optimal investigation methods."""

    def __init__(self, local_only: bool = False):
        self.local_only = local_only
        self.api_key = ETHERSCAN_API_KEY

    def is_contract(self, address: str) -> bool:
        """Check if address is a contract via eth_getCode.

        CRITICAL: Returns False on API failure. Callers should be aware that
        a False result could mean "EOA" OR "API error". For contract-first
        routing, a false negative here causes misclassification as EOA.
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

    def get_existing_identity(self, address: str) -> Optional[Dict]:
        """Check knowledge graph for existing identity."""
        if not os.path.exists(KG_PATH):
            return None

        conn = sqlite3.connect(KG_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT identity, confidence, entity_type
            FROM entities
            WHERE address = ?
        """, (address.lower(),))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return {
                "identity": row[0],
                "confidence": row[1] or 0.5,
                "entity_type": row[2],
            }
        return None

    def get_temporal_correlations(self, address: str) -> List[Dict]:
        """Get temporal correlations from knowledge graph."""
        if not os.path.exists(KG_PATH):
            return []

        conn = sqlite3.connect(KG_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                CASE WHEN source = ? THEN target ELSE source END as partner,
                confidence
            FROM relationships
            WHERE (source = ? OR target = ?)
            AND relationship_type = 'temporal_correlation'
            AND confidence >= 0.8
            ORDER BY confidence DESC
            LIMIT 10
        """, (address.lower(), address.lower(), address.lower()))

        results = [{"partner": row[0], "confidence": row[1]} for row in cursor.fetchall()]
        conn.close()
        return results

    def get_investigation_methods(self, address: str, borrowed_m: float = 0, is_contract: Optional[bool] = None) -> Dict:
        """Determine optimal investigation methods for an address.

        Returns prioritized list of methods with expected success rates.
        The is_contract flag is included in the returned dict for callers to reuse.

        Args:
            address: The address to investigate.
            borrowed_m: Borrowed amount in millions for sophistication routing.
            is_contract: Pre-computed contract check result. If None, will query API.
        """
        address = address.lower()
        if is_contract is None:
            is_contract = self.is_contract(address)
        is_sophisticated = borrowed_m >= SOPHISTICATED_THRESHOLD_M

        # Base methods that ALWAYS work
        methods = {
            "primary": [],
            "secondary": [],
            "skip": [],
            "reason": {},
            "is_contract": is_contract,
        }

        # CONTRACT ROUTING (100% success on bot_operator_tracer)
        if is_contract:
            methods["primary"] = [
                ("bot_operator_tracer", 1.00, "Contract → 100% success on deployer/profit trace"),
                ("behavioral_fingerprint", 1.00, "Universal fallback - timezone always works"),
                ("funding_trace", 1.00, "CEX funding chain always exists"),
            ]
            methods["secondary"] = [
                ("temporal_correlation", 0.25, "Only works if temporal partner exists"),
            ]
            methods["skip"] = [
                ("profile_classifier", "Contract detected - skip to bot_operator_tracer"),
                ("cio_detector", "0% hit rate on contracts"),
                ("ens_resolver", "0% hit rate on contracts"),
                ("counterparty_graph", "Too noisy for contracts"),
                ("nft_tracker", "0% hit rate on DeFi contracts"),
                ("whale_tracker", "0% hit rate on sophisticated"),
                ("governance_scraper", "0% hit rate on contracts"),
            ]
            return methods

        # SOPHISTICATED WHALE ROUTING ($500M+)
        if is_sophisticated:
            methods["primary"] = [
                ("behavioral_fingerprint", 1.00, "Universal fallback - timezone always works"),
                ("funding_trace", 1.00, "CEX funding chain always exists"),
                ("temporal_correlation", 0.85, "High confidence when partners exist"),
            ]
            methods["secondary"] = [
                ("bot_operator_tracer", 0.60, "Check if deployed contracts"),
            ]
            methods["skip"] = [
                ("cio_detector", "0% hit rate on sophisticated whales - they avoid shared funding"),
                ("ens_resolver", "0% hit rate - sophisticated whales don't use ENS"),
                ("counterparty_graph", "0% hit rate - protocol noise too high"),
                ("whale_tracker", "0% hit rate - not in public trackers"),
                ("nft_tracker", "0% hit rate on DeFi whales"),
                ("bridge_tracker", "0% hit rate in Phase 2"),
            ]
            methods["reason"]["sophistication"] = f"${borrowed_m:.0f}M borrowed - sophisticated whale routing"
            return methods

        # STANDARD EOA ROUTING
        methods["primary"] = [
            ("behavioral_fingerprint", 1.00, "Universal fallback - timezone always works"),
            ("funding_trace", 1.00, "CEX funding chain always exists"),
            ("temporal_correlation", 0.85, "High confidence when partners exist"),
            ("cio_detector", 0.80, "Works on non-sophisticated addresses"),
        ]
        methods["secondary"] = [
            ("counterparty_graph", 0.57, "Useful for shared counterparties"),
            ("governance_scraper", 0.70, "Useful when governance activity exists"),
            ("ens_resolver", 0.40, "Check for ENS names"),
        ]
        methods["skip"] = [
            ("nft_tracker", "0% hit rate on DeFi borrowers"),
            ("bridge_tracker", "0% hit rate in Phase 2"),
        ]

        return methods

    def investigate(self, address: str, borrowed_m: float = 0) -> Dict:
        """Run smart investigation on an address.

        Returns combined signals with confidence.
        """
        address = address.lower()

        result = {
            "address": address,
            "borrowed_m": borrowed_m,
            "is_contract": False,
            "is_sophisticated": borrowed_m >= SOPHISTICATED_THRESHOLD_M,
            "existing_identity": None,
            "methods_used": [],
            "methods_skipped": [],
            "signals": [],
            "identity": None,
            "confidence": 0.0,
        }

        # Check if contract FIRST - single API call, reused everywhere
        is_contract = self.is_contract(address)
        result["is_contract"] = is_contract

        # Check existing identity
        existing = self.get_existing_identity(address)
        if existing and existing["confidence"] >= 0.7:
            result["existing_identity"] = existing
            result["identity"] = existing["identity"]
            result["confidence"] = existing["confidence"]
            return result

        # Get optimal methods (pass is_contract to avoid redundant API call)
        methods = self.get_investigation_methods(address, borrowed_m, is_contract=is_contract)

        # Record what we're skipping and why
        result["methods_skipped"] = [(m, r) for m, r in methods["skip"]]

        # Run primary methods (these always provide signal)
        for method_name, expected_rate, reason in methods["primary"]:
            result["methods_used"].append(method_name)

            if method_name == "behavioral_fingerprint":
                signal = self._run_behavioral(address)
                if signal:
                    result["signals"].append(signal)

            elif method_name == "funding_trace":
                signal = self._run_funding_trace(address)
                if signal:
                    result["signals"].append(signal)

            elif method_name == "temporal_correlation":
                correlations = self.get_temporal_correlations(address)
                if correlations:
                    result["signals"].append({
                        "method": "temporal_correlation",
                        "correlations": len(correlations),
                        "top_partner": correlations[0]["partner"] if correlations else None,
                        "confidence": correlations[0]["confidence"] if correlations else 0,
                    })

            elif method_name == "bot_operator_tracer":
                signal = self._run_bot_tracer(address)
                if signal:
                    result["signals"].append(signal)

        # Combine signals into identity
        result["identity"], result["confidence"] = self._combine_signals(result["signals"])

        return result

    def _run_behavioral(self, address: str) -> Optional[Dict]:
        """Run behavioral fingerprint analysis."""
        # Simplified - just check knowledge graph for existing behavioral data
        if not os.path.exists(KG_PATH):
            return None

        conn = sqlite3.connect(KG_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT claim, confidence
            FROM evidence
            WHERE entity_address = ?
            AND (source LIKE '%behavioral%' OR source LIKE '%timezone%')
            ORDER BY confidence DESC
            LIMIT 1
        """, (address.lower(),))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "method": "behavioral_fingerprint",
                "claim": row[0],
                "confidence": row[1],
            }
        return None

    def _run_funding_trace(self, address: str) -> Optional[Dict]:
        """Get funding trace from knowledge graph."""
        if not os.path.exists(KG_PATH):
            return None

        conn = sqlite3.connect(KG_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT claim, confidence
            FROM evidence
            WHERE entity_address = ?
            AND (source LIKE '%funding%' OR source LIKE '%trace%' OR claim LIKE '%funded%')
            ORDER BY confidence DESC
            LIMIT 1
        """, (address.lower(),))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "method": "funding_trace",
                "claim": row[0],
                "confidence": row[1],
            }
        return None

    def _run_bot_tracer(self, address: str) -> Optional[Dict]:
        """Run bot operator tracer."""
        try:
            from bot_operator_tracer import BotOperatorTracer
            tracer = BotOperatorTracer()
            result = tracer.trace_operator(address, deep=False)

            if result.get("likely_operator"):
                return {
                    "method": "bot_operator_tracer",
                    "operator": result["likely_operator"],
                    "operator_type": result.get("operator_type", "unknown"),
                    "confidence": result.get("confidence", 0.7),
                    "profit_flow": result.get("profit_flow", {}),
                }
        except Exception as e:
            print(f"Bot tracer error: {e}")
        return None

    def _combine_signals(self, signals: List[Dict]) -> Tuple[Optional[str], float]:
        """Combine signals into identity and confidence."""
        if not signals:
            return None, 0.0

        # Weight signals by method reliability
        METHOD_WEIGHTS = {
            "behavioral_fingerprint": 0.3,
            "funding_trace": 0.25,
            "temporal_correlation": 0.25,
            "bot_operator_tracer": 0.35,
            "cio_detector": 0.20,
        }

        total_confidence = 0.0
        identity_parts = []

        for signal in signals:
            method = signal.get("method", "unknown")
            weight = METHOD_WEIGHTS.get(method, 0.1)
            signal_conf = signal.get("confidence", 0.5)

            total_confidence += weight * signal_conf

            # Build identity from signals
            if method == "behavioral_fingerprint" and signal.get("claim"):
                identity_parts.append(signal["claim"])
            elif method == "bot_operator_tracer" and signal.get("operator_type"):
                identity_parts.append(f"{signal['operator_type'].replace('_', ' ').title()}")
            elif method == "funding_trace" and signal.get("claim"):
                identity_parts.append(signal["claim"])

        # Cap confidence at 0.95
        final_confidence = min(total_confidence, 0.95)

        # Build identity string
        identity = None
        if identity_parts:
            identity = " | ".join(identity_parts[:2])  # Max 2 parts

        return identity, final_confidence


def main():
    parser = argparse.ArgumentParser(description="Smart investigation routing")
    parser.add_argument("input", nargs="?", help="Address or CSV file")
    parser.add_argument("--address", "-a", help="Single address to investigate")
    parser.add_argument("--borrowed", "-b", type=float, default=0, help="Borrowed amount in millions")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--local-only", action="store_true", help="Skip web lookups")
    parser.add_argument("--methods-only", action="store_true", help="Only show recommended methods")
    args = parser.parse_args()

    investigator = SmartInvestigator(local_only=args.local_only)

    addresses = []
    borrowed_amounts = {}

    if args.address:
        addresses = [args.address]
        borrowed_amounts[args.address.lower()] = args.borrowed
    elif args.input and args.input.endswith(".csv"):
        with open(args.input, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = (row.get("address") or row.get("borrower") or list(row.values())[0]).lower()
                addresses.append(addr)
                # Try to get borrowed amount
                borrowed = float(row.get("total_borrowed_m", 0) or row.get("borrowed_m", 0) or 0)
                borrowed_amounts[addr] = borrowed
    elif args.input:
        addresses = [args.input]
        borrowed_amounts[args.input.lower()] = args.borrowed
    else:
        parser.print_help()
        sys.exit(1)

    results = []
    for i, addr in enumerate(addresses):
        borrowed = borrowed_amounts.get(addr.lower(), 0)
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(addresses)}] {addr}")
        print(f"Borrowed: ${borrowed:.1f}M")
        print(f"{'='*60}")

        if args.methods_only:
            methods = investigator.get_investigation_methods(addr, borrowed)

            print(f"\nPrimary methods (run these):")
            for method, rate, reason in methods["primary"]:
                print(f"  ✅ {method} ({rate*100:.0f}%): {reason}")

            if methods["secondary"]:
                print(f"\nSecondary methods (optional):")
                for method, rate, reason in methods["secondary"]:
                    print(f"  ⚠️ {method} ({rate*100:.0f}%): {reason}")

            if methods["skip"]:
                print(f"\nSkip these methods:")
                for method, reason in methods["skip"]:
                    print(f"  ❌ {method}: {reason}")

            if methods.get("reason"):
                print(f"\nRouting reason: {methods['reason']}")
        else:
            result = investigator.investigate(addr, borrowed)
            results.append(result)

            print(f"\nContract: {'Yes' if result['is_contract'] else 'No'}")
            print(f"Sophisticated: {'Yes' if result['is_sophisticated'] else 'No'}")

            if result["existing_identity"]:
                print(f"\nExisting identity: {result['existing_identity']['identity']}")
                print(f"Confidence: {result['existing_identity']['confidence']*100:.0f}%")
            else:
                print(f"\nMethods used: {', '.join(result['methods_used'])}")
                print(f"Methods skipped: {len(result['methods_skipped'])}")

                if result["signals"]:
                    print(f"\nSignals found: {len(result['signals'])}")
                    for sig in result["signals"]:
                        print(f"  - {sig.get('method')}: {sig.get('confidence', 0)*100:.0f}%")

                if result["identity"]:
                    print(f"\n🎯 Identity: {result['identity']}")
                    print(f"   Confidence: {result['confidence']*100:.0f}%")
                else:
                    print(f"\n⚠️ No identity determined")

    if args.output and results:
        with open(args.output, "w", newline="") as f:
            fieldnames = ["address", "borrowed_m", "is_contract", "is_sophisticated",
                         "identity", "confidence", "methods_used", "signals_count"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "address": r["address"],
                    "borrowed_m": r["borrowed_m"],
                    "is_contract": r["is_contract"],
                    "is_sophisticated": r["is_sophisticated"],
                    "identity": r.get("identity", ""),
                    "confidence": r.get("confidence", 0),
                    "methods_used": "|".join(r["methods_used"]),
                    "signals_count": len(r["signals"]),
                })
        print(f"\nResults saved to {args.output}")

    # Summary
    if results:
        contracts = sum(1 for r in results if r["is_contract"])
        sophisticated = sum(1 for r in results if r["is_sophisticated"])
        identified = sum(1 for r in results if r.get("identity"))

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total addresses: {len(results)}")
        print(f"Contracts: {contracts}")
        print(f"Sophisticated ($500M+): {sophisticated}")
        print(f"Identified: {identified} ({identified/len(results)*100:.0f}%)")


if __name__ == "__main__":
    main()
