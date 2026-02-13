#!/usr/bin/env python3
"""
Counterparty Graph Analysis

Finds related wallets by analyzing WHO they transact with, not just funding.
This complements CIO (Common Input Ownership) by finding indirect relationships.

Key insight: Whales have consistent counterparties (OTC desks, market makers,
specific protocols). If two unknown wallets have 70%+ counterparty overlap,
they're likely related - even without direct funding links.

Signal Types:
1. Shared Counterparties - Both wallets transact with same addresses
2. Shared Deposit Targets - Both send to same exchange deposit addresses (VERY strong)
3. Shared Protocol Usage - Both use same DeFi protocols in same ways
4. Counterparty Overlap Score - Jaccard similarity of counterparty sets

Confidence Levels:
- 80%+ Jaccard overlap = 90% confidence (almost certainly related)
- 60-80% overlap = 75% confidence (likely related)
- 40-60% overlap = 55% confidence (possibly related)
- <40% overlap = not significant

Usage:
    # Analyze counterparty relationships for a set of addresses
    python3 counterparty_graph.py addresses.csv -o counterparty_results.csv

    # Analyze specific address
    python3 counterparty_graph.py addresses.csv --target 0x1234...

    # Integration with knowledge graph
    from counterparty_graph import process_addresses
    process_addresses(knowledge_graph, addresses)
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# API Configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# Rate limiting
RATE_LIMIT = 5.0
last_request_time = 0

# Minimum interactions to consider a counterparty significant
MIN_INTERACTIONS = 2
MIN_VALUE_ETH = 0.01  # Ignore dust

# Known contracts to EXCLUDE from counterparty analysis (everyone uses these)
# Phase 2 improvement: expanded list based on false positive analysis
COMMON_CONTRACTS = {
    # DEX Routers (too common)
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 SwapRouter",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router",
    "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b": "Uniswap Universal Router Old",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch V5",
    "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch V4",
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch V6",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange",
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Protocol",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "Sushiswap Router",
    "0x99a58482bd75cbab83b27ec03ca68ff489b5788f": "Curve Router",
    "0xf0d4c12a5768d806021f80a262b4d39d26c58b8d": "Curve Router 2",
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
    # Lending Pools (too common)
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave V3 Pool",
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": "Aave V2 Pool",
    "0xc13e21b648a5ee794902342038ff3adab66be987": "Spark Pool",
    "0xc3d688b66703497daa19211eedff47f25384cdc3": "Compound V3 USDC",
    "0xa17581a9e3356d9a858b789d68b4d866e593ae94": "Compound V3 WETH",
    "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb": "Morpho Blue",
    "0x3d9819210a31b4961b30ef54be2aed79b9c9cd3b": "Compound Comptroller",
    "0xa238dd80c259a72e81d7e4664a9801593f98d1c5": "Venus Pool",
    # Staking/Liquid Staking
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "wstETH",
    "0xac3e018457b222d93114458476f3e3416abbe38f": "Frax sfrxETH",
    "0x5e8422345238f34275888049021821e8e08caa1f": "frxETH",
    "0xbe9895146f7af43049ca1c1ae358b0541ea49704": "Coinbase cbETH",
    "0xa35b1b31ce002fbf2058d22f30f95d405200a15b": "Stader ETHx",
    "0xf951e335afb289353dc249e82926178eac7ded78": "swETH",
    # Bridges (too common)
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge",
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism Gateway",
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": "Base Bridge",
    "0x49048044d57e1c92a77f79988d21fa8faf74e97e": "Base Portal",
    "0x32400084c286cf3e17e7b677ea9583e60a000324": "zkSync Bridge",
    "0x3ee18b2214aff97000d974cf647e7c347e8fa585": "Wormhole",
    "0x4d73adb72bc3dd368966edd0f0b2148401a178e2": "Stargate",
    "0x2796317b0ff8538f253012862c06787adfb8ceb6": "Synapse Bridge",
    # Tokens (transfers to token contracts are approvals, not counterparties)
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3": "USDe",
    "0x9d39a5de30e57443bff2a8307a4256c8797a3497": "sUSDe",
    "0x83f20f44975d03b1b09e64809b757c47f942beea": "sDAI",
    "0x4fabb145d64652a948d72533023f6e7a623c7c53": "BUSD",
    "0x853d955acef822db058eb8505911ed77f175b99e": "FRAX",
    "0x5f98805a4e8be255a32880fdec7f6728c6568ba0": "LUSD",
    # GHO/Aave ecosystem
    "0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f": "GHO",
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": "AAVE",
    # Maker/Sky
    "0x9759a6ac90977b93b58547b4a71c78317f391a28": "MKR",
    "0x0ab87046fbb341d058f17cbc4c1133f25a20a52f": "gOHM",
}

# Known CEX hot wallets (deposits TO these are significant, but exclude from general analysis)
CEX_HOT_WALLETS = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance 17",
    "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Binance 18",
    "0x4976a4a02f38326660d17bf34b431dc6e2eb2327": "Binance 19",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance 8",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance 20",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 1",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 2",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase 4",
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511": "Coinbase 5",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX 2",
    "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88": "MEXC",
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
    "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23": "Bybit",
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": "FTX",  # Historical
}


def rate_limit():
    """Enforce rate limiting."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / RATE_LIMIT:
        time.sleep(1 / RATE_LIMIT - elapsed)
    last_request_time = time.time()


