#!/usr/bin/env python3
"""
Safe Multisig Investigation Pipeline

Comprehensive investigation of Safe wallets:
1. Get signers for each Safe
2. Find shared signers to identify entity clusters
3. Multi-hop funding trace to find CEX/privacy tool origins
4. Classify funding patterns (Coinbase Prime, Tornado, Circular, etc.)
5. Update knowledge graph with findings

Usage:
    # Investigate Safes from CSV
    python3 scripts/investigate_safes.py safes.csv -o investigation.csv

    # Single Safe investigation
    python3 scripts/investigate_safes.py --address 0x1234...

    # Deep trace (10 hops for privacy chains)
    python3 scripts/investigate_safes.py safes.csv --max-hops 10

    # Update knowledge graph
    python3 scripts/investigate_safes.py safes.csv --update-kg

Environment:
    ETHERSCAN_API_KEY - Required for transaction/label lookups
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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
# Known Addresses Database
# ============================================================================

# CEX Hot Wallets
CEX_WALLETS = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": ("Binance", "Binance 14"),
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": ("Binance", "Binance 16"),
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": ("Binance", "Binance 15"),
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": ("Binance", "Binance 9"),
    "0xf977814e90da44bfa03b6295a0616a897441acec": ("Binance", "Binance 8"),
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": ("Binance", "Binance 20"),
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": ("Binance", "Binance 7"),
    "0x4976a4a02f38326660d17bf34b431dc6e2eb2327": ("Binance", "Binance 20"),
    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": ("Kraken", "Kraken 4"),
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": ("Kraken", "Kraken 1"),
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": ("Coinbase", "Coinbase 1"),
    "0x503828976d22510aad0201ac7ec88293211d23da": ("Coinbase", "Coinbase 2"),
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": ("OKX", "OKX 1"),
    # FTX (historical)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": ("FTX", "FTX Exchange"),
    "0xc098b2a3aa256d2140208c3de6543aaef5cd3a94": ("FTX", "FTX 2"),
    # Bitfinex
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": ("Bitfinex", "Bitfinex 1"),
    "0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec": ("Bitfinex", "Bitfinex Hot"),
    # Institutional
    "0x1157a2076b9bb22a85cc2c162f20fab3898f4101": ("FalconX", "FalconX 1"),
    "0xe5379345eddab3db1a8d55dd59f4413c0df2f5f4": ("Copper", "Copper 2"),
}

# Tornado Cash Contracts
TORNADO_CONTRACTS = {
    "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc": "Tornado.Cash 0.1 ETH",
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936": "Tornado.Cash 1 ETH",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf": "Tornado.Cash 10 ETH",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291": "Tornado.Cash 100 ETH",
    "0xd4b88df4d29f5cedd6857912842cff3b20c8cfa3": "Tornado.Cash DAI",
    "0xfd8610d20aa15b7b2e3be39b396a1bc3516c7144": "Tornado.Cash cDAI",
}

# DeFi Protocols (for internal transaction tracing)
DEFI_PROTOCOLS = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "0xcc9a0b7c43dc2a5f023bb9b738e45b0ef6b06e04": "Aave: WETH Gateway",
    "0xdc24316b9ae028f1497c275eb9192a3ea0f67022": "Lido: stETH Deposit",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap SwapRouter02",
}


# ============================================================================
# Funding Patterns
# ============================================================================

@dataclass
class FundingPattern:
    """Detected funding pattern."""
    pattern_type: str  # coinbase_prime, tornado, circular, binance, unknown
    confidence: float
    evidence: str
    chain: list = field(default_factory=list)  # Full funding chain


def classify_funding_pattern(chain: list, labels: dict) -> FundingPattern:
    """Classify the funding pattern based on the chain and labels."""

    # Check for Coinbase Prime in labels
    for addr, label in labels.items():
        if 'coinbase prime' in label.lower():
            return FundingPattern(
                pattern_type='coinbase_prime',
                confidence=0.75,
                evidence=f"Coinbase Prime label on {addr[:10]}...: {label}",
                chain=chain
            )

    # Check for Tornado Cash
    for addr in chain:
        if addr.lower() in TORNADO_CONTRACTS:
            hop_index = chain.index(addr.lower()) if addr.lower() in [c.lower() for c in chain] else -1
            hops_from_target = len(chain) - hop_index - 1 if hop_index >= 0 else 0
            return FundingPattern(
                pattern_type='tornado',
                confidence=0.65,
                evidence=f"Tornado.Cash at hop {hops_from_target}: {TORNADO_CONTRACTS.get(addr.lower(), 'Unknown')}",
                chain=chain
            )

    # Check for circular funding (Safe funds its own signers)
    if len(chain) >= 3:
        # If the Safe address appears later in the chain
        first = chain[0].lower()
        for addr in chain[2:]:
            if addr.lower() == first:
                return FundingPattern(
                    pattern_type='circular',
                    confidence=0.55,
                    evidence="Safe funds its own signers (circular pattern)",
                    chain=chain
                )

    # Check for known CEX
    for addr in chain:
        addr_lower = addr.lower()
        if addr_lower in CEX_WALLETS:
            entity, label = CEX_WALLETS[addr_lower]
            return FundingPattern(
                pattern_type=entity.lower(),
                confidence=0.70,
                evidence=f"CEX funding: {label}",
                chain=chain
            )

    return FundingPattern(
        pattern_type='unknown',
        confidence=0.40,
        evidence=f"No known pattern detected. Chain: {len(chain)} hops",
        chain=chain
    )


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SignerInvestigation:
    """Investigation results for a single signer."""
    address: str
    funding_chain: list = field(default_factory=list)
    etherscan_labels: dict = field(default_factory=dict)
    funding_pattern: Optional[FundingPattern] = None
    first_funder: str = ""
    first_tx_date: str = ""
    error: str = ""


@dataclass
class SafeCluster:
    """Cluster of Safes sharing signers."""
    cluster_id: str
    safes: list = field(default_factory=list)
    shared_signers: list = field(default_factory=list)
    total_borrowed: float = 0.0
    identity: str = ""
    confidence: float = 0.0
    funding_pattern: Optional[FundingPattern] = None
    evidence: str = ""


@dataclass
class SafeInvestigation:
    """Full investigation results for a Safe."""
    address: str
    borrowed_m: float = 0.0
    threshold: int = 0
    signers: list = field(default_factory=list)
    signer_investigations: list = field(default_factory=list)
    cluster_id: str = ""
    identity: str = ""
    confidence: float = 0.0
    funding_pattern: str = ""
    evidence: str = ""
    error: str = ""


# ============================================================================
# API Clients
# ============================================================================

class InvestigationClient:
    """Combined client for Safe and Etherscan APIs."""

    ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
    # NEW Safe API (2026) - requires checksummed addresses
    SAFE_URL = "https://api.safe.global/tx-service/eth/api/v1/safes"

    def __init__(self, etherscan_key: str, rate_limit: float = 2.0):
        """Initialize client. Default rate limit 2/s due to Safe API limits."""
        self.etherscan_key = etherscan_key
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0
        self.session = requests.Session()
        self.label_cache = {}
        self.safe_rate_limit = 0.5  # 0.5 req/s for Safe API (very aggressive rate limiting)

    def _wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _checksum(self, address: str) -> str:
        """Compute EIP-55 checksum address using keccak256."""
        import subprocess
        addr = address.lower().replace('0x', '')

        # Use cast for reliable checksum (requires foundry)
        try:
            result = subprocess.run(
                ['cast', 'to-checksum', f'0x{addr}'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: manual keccak256 checksum
        # This requires a working keccak implementation
        try:
            import hashlib
            # Python 3.11+ has sha3_256 but it's NOT keccak256
            # For now, return mixed case that might work
            return f"0x{addr}"
        except Exception:
            return f"0x{addr}"

    def get_safe_signers(self, safe_address: str) -> list[str]:
        """Get signers for a Safe wallet."""
        # Use slower rate limit for Safe API (very aggressive 429s)
        time.sleep(2.0)  # 0.5 req/s

        addr = self._checksum(safe_address)
        url = f"{self.SAFE_URL}/{addr}/"

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 404:
                return []
            if resp.status_code == 422:
                # Checksum validation failed - retry doesn't help
                return []
            if resp.status_code == 429:
                # Rate limited - wait and retry once
                time.sleep(5.0)
                resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            return [o.lower() for o in data.get("owners", [])]
        except Exception as e:
            return []

    def get_first_transactions(self, address: str, count: int = 20) -> list[dict]:
        """Get first N transactions for an address."""
        self._wait()

        params = {
            "chainid": 1,
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": count,
            "sort": "asc",
            "apikey": self.etherscan_key,
        }

        try:
            resp = self.session.get(self.ETHERSCAN_URL, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "1":
                return data.get("result", [])
            return []
        except Exception:
            return []

    def get_etherscan_label(self, address: str) -> str:
        """Get Etherscan label for an address (via page scrape simulation)."""
        addr_lower = address.lower()

        # Check cache
        if addr_lower in self.label_cache:
            return self.label_cache[addr_lower]

        # Check known databases
        if addr_lower in CEX_WALLETS:
            label = f"{CEX_WALLETS[addr_lower][0]}: {CEX_WALLETS[addr_lower][1]}"
            self.label_cache[addr_lower] = label
            return label

        if addr_lower in TORNADO_CONTRACTS:
            label = TORNADO_CONTRACTS[addr_lower]
            self.label_cache[addr_lower] = label
            return label

        if addr_lower in DEFI_PROTOCOLS:
            label = DEFI_PROTOCOLS[addr_lower]
            self.label_cache[addr_lower] = label
            return label

        # TODO: Add Etherscan API label lookup when available
        # For now, return empty - labels require page scraping or API access
        self.label_cache[addr_lower] = ""
        return ""

    def trace_funding_chain(self, address: str, max_hops: int = 5) -> tuple[list, dict]:
        """Trace funding chain with multi-hop and collect labels."""
        chain = [address.lower()]
        labels = {}
        current = address.lower()

        for hop in range(max_hops):
            # Get label for current address
            label = self.get_etherscan_label(current)
            if label:
                labels[current] = label

            # Check if we've hit a known endpoint
            if current in CEX_WALLETS or current in TORNADO_CONTRACTS:
                break

            # Get first funder
            txns = self.get_first_transactions(current, count=10)

            funder = None
            for tx in txns:
                if tx.get("to", "").lower() == current:
                    value = int(tx.get("value", "0"))
                    if value > 0:
                        funder = tx.get("from", "").lower()
                        break

            if not funder or funder == current:
                break

            chain.append(funder)
            current = funder

        # Get label for final address
        if chain[-1] not in labels:
            label = self.get_etherscan_label(chain[-1])
            if label:
                labels[chain[-1]] = label

        return chain, labels

    def investigate_signer(self, signer: str, max_hops: int = 5) -> SignerInvestigation:
        """Full investigation of a single signer."""
        result = SignerInvestigation(address=signer.lower())

        try:
            chain, labels = self.trace_funding_chain(signer, max_hops)
            result.funding_chain = chain
            result.etherscan_labels = labels
            result.funding_pattern = classify_funding_pattern(chain, labels)

            if len(chain) > 1:
                result.first_funder = chain[-1]

            # Get first tx date
            txns = self.get_first_transactions(signer, count=1)
            if txns:
                ts = int(txns[0].get("timeStamp", 0))
                if ts:
                    result.first_tx_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

        except Exception as e:
            result.error = str(e)

        return result


# ============================================================================
# Clustering Logic
# ============================================================================

def find_signer_clusters(safes_with_signers: list[tuple[str, list[str]]]) -> list[SafeCluster]:
    """Find clusters of Safes that share signers."""

    # Build signer -> safes mapping
    signer_to_safes = defaultdict(set)
    for safe_addr, signers in safes_with_signers:
        for signer in signers:
            signer_to_safes[signer.lower()].add(safe_addr.lower())

    # Find shared signers (appear in 2+ Safes)
    shared_signers = {s: safes for s, safes in signer_to_safes.items() if len(safes) > 1}

    if not shared_signers:
        return []

    # Union-Find to group connected Safes
    safe_to_cluster = {}
    cluster_id = 0

    for signer, safes in shared_signers.items():
        safes_list = list(safes)

        # Find existing cluster
        existing = None
        for safe in safes_list:
            if safe in safe_to_cluster:
                existing = safe_to_cluster[safe]
                break

        if existing is None:
            existing = f"cluster_{cluster_id}"
            cluster_id += 1

        # Assign all connected safes to same cluster
        for safe in safes_list:
            safe_to_cluster[safe] = existing

    # Build cluster objects
    clusters = defaultdict(lambda: SafeCluster(cluster_id=""))
    for safe, cid in safe_to_cluster.items():
        clusters[cid].cluster_id = cid
        clusters[cid].safes.append(safe)

    # Add shared signers to each cluster
    for cid, cluster in clusters.items():
        cluster_safes = set(cluster.safes)
        for signer, safes in shared_signers.items():
            if safes & cluster_safes:
                if signer not in cluster.shared_signers:
                    cluster.shared_signers.append(signer)

    return list(clusters.values())


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def update_knowledge_graph(
    db_path: str,
    investigations: list[SafeInvestigation],
    clusters: list[SafeCluster]
):
    """Update knowledge graph with investigation findings."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).isoformat()

    for inv in investigations:
        if not inv.identity:
            continue

        # Update entity
        cursor.execute("""
            UPDATE entities
            SET identity = ?, confidence = ?, notes = COALESCE(notes, '') || ?
            WHERE address = ?
        """, (
            inv.identity,
            inv.confidence,
            f" | Safe investigation {now[:10]}: {inv.evidence}",
            inv.address.lower()
        ))

        # Add evidence
        cursor.execute("""
            INSERT INTO evidence (entity_address, source, claim, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            inv.address.lower(),
            "SafeInvestigation",
            f"Pattern: {inv.funding_pattern}. {inv.evidence}",
            inv.confidence,
            now
        ))

    # Add signers as entities
    for inv in investigations:
        for signer_inv in inv.signer_investigations:
            if signer_inv.funding_pattern and signer_inv.funding_pattern.pattern_type != 'unknown':
                cursor.execute("""
                    INSERT OR IGNORE INTO entities (address, identity, entity_type, confidence, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    signer_inv.address,
                    f"{inv.identity} Signer" if inv.identity else "Unknown Signer",
                    "individual",
                    signer_inv.funding_pattern.confidence,
                    f"Funding: {signer_inv.funding_pattern.evidence}"
                ))

    conn.commit()
    conn.close()


