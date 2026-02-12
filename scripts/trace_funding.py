#!/usr/bin/env python3
"""
Funding Origin Tracer

Traces the first ETH funding source for wallet addresses to identify CEX origins.
Expected hit rate: 30-40% (wallets funded from exchanges with KYC).

Usage:
    # Trace funding for addresses in CSV
    python3 scripts/trace_funding.py addresses.csv -o funding_traces.csv

    # Trace single address
    python3 scripts/trace_funding.py --address 0x1234...

    # Increase hop depth
    python3 scripts/trace_funding.py addresses.csv --max-hops 5

Environment:
    ETHERSCAN_API_KEY - Required for transaction history
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
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
# CEX Hot Wallet Database
# ============================================================================

# Comprehensive CEX hot wallet mapping with entity names
CEX_WALLETS = {
    # Binance (numbered wallets)
    "0x28c6c06298d514db089934071355e5743bf21d60": ("Binance", "Binance 14"),
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": ("Binance", "Binance 16"),
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": ("Binance", "Binance 15"),
    "0xf977814e90da44bfa03b6295a0616a897441acec": ("Binance", "Binance 8"),
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": ("Binance", "Binance 20"),
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": ("Binance", "Binance 7"),
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": ("Binance", "Binance 6"),
    "0xa2b5f80e12b6a53a5f9ad97e9b19e7a14d2c73d0": ("Binance", "Binance 25"),
    "0xfe4a8f53a7ce7de78e9f9f85c3d68a0d2d3fa3dc": ("Binance", "Binance 29"),
    "0x3c783c21a0383057d128bae431894a5c19f9cf06": ("Binance", "Binance 30"),
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": ("Binance", "Binance 9"),

    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": ("Kraken", "Kraken 4"),
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": ("Kraken", "Kraken 1"),
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": ("Kraken", "Kraken 2"),
    "0xe853c56864a2ebe4576a807d26fdc4a0ada51919": ("Kraken", "Kraken 3"),
    "0xda9dfa130df4de4673b89022ee50ff26f6ea73cf": ("Kraken", "Kraken 5"),
    "0xae2d4617c862309a3d75a0ffb358c7a5009c673f": ("Kraken", "Kraken 6"),

    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": ("Coinbase", "Coinbase 1"),
    "0x503828976d22510aad0201ac7ec88293211d23da": ("Coinbase", "Coinbase 2"),
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": ("Coinbase", "Coinbase 3"),
    "0x3cd751e6b0078be393132286c442345e5dc49699": ("Coinbase", "Coinbase 4"),
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511": ("Coinbase", "Coinbase 5"),
    "0xeb2629a2734e272bcc07bda959863f316f4bd4cf": ("Coinbase", "Coinbase 6"),
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": ("Coinbase", "Coinbase 10"),
    "0x02354e51a46ff63909ef28bb87ad2bec08e04ae6": ("Coinbase", "Coinbase 7"),

    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": ("Gemini", "Gemini 1"),
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": ("Gemini", "Gemini 2"),
    "0x07ee55aa48bb72dcc6e9d78256648910de513eca": ("Gemini", "Gemini 3"),
    "0x5f65f7b609678448494de4c87521cdf6cef1e932": ("Gemini", "Gemini 4"),
    "0x61edcdf5bb737adffe5043706e7c5bb1f1a56ef2": ("Gemini", "Gemini 5"),

    # OKX (formerly OKEx)
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": ("OKX", "OKX 1"),
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": ("OKX", "OKX 2"),
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128": ("OKX", "OKX 3"),
    "0x5041ed759dd4afc3a72b8192c143f72f4724081a": ("OKX", "OKX 4"),
    "0xcba38020cd7b6f51df6afaf507685add148f6ab6": ("OKX", "OKX 5"),

    # Poloniex
    "0xa910f92acdaf488fa6ef02174fb86208ad7722ba": ("Poloniex", "Poloniex 4"),
    "0x32be343b94f860124dc4fee278fdcbd38c102d88": ("Poloniex", "Poloniex 1"),
    "0xab11204cfeaccffa63c2d23aef2ea9accdb0a0d5": ("Poloniex", "Poloniex 2"),

    # Bitfinex
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": ("Bitfinex", "Bitfinex 1"),
    "0x742d35cc6634c0532925a3b844bc454e4438f44e": ("Bitfinex", "Bitfinex 2"),
    "0xc56fefd1028b0534bfadcdb580d3519b5586246e": ("Bitfinex", "Bitfinex 3"),
    "0xfcd1ed25f19bbb70bf2bd01cd5611eea83f71a12": ("Bitfinex", "Bitfinex 4"),

    # Huobi / HTX
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": ("Huobi", "Huobi 1"),
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": ("Huobi", "Huobi 2"),
    "0xfdb16996831753d5331ff813c29a93c76834a0ad": ("Huobi", "Huobi 3"),
    "0x46705dfff24256421a05d056c29e81bdc09723b8": ("Huobi", "Huobi 4"),

    # KuCoin
    "0x2b5634c42055806a59e9107ed44d43c426e58258": ("KuCoin", "KuCoin 1"),
    "0x689c56aef474df92d44a1b70850f808488f9769c": ("KuCoin", "KuCoin 2"),
    "0xa1d8d972560c2f8144af871db508f0b0b10a3fbf": ("KuCoin", "KuCoin 3"),

    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": ("Bybit", "Bybit 1"),
    "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4": ("Bybit", "Bybit 2"),

    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": ("Gate.io", "Gate.io 1"),
    "0x7793cd85c11a924478d358d49b05b37e91b5810f": ("Gate.io", "Gate.io 2"),

    # Crypto.com
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": ("Crypto.com", "Crypto.com 1"),
    "0x46340b20830761efd32832a74d7169b29feb9758": ("Crypto.com", "Crypto.com 2"),

    # FTX (Bankrupt - historical reference)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": ("FTX", "FTX Exchange"),
    "0xc098b2a3aa256d2140208c3de6543aaef5cd3a94": ("FTX", "FTX 2"),

    # Prime Brokers / Custodians (Institutional)
    "0x1157a2076b9bb22a85cc2c162f20fab3898f4101": ("FalconX", "FalconX 1"),
    "0xe5379345eddab3db1a8d55dd59f4413c0df2f5f4": ("Copper", "Copper 2"),
    "0x36a85757645e8e8aec062a1dee289c7d615901ca": ("Paxos", "Paxos 4"),

    # Anchorage (Institutional Custodian)
    "0x0a4e26d68ac51b7a5c18a68be0f3fae8e56f8a65": ("Anchorage", "Anchorage 1"),

    # BitGo (Institutional Custodian)
    "0x5b98b66de2b23c08af6b0c286e2f77bbb0dc45db": ("BitGo", "BitGo 1"),
}

# Known protocols (not CEXs but useful to identify)
PROTOCOL_WALLETS = {
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": ("0x Protocol", "0x Exchange Proxy"),
    "0x1111111254fb6c44bac0bed2854e76f90643097d": ("1inch", "1inch Router V4"),
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": ("Uniswap", "Uniswap V2 Router"),
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": ("Uniswap", "Uniswap SwapRouter02"),
}


@dataclass
class FundingTrace:
    """Result of funding origin trace."""
    address: str
    first_funder: str = ""
    funder_entity: str = ""  # Exchange/Protocol name
    funder_label: str = ""   # Specific wallet label
    funding_hops: int = 0
    funding_chain: list = None  # Full chain of addresses
    first_tx_hash: str = ""
    first_tx_value: float = 0.0
    first_tx_date: str = ""
    is_cex_funded: bool = False
    is_institutional: bool = False
    error: str = ""

    def __post_init__(self):
        if self.funding_chain is None:
            self.funding_chain = []


class FundingTracer:
    """Traces funding origins using Etherscan API."""

    BASE_URL = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str, rate_limit: float = 5.0, max_hops: int = 3):
        self.api_key = api_key
        self.max_hops = max_hops
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0

    def _wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _get_first_tx(self, address: str) -> Optional[dict]:
        """Get the first transaction for an address."""
        self._wait()

        params = {
            "chainid": 1,
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 10,  # Get first 10 to find first incoming
            "sort": "asc",
            "apikey": self.api_key,
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            data = resp.json()

            if data.get("status") != "1" or not data.get("result"):
                return None

            # Find first incoming transaction with value
            for tx in data["result"]:
                if tx.get("to", "").lower() == address.lower():
                    value = int(tx.get("value", "0"))
                    if value > 0:
                        return tx

            return None

        except Exception:
            return None

    def trace(self, address: str) -> FundingTrace:
        """Trace funding origin for an address."""
        address = address.lower()
        result = FundingTrace(address=address)

        current = address
        chain = [address]

        for hop in range(self.max_hops):
            tx = self._get_first_tx(current)
            if not tx:
                break

            from_addr = tx.get("from", "").lower()
            if not from_addr or from_addr == current:
                break

            chain.append(from_addr)
            result.funding_hops = hop + 1

            # Check if this is a known CEX/entity
            if from_addr in CEX_WALLETS:
                entity, label = CEX_WALLETS[from_addr]
                result.first_funder = from_addr
                result.funder_entity = entity
                result.funder_label = label
                result.is_cex_funded = True
                result.is_institutional = entity in ["FalconX", "Copper", "Paxos", "Anchorage", "BitGo"]

                # Store first tx details
                result.first_tx_hash = tx.get("hash", "")
                result.first_tx_value = int(tx.get("value", "0")) / 1e18
                result.first_tx_date = datetime.fromtimestamp(
                    int(tx.get("timeStamp", 0))
                ).isoformat() if tx.get("timeStamp") else ""

                break

            if from_addr in PROTOCOL_WALLETS:
                entity, label = PROTOCOL_WALLETS[from_addr]
                result.first_funder = from_addr
                result.funder_entity = entity
                result.funder_label = label
                break

            current = from_addr

        result.funding_chain = chain

        # If we traced but didn't find a known entity, record the origin
        if not result.first_funder and len(chain) > 1:
            result.first_funder = chain[-1]

        return result


def load_addresses(filepath: str) -> list[str]:
    """Load addresses from file."""
    addresses = []
    path = Path(filepath)

    if path.suffix == ".csv":
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = row.get("address") or row.get("Address") or row.get("wallet")
                if addr:
                    addresses.append(addr.strip().lower())
    else:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith("0x"):
                    addresses.append(line.lower())

    return list(set(addresses))


def save_results(results: list[FundingTrace], filepath: str, format: str = "csv"):
    """Save results to file."""
    if format == "json":
        with open(filepath, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
    else:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "address", "first_funder", "funder_entity", "funder_label",
                "funding_hops", "first_tx_hash", "first_tx_value", "first_tx_date",
                "is_cex_funded", "is_institutional", "error"
            ])
            writer.writeheader()
            for r in results:
                row = asdict(r)
                del row["funding_chain"]  # Skip chain in CSV
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Trace funding origins to identify CEX sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Trace single address
    python3 trace_funding.py --address 0xd1781818f7f30b68155fec7d31f812abe7b00be9

    # Batch trace from CSV
    python3 trace_funding.py whales.csv -o funding_traces.csv

    # Deeper trace (5 hops)
    python3 trace_funding.py whales.csv --max-hops 5
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with addresses"
    )

    parser.add_argument(
        "--address", "-a",
        help="Trace single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="funding_traces.csv",
        help="Output file (default: funding_traces.csv)"
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        default=3,
        help="Maximum hops to trace (default: 3)"
    )

    parser.add_argument(
        "--format", "-f",
        default="csv",
        choices=["csv", "json"],
        help="Output format (default: csv)"
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=5.0,
        help="Requests per second (default: 5.0)"
    )

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        print("Error: ETHERSCAN_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    tracer = FundingTracer(api_key, args.rate_limit, args.max_hops)

    # Single address mode
    if args.address:
        result = tracer.trace(args.address)
        output = asdict(result)
        print(json.dumps(output, indent=2))
        return

    # Batch mode
    addresses = load_addresses(args.input)
    print(f"Tracing funding for {len(addresses)} addresses...", file=sys.stderr)

    results = []
    for i, addr in enumerate(addresses):
        if (i + 1) % 20 == 0:
            print(f"Progress: {i + 1}/{len(addresses)}", file=sys.stderr)

        result = tracer.trace(addr)
        results.append(result)

    save_results(results, args.output, args.format)
    print(f"Saved to {args.output}", file=sys.stderr)

    # Summary
    cex_funded = sum(1 for r in results if r.is_cex_funded)
    institutional = sum(1 for r in results if r.is_institutional)
    traced = sum(1 for r in results if r.first_funder)

    # Count by exchange
    by_exchange = {}
    for r in results:
        if r.funder_entity:
            by_exchange[r.funder_entity] = by_exchange.get(r.funder_entity, 0) + 1

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total: {len(results)}", file=sys.stderr)
    print(f"  Traced to origin: {traced} ({100*traced/len(results):.1f}%)", file=sys.stderr)
    print(f"  CEX-funded: {cex_funded} ({100*cex_funded/len(results):.1f}%)", file=sys.stderr)
    print(f"  Institutional: {institutional}", file=sys.stderr)

    if by_exchange:
        print(f"\n  By Exchange:", file=sys.stderr)
        for exchange, count in sorted(by_exchange.items(), key=lambda x: -x[1]):
            print(f"    {exchange}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