def etherscan_request(params: dict, chain_id: int = 1) -> Any:
    """Make a rate-limited request to Etherscan V2 API."""
    rate_limit()
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = chain_id

    try:
        response = requests.get(
            "https://api.etherscan.io/v2/api",
            params=params,
            timeout=30
        )
        data = response.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"  API Error: {e}", file=sys.stderr)
        return []


def get_transactions(address: str, chain_id: int = 1, limit: int = 1000) -> List[dict]:
    """Get normal transactions for an address."""
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }
    return etherscan_request(params, chain_id)


def get_token_transfers(address: str, chain_id: int = 1, limit: int = 500) -> List[dict]:
    """Get ERC20 token transfers for an address."""
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "asc"
    }
    return etherscan_request(params, chain_id)


# ============================================================================
# Counterparty Extraction
# ============================================================================

class CounterpartyProfile:
    """Profile of an address's counterparty relationships."""

    def __init__(self, address: str):
        self.address = address.lower()
        self.sent_to: Dict[str, dict] = {}       # addr -> {count, total_value, last_ts}
        self.received_from: Dict[str, dict] = {} # addr -> {count, total_value, last_ts}
        self.deposit_targets: Set[str] = set()   # Addresses we sent to (potential exchange deposits)
        self.protocols_used: Dict[str, int] = defaultdict(int)  # Protocol -> interaction count
        self.tx_count = 0
        self.token_tx_count = 0

    def add_sent(self, to_addr: str, value_eth: float, timestamp: int):
        """Record an outgoing transaction."""
        to_addr = to_addr.lower()
        if to_addr not in self.sent_to:
            self.sent_to[to_addr] = {'count': 0, 'total_value': 0.0, 'last_ts': 0}
        self.sent_to[to_addr]['count'] += 1
        self.sent_to[to_addr]['total_value'] += value_eth
        self.sent_to[to_addr]['last_ts'] = max(self.sent_to[to_addr]['last_ts'], timestamp)

        # Track as potential deposit target
        if value_eth >= MIN_VALUE_ETH:
            self.deposit_targets.add(to_addr)

    def add_received(self, from_addr: str, value_eth: float, timestamp: int):
        """Record an incoming transaction."""
        from_addr = from_addr.lower()
        if from_addr not in self.received_from:
            self.received_from[from_addr] = {'count': 0, 'total_value': 0.0, 'last_ts': 0}
        self.received_from[from_addr]['count'] += 1
        self.received_from[from_addr]['total_value'] += value_eth
        self.received_from[from_addr]['last_ts'] = max(self.received_from[from_addr]['last_ts'], timestamp)

    def add_protocol(self, protocol_addr: str):
        """Record a protocol interaction."""
        self.protocols_used[protocol_addr.lower()] += 1

    def get_significant_counterparties(self, min_interactions: int = MIN_INTERACTIONS,
                                        exclude_common: bool = True) -> Set[str]:
        """Get counterparties with significant interaction history."""
        counterparties = set()

        for addr, data in self.sent_to.items():
            if data['count'] >= min_interactions:
                if exclude_common and addr in COMMON_CONTRACTS:
                    continue
                if exclude_common and addr in CEX_HOT_WALLETS:
                    continue  # Exclude CEX hot wallets from general counterparty set
                counterparties.add(addr)

        for addr, data in self.received_from.items():
            if data['count'] >= min_interactions:
                if exclude_common and addr in COMMON_CONTRACTS:
                    continue
                if exclude_common and addr in CEX_HOT_WALLETS:
                    continue
                counterparties.add(addr)

        return counterparties

    def get_deposit_targets(self, exclude_common: bool = True) -> Set[str]:
        """Get addresses we've sent value to (potential exchange deposits)."""
        targets = set()
        for addr in self.deposit_targets:
            if exclude_common and addr in COMMON_CONTRACTS:
                continue
            # Include CEX hot wallets as deposit targets (this is significant)
            targets.add(addr)
        return targets

    def get_unique_deposit_addresses(self) -> Set[str]:
        """
        Get addresses that are likely unique deposit addresses (not hot wallets).
        These are addresses we sent to that are NOT known contracts or hot wallets.
        """
        unique = set()
        for addr in self.deposit_targets:
            if addr in COMMON_CONTRACTS:
                continue
            if addr in CEX_HOT_WALLETS:
                continue
            # If we sent to this address and it's not a known contract,
            # it might be a unique deposit address
            unique.add(addr)
        return unique

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'address': self.address,
            'sent_to_count': len(self.sent_to),
            'received_from_count': len(self.received_from),
            'deposit_targets_count': len(self.deposit_targets),
            'protocols_used': dict(self.protocols_used),
            'tx_count': self.tx_count,
            'token_tx_count': self.token_tx_count,
            'top_sent_to': dict(sorted(self.sent_to.items(),
                                       key=lambda x: -x[1]['count'])[:10]),
            'top_received_from': dict(sorted(self.received_from.items(),
                                             key=lambda x: -x[1]['count'])[:10]),
        }


