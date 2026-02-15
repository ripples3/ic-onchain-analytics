#!/usr/bin/env python3
"""
Incremental Update Pipeline - Sync Dune query results into Knowledge Graph.

Fetches latest lending borrower data from Dune (cached, no credits), diffs
against the existing knowledge graph, and optionally applies changes and
queues new high-value addresses for investigation.

Usage:
    # Dry run - show what would change
    python3 scripts/incremental_update.py

    # Apply changes to KG
    python3 scripts/incremental_update.py --apply

    # Apply + queue new addresses for investigation
    python3 scripts/incremental_update.py --apply --investigate

    # Only flag new addresses with >$50M borrowed
    python3 scripts/incremental_update.py --threshold 50

    # Force fresh Dune execution (uses credits!)
    python3 scripts/incremental_update.py --apply --execute

    # Use a local CSV instead of Dune API
    python3 scripts/incremental_update.py --from-csv data/latest_borrowers.csv

Environment:
    DUNE_API_KEY - Required for Dune API access (not needed with --from-csv)
"""

import argparse
import csv
import io
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "knowledge_graph.db"
REFERENCE_CSV = PROJECT_DIR / "references" / "top_lending_protocol_borrowers_eoa_safe_with_identity.csv"
UPDATE_LOG_DIR = DATA_DIR / "updates"

# Dune query ID for top lending borrowers
DUNE_QUERY_ID = 6654792

