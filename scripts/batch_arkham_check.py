#!/usr/bin/env python3
"""
Arkham Intelligence Label Checker

Batch-checks addresses against Arkham Intelligence for entity labels.
Uses the public intel.arkm.com website (no API key required).

Expected hit rate: 20-30% (Arkham has extensive coverage of major entities).

Usage:
    # Check addresses from CSV
    python3 scripts/batch_arkham_check.py addresses.csv -o arkham_labels.csv

    # Check single address
    python3 scripts/batch_arkham_check.py --address 0x1234...

    # Use cache file
    python3 scripts/batch_arkham_check.py addresses.csv --cache arkham_cache.json

Rate Limiting:
    Default: 1 request per 2 seconds to avoid IP blocks
    Recommended: Use rotating proxies for >100 addresses
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ArkhamResult:
    """Result from Arkham lookup."""
    address: str
    has_label: bool = False
    entity_name: str = ""
    entity_type: str = ""  # fund, exchange, protocol, individual, etc.
    description: str = ""
    portfolio_value: str = ""
    twitter: str = ""
    website: str = ""
    related_addresses: int = 0
    last_checked: str = ""
    cached: bool = False
    error: str = ""


# ============================================================================
# Cache Management
# ============================================================================

class ArkhamCache:
    """Simple JSON cache for Arkham results."""

    def __init__(self, cache_file: str, max_age_days: int = 7):
        self.cache_file = Path(cache_file)
        self.max_age = timedelta(days=max_age_days)
        self.data = self._load()

    def _load(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get(self, address: str) -> Optional[ArkhamResult]:
        """Get cached result if not expired."""
        address = address.lower()
        if address not in self.data:
            return None

        entry = self.data[address]
        checked = datetime.fromisoformat(entry.get("last_checked", "2000-01-01"))

        if datetime.now(timezone.utc) - checked > self.max_age:
            return None

        result = ArkhamResult(**entry)
        result.cached = True
        return result

    def set(self, result: ArkhamResult):
        """Cache a result."""
        self.data[result.address.lower()] = asdict(result)


# ============================================================================
# Arkham Scraper
# ============================================================================

class ArkhamScraper:
    """
    Scrapes Arkham Intelligence for wallet labels.

    Uses the public explorer page at intel.arkm.com/explorer/address/{addr}
    """

    BASE_URL = "https://intel.arkm.com/explorer/address/"

    # User agent to avoid blocks
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, rate_limit: float = 0.5, cache: Optional[ArkhamCache] = None):
        """
        Args:
            rate_limit: Requests per second (default 0.5 = 1 req per 2 seconds)
            cache: Optional cache instance
        """
        self.min_interval = 1.0 / rate_limit
        self.last_call = 0
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

    def _parse_html(self, html: str, address: str) -> ArkhamResult:
        """Parse Arkham page HTML to extract label info."""
        result = ArkhamResult(
            address=address.lower(),
            last_checked=datetime.now(timezone.utc).isoformat()
        )

        if not HAS_BS4:
            # Fallback: regex-based extraction
            return self._parse_regex(html, result)

        soup = BeautifulSoup(html, 'html.parser')

        # Look for entity name in various locations
        # Arkham uses React with dynamic content, so we look for patterns

        # Check page title for entity name
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            # Pattern: "Entity Name | Arkham Intelligence"
            if "|" in title_text and "Arkham" in title_text:
                entity = title_text.split("|")[0].strip()
                if entity and entity != address[:10]:
                    result.has_label = True
                    result.entity_name = entity

        # Look for entity name in meta tags
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            desc = meta_desc.get('content', '')
            if desc and 'wallet' not in desc.lower():
                result.description = desc[:200]

        # Look for JSON data in script tags (React hydration)
        for script in soup.find_all('script'):
            text = script.get_text()
            if '"entityName"' in text or '"entity"' in text:
                # Try to extract entity info from JSON
                try:
                    # Find JSON-like patterns
                    name_match = re.search(r'"entityName"\s*:\s*"([^"]+)"', text)
                    if name_match:
                        result.has_label = True
                        result.entity_name = name_match.group(1)

                    type_match = re.search(r'"entityType"\s*:\s*"([^"]+)"', text)
                    if type_match:
                        result.entity_type = type_match.group(1)

                except Exception:
                    pass

        return result

    def _parse_regex(self, html: str, result: ArkhamResult) -> ArkhamResult:
        """Fallback regex parsing when BeautifulSoup not available."""
        # Look for entity name patterns
        patterns = [
            r'"entityName"\s*:\s*"([^"]+)"',
            r'"name"\s*:\s*"([^"]+)"',
            r'<title>([^|<]+)\s*\|',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                name = match.group(1).strip()
                if name and len(name) < 50 and not name.startswith("0x"):
                    result.has_label = True
                    result.entity_name = name
                    break

        # Entity type
        type_match = re.search(r'"entityType"\s*:\s*"([^"]+)"', html)
        if type_match:
            result.entity_type = type_match.group(1)

        return result

    def check_address(self, address: str) -> ArkhamResult:
        """Check a single address against Arkham."""
        address = address.lower()

        # Check cache first
        if self.cache:
            cached = self.cache.get(address)
            if cached:
                return cached

        result = ArkhamResult(
            address=address,
            last_checked=datetime.now(timezone.utc).isoformat()
        )

        try:
            self._wait()

            url = f"{self.BASE_URL}{address}"
            resp = self.session.get(url, timeout=15)

            if resp.status_code == 404:
                # No label found (address not indexed)
                pass
            elif resp.status_code == 200:
                result = self._parse_html(resp.text, address)
            elif resp.status_code == 429:
                result.error = "Rate limited"
            else:
                result.error = f"HTTP {resp.status_code}"

        except requests.exceptions.Timeout:
            result.error = "Timeout"
        except Exception as e:
            result.error = str(e)

        # Cache result
        if self.cache and not result.error:
            self.cache.set(result)

        return result


# ============================================================================
# Main
# ============================================================================

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


def save_results(results: list[ArkhamResult], filepath: str, format: str = "csv"):
    """Save results to file."""
    if format == "json":
        with open(filepath, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
    else:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "address", "has_label", "entity_name", "entity_type",
                "description", "twitter", "website",
                "last_checked", "cached", "error"
            ])
            writer.writeheader()
            for r in results:
                row = {
                    "address": r.address,
                    "has_label": r.has_label,
                    "entity_name": r.entity_name,
                    "entity_type": r.entity_type,
                    "description": r.description,
                    "twitter": r.twitter,
                    "website": r.website,
                    "last_checked": r.last_checked,
                    "cached": r.cached,
                    "error": r.error,
                }
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Check addresses against Arkham Intelligence labels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check single address
    python3 batch_arkham_check.py --address 0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c

    # Batch check from CSV
    python3 batch_arkham_check.py whales.csv -o arkham_labels.csv

    # Use cache to avoid re-checking
    python3 batch_arkham_check.py whales.csv --cache arkham_cache.json

Note:
    - Default rate limit is 1 request per 2 seconds to avoid IP blocks
    - For large batches (>100), consider using a proxy or spreading over multiple sessions
    - Install beautifulsoup4 for better parsing: pip install beautifulsoup4
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with addresses"
    )

    parser.add_argument(
        "--address", "-a",
        help="Check single address"
    )

    parser.add_argument(
        "--output", "-o",
        default="arkham_labels.csv",
        help="Output file (default: arkham_labels.csv)"
    )

    parser.add_argument(
        "--cache", "-c",
        help="Cache file for storing results"
    )

    parser.add_argument(
        "--cache-days",
        type=int,
        default=7,
        help="Cache expiry in days (default: 7)"
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
        default=0.5,
        help="Requests per second (default: 0.5 = 1 per 2 sec)"
    )

    args = parser.parse_args()

    if not args.input and not args.address:
        parser.error("Either input file or --address required")

    if not HAS_BS4:
        print("Warning: beautifulsoup4 not installed. Using fallback parser.", file=sys.stderr)
        print("Install with: pip install beautifulsoup4", file=sys.stderr)

    # Initialize cache
    cache = None
    if args.cache:
        cache = ArkhamCache(args.cache, args.cache_days)
        print(f"Using cache: {args.cache} ({len(cache.data)} entries)", file=sys.stderr)

    scraper = ArkhamScraper(args.rate_limit, cache)

    # Single address mode
    if args.address:
        result = scraper.check_address(args.address)
        print(json.dumps(asdict(result), indent=2))
        if cache:
            cache.save()
        return

    # Batch mode
    addresses = load_addresses(args.input)
    print(f"Checking {len(addresses)} addresses against Arkham...", file=sys.stderr)

    # Estimate time
    cached_count = sum(1 for a in addresses if cache and cache.get(a))
    to_fetch = len(addresses) - cached_count
    est_time = to_fetch * (1.0 / args.rate_limit)
    print(f"Cached: {cached_count}, To fetch: {to_fetch}", file=sys.stderr)
    print(f"Estimated time: {est_time/60:.1f} minutes", file=sys.stderr)

    results = []
    labeled = 0
    errors = 0

    for i, addr in enumerate(addresses):
        result = scraper.check_address(addr)
        results.append(result)

        if result.has_label:
            labeled += 1
        if result.error:
            errors += 1

        # Progress
        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{len(addresses)} ({labeled} labeled, {errors} errors)", file=sys.stderr)

        # Save cache periodically
        if cache and (i + 1) % 50 == 0:
            cache.save()

    # Final cache save
    if cache:
        cache.save()

    save_results(results, args.output, args.format)
    print(f"\nSaved to {args.output}", file=sys.stderr)

    # Summary
    cached = sum(1 for r in results if r.cached)

    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total: {len(results)}", file=sys.stderr)
    print(f"  Labeled: {labeled} ({100*labeled/len(results):.1f}%)", file=sys.stderr)
    print(f"  From cache: {cached}", file=sys.stderr)
    print(f"  Errors: {errors}", file=sys.stderr)

    if labeled > 0:
        print(f"\nLabeled addresses:", file=sys.stderr)
        for r in results:
            if r.has_label:
                print(f"  {r.address[:10]}... -> {r.entity_name}", file=sys.stderr)


if __name__ == "__main__":
    main()