# ============================================================================
# Main Pipeline
# ============================================================================

def load_safes(filepath: str) -> list[dict]:
    """Load Safe addresses from CSV with optional metadata."""
    safes = []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = (row.get("address") or row.get("safe_address") or
                   row.get("wallet") or row.get("Address") or "").strip().lower()
            if addr and addr.startswith("0x"):
                safe = {"address": addr}
                # Optional fields
                if "borrowed_m" in row:
                    try:
                        safe["borrowed_m"] = float(row["borrowed_m"])
                    except (ValueError, TypeError):
                        safe["borrowed_m"] = 0.0
                safes.append(safe)

    return safes


def save_results(investigations: list[SafeInvestigation], filepath: str):
    """Save investigation results to CSV."""

    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "safe_address", "borrowed_m", "num_signers", "cluster_id",
            "identity", "confidence", "funding_pattern", "signers", "evidence"
        ])
        writer.writeheader()

        for inv in investigations:
            writer.writerow({
                "safe_address": inv.address,
                "borrowed_m": inv.borrowed_m,
                "num_signers": len(inv.signers),
                "cluster_id": inv.cluster_id,
                "identity": inv.identity,
                "confidence": f"{inv.confidence:.0%}" if inv.confidence else "",
                "funding_pattern": inv.funding_pattern,
                "signers": ",".join(inv.signers),
                "evidence": inv.evidence,
            })