# Default threshold: only flag addresses borrowing above this amount ($M)
DEFAULT_THRESHOLD_M = 10.0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("incremental_update")

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    env_paths = [SCRIPT_DIR / ".env", PROJECT_DIR / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


# ============================================================================
# Metadata table for tracking update history
# ============================================================================

UPDATE_METADATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS update_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    update_type TEXT NOT NULL,           -- 'incremental_dune', 'manual_import', etc.
    query_id INTEGER,                    -- Dune query ID if applicable
    timestamp TEXT NOT NULL,             -- ISO timestamp of this update
    new_addresses INTEGER DEFAULT 0,
    updated_addresses INTEGER DEFAULT 0,
    dropped_addresses INTEGER DEFAULT 0,
    total_in_source INTEGER DEFAULT 0,
    total_in_kg INTEGER DEFAULT 0,
    threshold_m REAL,
    investigation_queued INTEGER DEFAULT 0,
    details TEXT,                        -- JSON with additional context
    dry_run BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_update_metadata_timestamp
    ON update_metadata(timestamp);
"""


# ============================================================================
# Dune Data Fetcher
# ============================================================================

def fetch_dune_results(query_id: int, execute: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch results from Dune Analytics for the given query ID.

    By default uses cached results (free). Pass execute=True to force
    a fresh execution (consumes API credits).

    Returns a list of row dicts.
    """
    try:
        from dune_client.client import DuneClient
        from dune_client.query import QueryBase
    except ImportError:
        log.error("dune-client not installed. Run: pip install dune-client")
        sys.exit(1)

    api_key = os.getenv("DUNE_API_KEY")
    if not api_key:
        log.error("DUNE_API_KEY environment variable not set.")
        log.error("Get your API key from: https://dune.com/settings/api")
        sys.exit(1)

    dune = DuneClient(api_key)

    if execute:
        log.warning("Executing fresh query (consumes API credits)...")
        query = QueryBase(query_id=query_id)
        results = dune.run_query(query)
    else:
        log.info("Fetching cached results for query %d (free)...", query_id)
        results = dune.get_latest_result(query_id)

    if not results.result or not results.result.rows:
        log.warning("Dune returned no results for query %d", query_id)
        return []

    rows = results.result.rows
    cols = len(rows[0].keys()) if rows else 0
    log.info("Received %d rows x %d columns from Dune", len(rows), cols)
    return rows


def load_csv_results(csv_path: str) -> List[Dict[str, Any]]:
    """Load borrower data from a local CSV file instead of Dune."""
    path = Path(csv_path)
    if not path.exists():
        log.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info("Loaded %d rows from %s", len(rows), csv_path)
    return rows


# ============================================================================
# Data Normalization
# ============================================================================

def normalize_dune_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Normalize Dune/CSV rows into a consistent per-address dict.

    Dune query 6654792 returns one row per (borrower, project) pair.
    We aggregate across projects to get a single record per borrower
    with the total borrowed amount summed.

    Returns: {address: {total_borrowed_m, address_type, borrowed_assets,
                        projects, identity, confidence, source, ...}}
    """
    by_address: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        # Support column name variations
        address = (
            row.get("borrower")
            or row.get("address")
            or row.get("Borrower")
            or ""
        ).strip().lower()

        if not address or not address.startswith("0x"):
            continue

        # Parse borrowed amount
        borrowed_str = (
            row.get("total_borrowed_m")
            or row.get("total_borrowed")
            or "0"
        )
        try:
            borrowed_m = float(str(borrowed_str).replace(",", ""))
        except (ValueError, TypeError):
            borrowed_m = 0.0

        # Parse other fields
        address_type = row.get("address_type", "").strip()
        project = row.get("project", "").strip()
        identity = row.get("identity", "").strip()
        confidence = row.get("confidence", "").strip()
        source = row.get("source", "").strip()
        borrowed_assets = row.get("borrowed_assets", "").strip()
        ens_name = row.get("ens_name", "").strip()

        if address not in by_address:
            by_address[address] = {
                "total_borrowed_m": 0.0,
                "address_type": address_type,
                "projects": set(),
                "borrowed_assets": set(),
                "identity": identity if identity else None,
                "confidence": confidence if confidence else None,
                "source": source if source else None,
                "ens_name": ens_name if ens_name else None,
            }

        entry = by_address[address]
        entry["total_borrowed_m"] += borrowed_m
        if project:
            entry["projects"].add(project)
        if borrowed_assets:
            # Parse the list-like string e.g. "['USDC', 'WETH']"
            try:
                assets = json.loads(borrowed_assets.replace("'", '"'))
                if isinstance(assets, list):
                    entry["borrowed_assets"].update(assets)
            except (json.JSONDecodeError, AttributeError):
                entry["borrowed_assets"].add(borrowed_assets)

        # Keep the highest-confidence identity
        if identity and identity.lower() not in ("unknown", "unidentified", ""):
            existing_id = entry.get("identity")
            if not existing_id or existing_id.lower() in ("unknown", "unidentified", ""):
                entry["identity"] = identity
                entry["confidence"] = confidence
                entry["source"] = source

    # Convert sets to sorted lists for serialization
    for addr, entry in by_address.items():
        entry["projects"] = sorted(entry["projects"])
        entry["borrowed_assets"] = sorted(entry["borrowed_assets"])

    return by_address


# ============================================================================
# Knowledge Graph Diff
# ============================================================================

class DiffResult:
    """Encapsulates the diff between Dune data and the knowledge graph."""

    def __init__(self):
        self.new_addresses: List[Dict[str, Any]] = []       # Not yet in KG
        self.updated_amounts: List[Dict[str, Any]] = []     # Borrowed amount changed
        self.dropped_addresses: List[Dict[str, Any]] = []   # In KG but not in Dune
        self.unchanged: List[str] = []                      # No change
        self.total_source: int = 0
        self.total_kg: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new_addresses or self.updated_amounts or self.dropped_addresses)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "INCREMENTAL UPDATE DIFF REPORT",
            "=" * 60,
            f"  Source addresses:    {self.total_source}",
            f"  KG addresses:        {self.total_kg}",
            f"  New addresses:       {len(self.new_addresses)}",
            f"  Updated amounts:     {len(self.updated_amounts)}",
            f"  Dropped addresses:   {len(self.dropped_addresses)}",
            f"  Unchanged:           {len(self.unchanged)}",
        ]
        return "\n".join(lines)


def compute_diff(
    source_data: Dict[str, Dict[str, Any]],
    db_path: Path,
    threshold_m: float = 0.0,
) -> DiffResult:
    """
    Compare source data against the knowledge graph and compute the diff.

    Args:
        source_data: Normalized per-address data from Dune/CSV.
        db_path: Path to the knowledge graph SQLite database.
        threshold_m: Only include new addresses above this borrowed threshold.

    Returns:
        DiffResult with categorized changes.
    """
    diff = DiffResult()
    diff.total_source = len(source_data)

    # Connect to KG (read-only for diff)
    if not db_path.exists():
        log.warning("Knowledge graph not found at %s. All addresses will be new.", db_path)
        kg_addresses: Dict[str, Dict[str, Any]] = {}
    else:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM entities").fetchall()
        kg_addresses = {row["address"]: dict(row) for row in rows}

        # Try to read stored borrowed amounts from evidence table
        kg_borrowed: Dict[str, float] = {}
        try:
            evidence_rows = conn.execute(
                """SELECT entity_address, raw_data FROM evidence
                   WHERE source = 'dune_incremental'
                   ORDER BY created_at DESC"""
            ).fetchall()
            for ev_row in evidence_rows:
                addr = ev_row["entity_address"]
                if addr not in kg_borrowed:
                    try:
                        data = json.loads(ev_row["raw_data"])
                        kg_borrowed[addr] = float(data.get("total_borrowed_m", 0))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
        except sqlite3.OperationalError:
            pass

        conn.close()

    diff.total_kg = len(kg_addresses)

    source_addrs = set(source_data.keys())
    kg_addrs = set(kg_addresses.keys())

    # --- New addresses (in source, not in KG) ---
    for addr in sorted(source_addrs - kg_addrs):
        entry = source_data[addr]
        borrowed = entry["total_borrowed_m"]
        if borrowed >= threshold_m:
            diff.new_addresses.append({
                "address": addr,
                "total_borrowed_m": borrowed,
                "address_type": entry["address_type"],
                "projects": entry["projects"],
                "borrowed_assets": entry["borrowed_assets"],
                "identity": entry.get("identity"),
                "confidence": entry.get("confidence"),
                "source": entry.get("source"),
                "ens_name": entry.get("ens_name"),
            })

    # Sort new addresses by borrowed amount descending
    diff.new_addresses.sort(key=lambda x: x["total_borrowed_m"], reverse=True)

    # --- Updated amounts (in both, but borrowed amount changed significantly) ---
    for addr in sorted(source_addrs & kg_addrs):
        new_borrowed = source_data[addr]["total_borrowed_m"]

        # Check if we have a previously stored borrowed amount
        old_borrowed = kg_borrowed.get(addr) if db_path.exists() else None

        if old_borrowed is not None:
            # Significant change = more than 5% or more than $1M difference
            abs_diff = abs(new_borrowed - old_borrowed)
            pct_diff = abs_diff / old_borrowed if old_borrowed > 0 else float("inf")
            if abs_diff > 1.0 and pct_diff > 0.05:
                diff.updated_amounts.append({
                    "address": addr,
                    "old_borrowed_m": old_borrowed,
                    "new_borrowed_m": new_borrowed,
                    "change_m": new_borrowed - old_borrowed,
                    "change_pct": (new_borrowed - old_borrowed) / old_borrowed * 100
                    if old_borrowed > 0 else 0,
                    "identity": kg_addresses.get(addr, {}).get("identity", ""),
                })
        else:
            # First time tracking this amount -- record it as an update
            # so the amount gets stored in evidence for future diffs
            diff.updated_amounts.append({
                "address": addr,
                "old_borrowed_m": None,
                "new_borrowed_m": new_borrowed,
                "change_m": 0.0,
                "change_pct": 0.0,
                "identity": kg_addresses.get(addr, {}).get("identity", ""),
                "_first_record": True,
            })

    # Sort updates by absolute change descending
    diff.updated_amounts.sort(
        key=lambda x: abs(x.get("change_m", 0)),
        reverse=True,
    )

    # --- Dropped addresses (in KG from previous Dune data, not in current source) ---
    # Only flag addresses that we previously imported from Dune (have dune_incremental evidence)
    if db_path.exists():
        for addr in sorted(kg_addrs - source_addrs):
            # Only flag if we previously recorded this from Dune
            if addr in kg_borrowed:
                entity = kg_addresses.get(addr, {})
                diff.dropped_addresses.append({
                    "address": addr,
                    "previous_borrowed_m": kg_borrowed.get(addr, 0),
                    "identity": entity.get("identity", ""),
                    "entity_type": entity.get("entity_type", ""),
                })

    # --- Unchanged ---
    for addr in sorted(source_addrs & kg_addrs):
        if not any(u["address"] == addr for u in diff.updated_amounts):
            diff.unchanged.append(addr)

    return diff


# ============================================================================
# Apply Changes
# ============================================================================

def apply_changes(
    diff: DiffResult,
    source_data: Dict[str, Dict[str, Any]],
    db_path: Path,
    investigate: bool = False,
    threshold_m: float = DEFAULT_THRESHOLD_M,
) -> Dict[str, Any]:
    """
    Apply diff changes to the knowledge graph.

    Returns a summary dict of actions taken.
    """
    # Import KnowledgeGraph class from build_knowledge_graph
    sys.path.insert(0, str(SCRIPT_DIR))
    from build_knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph(db_path)
    kg.connect()

    # Ensure update_metadata table exists
    kg.connect().executescript(UPDATE_METADATA_SCHEMA)
    kg.connect().commit()

    now = datetime.now(timezone.utc).isoformat()
    actions = {
        "added": 0,
        "updated": 0,
        "investigated_queued": 0,
    }

    # --- Add new entities ---
    for entry in diff.new_addresses:
        addr = entry["address"]
        entity_kwargs = {
            "entity_type": "unknown",
        }
        # If the source data includes an identity, use it
        if entry.get("identity") and entry["identity"].lower() not in ("unknown", "unidentified"):
            entity_kwargs["identity"] = entry["identity"]
            confidence_str = entry.get("confidence", "")
            if confidence_str:
                conf_map = {"high": 0.85, "medium": 0.6, "low": 0.3, "unverified": 0.2}
                entity_kwargs["confidence"] = conf_map.get(
                    confidence_str.lower(), 0.5
                )
        if entry.get("address_type"):
            contract_type = entry["address_type"].upper()
            if contract_type in ("EOA", "SAFE", "CONTRACT"):
                entity_kwargs["contract_type"] = contract_type
        if entry.get("ens_name"):
            entity_kwargs["ens_name"] = entry["ens_name"]

        is_new = kg.add_entity(addr, **entity_kwargs)
        if is_new:
            actions["added"] += 1

        # Store borrowed amount as evidence for future diffs
        kg.add_evidence(
            addr,
            source="dune_incremental",
            claim=f"Total borrowed: ${entry['total_borrowed_m']:.2f}M across {', '.join(entry['projects'])}",
            confidence=0.95,
            raw_data={
                "total_borrowed_m": entry["total_borrowed_m"],
                "projects": entry["projects"],
                "borrowed_assets": entry["borrowed_assets"],
                "query_id": DUNE_QUERY_ID,
                "timestamp": now,
            },
        )

        # Queue for investigation if above threshold
        if investigate and entry["total_borrowed_m"] >= threshold_m:
            for layer in ["onchain", "behavioral", "osint"]:
                # Priority based on borrowed amount (higher = process first)
                priority = min(int(entry["total_borrowed_m"]), 9999)
                kg.queue_address(addr, layer, priority)
            actions["investigated_queued"] += 1

    # --- Update borrowed amounts for existing entities ---
    for entry in diff.updated_amounts:
        addr = entry["address"]
        new_borrowed = entry["new_borrowed_m"]

        # Get full source data for this address
        src = source_data.get(addr, {})

        # Store updated borrowed amount
        claim_parts = [f"Total borrowed: ${new_borrowed:.2f}M"]
        if entry.get("old_borrowed_m") is not None and not entry.get("_first_record"):
            change = entry["change_m"]
            direction = "increased" if change > 0 else "decreased"
            claim_parts.append(
                f"({direction} by ${abs(change):.2f}M from ${entry['old_borrowed_m']:.2f}M)"
            )
        if src.get("projects"):
            claim_parts.append(f"across {', '.join(src['projects'])}")

        kg.add_evidence(
            addr,
            source="dune_incremental",
            claim=" ".join(claim_parts),
            confidence=0.95,
            raw_data={
                "total_borrowed_m": new_borrowed,
                "projects": src.get("projects", []),
                "borrowed_assets": src.get("borrowed_assets", []),
                "query_id": DUNE_QUERY_ID,
                "timestamp": now,
                "previous_borrowed_m": entry.get("old_borrowed_m"),
            },
        )
        actions["updated"] += 1

    # --- Record update metadata ---
    conn = kg.connect()
    conn.execute(
        """INSERT INTO update_metadata
           (update_type, query_id, timestamp, new_addresses, updated_addresses,
            dropped_addresses, total_in_source, total_in_kg, threshold_m,
            investigation_queued, details, dry_run)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "incremental_dune",
            DUNE_QUERY_ID,
            now,
            len(diff.new_addresses),
            len(diff.updated_amounts),
            len(diff.dropped_addresses),
            diff.total_source,
            diff.total_kg,
            threshold_m,
            actions["investigated_queued"],
            json.dumps({
                "new_addresses": [e["address"] for e in diff.new_addresses],
                "top_changes": [
                    {
                        "address": e["address"],
                        "change_m": e.get("change_m", 0),
                    }
                    for e in diff.updated_amounts[:10]
                    if not e.get("_first_record")
                ],
            }),
            False,
        ),
    )
    conn.commit()
    kg.close()

    return actions