def build_counterparty_profile(address: str, chain_id: int = 1) -> CounterpartyProfile:
    """
    Build a complete counterparty profile for an address.
    """
    profile = CounterpartyProfile(address)
    address = address.lower()

    # Get normal transactions
    txs = get_transactions(address, chain_id, limit=1000)
    profile.tx_count = len(txs)

    for tx in txs:
        from_addr = tx.get('from', '').lower()
        to_addr = tx.get('to', '').lower()
        value_eth = int(tx.get('value', 0)) / 1e18
        timestamp = int(tx.get('timeStamp', 0))

        if from_addr == address:
            # Outgoing transaction
            if to_addr:
                profile.add_sent(to_addr, value_eth, timestamp)

                # Track protocol usage
                if to_addr in COMMON_CONTRACTS:
                    profile.add_protocol(to_addr)
        else:
            # Incoming transaction
            profile.add_received(from_addr, value_eth, timestamp)

    # Get token transfers
    token_txs = get_token_transfers(address, chain_id, limit=500)
    profile.token_tx_count = len(token_txs)

    for tx in token_txs:
        from_addr = tx.get('from', '').lower()
        to_addr = tx.get('to', '').lower()
        timestamp = int(tx.get('timeStamp', 0))

        # Estimate value in ETH (rough)
        decimals = int(tx.get('tokenDecimal', 18))
        value = int(tx.get('value', 0)) / (10 ** decimals)

        # For stablecoins, assume 1:1 with ETH value (rough approximation)
        token_symbol = tx.get('tokenSymbol', '').upper()
        if token_symbol in ['USDC', 'USDT', 'DAI', 'BUSD']:
            value_eth = value / 2000  # Rough ETH price approximation
        elif token_symbol in ['WETH', 'STETH', 'WSTETH']:
            value_eth = value
        else:
            value_eth = 0.01  # Nominal value for other tokens

        if from_addr == address and to_addr:
            profile.add_sent(to_addr, value_eth, timestamp)
        elif to_addr == address:
            profile.add_received(from_addr, value_eth, timestamp)

    return profile


# ============================================================================
# Similarity Calculation
# ============================================================================

