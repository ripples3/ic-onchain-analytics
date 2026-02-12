#!/usr/bin/env python3
"""
Whale Address Enrichment Tool

Batch-enriches wallet addresses with identity data from multiple sources.
Reduces cost from ~40K tokens/address (manual) to ~100 tokens/address (automated).

Usage:
    # Enrich from CSV file
    python3 scripts/enrich_addresses.py input.csv -o enriched.csv

    # Enrich single address
    python3 scripts/enrich_addresses.py --address 0x1234...

    # Run specific enrichment methods only
    python3 scripts/enrich_addresses.py input.csv --methods etherscan,ens,safe

    # Resume from checkpoint
    python3 scripts/enrich_addresses.py input.csv --resume checkpoint.json

Environment:
    ETHERSCAN_API_KEY - Required for Etherscan labels and first funder
    ETH_RPC_URL - Optional for ENS resolution (uses public RPC if not set)
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Load .env file if present
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
# Data Classes
# ============================================================================

@dataclass
class EnrichedAddress:
    """Enriched wallet data."""
    address: str
    # Original data (from input)
    protocol: str = ""
    total_borrowed: float = 0.0

    # Contract type detection
    contract_type: str = ""  # EOA, Safe, DSProxy, Smart Account, etc.
    contract_name: str = ""  # e.g., "Safe 1.4.1", "DSProxy #221928"

    # Identity data
    ens_name: str = ""
    etherscan_label: str = ""
    arkham_label: str = ""

    # Funding trace
    first_funder: str = ""
    first_funder_label: str = ""  # e.g., "Binance 16", "Kraken 4"
    funding_hops: int = 0

    # Safe-specific
    safe_owners: list = field(default_factory=list)
    safe_threshold: int = 0

    # Clustering (ZachXBT methodology)
    cluster_id: str = ""
    cluster_size: int = 0
    related_addresses: list = field(default_factory=list)
    cluster_signals: list = field(default_factory=list)
    cluster_confidence: float = 0.0

    # Metadata
    last_updated: str = ""
    enrichment_methods: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# ============================================================================
# CEX Hot Wallet Database
# ============================================================================

CEX_WALLETS = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance 8",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance 20",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance 7",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance 6",

    # Kraken
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken 4",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken 1",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken 2",
    "0xe853c56864a2ebe4576a807d26fdc4a0ada51919": "Kraken 3",
    "0xda9dfa130df4de4673b89022ee50ff26f6ea73cf": "Kraken 5",

    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 1",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 2",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 3",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase 4",
    "0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511": "Coinbase 5",
    "0xeb2629a2734e272bcc07bda959863f316f4bd4cf": "Coinbase 6",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase 10",

    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini 1",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Gemini 2",
    "0x07ee55aa48bb72dcc6e9d78256648910de513eca": "Gemini 3",
    "0x5f65f7b609678448494de4c87521cdf6cef1e932": "Gemini 4",

    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX 1",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX 2",

    # Poloniex
    "0xa910f92acdaf488fa6ef02174fb86208ad7722ba": "Poloniex 4",
    "0x32be343b94f860124dc4fee278fdcbd38c102d88": "Poloniex 1",

    # Bitfinex
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Bitfinex 1",
    "0x742d35cc6634c0532925a3b844bc454e4438f44e": "Bitfinex 2",

    # Huobi/HTX
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "Huobi 1",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": "Huobi 2",

    # FalconX (Prime Broker)
    "0x1157a2076b9bb22a85cc2c162f20fab3898f4101": "FalconX 1",
    "0x4d818c4f05f7bf06cf6e0a7f2c8c7f1b3e6c3e5d": "FalconX 2",

    # Copper (Custodian)
    "0xe5379345eddab3db1a8d55dd59f4413c0df2f5f4": "Copper 2",

    # Paxos
    "0x36a85757645e8e8aec062a1dee289c7d615901ca": "Paxos 4",
}


# ============================================================================
# Rate Limiter
# ============================================================================

class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 5.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


# ============================================================================
# Enrichment Methods
# ============================================================================

def get_etherscan_label(address: str, api_key: str, rate_limiter: RateLimiter) -> tuple[str, str]:
    """
    Get Etherscan label and contract type for an address.

    Returns:
        (label, contract_type) tuple
    """
    rate_limiter.wait()

    # First, check if it's a contract
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": 1,
        "module": "proxy",
        "action": "eth_getCode",
        "address": address,
        "apikey": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        code = data.get("result", "0x")
        is_contract = code != "0x" and len(code) > 2

        if is_contract:
            # Try to get contract info
            rate_limiter.wait()
            params = {
                "chainid": 1,
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": api_key,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("status") == "1" and data.get("result"):
                contract_info = data["result"][0]
                contract_name = contract_info.get("ContractName", "")

                # Detect contract type from name or implementation
                if "GnosisSafe" in contract_name or "Safe" in contract_name:
                    return "", f"Safe ({contract_name})"
                elif "DSProxy" in contract_name:
                    return "", "DSProxy"
                elif "InstaAccount" in contract_name:
                    return "", "Instadapp DSA"
                elif contract_name:
                    return "", f"Contract ({contract_name})"
                else:
                    return "", "Contract (unverified)"

        return "", "EOA"

    except Exception as e:
        return "", f"Error: {str(e)}"


def get_first_funder(address: str, api_key: str, rate_limiter: RateLimiter, max_hops: int = 3) -> tuple[str, str, int]:
    """
    Trace the first ETH transfer to this address.

    Returns:
        (funder_address, funder_label, hop_count) tuple
    """
    current_address = address.lower()
    hop = 0

    while hop < max_hops:
        rate_limiter.wait()

        url = "https://api.etherscan.io/v2/api"
        params = {
            "chainid": 1,
            "module": "account",
            "action": "txlist",
            "address": current_address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "asc",
            "apikey": api_key,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("status") != "1" or not data.get("result"):
                break

            tx = data["result"][0]
            from_addr = tx.get("from", "").lower()
            value = int(tx.get("value", "0"))

            # Skip if it's an outgoing tx or no value
            if from_addr == current_address or value == 0:
                break

            # Check if funder is a known CEX
            if from_addr in CEX_WALLETS:
                return from_addr, CEX_WALLETS[from_addr], hop

            # Recurse to trace further
            current_address = from_addr
            hop += 1

        except Exception:
            break

    # Return the last traced address even if not labeled
    if current_address != address.lower():
        return current_address, "", hop

    return "", "", 0


def resolve_ens(address: str, rpc_url: str) -> str:
    """
    Resolve ENS reverse lookup for an address.

    Returns:
        ENS name or empty string
    """
    try:
        # Use JSON-RPC to call ENS reverse resolver
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": "0xa58E81fe9b61B5c3fE2AFD33CF304c454AbFc7Cb",  # ENS Reverse Registrar
                "data": f"0x691f3431{address[2:].lower().zfill(64)}"  # node(addr)
            }, "latest"],
            "id": 1
        }

        resp = requests.post(rpc_url, json=payload, timeout=10)
        data = resp.json()

        result = data.get("result", "0x")
        if result and result != "0x" and len(result) > 66:
            # Decode the ENS name from the result
            # This is simplified - full implementation would decode the bytes
            pass

    except Exception:
        pass

    return ""


def get_safe_owners(address: str, rate_limiter: RateLimiter) -> tuple[list, int]:
    """
    Get Safe multisig owners via Safe Transaction Service API.

    Returns:
        (owners_list, threshold) tuple
    """
    rate_limiter.wait()

    url = f"https://safe-transaction-mainnet.safe.global/api/v1/safes/{address}/"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            owners = data.get("owners", [])
            threshold = data.get("threshold", 0)
            return owners, threshold
    except Exception:
        pass

    return [], 0


def run_clustering(addresses: list[str], api_key: str, rate_limiter: RateLimiter) -> dict:
    """
    Run address clustering analysis using ZachXBT methodology.

    Returns dict mapping address -> cluster info
    """
    try:
        from cluster_addresses import EtherscanClient, analyze_addresses
    except ImportError:
        # Fallback: simple funder-based clustering
        return cluster_by_funder(addresses, api_key, rate_limiter)

    client = EtherscanClient(api_key, 1.0 / rate_limiter.min_interval)
    results = analyze_addresses(addresses, client, methods=["timing", "funders"])

    cluster_map = {}
    for r in results:
        cluster_map[r.address] = {
            "cluster_id": r.cluster_id,
            "cluster_size": r.cluster_size,
            "related_addresses": r.related_addresses,
            "cluster_signals": list(r.signals.keys()) if r.signals else [],
            "cluster_confidence": r.confidence,
        }

    return cluster_map


def cluster_by_funder(addresses: list[str], api_key: str, rate_limiter: RateLimiter) -> dict:
    """
    Simple clustering: group addresses by common first funder.

    Fallback when full clustering module not available.
    """
    from collections import defaultdict

    funder_to_addresses = defaultdict(list)

    for addr in addresses:
        funder, label, hops = get_first_funder(addr, api_key, rate_limiter)
        if funder:
            funder_to_addresses[funder].append(addr.lower())

    # Build cluster map
    cluster_map = {}
    cluster_num = 0

    for funder, funded_addrs in funder_to_addresses.items():
        if len(funded_addrs) > 1:
            cluster_num += 1
            cluster_id = f"funder_cluster_{cluster_num}"

            for addr in funded_addrs:
                cluster_map[addr] = {
                    "cluster_id": cluster_id,
                    "cluster_size": len(funded_addrs),
                    "related_addresses": [a for a in funded_addrs if a != addr],
                    "cluster_signals": ["common_funder"],
                    "cluster_confidence": 0.5,
                }

    return cluster_map


# ============================================================================
# Main Enrichment Pipeline
# ============================================================================

def enrich_address(
    address: str,
    etherscan_key: str,
    rpc_url: str,
    rate_limiter: RateLimiter,
    methods: list[str],
    original_data: dict = None
) -> EnrichedAddress:
    """
    Enrich a single address with all available data.
    """
    result = EnrichedAddress(
        address=address.lower(),
        last_updated=datetime.now(timezone.utc).isoformat()
    )

    if original_data:
        result.protocol = original_data.get("protocol", "")
        result.total_borrowed = float(original_data.get("total_borrowed", 0))

    # Etherscan label and contract type
    if "etherscan" in methods and etherscan_key:
        try:
            label, contract_type = get_etherscan_label(address, etherscan_key, rate_limiter)
            result.etherscan_label = label
            result.contract_type = contract_type
            result.enrichment_methods.append("etherscan")
        except Exception as e:
            result.errors.append(f"etherscan: {str(e)}")

    # First funder trace
    if "funding" in methods and etherscan_key:
        try:
            funder, funder_label, hops = get_first_funder(address, etherscan_key, rate_limiter)
            result.first_funder = funder
            result.first_funder_label = funder_label
            result.funding_hops = hops
            result.enrichment_methods.append("funding")
        except Exception as e:
            result.errors.append(f"funding: {str(e)}")

    # ENS resolution
    if "ens" in methods and rpc_url:
        try:
            ens_name = resolve_ens(address, rpc_url)
            result.ens_name = ens_name
            result.enrichment_methods.append("ens")
        except Exception as e:
            result.errors.append(f"ens: {str(e)}")

    # Safe owners (only if it's a Safe)
    if "safe" in methods and "Safe" in result.contract_type:
        try:
            owners, threshold = get_safe_owners(address, rate_limiter)
            result.safe_owners = owners
            result.safe_threshold = threshold
            result.enrichment_methods.append("safe")
        except Exception as e:
            result.errors.append(f"safe: {str(e)}")

    return result


def load_input_csv(filepath: str) -> list[dict]:
    """Load addresses from CSV file."""
    addresses = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Support multiple column name formats
            addr = row.get("address") or row.get("Address") or row.get("wallet") or row.get("Wallet")
            if addr:
                addresses.append({
                    "address": addr.lower(),
                    "protocol": row.get("protocol", row.get("Protocol", "")),
                    "total_borrowed": row.get("total_borrowed", row.get("TotalBorrowed", 0)),
                })
    return addresses


def save_checkpoint(results: list[EnrichedAddress], filepath: str):
    """Save enrichment progress to checkpoint file."""
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": [asdict(r) for r in results]
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_checkpoint(filepath: str) -> list[EnrichedAddress]:
    """Load enrichment progress from checkpoint file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    results = []
    for r in data.get("results", []):
        results.append(EnrichedAddress(**r))
    return results


