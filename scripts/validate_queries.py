#!/usr/bin/env python3
"""
Validate Dune Analytics query files for consistency and best practices.

Usage:
    python3 scripts/validate_queries.py
"""

import os
import re
import glob
from pathlib import Path

QUERIES_DIR = Path(__file__).parent.parent / "queries"
CLAUDE_MD = Path(__file__).parent.parent / "CLAUDE.md"
SKILLS_MD = Path(__file__).parent.parent / ".claude" / "skills" / "dune-analytics.md"

# Known materialized views
MATERIALIZED_VIEWS = {
    "5140527": "result_multichain_indexcoop_tokenlist",
    "4771298": "result_index_coop_leverage_suite_tokens",
    "3713252": "result_allchain_lev_suite_tokens_nav_hourly",
    "2646506": "result_index_coop_issuance_events_all_products",
    "2812068": "result_index_coop_token_prices_daily",
    "3668275": "result_index_coop_product_core_kpi_daily",
}

def check_file_naming():
    """Check all files follow {query_id}_{description}.sql naming."""
    print("\n=== File Naming Convention ===")
    errors = []
    valid = 0

    for f in QUERIES_DIR.glob("*.sql"):
        name = f.stem
        match = re.match(r'^(\d+)_(.+)$', name)
        if match:
            valid += 1
            print(f"  ✓ {f.name}")
        else:
            errors.append(f.name)
            print(f"  ✗ {f.name} - does not match {{query_id}}_{{description}}.sql")

    print(f"\n  Result: {valid} valid, {len(errors)} errors")
    return errors

def check_file_headers():
    """Check all files have required headers."""
    print("\n=== File Headers ===")
    required = ["Query:", "Dune ID:", "Columns:"]
    errors = []

    for f in QUERIES_DIR.glob("*.sql"):
        content = f.read_text()
        header_lines = content[:500]  # Check first 500 chars

        missing = [r for r in required if r not in header_lines]
        if missing:
            errors.append((f.name, missing))
            print(f"  ✗ {f.name} - missing: {', '.join(missing)}")
        else:
            print(f"  ✓ {f.name}")

    print(f"\n  Result: {len(list(QUERIES_DIR.glob('*.sql'))) - len(errors)} valid, {len(errors)} errors")
    return errors

def check_multichain_joins():
    """Check multichain queries join on blockchain."""
    print("\n=== Multichain Join Patterns ===")
    warnings = []

    multichain_tables = [
        "query_2812068",
        "query_2621012",
        "query_2364999",
        "query_4153359",
        "result_multichain",
        "result_allchain",
        "result_index_coop_token_prices",
        "result_index_coop_product_core_kpi",
    ]

    for f in QUERIES_DIR.glob("*.sql"):
        content = f.read_text()

        for table in multichain_tables:
            if table in content:
                # Check if there's a join on this table
                # Look for patterns like "join ... table ... on ... blockchain"
                join_pattern = rf'join[^)]+{re.escape(table)}[^)]+on[^)]+blockchain'
                if not re.search(join_pattern, content, re.IGNORECASE | re.DOTALL):
                    # Check if it's just a FROM (not a JOIN)
                    from_pattern = rf'from\s+[^\s]+{re.escape(table)}'
                    join_exists = re.search(rf'join[^)]+{re.escape(table)}', content, re.IGNORECASE)
                    if join_exists:
                        warnings.append((f.name, table))
                        print(f"  ⚠ {f.name} - joins {table} but may be missing blockchain condition")

    if not warnings:
        print("  ✓ All multichain joins appear to include blockchain condition")

    print(f"\n  Result: {len(warnings)} potential issues")
    return warnings

def check_docs_query_ids():
    """Check query IDs in docs have matching files."""
    print("\n=== Documentation Query IDs ===")
    errors = []

    # Get all query IDs from files
    file_query_ids = set()
    for f in QUERIES_DIR.glob("*.sql"):
        match = re.match(r'^(\d+)_', f.stem)
        if match:
            file_query_ids.add(match.group(1))

    # Check CLAUDE.md
    if CLAUDE_MD.exists():
        content = CLAUDE_MD.read_text()
        doc_ids = set(re.findall(r'\|\s*\*?\*?(\d{7})\*?\*?\s*\|', content))

        missing_files = doc_ids - file_query_ids
        if missing_files:
            for qid in missing_files:
                errors.append((qid, "CLAUDE.md"))
                print(f"  ✗ Query {qid} in CLAUDE.md but no file exists")
        else:
            print(f"  ✓ CLAUDE.md - all {len(doc_ids)} query IDs have files")

    print(f"\n  Result: {len(errors)} missing files")
    return errors

def check_sql_style():
    """Check SQL style compliance."""
    print("\n=== SQL Style Compliance ===")
    issues = []

    uppercase_keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN',
                          'GROUP BY', 'ORDER BY', 'UNION', 'WITH', 'AS', 'AND', 'OR']

    for f in QUERIES_DIR.glob("*.sql"):
        content = f.read_text()
        file_issues = []

        for kw in uppercase_keywords:
            # Check for uppercase keyword not in a string or comment
            pattern = rf'(?<!["\'-])\b{kw}\b(?!["\'-])'
            if re.search(pattern, content):
                file_issues.append(f"uppercase '{kw}'")

        if file_issues:
            issues.append((f.name, file_issues[:3]))  # Limit to first 3
            print(f"  ⚠ {f.name} - {', '.join(file_issues[:3])}")
        else:
            print(f"  ✓ {f.name}")

    print(f"\n  Result: {len(issues)} files with style issues")
    return issues

def check_materialized_view_usage():
    """Check materialized views are used consistently."""
    print("\n=== Materialized View Usage ===")
    recommendations = []

    for f in QUERIES_DIR.glob("*.sql"):
        content = f.read_text()

        for query_id, mv_name in MATERIALIZED_VIEWS.items():
            # Check if query_XXXXX is used instead of materialized view
            query_ref = f"query_{query_id}"
            if query_ref in content and mv_name not in content:
                recommendations.append((f.name, query_id, mv_name))
                print(f"  ⚠ {f.name} - uses {query_ref}, could use dune.index_coop.{mv_name}")

    if not recommendations:
        print("  ✓ All queries use materialized views where available")

    print(f"\n  Result: {len(recommendations)} potential optimizations")
    return recommendations

def main():
    print("=" * 60)
    print("Dune Analytics Query Validation")
    print("=" * 60)

    results = {
        "naming": check_file_naming(),
        "headers": check_file_headers(),
        "multichain": check_multichain_joins(),
        "docs": check_docs_query_ids(),
        "style": check_sql_style(),
        "materialized": check_materialized_view_usage(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_errors = sum(len(v) for v in results.values())
    if total_errors == 0:
        print("✓ All checks passed!")
    else:
        print(f"⚠ {total_errors} total issues found")
        for check, issues in results.items():
            if issues:
                print(f"  - {check}: {len(issues)} issues")

    return total_errors

if __name__ == "__main__":
    exit(main())