def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def weighted_overlap(profile1: CounterpartyProfile, profile2: CounterpartyProfile) -> dict:
    """
    Calculate weighted overlap between two profiles.
    Weights interactions by frequency and value.
    """
    # Get counterparty sets
    cp1 = profile1.get_significant_counterparties()
    cp2 = profile2.get_significant_counterparties()

    # Basic Jaccard
    basic_jaccard = jaccard_similarity(cp1, cp2)

    # Shared counterparties with details
    shared = cp1 & cp2
    shared_details = []

    for addr in shared:
        data1_sent = profile1.sent_to.get(addr, {})
        data1_recv = profile1.received_from.get(addr, {})
        data2_sent = profile2.sent_to.get(addr, {})
        data2_recv = profile2.received_from.get(addr, {})

        total_interactions = (
            data1_sent.get('count', 0) + data1_recv.get('count', 0) +
            data2_sent.get('count', 0) + data2_recv.get('count', 0)
        )

        shared_details.append({
            'address': addr,
            'label': CEX_HOT_WALLETS.get(addr) or COMMON_CONTRACTS.get(addr) or 'Unknown',
            'total_interactions': total_interactions,
            'profile1_sent': data1_sent.get('count', 0),
            'profile1_recv': data1_recv.get('count', 0),
            'profile2_sent': data2_sent.get('count', 0),
            'profile2_recv': data2_recv.get('count', 0),
        })

    # Sort by total interactions
    shared_details.sort(key=lambda x: -x['total_interactions'])

    # Deposit target overlap (VERY strong signal)
    deposits1 = profile1.get_unique_deposit_addresses()
    deposits2 = profile2.get_unique_deposit_addresses()
    shared_deposits = deposits1 & deposits2
    deposit_jaccard = jaccard_similarity(deposits1, deposits2)

    # Protocol usage overlap
    protocols1 = set(profile1.protocols_used.keys())
    protocols2 = set(profile2.protocols_used.keys())
    protocol_jaccard = jaccard_similarity(protocols1, protocols2)

    # Calculate weighted score
    # Shared deposits are extremely strong (unique per user at exchanges)
    # Regular counterparty overlap is good
    # Protocol overlap is weaker (everyone uses Aave/Uniswap)
    weighted_score = (
        basic_jaccard * 0.4 +
        deposit_jaccard * 0.5 +
        protocol_jaccard * 0.1
    )

    return {
        'basic_jaccard': basic_jaccard,
        'deposit_jaccard': deposit_jaccard,
        'protocol_jaccard': protocol_jaccard,
        'weighted_score': weighted_score,
        'shared_counterparties': len(shared),
        'shared_deposits': len(shared_deposits),
        'shared_counterparty_details': shared_details[:10],  # Top 10
        'shared_deposit_addresses': list(shared_deposits)[:5],
        'unique_to_profile1': len(cp1 - cp2),
        'unique_to_profile2': len(cp2 - cp1),
    }


def calculate_confidence(overlap: dict) -> float:
    """
    Calculate confidence score from overlap metrics.
    """
    weighted = overlap['weighted_score']
    shared_deposits = overlap['shared_deposits']

    # Base confidence from weighted Jaccard
    if weighted >= 0.8:
        base_confidence = 0.90
    elif weighted >= 0.6:
        base_confidence = 0.75
    elif weighted >= 0.4:
        base_confidence = 0.55
    elif weighted >= 0.2:
        base_confidence = 0.35
    else:
        base_confidence = 0.0

    # Boost for shared deposit addresses (very strong signal)
    if shared_deposits >= 3:
        deposit_boost = 0.15
    elif shared_deposits >= 1:
        deposit_boost = 0.10
    else:
        deposit_boost = 0.0

    # Boost for many shared counterparties
    if overlap['shared_counterparties'] >= 10:
        counterparty_boost = 0.05
    else:
        counterparty_boost = 0.0

    return min(0.98, base_confidence + deposit_boost + counterparty_boost)


# ============================================================================
# Batch Analysis
# ============================================================================