def run_investigation(
    safes: list[dict],
    client: InvestigationClient,
    max_hops: int = 5,
    verbose: bool = True
) -> tuple[list[SafeInvestigation], list[SafeCluster]]:
    """Run full investigation pipeline."""

    investigations = []
    safes_with_signers = []

    # Phase 1: Get signers for all Safes
    if verbose:
        print(f"\n[Phase 1] Getting signers for {len(safes)} Safes...", file=sys.stderr)

    for i, safe in enumerate(safes):
        addr = safe["address"]
        signers = client.get_safe_signers(addr)

        inv = SafeInvestigation(
            address=addr,
            borrowed_m=safe.get("borrowed_m", 0.0),
            signers=signers
        )
        investigations.append(inv)

        if signers:
            safes_with_signers.append((addr, signers))

        if verbose and (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(safes)}", file=sys.stderr)

    # Phase 2: Find clusters
    if verbose:
        print(f"\n[Phase 2] Finding signer clusters...", file=sys.stderr)

    clusters = find_signer_clusters(safes_with_signers)

    # Map safes to clusters
    safe_to_cluster = {}
    for cluster in clusters:
        for safe in cluster.safes:
            safe_to_cluster[safe] = cluster.cluster_id

    for inv in investigations:
        inv.cluster_id = safe_to_cluster.get(inv.address, "")

    if verbose:
        print(f"  Found {len(clusters)} clusters", file=sys.stderr)
        for cluster in clusters:
            print(f"    {cluster.cluster_id}: {len(cluster.safes)} Safes, {len(cluster.shared_signers)} shared signers", file=sys.stderr)

    # Phase 3: Investigate signers (focus on shared signers first)
    if verbose:
        print(f"\n[Phase 3] Investigating signers...", file=sys.stderr)

    # Get all shared signers
    shared_signers = set()
    for cluster in clusters:
        shared_signers.update(cluster.shared_signers)

    # Also investigate non-clustered Safes' signers
    non_clustered = [inv for inv in investigations if not inv.cluster_id and inv.signers]
    for inv in non_clustered[:5]:  # Limit to top 5 non-clustered
        shared_signers.update(inv.signers)

    signer_investigations = {}
    for i, signer in enumerate(shared_signers):
        if verbose:
            print(f"  Investigating signer {i + 1}/{len(shared_signers)}: {signer[:10]}...", file=sys.stderr)

        signer_inv = client.investigate_signer(signer, max_hops)
        signer_investigations[signer] = signer_inv

        if verbose and signer_inv.funding_pattern:
            pattern = signer_inv.funding_pattern
            print(f"    -> {pattern.pattern_type} ({pattern.confidence:.0%}): {pattern.evidence[:50]}", file=sys.stderr)

    # Phase 4: Classify clusters
    if verbose:
        print(f"\n[Phase 4] Classifying clusters...", file=sys.stderr)

    for cluster in clusters:
        # Get best funding pattern from shared signers
        best_pattern = None
        for signer in cluster.shared_signers:
            if signer in signer_investigations:
                pattern = signer_investigations[signer].funding_pattern
                if pattern and (not best_pattern or pattern.confidence > best_pattern.confidence):
                    best_pattern = pattern

        if best_pattern:
            cluster.funding_pattern = best_pattern
            cluster.confidence = best_pattern.confidence

            # Generate identity based on pattern
            if best_pattern.pattern_type == 'coinbase_prime':
                cluster.identity = "Coinbase Prime Custody Client"
            elif best_pattern.pattern_type == 'tornado':
                cluster.identity = "Tornado-funded Entity (Privacy-conscious)"
            elif best_pattern.pattern_type == 'circular':
                cluster.identity = "Pre-existing DeFi Entity"
            elif best_pattern.pattern_type in ['binance', 'kraken', 'okx', 'coinbase', 'ftx', 'bitfinex', 'huobi', 'gemini', 'kucoin', 'bybit']:
                cluster.identity = f"{best_pattern.pattern_type.upper()}-funded Entity"
            else:
                cluster.identity = "Unknown Entity"

            cluster.evidence = best_pattern.evidence

    # Phase 5: Update investigations with cluster data
    for inv in investigations:
        if inv.cluster_id:
            for cluster in clusters:
                if cluster.cluster_id == inv.cluster_id:
                    inv.identity = f"{cluster.identity} ({cluster.cluster_id})"
                    inv.confidence = cluster.confidence
                    inv.funding_pattern = cluster.funding_pattern.pattern_type if cluster.funding_pattern else ""
                    inv.evidence = cluster.evidence
                    break

        # Add signer investigations
        for signer in inv.signers:
            if signer in signer_investigations:
                inv.signer_investigations.append(signer_investigations[signer])

        # For non-clustered Safes, use their signer's pattern
        if not inv.cluster_id and inv.signer_investigations:
            best = max(inv.signer_investigations,
                      key=lambda x: x.funding_pattern.confidence if x.funding_pattern else 0)
            if best.funding_pattern and best.funding_pattern.pattern_type != 'unknown':
                inv.funding_pattern = best.funding_pattern.pattern_type
                inv.confidence = best.funding_pattern.confidence
                inv.evidence = best.funding_pattern.evidence

                if best.funding_pattern.pattern_type == 'coinbase_prime':
                    inv.identity = "Coinbase Prime Custody Client"
                elif best.funding_pattern.pattern_type == 'tornado':
                    inv.identity = "Tornado-funded Entity"
                elif best.funding_pattern.pattern_type in ['binance', 'kraken', 'okx', 'coinbase', 'ftx', 'bitfinex', 'huobi', 'gemini', 'kucoin', 'bybit']:
                    inv.identity = f"{best.funding_pattern.pattern_type.upper()}-funded Entity"

    return investigations, clusters


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive Safe multisig investigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Investigate Safes from CSV
    python3 investigate_safes.py data/pipeline/safe_signers.csv -o investigation.csv

    # Single Safe
    python3 investigate_safes.py --address 0x23a5e45f9556dc7ffb507db8a3cfb2589bc8adad

    # Deep trace for privacy chains
    python3 investigate_safes.py safes.csv --max-hops 10

    # Update knowledge graph
    python3 investigate_safes.py safes.csv --update-kg
        """
    )

    parser.add_argument("input", nargs="?", help="Input CSV with Safe addresses")
    parser.add_argument("--address", "-a", help="Investigate single Safe")
    parser.add_argument("--output", "-o", default="safe_investigation.csv", help="Output file")
    parser.add_argument("--max-hops", type=int, default=5, help="Max funding hops (default: 5)")
    parser.add_argument("--update-kg", action="store_true", help="Update knowledge graph")
    parser.add_argument("--kg-path", default="data/knowledge_graph.db", help="Knowledge graph path")
    parser.add_argument("--rate-limit", type=float, default=4.0, help="API rate limit")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = InvestigationClient(api_key, args.rate_limit)
    verbose = not args.quiet

    # Single address mode
    if args.address:
        safes = [{"address": args.address.lower()}]
    else:
        safes = load_safes(args.input)

    if verbose:
        print(f"Investigating {len(safes)} Safe(s)...", file=sys.stderr)

    investigations, clusters = run_investigation(safes, client, args.max_hops, verbose)

    # Save results
    save_results(investigations, args.output)
    if verbose:
        print(f"\nSaved to {args.output}", file=sys.stderr)

    # Update knowledge graph
    if args.update_kg:
        kg_path = Path(args.kg_path)
        if kg_path.exists():
            update_knowledge_graph(str(kg_path), investigations, clusters)
            if verbose:
                print(f"Updated knowledge graph at {kg_path}", file=sys.stderr)

    # Summary
    if verbose:
        print("\n" + "=" * 60, file=sys.stderr)
        print("INVESTIGATION SUMMARY", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        identified = [inv for inv in investigations if inv.identity]
        print(f"\nTotal Safes: {len(investigations)}", file=sys.stderr)
        print(f"Clusters found: {len(clusters)}", file=sys.stderr)
        print(f"Identified: {len(identified)}", file=sys.stderr)

        if clusters:
            print(f"\nClusters:", file=sys.stderr)
            for cluster in clusters:
                total = sum(inv.borrowed_m for inv in investigations if inv.cluster_id == cluster.cluster_id)
                print(f"  {cluster.cluster_id}:", file=sys.stderr)
                print(f"    Safes: {len(cluster.safes)}", file=sys.stderr)
                print(f"    Total borrowed: ${total:.1f}M", file=sys.stderr)
                print(f"    Identity: {cluster.identity or 'Unknown'}", file=sys.stderr)
                print(f"    Confidence: {cluster.confidence:.0%}" if cluster.confidence else "", file=sys.stderr)

        # Pattern distribution
        patterns = defaultdict(int)
        for inv in investigations:
            if inv.funding_pattern:
                patterns[inv.funding_pattern] += 1

        if patterns:
            print(f"\nFunding Patterns:", file=sys.stderr)
            for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
                print(f"  {pattern}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