# ============================================================================
# Report Generation
# ============================================================================

def print_report(diff: DiffResult, threshold_m: float, apply: bool, investigate: bool):
    """Print a human-readable diff report."""
    print(diff.summary())

    # --- New addresses ---
    if diff.new_addresses:
        print(f"\n--- NEW ADDRESSES ({len(diff.new_addresses)}) ---")
        print(f"{'Address':<44} {'Borrowed ($M)':>14} {'Type':<10} {'Projects'}")
        print("-" * 100)
        for entry in diff.new_addresses[:30]:
            projects_str = ", ".join(entry["projects"][:3])
            print(
                f"{entry['address']:<44} "
                f"{entry['total_borrowed_m']:>14.2f} "
                f"{entry.get('address_type', ''):.<10} "
                f"{projects_str}"
            )
        if len(diff.new_addresses) > 30:
            print(f"  ... and {len(diff.new_addresses) - 30} more")
    else:
        print("\n--- No new addresses ---")

    # --- Updated amounts ---
    real_updates = [u for u in diff.updated_amounts if not u.get("_first_record")]
    if real_updates:
        print(f"\n--- AMOUNT CHANGES ({len(real_updates)}) ---")
        print(
            f"{'Address':<44} {'Old ($M)':>10} {'New ($M)':>10} "
            f"{'Change ($M)':>12} {'Change %':>10} {'Identity'}"
        )
        print("-" * 120)
        for entry in real_updates[:20]:
            identity = entry.get("identity", "") or ""
            identity_short = identity[:25] + "..." if len(identity) > 28 else identity
            change_prefix = "+" if entry["change_m"] > 0 else ""
            print(
                f"{entry['address']:<44} "
                f"{entry.get('old_borrowed_m', 0):>10.2f} "
                f"{entry['new_borrowed_m']:>10.2f} "
                f"{change_prefix}{entry['change_m']:>11.2f} "
                f"{change_prefix}{entry['change_pct']:>9.1f}% "
                f"{identity_short}"
            )
        if len(real_updates) > 20:
            print(f"  ... and {len(real_updates) - 20} more")
    else:
        print("\n--- No amount changes ---")

    # --- First-time recordings ---
    first_records = [u for u in diff.updated_amounts if u.get("_first_record")]
    if first_records:
        print(f"\n--- FIRST-TIME AMOUNT RECORDINGS ({len(first_records)}) ---")
        print("  (These addresses exist in KG but had no previous borrowed amount tracked)")
        for entry in first_records[:10]:
            identity = entry.get("identity", "") or "Unknown"
            print(
                f"  {entry['address'][:20]}...  "
                f"${entry['new_borrowed_m']:.2f}M  "
                f"({identity})"
            )
        if len(first_records) > 10:
            print(f"  ... and {len(first_records) - 10} more")

    # --- Dropped ---
    if diff.dropped_addresses:
        print(f"\n--- DROPPED FROM SOURCE ({len(diff.dropped_addresses)}) ---")
        print("  (Previously tracked addresses no longer in Dune results)")
        for entry in diff.dropped_addresses[:10]:
            identity = entry.get("identity", "") or "Unknown"
            print(
                f"  {entry['address'][:20]}...  "
                f"was ${entry.get('previous_borrowed_m', 0):.2f}M  "
                f"({identity})"
            )
        if len(diff.dropped_addresses) > 10:
            print(f"  ... and {len(diff.dropped_addresses) - 10} more")

    # --- Status ---
    print("\n" + "=" * 60)
    if apply:
        print("MODE: APPLY (changes will be written to knowledge graph)")
    else:
        print("MODE: DRY RUN (no changes applied)")
        print("  Re-run with --apply to write changes")
    if investigate:
        above_threshold = [
            e for e in diff.new_addresses if e["total_borrowed_m"] >= threshold_m
        ]
        print(
            f"  Investigation queued for {len(above_threshold)} new address(es) "
            f"above ${threshold_m:.0f}M threshold"
        )
    print("=" * 60)