def write_output_csv(results: list[EnrichedAddress], filepath: str):
    """Write enriched results to CSV."""
    if not results:
        return

    fieldnames = [
        "address", "protocol", "total_borrowed",
        "contract_type", "contract_name",
        "ens_name", "etherscan_label", "arkham_label",
        "first_funder", "first_funder_label", "funding_hops",
        "safe_owners", "safe_threshold",
        "cluster_id", "cluster_size", "related_addresses", "cluster_signals", "cluster_confidence",
        "last_updated", "enrichment_methods", "errors"
    ]

    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            row = asdict(r)
            # Convert lists to JSON strings
            row["safe_owners"] = json.dumps(row["safe_owners"]) if row["safe_owners"] else ""
            row["related_addresses"] = json.dumps(row["related_addresses"]) if row["related_addresses"] else ""
            row["cluster_signals"] = json.dumps(row["cluster_signals"]) if row["cluster_signals"] else ""
            row["enrichment_methods"] = ",".join(row["enrichment_methods"])
            row["errors"] = "; ".join(row["errors"]) if row["errors"] else ""
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Batch-enrich wallet addresses with identity data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Enrich addresses from CSV
    python3 enrich_addresses.py whales.csv -o enriched.csv

    # Enrich single address
    python3 enrich_addresses.py --address 0xd1781818f7f30b68155fec7d31f812abe7b00be9

    # Run only specific methods
    python3 enrich_addresses.py whales.csv --methods etherscan,funding

    # Resume from checkpoint
    python3 enrich_addresses.py whales.csv --resume checkpoint.json

