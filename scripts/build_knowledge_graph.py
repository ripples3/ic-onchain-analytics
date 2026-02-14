#!/usr/bin/env python3
"""
Whale Intelligence System - Knowledge Graph Builder

A forensic investigation system that compounds findings using:
1. Cluster Expansion - Every identified wallet reveals related wallets
2. Knowledge Graph - Persistent SQLite database for all findings
3. Multi-Layer Analysis - On-chain + behavioral + social
4. Pattern Recognition - Entity templates for matching unknowns
5. Evidence Chains - Traceable sources for every identification

Based on ZachXBT and Chainalysis methodologies.

Usage:
    # Initialize database and import seed addresses
    python3 build_knowledge_graph.py init --seeds addresses.csv

    # Run full investigation pipeline
    python3 build_knowledge_graph.py run

    # Run specific layer only
    python3 build_knowledge_graph.py run --layer onchain
    python3 build_knowledge_graph.py run --layer behavioral
    python3 build_knowledge_graph.py run --layer osint

    # Query the knowledge graph
    python3 build_knowledge_graph.py query --address 0x1234...
    python3 build_knowledge_graph.py query --cluster 5
    python3 build_knowledge_graph.py query --entity "Trend Research"

    # Export results
    python3 build_knowledge_graph.py export --format csv -o results.csv

    # Show statistics
    python3 build_knowledge_graph.py stats
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database location
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "knowledge_graph.db"


# ============================================================================
# SQLite Schema
# ============================================================================

SCHEMA = """
-- Core entity table: addresses we're tracking
CREATE TABLE IF NOT EXISTS entities (
    address TEXT PRIMARY KEY,
    identity TEXT,                          -- Identified name (e.g., "Justin Sun", "Trend Research")
    entity_type TEXT DEFAULT 'unknown',     -- individual, fund, protocol, exchange, bot, unknown
    confidence REAL DEFAULT 0.0,            -- 0.0 to 1.0
    cluster_id INTEGER,                     -- FK to clusters table
    contract_type TEXT,                     -- EOA, Safe, DSProxy, etc.
    ens_name TEXT,
    first_seen TEXT,                        -- ISO timestamp
    last_updated TEXT,                      -- ISO timestamp
    notes TEXT
);

-- Clusters of related addresses
CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,                              -- Optional cluster name (e.g., "Trend Research Cluster")
    entity_type TEXT,                       -- Type of entity the cluster represents
    confidence REAL DEFAULT 0.0,
    detection_methods TEXT,                 -- JSON array of methods that detected this cluster
    created_at TEXT,
    updated_at TEXT
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                   -- Address
    target TEXT NOT NULL,                   -- Address
    relationship_type TEXT NOT NULL,        -- funded_by, same_entity, same_cluster, traded_with, delegated_to
    confidence REAL DEFAULT 0.5,
    evidence TEXT,                          -- JSON: {method: 'CIO', data: {...}}
    created_at TEXT,
    FOREIGN KEY (source) REFERENCES entities(address),
    FOREIGN KEY (target) REFERENCES entities(address),
    UNIQUE(source, target, relationship_type)
);

-- Evidence for identifications
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_address TEXT NOT NULL,
    source TEXT NOT NULL,                   -- ENS, Snapshot, Arkham, Etherscan, Lookonchain, etc.
    claim TEXT NOT NULL,                    -- What the source says
    confidence REAL DEFAULT 0.5,
    url TEXT,                               -- Source URL if available
    raw_data TEXT,                          -- JSON
    created_at TEXT,
    FOREIGN KEY (entity_address) REFERENCES entities(address)
);

-- Behavioral fingerprints
CREATE TABLE IF NOT EXISTS behavioral_fingerprints (
    address TEXT PRIMARY KEY,
    timezone_signal TEXT,                   -- Inferred timezone from activity patterns
    gas_strategy TEXT,                      -- low, medium, high, adaptive
    trading_style TEXT,                     -- spot, leverage, arbitrage, mev
    protocol_preferences TEXT,              -- JSON array of preferred protocols
    activity_pattern TEXT,                  -- JSON: hourly/daily activity distribution
    risk_profile TEXT,                      -- conservative, moderate, aggressive
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (address) REFERENCES entities(address)
);

-- Entity templates for pattern matching
CREATE TABLE IF NOT EXISTS entity_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                     -- Template name (e.g., "VC Fund Pattern")
    description TEXT,
    patterns TEXT NOT NULL,                 -- JSON: {funding_pattern: ..., behavior: ..., etc.}
    examples TEXT,                          -- JSON array of known matching addresses
    confidence REAL DEFAULT 0.7,
    created_at TEXT
);

-- Processing queue for incremental updates
CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    layer TEXT NOT NULL,                    -- onchain, behavioral, osint
    status TEXT DEFAULT 'pending',          -- pending, processing, completed, failed
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_attempt TEXT,
    error TEXT,
    created_at TEXT,
    UNIQUE(address, layer)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entities_cluster ON entities(cluster_id);
