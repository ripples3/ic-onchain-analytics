#!/usr/bin/env python3
"""Update CSV with identities from knowledge graph database."""

import csv
import sqlite3
import sys
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "data" / "knowledge_graph.db"
    csv_path = Path(__file__).parent.parent / "references" / "top_lending_protocol_borrowers_eoa_safe_with_identity.csv"

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    # Load identities from knowledge graph
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.address, e.identity, e.entity_type, e.confidence,
               GROUP_CONCAT(DISTINCT ev.source) as sources
        FROM entities e
        LEFT JOIN evidence ev ON e.address = ev.entity_address
        WHERE e.identity IS NOT NULL AND e.identity != ''
        GROUP BY e.address
    """)

    kg_identities = {}
    for row in cursor.fetchall():
        address, identity, entity_type, confidence, sources = row
        kg_identities[address.lower()] = {
            'identity': identity,
            'entity_type': entity_type,
            'confidence': confidence,
            'sources': sources or 'KnowledgeGraph'
        }

    print(f"Loaded {len(kg_identities)} identities from knowledge graph")

    # Read existing CSV
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Read {len(rows)} rows from CSV")

    # Update rows with knowledge graph data
    updated_count = 0
    new_identities = 0

    for row in rows:
        borrower = row.get('borrower', '').lower()
        if borrower in kg_identities:
            kg_data = kg_identities[borrower]

            # Only update if KG has higher confidence or CSV is empty
            current_identity = row.get('identity', '').strip()
            current_confidence = row.get('confidence', '').strip()

            # Map confidence to HIGH/MEDIUM/LOW
            kg_conf = kg_data['confidence']
            if kg_conf >= 0.7:
                conf_label = 'HIGH'
            elif kg_conf >= 0.4:
                conf_label = 'MEDIUM'
            else:
                conf_label = 'LOW'

            # Update if no existing identity or KG has better data
            should_update = False
            if not current_identity:
                should_update = True
                new_identities += 1
            elif current_confidence == 'LOW' and conf_label in ('HIGH', 'MEDIUM'):
                should_update = True
            elif current_confidence == 'MEDIUM' and conf_label == 'HIGH':
                should_update = True

            if should_update:
                row['identity'] = kg_data['identity']
                row['confidence'] = conf_label
                row['source'] = kg_data['sources']
                updated_count += 1

    print(f"Updated {updated_count} rows ({new_identities} new identities)")

    # Write updated CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote updated CSV to {csv_path}")

    # Summary stats
    identified = sum(1 for r in rows if r.get('identity', '').strip())
    print(f"\nSummary: {identified}/{len(rows)} rows now have identities ({100*identified/len(rows):.1f}%)")

if __name__ == '__main__':
    main()