def analyze_all_pairs(
    addresses: List[str],
    chain_id: int = 1,
    min_overlap: float = 0.2,
    progress_callback=None
) -> Dict[Tuple[str, str], dict]:
    """
    Analyze counterparty overlap for all address pairs.
    """
    print(f"  Building counterparty profiles for {len(addresses)} addresses...")

    # Build profiles
    profiles: Dict[str, CounterpartyProfile] = {}

    for i, addr in enumerate(addresses):
        if progress_callback:
            progress_callback(i, len(addresses), "Building profiles")
        elif (i + 1) % 10 == 0:
            print(f"    Processed {i + 1}/{len(addresses)}...")

        profiles[addr.lower()] = build_counterparty_profile(addr, chain_id)

    print(f"  Comparing {len(addresses) * (len(addresses) - 1) // 2} address pairs...")

    # Compare all pairs
    results = {}
    pair_count = 0
    total_pairs = len(addresses) * (len(addresses) - 1) // 2

    for i, addr1 in enumerate(addresses):
        for addr2 in addresses[i + 1:]:
            pair_count += 1

            if pair_count % 100 == 0:
                print(f"    Compared {pair_count}/{total_pairs} pairs...")

            addr1_lower = addr1.lower()
            addr2_lower = addr2.lower()

            overlap = weighted_overlap(profiles[addr1_lower], profiles[addr2_lower])

            if overlap['weighted_score'] >= min_overlap:
                confidence = calculate_confidence(overlap)
                results[(addr1_lower, addr2_lower)] = {
                    'overlap': overlap,
                    'confidence': confidence,
                    'profile1': profiles[addr1_lower].to_dict(),
                    'profile2': profiles[addr2_lower].to_dict(),
                }

    return results


def analyze_target_vs_pool(
    target: str,
    pool: List[str],
    chain_id: int = 1,
    min_overlap: float = 0.2
) -> Dict[str, dict]:
    """
    Analyze counterparty overlap between a target and a pool of addresses.
    """
    target = target.lower()
    print(f"  Building profile for target {target[:10]}...")
    target_profile = build_counterparty_profile(target, chain_id)

    print(f"  Comparing against {len(pool)} addresses...")
    results = {}

    for i, addr in enumerate(pool):
        if (i + 1) % 20 == 0:
            print(f"    Compared {i + 1}/{len(pool)}...")

        addr_lower = addr.lower()
        if addr_lower == target:
            continue

        profile = build_counterparty_profile(addr_lower, chain_id)
        overlap = weighted_overlap(target_profile, profile)

        if overlap['weighted_score'] >= min_overlap:
            confidence = calculate_confidence(overlap)
            results[addr_lower] = {
                'overlap': overlap,
                'confidence': confidence,
                'profile': profile.to_dict(),
            }

    return results


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

def process_single_address(kg: 'KnowledgeGraph', addr: str):
    """
    Process counterparty analysis for a single address.
    """
    if not ETHERSCAN_API_KEY:
        raise ValueError("ETHERSCAN_API_KEY not set")

    profile = build_counterparty_profile(addr)

    # Store profile summary as evidence
    counterparties = profile.get_significant_counterparties()
    deposit_targets = profile.get_deposit_targets()

    kg.add_evidence(
        addr,
        source='Counterparty',
        claim=f"Has {len(counterparties)} significant counterparties, {len(deposit_targets)} deposit targets",
        confidence=0.5,
        raw_data=profile.to_dict()
    )

    return profile.to_dict()


def process_addresses(kg: 'KnowledgeGraph', addresses: List[str], min_overlap: float = 0.3):
    """
    Process counterparty graph analysis for a batch of addresses.
    """
    print(f"\n  Running counterparty graph analysis on {len(addresses)} addresses...")

    if not ETHERSCAN_API_KEY:
        print("  Warning: ETHERSCAN_API_KEY not set", file=sys.stderr)
        return

    results = analyze_all_pairs(addresses, min_overlap=min_overlap)

    print(f"\n  Found {len(results)} address pairs with significant overlap")

    # Store in knowledge graph
    high_confidence_count = 0

    for (addr1, addr2), data in results.items():
        confidence = data['confidence']
        overlap = data['overlap']

        # Add relationship
        kg.add_relationship(
            addr1,
            addr2,
            'counterparty_overlap',
            confidence=confidence,
            evidence={
                'method': 'counterparty_graph',
                'weighted_score': overlap['weighted_score'],
                'shared_counterparties': overlap['shared_counterparties'],
                'shared_deposits': overlap['shared_deposits'],
                'basic_jaccard': overlap['basic_jaccard'],
            }
        )

        # Add evidence to both addresses
        for addr in [addr1, addr2]:
            other = addr2 if addr == addr1 else addr1
            kg.add_evidence(
                addr,
                source='Counterparty',
                claim=f"Shares {overlap['shared_counterparties']} counterparties with {other[:10]}... ({confidence:.0%})",
                confidence=confidence,
                raw_data={
                    'other_address': other,
                    'overlap': overlap
                }
            )

        if confidence >= 0.70:
            high_confidence_count += 1
            print(f"    HIGH: {addr1[:10]}... ↔ {addr2[:10]}... ({confidence:.0%}) - "
                  f"{overlap['shared_counterparties']} shared, {overlap['shared_deposits']} deposits")

    print(f"\n  Counterparty analysis complete")
    print(f"    Total pairs with overlap: {len(results)}")
    print(f"    High confidence (>=70%): {high_confidence_count}")


