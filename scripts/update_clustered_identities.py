#!/usr/bin/env python3
"""
Add identity column to whale_top200_clustered.csv based on cluster_id.
cluster_1 = Trend Research (LD Capital)
"""

import csv
from pathlib import Path

def update_clustered(input_path: Path, output_path: Path):
    """Add identity column based on cluster_id."""
    rows = []

    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) + ['identity']

        for row in reader:
            cluster_id = row.get('cluster_id', '').strip()
            if cluster_id == 'cluster_1':
                row['identity'] = 'Trend Research (Jack Yi / LD Capital)'
            else:
                row['identity'] = ''
            rows.append(row)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    identified = sum(1 for r in rows if r['identity'])
    return identified, len(rows)

def main():
    input_path = Path("whale_top200_clustered.csv")
    output_path = input_path

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return

    identified, total = update_clustered(input_path, output_path)
    print(f"Added identity to {identified} of {total} rows in whale_top200_clustered.csv")
    print(f"(cluster_1 = Trend Research)")

if __name__ == "__main__":
    main()