CREATE INDEX IF NOT EXISTS idx_entities_identity ON entities(identity);
CREATE INDEX IF NOT EXISTS idx_entities_confidence ON entities(confidence);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target);
CREATE INDEX IF NOT EXISTS idx_evidence_entity ON evidence(entity_address);
CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status, priority);
"""


# ============================================================================
# Database Operations
# ============================================================================

class KnowledgeGraph:
    """SQLite-based knowledge graph for whale intelligence."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def initialize(self):
        """Initialize database schema."""
        conn = self.connect()
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"Database initialized at {self.db_path}")

    def reset(self):
        """Reset database (drop all tables)."""
        if self.db_path.exists():
            self.close()
            self.db_path.unlink()
        self.initialize()
        print("Database reset complete")

    # ---- Entity Operations ----

    def add_entity(self, address: str, **kwargs) -> bool:
        """Add or update an entity."""
        conn = self.connect()
        address = address.lower()

        # Check if exists
        existing = conn.execute(
            "SELECT * FROM entities WHERE address = ?", (address,)
        ).fetchone()

        now = datetime.now(timezone.utc).isoformat()

        if existing:
            # Update existing
            updates = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    updates.append(f"{key} = ?")
                    values.append(value)
            if updates:
                updates.append("last_updated = ?")
                values.append(now)
                values.append(address)
                conn.execute(
                    f"UPDATE entities SET {', '.join(updates)} WHERE address = ?",
                    values
                )
                conn.commit()
            return False  # Not new
        else:
            # Insert new
            kwargs['address'] = address
            kwargs['first_seen'] = now
            kwargs['last_updated'] = now

            columns = ', '.join(kwargs.keys())
            placeholders = ', '.join(['?' for _ in kwargs])
            conn.execute(
                f"INSERT INTO entities ({columns}) VALUES ({placeholders})",
                list(kwargs.values())
            )
            conn.commit()
            return True  # New entity

    def get_entity(self, address: str) -> Optional[dict]:
        """Get entity by address."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM entities WHERE address = ?", (address.lower(),)
        ).fetchone()
        return dict(row) if row else None

    def get_entities(self, filters: dict = None, limit: int = 1000) -> List[dict]:
        """Get entities with optional filters."""
        conn = self.connect()

        query = "SELECT * FROM entities"
        conditions = []
        values = []

        if filters:
            if 'cluster_id' in filters:
                conditions.append("cluster_id = ?")
                values.append(filters['cluster_id'])
            if 'entity_type' in filters:
                conditions.append("entity_type = ?")
                values.append(filters['entity_type'])
            if 'min_confidence' in filters:
                conditions.append("confidence >= ?")
                values.append(filters['min_confidence'])
            if 'identified' in filters:
                if filters['identified']:
                    conditions.append("identity IS NOT NULL AND identity != ''")
                else:
                    conditions.append("(identity IS NULL OR identity = '')")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY confidence DESC LIMIT {limit}"

        rows = conn.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def get_unidentified(self, limit: int = 100) -> List[dict]:
        """Get unidentified entities."""
        return self.get_entities({'identified': False}, limit)

    def set_identity(self, address: str, identity: str, confidence: float,
                     entity_type: str = None, notes: str = None):
        """Set identity for an entity."""
        self.add_entity(
            address,
            identity=identity,
            confidence=confidence,
            entity_type=entity_type or 'unknown',
            notes=notes
        )

    # ---- Cluster Operations ----

    def create_cluster(self, addresses: List[str], name: str = None,
                       methods: List[str] = None, confidence: float = 0.5) -> int:
        """Create a new cluster and assign addresses to it."""
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()

        cursor = conn.execute(
            """INSERT INTO clusters (name, detection_methods, confidence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (name, json.dumps(methods or []), confidence, now, now)
        )
        cluster_id = cursor.lastrowid

        # Assign addresses to cluster
        for addr in addresses:
            self.add_entity(addr, cluster_id=cluster_id)

        # Create same_entity relationships within cluster
        for i, addr1 in enumerate(addresses):
            for addr2 in addresses[i+1:]:
                self.add_relationship(
                    addr1, addr2, 'same_cluster',
                    confidence=confidence,
                    evidence={'method': 'clustering', 'methods': methods}
                )

        conn.commit()
        return cluster_id

    def get_cluster(self, cluster_id: int) -> dict:
        """Get cluster info with member addresses."""
        conn = self.connect()

        cluster = conn.execute(
            "SELECT * FROM clusters WHERE id = ?", (cluster_id,)
        ).fetchone()

        if not cluster:
            return None

        members = conn.execute(
            "SELECT * FROM entities WHERE cluster_id = ?", (cluster_id,)
        ).fetchall()

        return {
            'cluster': dict(cluster),
            'members': [dict(m) for m in members]
        }

    def merge_clusters(self, cluster_ids: List[int], new_name: str = None) -> int:
        """Merge multiple clusters into one."""
        if len(cluster_ids) < 2:
            return cluster_ids[0] if cluster_ids else None

        conn = self.connect()

        # Get all addresses from clusters
        addresses = []
        for cid in cluster_ids:
            members = conn.execute(
                "SELECT address FROM entities WHERE cluster_id = ?", (cid,)
            ).fetchall()
            addresses.extend([m[0] for m in members])

        # Delete old same_cluster relationships for these addresses
        # to prevent orphaned relationships and duplicates
        placeholders = ','.join(['?'] * len(addresses))
        conn.execute(
            f"""DELETE FROM relationships
                WHERE relationship_type = 'same_cluster'
                AND (source IN ({placeholders}) OR target IN ({placeholders}))""",
            addresses + addresses
        )

        # Delete old clusters
        for cid in cluster_ids:
            conn.execute("DELETE FROM clusters WHERE id = ?", (cid,))

        conn.commit()

        # Create new cluster (this will add new same_cluster relationships)
        new_cluster_id = self.create_cluster(addresses, name=new_name)

        return new_cluster_id

    # ---- Relationship Operations ----

    def add_relationship(self, source: str, target: str, rel_type: str,
                        confidence: float = 0.5, evidence: dict = None) -> bool:
        """Add a relationship between two entities."""
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()

        # Ensure both entities exist
        self.add_entity(source)
        self.add_entity(target)

        try:
            # Check if relationship exists with higher confidence
            existing = conn.execute(
                """SELECT confidence FROM relationships
                   WHERE source = ? AND target = ? AND relationship_type = ?""",
                (source.lower(), target.lower(), rel_type)
            ).fetchone()

            if existing and existing[0] >= confidence:
                # Keep existing higher confidence relationship
                return False

            conn.execute(
                """INSERT OR REPLACE INTO relationships
                   (source, target, relationship_type, confidence, evidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source.lower(), target.lower(), rel_type,
                 confidence, json.dumps(evidence or {}), now)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_relationships(self, address: str, direction: str = 'both') -> List[dict]:
        """Get relationships for an address."""
        conn = self.connect()
        address = address.lower()

        if direction == 'outgoing':
            query = "SELECT * FROM relationships WHERE source = ?"
            rows = conn.execute(query, (address,)).fetchall()
        elif direction == 'incoming':
            query = "SELECT * FROM relationships WHERE target = ?"
            rows = conn.execute(query, (address,)).fetchall()
        else:
            query = "SELECT * FROM relationships WHERE source = ? OR target = ?"
            rows = conn.execute(query, (address, address)).fetchall()

        return [dict(row) for row in rows]

    def get_related_addresses(self, address: str, rel_type: str = None) -> List[str]:
        """Get addresses related to the given address."""
        conn = self.connect()
        address = address.lower()

        if rel_type:
            query = """
                SELECT DISTINCT
                    CASE WHEN source = ? THEN target ELSE source END as related
                FROM relationships
                WHERE (source = ? OR target = ?) AND relationship_type = ?
            """
            rows = conn.execute(query, (address, address, address, rel_type)).fetchall()
        else:
            query = """
                SELECT DISTINCT
                    CASE WHEN source = ? THEN target ELSE source END as related
                FROM relationships
                WHERE source = ? OR target = ?
            """
            rows = conn.execute(query, (address, address, address)).fetchall()

        return [row[0] for row in rows]

    # ---- Evidence Operations ----

    def add_evidence(self, address: str, source: str, claim: str,
                    confidence: float = 0.5, url: str = None, raw_data: dict = None):
        """Add evidence for an entity."""
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()

        self.add_entity(address)

        conn.execute(
            """INSERT INTO evidence
               (entity_address, source, claim, confidence, url, raw_data, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (address.lower(), source, claim, confidence, url,
             json.dumps(raw_data or {}), now)
        )
        conn.commit()

    def get_evidence(self, address: str) -> List[dict]:
        """Get all evidence for an entity."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM evidence WHERE entity_address = ? ORDER BY confidence DESC",
            (address.lower(),)
        ).fetchall()
        return [dict(row) for row in rows]

    # ---- Behavioral Fingerprint Operations ----

    def set_fingerprint(self, address: str, **kwargs):
        """Set or update behavioral fingerprint."""
        conn = self.connect()
        address = address.lower()
        now = datetime.now(timezone.utc).isoformat()

        existing = conn.execute(
            "SELECT * FROM behavioral_fingerprints WHERE address = ?", (address,)
        ).fetchone()

        if existing:
            updates = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    updates.append(f"{key} = ?")
                    values.append(value)
            if updates:
                updates.append("updated_at = ?")
                values.append(now)
                values.append(address)
                conn.execute(
                    f"UPDATE behavioral_fingerprints SET {', '.join(updates)} WHERE address = ?",
                    values
                )
        else:
            kwargs['address'] = address
            kwargs['created_at'] = now
            kwargs['updated_at'] = now

            # Serialize JSON fields
            for key in ['protocol_preferences', 'activity_pattern']:
                if key in kwargs and isinstance(kwargs[key], (dict, list)):
                    kwargs[key] = json.dumps(kwargs[key])

            columns = ', '.join(kwargs.keys())
            placeholders = ', '.join(['?' for _ in kwargs])
            conn.execute(
                f"INSERT INTO behavioral_fingerprints ({columns}) VALUES ({placeholders})",
                list(kwargs.values())
            )

        conn.commit()

    def get_fingerprint(self, address: str) -> Optional[dict]:
        """Get behavioral fingerprint."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM behavioral_fingerprints WHERE address = ?",
            (address.lower(),)
        ).fetchone()
        if row:
            result = dict(row)
            for key in ['protocol_preferences', 'activity_pattern']:
                if result.get(key):
                    try:
                        result[key] = json.loads(result[key])
                    except:
                        pass
            return result
        return None

    # ---- Queue Operations ----

    def queue_address(self, address: str, layer: str, priority: int = 0):
        """Add address to processing queue."""
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()

        try:
            conn.execute(
                """INSERT OR IGNORE INTO processing_queue
                   (address, layer, priority, created_at)
                   VALUES (?, ?, ?, ?)""",
                (address.lower(), layer, priority, now)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_queued(self, layer: str = None, limit: int = 100) -> List[dict]:
        """Get pending items from queue."""
        conn = self.connect()

        if layer:
            rows = conn.execute(
                """SELECT * FROM processing_queue
                   WHERE status = 'pending' AND layer = ?
                   ORDER BY priority DESC, created_at ASC
                   LIMIT ?""",
                (layer, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM processing_queue
                   WHERE status = 'pending'
                   ORDER BY priority DESC, created_at ASC
                   LIMIT ?""",
                (limit,)
            ).fetchall()

        return [dict(row) for row in rows]

    def update_queue_status(self, address: str, layer: str, status: str, error: str = None):
        """Update queue item status."""
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """UPDATE processing_queue
               SET status = ?, last_attempt = ?, error = ?, attempts = attempts + 1
               WHERE address = ? AND layer = ?""",
            (status, now, error, address.lower(), layer)
        )
        conn.commit()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = self.connect()

        stats = {}

        # Entity counts
        stats['total_entities'] = conn.execute(
            "SELECT COUNT(*) FROM entities"
        ).fetchone()[0]

        stats['identified'] = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE identity IS NOT NULL AND identity != ''"
        ).fetchone()[0]

        stats['high_confidence'] = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE confidence >= 0.7"
        ).fetchone()[0]

        # By entity type
        type_counts = conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        ).fetchall()
        stats['by_type'] = {row[0] or 'unknown': row[1] for row in type_counts}

        # Cluster counts
        stats['total_clusters'] = conn.execute(
            "SELECT COUNT(*) FROM clusters"
        ).fetchone()[0]

        stats['clustered_entities'] = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE cluster_id IS NOT NULL"
        ).fetchone()[0]

        # Relationship counts
        stats['total_relationships'] = conn.execute(
            "SELECT COUNT(*) FROM relationships"
        ).fetchone()[0]

        rel_counts = conn.execute(
            "SELECT relationship_type, COUNT(*) FROM relationships GROUP BY relationship_type"
        ).fetchall()
        stats['by_relationship'] = {row[0]: row[1] for row in rel_counts}

        # Evidence counts
        stats['total_evidence'] = conn.execute(
            "SELECT COUNT(*) FROM evidence"
        ).fetchone()[0]

        source_counts = conn.execute(
            "SELECT source, COUNT(*) FROM evidence GROUP BY source"
        ).fetchall()
        stats['by_evidence_source'] = {row[0]: row[1] for row in source_counts}

        # Queue status
        queue_status = conn.execute(
            "SELECT layer, status, COUNT(*) FROM processing_queue GROUP BY layer, status"
        ).fetchall()
        stats['queue'] = {}
        for row in queue_status:
            layer, status, count = row
            if layer not in stats['queue']:
                stats['queue'][layer] = {}
            stats['queue'][layer][status] = count

        return stats


# ============================================================================
# Import Functions
# ============================================================================

def import_seeds(kg: KnowledgeGraph, csv_path: str, priority: int = 0):
    """Import seed addresses from CSV."""
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Importing {len(rows)} addresses from {csv_path}")

    new_count = 0
    for row in rows:
        # Support multiple column name formats
        address = (row.get('address') or row.get('Address') or
                   row.get('wallet') or row.get('Wallet') or
                   row.get('borrower') or row.get('Borrower'))

        if not address:
            continue

        # Extract metadata
        metadata = {}

        # Check for existing identity
        identity = row.get('identity') or row.get('Identity') or row.get('name') or row.get('Name')
        if identity and identity.lower() not in ('unknown', 'unidentified', ''):
            metadata['identity'] = identity

        # Check for contract type
        contract_type = row.get('contract_type') or row.get('type') or row.get('Type')
        if contract_type:
            metadata['contract_type'] = contract_type

        # Check for ENS
        ens = row.get('ens_name') or row.get('ens') or row.get('ENS')
        if ens:
            metadata['ens_name'] = ens

        # Add entity
        is_new = kg.add_entity(address, **metadata)
        if is_new:
            new_count += 1

            # Queue for all processing layers
            for layer in ['onchain', 'behavioral', 'osint']:
                kg.queue_address(address, layer, priority)

    print(f"  Added {new_count} new entities")
    print(f"  Queued for processing across 3 layers")


# ============================================================================
# Pipeline Runner
# ============================================================================

def run_layer(kg: KnowledgeGraph, layer: str, batch_size: int = 50):
    """Run a specific processing layer."""
    print(f"\n{'='*60}")
    print(f"Running {layer.upper()} layer")
    print(f"{'='*60}")

    # Get queued items
    queued = kg.get_queued(layer, limit=batch_size)
    print(f"Processing {len(queued)} addresses")

    if not queued:
        print("No addresses queued for this layer")
        return

    # Import the appropriate processor
    script_dir = Path(__file__).parent

    # Process each address individually with error handling
    addresses = [q['address'] for q in queued]

    if layer == 'onchain':
        from cluster_expander import process_single_address as process_onchain
        processor = process_onchain
    elif layer == 'behavioral':
        from behavioral_fingerprint import process_single_address as process_behavioral
        processor = process_behavioral
    elif layer == 'osint':
        from osint_aggregator import process_single_address as process_osint
        processor = process_osint
    elif layer == 'temporal':
        # Temporal correlation is batch-only, not per-address
        # Run on all addresses at once for efficiency
        from temporal_correlation import process_addresses as process_temporal
        process_temporal(kg, addresses)
        for addr in addresses:
            kg.update_queue_status(addr, layer, 'completed')
        return
    else:
        print(f"Unknown layer: {layer}")
        return

    success_count = 0
    error_count = 0

    for addr in addresses:
        try:
            processor(kg, addr)
            kg.update_queue_status(addr, layer, 'completed')
            success_count += 1
        except Exception as e:
            print(f"  Error processing {addr}: {e}")
            kg.update_queue_status(addr, layer, 'error')
            error_count += 1

    print(f"  Completed: {success_count}, Errors: {error_count}")


def run_pattern_matching(kg: KnowledgeGraph):
    """Run pattern matching on unidentified entities."""
    print(f"\n{'='*60}")
    print("Running PATTERN MATCHING")
    print(f"{'='*60}")

    from pattern_matcher import match_patterns
    match_patterns(kg)


def run_temporal_correlation(kg: KnowledgeGraph, batch_size: int = 100):
    """Run temporal correlation analysis on all entities."""
    print(f"\n{'='*60}")
    print("Running TEMPORAL CORRELATION layer")
    print(f"{'='*60}")

    # Get all entities for temporal analysis
    conn = kg.connect()
    entities = conn.execute(
        "SELECT address FROM entities ORDER BY confidence DESC LIMIT ?",
        (batch_size,)
    ).fetchall()

    addresses = [e[0] for e in entities]

    if len(addresses) < 2:
        print("Need at least 2 addresses for temporal correlation")
        return

    from temporal_correlation import process_addresses as process_temporal
    process_temporal(kg, addresses)


def run_counterparty_graph(kg: KnowledgeGraph, batch_size: int = 50):
    """Run counterparty graph analysis on all entities."""
    print(f"\n{'='*60}")
    print("Running COUNTERPARTY GRAPH layer")
    print(f"{'='*60}")

    # Get entities for counterparty analysis
    conn = kg.connect()
    entities = conn.execute(
        "SELECT address FROM entities ORDER BY confidence DESC LIMIT ?",
        (batch_size,)
    ).fetchall()

    addresses = [e[0] for e in entities]

    if len(addresses) < 2:
        print("Need at least 2 addresses for counterparty analysis")
        return

    from counterparty_graph import process_addresses as process_counterparty
    process_counterparty(kg, addresses, min_overlap=0.25)


def run_label_propagation(kg: KnowledgeGraph):
    """Run label propagation to spread identities through the graph."""
    print(f"\n{'='*60}")
    print("Running LABEL PROPAGATION")
    print(f"{'='*60}")

    from label_propagation import run_full_propagation
    run_full_propagation(kg, max_hops=4, min_confidence=0.3, verbose=True)


def run_full_pipeline(kg: KnowledgeGraph, batch_size: int = 50):
    """Run the complete investigation pipeline."""
    print("\n" + "="*60)
    print("WHALE INTELLIGENCE SYSTEM - FULL PIPELINE")
    print("="*60)

    # Run each layer in order
    for layer in ['onchain', 'behavioral', 'osint']:
        run_layer(kg, layer, batch_size)

    # Run advanced correlation layers (batch analysis across all addresses)
    run_temporal_correlation(kg, batch_size=min(batch_size * 2, 100))
    run_counterparty_graph(kg, batch_size=min(batch_size, 50))

    # Run pattern matching
    run_pattern_matching(kg)

    # Run label propagation to spread identities through the graph
    run_label_propagation(kg)

    # Print final stats
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    print_stats(kg)


# ============================================================================
# Query Functions
# ============================================================================

def query_address(kg: KnowledgeGraph, address: str):
    """Query all information about an address."""
    entity = kg.get_entity(address)
    if not entity:
        print(f"Address not found: {address}")
        return

    print(f"\n{'='*60}")
    print(f"ENTITY: {address}")
    print(f"{'='*60}")

    print(f"\nIdentity: {entity.get('identity') or 'Unknown'}")
    print(f"Confidence: {entity.get('confidence', 0):.0%}")
    print(f"Type: {entity.get('entity_type') or 'unknown'}")
    print(f"Contract: {entity.get('contract_type') or 'Unknown'}")
    print(f"ENS: {entity.get('ens_name') or 'None'}")

    if entity.get('cluster_id'):
        cluster = kg.get_cluster(entity['cluster_id'])
        print(f"\nCluster: {cluster['cluster'].get('name') or f'Cluster #{entity['cluster_id']}'}")
        print(f"  Members: {len(cluster['members'])}")
        print(f"  Methods: {cluster['cluster'].get('detection_methods')}")

    # Relationships
    rels = kg.get_relationships(address)
    if rels:
        print(f"\nRelationships: {len(rels)}")
        for rel in rels[:5]:
            other = rel['target'] if rel['source'] == address.lower() else rel['source']
            print(f"  {rel['relationship_type']} → {other[:20]}...")

    # Evidence
    evidence = kg.get_evidence(address)
    if evidence:
        print(f"\nEvidence: {len(evidence)} items")
        for ev in evidence[:5]:
            print(f"  [{ev['source']}] {ev['claim'][:50]}... ({ev['confidence']:.0%})")

    # Fingerprint
    fp = kg.get_fingerprint(address)
    if fp:
        print(f"\nBehavioral Fingerprint:")
        if fp.get('timezone_signal'):
            print(f"  Timezone: {fp['timezone_signal']}")
        if fp.get('trading_style'):
            print(f"  Trading Style: {fp['trading_style']}")
        if fp.get('risk_profile'):
            print(f"  Risk Profile: {fp['risk_profile']}")


def query_cluster(kg: KnowledgeGraph, cluster_id: int):
    """Query cluster information."""
    cluster = kg.get_cluster(cluster_id)
    if not cluster:
        print(f"Cluster not found: {cluster_id}")
        return

    print(f"\n{'='*60}")
    print(f"CLUSTER #{cluster_id}: {cluster['cluster'].get('name') or 'Unnamed'}")
    print(f"{'='*60}")

    print(f"\nConfidence: {cluster['cluster'].get('confidence', 0):.0%}")
    print(f"Methods: {cluster['cluster'].get('detection_methods')}")
    print(f"\nMembers ({len(cluster['members'])}):")

    for member in cluster['members']:
        identity = member.get('identity') or 'Unknown'
        print(f"  {member['address'][:20]}... - {identity} ({member.get('confidence', 0):.0%})")


def query_entity(kg: KnowledgeGraph, entity_name: str):
    """Search for entities by name."""
    conn = kg.connect()
    rows = conn.execute(
        "SELECT * FROM entities WHERE identity LIKE ? ORDER BY confidence DESC LIMIT 20",
        (f"%{entity_name}%",)
    ).fetchall()

    if not rows:
        print(f"No entities found matching: {entity_name}")
        return

    print(f"\n{'='*60}")
    print(f"SEARCH RESULTS: '{entity_name}'")
    print(f"{'='*60}")

    for row in rows:
        entity = dict(row)
        print(f"\n{entity['address']}")
        print(f"  Identity: {entity.get('identity')}")
        print(f"  Confidence: {entity.get('confidence', 0):.0%}")
        print(f"  Type: {entity.get('entity_type')}")


# ============================================================================
# Export Functions
# ============================================================================

def export_results(kg: KnowledgeGraph, output_path: str, format: str = 'csv',
                   min_confidence: float = 0.0):
    """Export identified entities."""
    entities = kg.get_entities({'min_confidence': min_confidence})

    # Pre-fetch all evidence counts in one query to avoid N+1
    conn = kg.connect()
    evidence_counts = {}
    for row in conn.execute(
        "SELECT entity_address, COUNT(*) FROM evidence GROUP BY entity_address"
    ).fetchall():
        evidence_counts[row[0]] = row[1]

    if format == 'csv':
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'address', 'identity', 'confidence', 'entity_type',
                'contract_type', 'ens_name', 'cluster_id', 'evidence_count'
            ])

            for e in entities:
                writer.writerow([
                    e['address'],
                    e.get('identity') or '',
                    e.get('confidence', 0),
                    e.get('entity_type') or 'unknown',
                    e.get('contract_type') or '',
                    e.get('ens_name') or '',
                    e.get('cluster_id') or '',
                    evidence_counts.get(e['address'], 0)
                ])

    elif format == 'json':
        # Pre-fetch all evidence and relationships
        all_evidence = {}
        for row in conn.execute("SELECT * FROM evidence").fetchall():
            addr = row['entity_address']
            if addr not in all_evidence:
                all_evidence[addr] = []
            all_evidence[addr].append(dict(row))

        all_relationships = {}
        for row in conn.execute("SELECT * FROM relationships").fetchall():
            for addr in (row['source'], row['target']):
                if addr not in all_relationships:
                    all_relationships[addr] = []
                all_relationships[addr].append(dict(row))

        results = []
        for e in entities:
            e['evidence'] = all_evidence.get(e['address'], [])
            e['relationships'] = all_relationships.get(e['address'], [])
            results.append(e)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

    print(f"Exported {len(entities)} entities to {output_path}")


# ============================================================================
# Print Functions
# ============================================================================

def print_stats(kg: KnowledgeGraph):
    """Print database statistics."""
    stats = kg.get_stats()

    print(f"\n{'='*60}")
    print("KNOWLEDGE GRAPH STATISTICS")
    print(f"{'='*60}")

    total = stats['total_entities']
    identified = stats['identified']
    high_conf = stats['high_confidence']

    print(f"\nEntities:")
    print(f"  Total: {total}")
    print(f"  Identified: {identified} ({100*identified/total:.1f}%)" if total else "  Identified: 0")
    print(f"  High Confidence (>70%): {high_conf}")

    print(f"\nBy Type:")
    for entity_type, count in stats['by_type'].items():
        print(f"  {entity_type}: {count}")

    print(f"\nClusters:")
    print(f"  Total Clusters: {stats['total_clusters']}")
    print(f"  Entities in Clusters: {stats['clustered_entities']}")

    print(f"\nRelationships: {stats['total_relationships']}")
    for rel_type, count in stats.get('by_relationship', {}).items():
        print(f"  {rel_type}: {count}")

    print(f"\nEvidence: {stats['total_evidence']} items")
    for source, count in stats.get('by_evidence_source', {}).items():
        print(f"  {source}: {count}")

    if stats.get('queue'):
        print(f"\nProcessing Queue:")
        for layer, statuses in stats['queue'].items():
            status_str = ", ".join([f"{s}: {c}" for s, c in statuses.items()])
            print(f"  {layer}: {status_str}")


# ============================================================================
# Health Check Functions
# ============================================================================

def check_cross_cluster_correlations(kg: KnowledgeGraph) -> List[dict]:
    """Alert when temporal correlations exist between addresses in different clusters/identities.

    Detects potential cluster contamination by finding high-confidence temporal
    correlations between addresses that belong to different clusters or have
    different identity labels. This is a key signal that label propagation
    may have incorrectly assigned labels.

    Returns a list of alert dicts with keys:
        type, severity, source, target, source_label, target_label, confidence, action
    """
    conn = kg.connect()

    # Build a mapping of address -> cluster/identity label.
    # We use identity first (more specific), falling back to cluster name.
    rows = conn.execute("""
        SELECT e.address, e.identity, e.cluster_id, c.name as cluster_name
        FROM entities e
        LEFT JOIN clusters c ON e.cluster_id = c.id
        WHERE e.identity IS NOT NULL AND e.identity != ''
           OR e.cluster_id IS NOT NULL
    """).fetchall()

    label_map: Dict[str, str] = {}
    for row in rows:
        address = row['address']
        identity = row['identity']
        cluster_name = row['cluster_name']
        # Prefer identity over cluster name
        if identity:
            label_map[address] = identity
        elif cluster_name:
            label_map[address] = cluster_name

    if not label_map:
        return []

    # Get all temporal_correlation relationships with confidence > 0.8
    correlations = conn.execute("""
        SELECT source, target, confidence, evidence
        FROM relationships
        WHERE relationship_type = 'temporal_correlation'
          AND confidence > 0.8
    """).fetchall()

    alerts: List[dict] = []

    for corr in correlations:
        source = corr['source']
        target = corr['target']
        source_label = label_map.get(source)
        target_label = label_map.get(target)

        # Skip if either address has no label
        if not source_label or not target_label:
            continue

        # Normalize labels for comparison: strip " (propagated)" and
        # " (cluster member)" suffixes so we compare base identities
        def normalize_label(label: str) -> str:
            for suffix in [' (propagated)', ' (cluster member)', ' (unverified)']:
                if label.endswith(suffix):
                    label = label[:-len(suffix)]
            return label.strip()

        source_base = normalize_label(source_label)
        target_base = normalize_label(target_label)

        if source_base != target_base:
            confidence = corr['confidence']
            severity = 'HIGH' if confidence > 0.9 else 'MEDIUM'

            alert = {
                'type': 'CROSS_CLUSTER_CORRELATION',
                'severity': severity,
                'source': source,
                'target': target,
                'source_label': source_label,
                'target_label': target_label,
                'confidence': confidence,
                'action': 'Review cluster assignments - likely contamination'
            }
            alerts.append(alert)

            # Print warning immediately
            icon = '!!' if severity == 'HIGH' else '! '
            print(f"  [{icon}] {severity}: {source[:16]}... ({source_label}) "
                  f"<-> {target[:16]}... ({target_label}) "
                  f"[correlation: {confidence:.0%}]")

    return alerts


def cluster_health_check(kg: KnowledgeGraph) -> List[dict]:
    """Run comprehensive cluster health checks.

    Checks performed:
    1. Timezone consistency per cluster (warn if >3 different timezones)
    2. Cross-cluster correlations (via check_cross_cluster_correlations)
    3. Propagation explosion detection (propagated > 10x original labels)

    Returns a list of issue dicts with keys: cluster, issue, detail, severity
    """
    conn = kg.connect()
    issues: List[dict] = []

    # Get all clusters
    clusters = conn.execute("SELECT * FROM clusters").fetchall()

    if not clusters:
        print("No clusters found in knowledge graph.")
        return issues

    print(f"\nChecking {len(clusters)} clusters...\n")

    # ---- Check 1: Timezone consistency per cluster ----
    print("--- Timezone Consistency ---")
    for cluster in clusters:
        cluster_id = cluster['id']
        cluster_name = cluster['name'] or f'Cluster #{cluster_id}'

        # Get all member addresses and their timezone signals
        members_with_tz = conn.execute("""
            SELECT e.address, bf.timezone_signal
            FROM entities e
            LEFT JOIN behavioral_fingerprints bf ON e.address = bf.address
            WHERE e.cluster_id = ?
        """, (cluster_id,)).fetchall()

        # Collect non-null timezones
        timezones = set()
        for m in members_with_tz:
            tz = m['timezone_signal']
            if tz:
                timezones.add(tz)

        member_count = len(members_with_tz)

        if len(timezones) > 3:
            issue = {
                'cluster': cluster_name,
                'issue': 'TIMEZONE_SPREAD',
                'detail': (f"{len(timezones)} different timezones across "
                           f"{member_count} members: {', '.join(sorted(timezones))}"),
                'severity': 'HIGH' if len(timezones) > 5 else 'MEDIUM'
            }
            issues.append(issue)
            print(f"  [!!] {cluster_name}: {issue['detail']}")
        elif timezones:
            print(f"  [OK] {cluster_name}: {len(timezones)} timezone(s) "
                  f"across {member_count} members")
        else:
            print(f"  [--] {cluster_name}: No timezone data ({member_count} members)")

    # ---- Check 2: Cross-cluster correlations ----
    print("\n--- Cross-Cluster Correlations ---")
    cross_alerts = check_cross_cluster_correlations(kg)

    if cross_alerts:
        # Group by cluster pair for summary
        cluster_pairs: Dict[str, int] = {}
        for alert in cross_alerts:
            pair_key = ' <-> '.join(sorted([alert['source_label'], alert['target_label']]))
            cluster_pairs[pair_key] = cluster_pairs.get(pair_key, 0) + 1

        for pair, count in cluster_pairs.items():
            issue = {
                'cluster': pair,
                'issue': 'CROSS_CLUSTER_CORRELATIONS',
                'detail': f"{count} temporal correlation(s) between clusters",
                'severity': 'HIGH' if any(
                    a['severity'] == 'HIGH' for a in cross_alerts
                    if ' <-> '.join(sorted([a['source_label'], a['target_label']])) == pair
                ) else 'MEDIUM'
            }
            issues.append(issue)
    else:
        print("  [OK] No cross-cluster correlations detected")

    # ---- Check 3: Propagation explosion detection ----
    print("\n--- Propagation Explosion ---")

    # Count original labels (from evidence sources like Arkham, Etherscan, etc.)
    # vs propagated labels (identity containing "(propagated)" or "(cluster member)")
    identity_rows = conn.execute("""
        SELECT identity, COUNT(*) as cnt
        FROM entities
        WHERE identity IS NOT NULL AND identity != ''
        GROUP BY identity
    """).fetchall()

    # Group by base identity (strip suffixes)
    base_identity_counts: Dict[str, Dict[str, int]] = {}
    for row in identity_rows:
        identity = row['identity']
        count = row['cnt']

        is_propagated = any(
            identity.endswith(suffix)
            for suffix in [' (propagated)', ' (cluster member)', ' (unverified)']
        )

        # Extract base identity
        base = identity
        for suffix in [' (propagated)', ' (cluster member)', ' (unverified)']:
            if base.endswith(suffix):
                base = base[:-len(suffix)].strip()
                break

        if base not in base_identity_counts:
            base_identity_counts[base] = {'original': 0, 'propagated': 0}

        if is_propagated:
            base_identity_counts[base]['propagated'] += count
        else:
            base_identity_counts[base]['original'] += count

    for base_identity, counts in base_identity_counts.items():
        original = counts['original']
        propagated = counts['propagated']

        if original > 0 and propagated > original * 10:
            issue = {
                'cluster': base_identity,
                'issue': 'PROPAGATION_EXPLOSION',
                'detail': (f"{propagated} propagated labels from "
                           f"{original} original(s) ({propagated / original:.0f}x ratio)"),
                'severity': 'HIGH' if propagated > original * 20 else 'MEDIUM'
            }
            issues.append(issue)
            print(f"  [!!] {base_identity}: {issue['detail']}")
        elif propagated > 0:
            ratio = propagated / original if original > 0 else float('inf')
            print(f"  [OK] {base_identity}: {original} original, "
                  f"{propagated} propagated ({ratio:.1f}x)")
        # Skip identities with no propagated labels (nothing to check)

    # If no propagation data at all
    if not any(c['propagated'] > 0 for c in base_identity_counts.values()):
        print("  [--] No propagated labels found")

    return issues


def print_health_report(issues: List[dict]):
    """Print a summary health report from cluster_health_check results."""
    print(f"\n{'='*60}")
    print("HEALTH CHECK SUMMARY")
    print(f"{'='*60}")

    if not issues:
        print("\n  All checks passed. No issues detected.")
        return

    high = [i for i in issues if i.get('severity') == 'HIGH']
    medium = [i for i in issues if i.get('severity') == 'MEDIUM']

    print(f"\n  Total issues: {len(issues)}")
    print(f"  HIGH severity: {len(high)}")
    print(f"  MEDIUM severity: {len(medium)}")

    if high:
        print(f"\n  HIGH severity issues requiring immediate attention:")
        for i, issue in enumerate(high, 1):
            print(f"    {i}. [{issue['issue']}] {issue['cluster']}: {issue['detail']}")

    if medium:
        print(f"\n  MEDIUM severity issues to review:")
        for i, issue in enumerate(medium, 1):
            print(f"    {i}. [{issue['issue']}] {issue['cluster']}: {issue['detail']}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Whale Intelligence System - Knowledge Graph",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    init_parser.add_argument('--seeds', help='CSV file with seed addresses')
    init_parser.add_argument('--reset', action='store_true', help='Reset database first')

    # run command
    run_parser = subparsers.add_parser('run', help='Run investigation pipeline')
    run_parser.add_argument('--layer', choices=['onchain', 'behavioral', 'osint', 'temporal', 'counterparty', 'propagation'],
                           help='Run specific layer only')
    run_parser.add_argument('--batch-size', type=int, default=50,
                           help='Batch size for processing')

    # query command
    query_parser = subparsers.add_parser('query', help='Query the knowledge graph')
    query_parser.add_argument('--address', help='Query by address')
    query_parser.add_argument('--cluster', type=int, help='Query by cluster ID')
    query_parser.add_argument('--entity', help='Search by entity name')

    # export command
    export_parser = subparsers.add_parser('export', help='Export results')
    export_parser.add_argument('-o', '--output', required=True, help='Output file')
    export_parser.add_argument('--format', choices=['csv', 'json'], default='csv')
    export_parser.add_argument('--min-confidence', type=float, default=0.0,
                              help='Minimum confidence threshold')

    # stats command
    subparsers.add_parser('stats', help='Show database statistics')

    # health command
    health_parser = subparsers.add_parser(
        'health',
        help='Run cluster health checks (timezone, cross-cluster correlations, propagation)'
    )
    health_parser.add_argument(
        '--json', action='store_true',
        help='Output results as JSON'
    )

    # import command (for adding more addresses)
    import_parser = subparsers.add_parser('import', help='Import additional addresses')
    import_parser.add_argument('csv', help='CSV file with addresses')
    import_parser.add_argument('--priority', type=int, default=0, help='Queue priority')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize knowledge graph
    kg = KnowledgeGraph()

    try:
        if args.command == 'init':
            if args.reset:
                kg.reset()
            else:
                kg.initialize()

            if args.seeds:
                import_seeds(kg, args.seeds)

        elif args.command == 'run':
            kg.connect()
            if args.layer:
                if args.layer == 'temporal':
                    # Temporal requires batch analysis, not per-address queue processing
                    run_temporal_correlation(kg, args.batch_size)
                elif args.layer == 'counterparty':
                    # Counterparty requires batch analysis
                    run_counterparty_graph(kg, args.batch_size)
                elif args.layer == 'propagation':
                    # Label propagation spreads identities through graph
                    run_label_propagation(kg)
                else:
                    run_layer(kg, args.layer, args.batch_size)
            else:
                run_full_pipeline(kg, args.batch_size)

        elif args.command == 'query':
            kg.connect()
            if args.address:
                query_address(kg, args.address)
            elif args.cluster:
                query_cluster(kg, args.cluster)
            elif args.entity:
                query_entity(kg, args.entity)
            else:
                print("Specify --address, --cluster, or --entity")

        elif args.command == 'export':
            kg.connect()
            export_results(kg, args.output, args.format, args.min_confidence)

        elif args.command == 'stats':
            kg.connect()
            print_stats(kg)

        elif args.command == 'health':
            kg.connect()
            print(f"\n{'='*60}")
            print("CLUSTER HEALTH CHECK")
            print(f"{'='*60}")
            issues = cluster_health_check(kg)
            if args.json:
                print(json.dumps(issues, indent=2))
            else:
                print_health_report(issues)

        elif args.command == 'import':
            kg.connect()
            import_seeds(kg, args.csv, args.priority)

    finally:
        kg.close()


if __name__ == "__main__":
    main()