# ============================================================================
# Standalone Mode
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Counterparty Graph Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze counterparty relationships for addresses
    python3 counterparty_graph.py addresses.csv -o results.csv

    # Analyze specific target against pool
    python3 counterparty_graph.py addresses.csv --target 0x1234...

    # Lower overlap threshold (more results, lower confidence)
    python3 counterparty_graph.py addresses.csv --min-overlap 0.15
        """
    )

    parser.add_argument("input", nargs="?", help="Input CSV with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--target", help="Analyze specific address against pool")
    parser.add_argument("--min-overlap", type=float, default=0.2,
                        help="Minimum weighted overlap to report (default: 0.2)")
    parser.add_argument("--chain-id", type=int, default=1, help="Chain ID (default: 1)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--kg", action="store_true", help="Store results in knowledge graph")
    parser.add_argument("--profile", help="Show detailed profile for single address")

    args = parser.parse_args()

    if not ETHERSCAN_API_KEY:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Single profile mode
    if args.profile:
        print(f"Building counterparty profile for {args.profile}...")
        profile = build_counterparty_profile(args.profile, args.chain_id)

        print(f"\n{'='*60}")
        print(f"COUNTERPARTY PROFILE: {args.profile[:20]}...")
        print(f"{'='*60}")
        print(f"\nTransactions: {profile.tx_count} normal, {profile.token_tx_count} token")
        print(f"Sent to: {len(profile.sent_to)} unique addresses")
        print(f"Received from: {len(profile.received_from)} unique addresses")
        print(f"Deposit targets: {len(profile.deposit_targets)}")
        print(f"Protocols used: {len(profile.protocols_used)}")

        sig_counterparties = profile.get_significant_counterparties()
        print(f"\nSignificant counterparties ({len(sig_counterparties)}):")
        for addr in list(sig_counterparties)[:10]:
            sent = profile.sent_to.get(addr, {})
            recv = profile.received_from.get(addr, {})
            label = CEX_HOT_WALLETS.get(addr) or COMMON_CONTRACTS.get(addr) or ""
            print(f"  {addr[:16]}... {label} - sent:{sent.get('count',0)} recv:{recv.get('count',0)}")

        unique_deposits = profile.get_unique_deposit_addresses()
        if unique_deposits:
            print(f"\nUnique deposit addresses ({len(unique_deposits)}):")
            for addr in list(unique_deposits)[:5]:
                print(f"  {addr}")

        return

    if not args.input:
        parser.error("Input CSV required (or use --profile)")

    # Load addresses
    with open(args.input) as f:
        reader = csv.DictReader(f)
        addresses = [row.get("address") or row.get("borrower") for row in reader]
        addresses = [a for a in addresses if a]

    print(f"Loaded {len(addresses)} addresses")
    print(f"Minimum overlap threshold: {args.min_overlap}")

    # Run analysis
    if args.target:
        print(f"\nAnalyzing target: {args.target}")
        results = analyze_target_vs_pool(
            args.target,
            addresses,
            chain_id=args.chain_id,
            min_overlap=args.min_overlap
        )
        # Convert to pair format
        results = {(args.target.lower(), addr): data for addr, data in results.items()}
    else:
        print(f"\nAnalyzing all pairs...")
        results = analyze_all_pairs(
            addresses,
            chain_id=args.chain_id,
            min_overlap=args.min_overlap
        )

    # Store in knowledge graph if requested
    if args.kg:
        from build_knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.connect()

        for (addr1, addr2), data in results.items():
            kg.add_relationship(
                addr1, addr2, 'counterparty_overlap',
                confidence=data['confidence'],
                evidence={
                    'method': 'counterparty_graph',
                    'overlap': data['overlap']
                }
            )

        kg.close()
        print(f"\nStored {len(results)} relationships in knowledge graph")

    # Output
    if args.json:
        json_results = {}
        for (addr1, addr2), data in results.items():
            key = f"{addr1}|{addr2}"
            json_results[key] = {
                'addr1': addr1,
                'addr2': addr2,
                'confidence': data['confidence'],
                'overlap': data['overlap'],
            }
        print(json.dumps(json_results, indent=2, default=str))
    else:
        # Print summary
        print(f"\n{'='*80}")
        print(f"COUNTERPARTY GRAPH RESULTS")
        print(f"{'='*80}")
        print(f"\nFound {len(results)} address pairs with significant overlap\n")

        # Sort by confidence
        sorted_results = sorted(results.items(), key=lambda x: -x[1]['confidence'])

        for (addr1, addr2), data in sorted_results[:20]:
            conf = data['confidence']
            overlap = data['overlap']

            conf_label = "🔴 HIGH" if conf >= 0.70 else "🟡 MEDIUM" if conf >= 0.50 else "🟢 LOW"

            print(f"{conf_label} [{conf:.0%}] {addr1[:16]}... ↔ {addr2[:16]}...")
            print(f"    Overlap: {overlap['weighted_score']:.1%} weighted, "
                  f"{overlap['shared_counterparties']} shared counterparties")
            if overlap['shared_deposits'] > 0:
                print(f"    ⚠️  SHARED DEPOSITS: {overlap['shared_deposits']} (strong signal)")
            if overlap['shared_counterparty_details']:
                top_shared = overlap['shared_counterparty_details'][0]
                print(f"    Top shared: {top_shared['address'][:16]}... ({top_shared['total_interactions']} interactions)")
            print()

        if len(results) > 20:
            print(f"... and {len(results) - 20} more pairs")

    # Save to CSV
    if args.output:
        sorted_results = sorted(results.items(), key=lambda x: -x[1]['confidence'])

        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "addr1", "addr2", "confidence", "weighted_overlap",
                "shared_counterparties", "shared_deposits", "basic_jaccard"
            ])

            for (addr1, addr2), data in sorted_results:
                overlap = data['overlap']
                writer.writerow([
                    addr1,
                    addr2,
                    f"{data['confidence']:.3f}",
                    f"{overlap['weighted_score']:.3f}",
                    overlap['shared_counterparties'],
                    overlap['shared_deposits'],
                    f"{overlap['basic_jaccard']:.3f}"
                ])

        print(f"\nSaved to {args.output}")

    # Summary statistics
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    high_conf = sum(1 for _, d in results.items() if d['confidence'] >= 0.70)
    medium_conf = sum(1 for _, d in results.items() if 0.50 <= d['confidence'] < 0.70)
    low_conf = len(results) - high_conf - medium_conf

    print(f"\nConfidence Distribution:")
    print(f"  High (>=70%):    {high_conf}")
    print(f"  Medium (50-69%): {medium_conf}")
    print(f"  Low (<50%):      {low_conf}")

    # Pairs with shared deposits (very strong)
    deposit_pairs = sum(1 for _, d in results.items() if d['overlap']['shared_deposits'] > 0)
    if deposit_pairs:
        print(f"\n⚠️  Pairs with shared deposit addresses: {deposit_pairs}")
        print("    (Shared deposits are a very strong same-entity signal)")

    # Most connected addresses
    addr_counts = defaultdict(int)
    for (addr1, addr2), data in results.items():
        if data['confidence'] >= 0.50:
            addr_counts[addr1] += 1
            addr_counts[addr2] += 1

    if addr_counts:
        print(f"\nMost Connected Addresses (>=50% confidence):")
        for addr, count in sorted(addr_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"  {addr[:20]}... - {count} connections")


if __name__ == "__main__":
    main()