def save_report_csv(diff: DiffResult, output_path: Path):
    """Save the diff report as a CSV for archival."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "change_type", "address", "total_borrowed_m", "old_borrowed_m",
            "change_m", "change_pct", "address_type", "projects", "identity",
        ])

        for entry in diff.new_addresses:
            writer.writerow([
                "NEW",
                entry["address"],
                f"{entry['total_borrowed_m']:.2f}",
                "",
                "",
                "",
                entry.get("address_type", ""),
                "; ".join(entry.get("projects", [])),
                entry.get("identity", ""),
            ])

        for entry in diff.updated_amounts:
            if entry.get("_first_record"):
                change_type = "FIRST_RECORD"
            else:
                change_type = "INCREASED" if entry.get("change_m", 0) > 0 else "DECREASED"
            writer.writerow([
                change_type,
                entry["address"],
                f"{entry['new_borrowed_m']:.2f}",
                f"{entry.get('old_borrowed_m', '')}" if entry.get("old_borrowed_m") is not None else "",
                f"{entry.get('change_m', 0):.2f}" if not entry.get("_first_record") else "",
                f"{entry.get('change_pct', 0):.1f}" if not entry.get("_first_record") else "",
                "",
                "",
                entry.get("identity", ""),
            ])

        for entry in diff.dropped_addresses:
            writer.writerow([
                "DROPPED",
                entry["address"],
                "",
                f"{entry.get('previous_borrowed_m', 0):.2f}",
                "",
                "",
                entry.get("entity_type", ""),
                "",
                entry.get("identity", ""),
            ])

    log.info("Report saved to %s", output_path)


# ============================================================================
# Last Update Info
# ============================================================================

def get_last_update(db_path: Path) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent update metadata record."""
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            """SELECT * FROM update_metadata
               WHERE dry_run = 0
               ORDER BY timestamp DESC LIMIT 1"""
        ).fetchone()
        result = dict(row) if row else None
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        result = None
    finally:
        conn.close()

    return result