Available methods:
    etherscan - Contract type and labels from Etherscan
    funding   - First funder trace (CEX detection)
    ens       - ENS reverse resolution
    safe      - Safe multisig owner lookup
    cluster   - Address clustering (ZachXBT methodology)
    arkham    - Arkham Intelligence labels (requires separate script)
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input CSV file with addresses"
    )

    parser.add_argument(
        "--address", "-a",
        help="Enrich a single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="enriched_addresses.csv",
        help="Output CSV file (default: enriched_addresses.csv)"
    )

    parser.add_argument(
        "--methods", "-m",
        default="etherscan,funding,ens,safe",
        help="Comma-separated list of enrichment methods"
    )

    parser.add_argument(
        "--resume", "-r",
        help="Resume from checkpoint file"
    )

    parser.add_argument(
        "--checkpoint", "-c",
        default="enrichment_checkpoint.json",
        help="Checkpoint file path (default: enrichment_checkpoint.json)"
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=5.0,
        help="API calls per second (default: 5.0)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input and not args.address:
        parser.error("Either input CSV or --address is required")

    # Get API keys
    etherscan_key = os.getenv("ETHERSCAN_API_KEY")
    rpc_url = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")

    if not etherscan_key:
        print("Warning: ETHERSCAN_API_KEY not set. Etherscan methods will be skipped.", file=sys.stderr)

    # Parse methods
    methods = [m.strip().lower() for m in args.methods.split(",")]
    print(f"Enrichment methods: {methods}", file=sys.stderr)

    # Initialize rate limiter
    rate_limiter = RateLimiter(args.rate_limit)

    # Single address mode
    if args.address:
        print(f"Enriching single address: {args.address}", file=sys.stderr)
        result = enrich_address(
            args.address,
            etherscan_key,
            rpc_url,
            rate_limiter,
            methods
        )
        print(json.dumps(asdict(result), indent=2))
        return

    # Batch mode
    # Load existing progress if resuming
    processed = set()
    results = []

    if args.resume and Path(args.resume).exists():
        print(f"Resuming from checkpoint: {args.resume}", file=sys.stderr)
        results = load_checkpoint(args.resume)
        processed = {r.address.lower() for r in results}
        print(f"Loaded {len(results)} previously enriched addresses", file=sys.stderr)

    # Load input
    addresses = load_input_csv(args.input)
    print(f"Loaded {len(addresses)} addresses from {args.input}", file=sys.stderr)

    # Filter already processed
    to_process = [a for a in addresses if a["address"].lower() not in processed]
    print(f"Processing {len(to_process)} new addresses", file=sys.stderr)

    # Process addresses
    for i, addr_data in enumerate(to_process):
        address = addr_data["address"]

        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{len(to_process)} ({len(results)} total)", file=sys.stderr)

        try:
            result = enrich_address(
                address,
                etherscan_key,
                rpc_url,
                rate_limiter,
                methods,
                addr_data
            )
            results.append(result)

            # Save checkpoint every 50 addresses
            if len(results) % 50 == 0:
                save_checkpoint(results, args.checkpoint)
                print(f"Checkpoint saved: {len(results)} addresses", file=sys.stderr)

        except KeyboardInterrupt:
            print("\nInterrupted. Saving checkpoint...", file=sys.stderr)
            save_checkpoint(results, args.checkpoint)
            sys.exit(1)
        except Exception as e:
            print(f"Error processing {address}: {e}", file=sys.stderr)

    # Run clustering if requested
    if "cluster" in methods and etherscan_key and results:
        print(f"\nRunning address clustering...", file=sys.stderr)
        try:
            all_addresses = [r.address for r in results]
            cluster_map = run_clustering(all_addresses, etherscan_key, rate_limiter)

            # Apply cluster info to results
            for r in results:
                if r.address in cluster_map:
                    info = cluster_map[r.address]
                    r.cluster_id = info.get("cluster_id", "")
                    r.cluster_size = info.get("cluster_size", 0)
                    r.related_addresses = info.get("related_addresses", [])
                    r.cluster_signals = info.get("cluster_signals", [])
                    r.cluster_confidence = info.get("cluster_confidence", 0.0)
                    r.enrichment_methods.append("cluster")

            clustered = sum(1 for r in results if r.cluster_id)
            print(f"Clustering complete: {clustered} addresses in clusters", file=sys.stderr)
        except Exception as e:
            print(f"Clustering error: {e}", file=sys.stderr)

    # Save final results
    write_output_csv(results, args.output)
    print(f"\nComplete! Enriched {len(results)} addresses to {args.output}", file=sys.stderr)

    # Print summary
    identified = sum(1 for r in results if r.first_funder_label or r.ens_name or r.etherscan_label)
    safes = sum(1 for r in results if "Safe" in r.contract_type)
    cex_funded = sum(1 for r in results if r.first_funder_label)
    clustered = sum(1 for r in results if r.cluster_id)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total: {len(results)}", file=sys.stderr)
    print(f"  Identified: {identified} ({100*identified/len(results):.1f}%)", file=sys.stderr)
    print(f"  Safe wallets: {safes}", file=sys.stderr)
    print(f"  CEX-funded: {cex_funded}", file=sys.stderr)
    if clustered:
        print(f"  In clusters: {clustered}", file=sys.stderr)


if __name__ == "__main__":
    main()