def print_last_update(db_path: Path):
    """Print info about the last update."""
    last = get_last_update(db_path)
    if last:
        print(f"\nLast update: {last['timestamp']}")
        print(f"  Type: {last['update_type']}")
        print(f"  New: {last['new_addresses']}, Updated: {last['updated_addresses']}, "
              f"Dropped: {last['dropped_addresses']}")
        print(f"  Source rows: {last['total_in_source']}, KG entities: {last['total_in_kg']}")
        if last.get("investigation_queued"):
            print(f"  Investigations queued: {last['investigation_queued']}")
    else:
        print("\nNo previous updates recorded.")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Incremental Update Pipeline - Sync Dune results to Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run - show diff without applying
  python3 scripts/incremental_update.py

  # Apply changes to knowledge graph
  python3 scripts/incremental_update.py --apply

  # Apply + queue new high-value addresses for investigation
  python3 scripts/incremental_update.py --apply --investigate

  # Custom threshold for investigation (default: $10M)
  python3 scripts/incremental_update.py --threshold 50

  # Use local CSV instead of Dune API
  python3 scripts/incremental_update.py --from-csv data/borrowers.csv --apply

  # Force fresh Dune execution (uses API credits!)
  python3 scripts/incremental_update.py --execute --apply

  # Show last update info only
  python3 scripts/incremental_update.py --status
        """,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the knowledge graph (default: dry run)",
    )
    parser.add_argument(
        "--investigate",
        action="store_true",
        help="Queue new addresses above threshold for investigation",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_M,
        help=f"Minimum borrowed amount ($M) for flagging/investigation (default: {DEFAULT_THRESHOLD_M})",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Force fresh Dune query execution (uses API credits!)",
    )
    parser.add_argument(
        "--from-csv",
        type=str,
        metavar="CSV_PATH",
        help="Load data from local CSV instead of Dune API",
    )
    parser.add_argument(
        "--query-id",
        type=int,
        default=DUNE_QUERY_ID,
        help=f"Dune query ID to fetch (default: {DUNE_QUERY_ID})",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DB_PATH),
        help=f"Path to knowledge graph database (default: {DB_PATH})",
    )
    parser.add_argument(
        "--save-report",
        type=str,
        metavar="CSV_PATH",
        help="Save diff report to CSV file",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show last update info and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    db_path = Path(args.db)

    # --- Status only ---
    if args.status:
        print_last_update(db_path)
        return 0

    # --- Show last update context ---
    print_last_update(db_path)

    # --- Fetch data ---
    if args.from_csv:
        raw_rows = load_csv_results(args.from_csv)
    else:
        raw_rows = fetch_dune_results(args.query_id, execute=args.execute)

    if not raw_rows:
        log.error("No data to process. Exiting.")
        return 1

    # --- Normalize ---
    source_data = normalize_dune_rows(raw_rows)
    log.info(
        "Normalized to %d unique addresses (from %d raw rows)",
        len(source_data),
        len(raw_rows),
    )

    # --- Compute diff ---
    diff = compute_diff(source_data, db_path, threshold_m=args.threshold)

    # --- Print report ---
    print_report(diff, args.threshold, args.apply, args.investigate)

    # --- Save report CSV if requested ---
    if args.save_report:
        save_report_csv(diff, Path(args.save_report))
    else:
        # Auto-save timestamped report
        UPDATE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_path = UPDATE_LOG_DIR / f"diff_{ts}.csv"
        save_report_csv(diff, auto_path)

    # --- Apply if requested ---
    if args.apply:
        if not diff.has_changes:
            log.info("No changes to apply.")
            return 0

        log.info("Applying changes to knowledge graph at %s ...", db_path)
        actions = apply_changes(
            diff,
            source_data,
            db_path,
            investigate=args.investigate,
            threshold_m=args.threshold,
        )

        print(f"\nApplied: {actions['added']} added, {actions['updated']} updated")
        if actions["investigated_queued"] > 0:
            print(
                f"Queued {actions['investigated_queued']} address(es) for investigation. "
                f"Run the pipeline to process them:"
            )
            print(f"  python3 scripts/build_knowledge_graph.py run")
    else:
        if diff.has_changes:
            print(
                f"\nDry run complete. Re-run with --apply to write "
                f"{len(diff.new_addresses)} new + {len(diff.updated_amounts)} updated."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
