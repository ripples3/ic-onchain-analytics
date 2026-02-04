#!/usr/bin/env python3
"""
Dune Analytics Query Tool

A datapoint-conscious CLI for executing Dune queries.

IMPORTANT: Dune charges for DATAPOINTS (rows × columns) even for cached results!
Use --limit to restrict rows and reduce costs.

Usage:
    python dune_query.py <query_id> [options]
    python dune_query.py --sql "SELECT * FROM ethereum.transactions LIMIT 10"

Environment:
    DUNE_API_KEY - Required. Get from https://dune.com/settings/api
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in script dir or parent dir
    script_dir = Path(__file__).parent
    env_paths = [script_dir / ".env", script_dir.parent / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass  # python-dotenv not installed, use regular env vars

try:
    from dune_client.client import DuneClient
    from dune_client.query import QueryBase
    from dune_client.types import QueryParameter
except ImportError:
    print("Error: dune-client not installed. Run: pip install dune-client")
    sys.exit(1)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def get_client() -> DuneClient:
    """Initialize Dune client from environment variable."""
    api_key = os.getenv("DUNE_API_KEY")
    if not api_key:
        print("Error: DUNE_API_KEY environment variable not set")
        print("Get your API key from: https://dune.com/settings/api")
        sys.exit(1)
    return DuneClient(api_key)


def parse_parameters(param_strings: list[str]) -> list[QueryParameter]:
    """
    Parse parameter strings in format 'name:type:value'.

    Types: text, number, date, enum
    Examples:
        address:text:0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b
        days:number:30
        start_date:date:2024-01-01
    """
    params = []
    for param_str in param_strings:
        parts = param_str.split(":", 2)
        if len(parts) != 3:
            print(f"Warning: Invalid parameter format '{param_str}', expected 'name:type:value'")
            continue

        name, ptype, value = parts
        ptype = ptype.lower()

        if ptype == "text":
            params.append(QueryParameter.text_type(name, value))
        elif ptype == "number":
            params.append(QueryParameter.number_type(name, float(value)))
        elif ptype == "date":
            params.append(QueryParameter.date_type(name, value))
        elif ptype == "enum":
            params.append(QueryParameter.enum_type(name, value))
        else:
            print(f"Warning: Unknown parameter type '{ptype}', using text")
            params.append(QueryParameter.text_type(name, value))

    return params


def format_table(results) -> str:
    """Format results as a readable ASCII table."""
    if not results.result or not results.result.rows:
        return "No results returned"

    rows = results.result.rows
    if not rows:
        return "Empty result set"

    # Get column names from first row
    columns = list(rows[0].keys())

    # Calculate column widths (max 40 chars per column)
    widths = {}
    for col in columns:
        col_values = [str(row.get(col, "")) for row in rows]
        widths[col] = min(40, max(len(col), max(len(v) for v in col_values) if col_values else 0))

    # Build table
    lines = []

    # Header
    header = " | ".join(col.ljust(widths[col])[:widths[col]] for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    # Data rows (limit to 100 for display)
    for row in rows[:100]:
        line = " | ".join(str(row.get(col, "")).ljust(widths[col])[:widths[col]] for col in columns)
        lines.append(line)

    if len(rows) > 100:
        lines.append(f"... and {len(rows) - 100} more rows")

    # Metadata
    lines.append("")
    lines.append(f"Total rows: {len(rows)}")
    if hasattr(results, 'execution_id'):
        lines.append(f"Execution ID: {results.execution_id}")

    return "\n".join(lines)


def format_json(results) -> str:
    """Format results as JSON."""
    if not results.result or not results.result.rows:
        return json.dumps({"rows": [], "metadata": {"row_count": 0}}, indent=2)

    output = {
        "rows": results.result.rows,
        "metadata": {
            "row_count": len(results.result.rows),
            "execution_id": getattr(results, 'execution_id', None),
        }
    }
    return json.dumps(output, indent=2, default=str)


def format_csv(results) -> str:
    """Format results as CSV."""
    if not results.result or not results.result.rows:
        return ""

    rows = results.result.rows
    if not rows:
        return ""

    columns = list(rows[0].keys())
    lines = [",".join(columns)]

    for row in rows:
        values = []
        for col in columns:
            val = str(row.get(col, ""))
            # Escape quotes and wrap in quotes if contains comma
            if "," in val or '"' in val or "\n" in val:
                val = '"' + val.replace('"', '""') + '"'
            values.append(val)
        lines.append(",".join(values))

    return "\n".join(lines)


def get_cached_result(
    dune: DuneClient,
    query_id: int,
    max_age_hours: Optional[int] = None,
    output_format: str = "table",
    limit: Optional[int] = None
) -> str:
    """
    Get cached query results.

    NOTE: Dune charges DATAPOINTS (rows × columns) even for cached results!

    Args:
        query_id: Dune query ID
        max_age_hours: If set, re-execute if cache is older than this
        output_format: table, json, csv, or dataframe
        limit: Max rows to return (reduces datapoint usage)
    """
    print(f"Fetching results for query {query_id}...", file=sys.stderr)

    if max_age_hours:
        results = dune.get_latest_result(query_id, max_age_hours=max_age_hours)
    else:
        results = dune.get_latest_result(query_id)

    # Show datapoint estimate
    if results.result and results.result.rows:
        rows = results.result.rows
        cols = len(rows[0].keys()) if rows else 0
        total_rows = len(rows)

        # Apply limit if specified
        if limit and limit < total_rows:
            results.result.rows = rows[:limit]
            print(f"Datapoints: ~{limit * cols} (limited from {total_rows} rows)", file=sys.stderr)
        else:
            print(f"Datapoints: ~{total_rows * cols} ({total_rows} rows × {cols} cols)", file=sys.stderr)

    if output_format == "json":
        return format_json(results)
    elif output_format == "csv":
        return format_csv(results)
    elif output_format == "dataframe":
        if not HAS_PANDAS:
            print("Warning: pandas not installed, falling back to table format", file=sys.stderr)
            return format_table(results)
        if results.result and results.result.rows:
            df = pd.DataFrame(results.result.rows)
            return df.to_string()
        return "Empty DataFrame"
    else:
        return format_table(results)


def execute_query(
    dune: DuneClient,
    query_id: int,
    params: Optional[list[QueryParameter]] = None,
    output_format: str = "table"
) -> str:
    """
    Execute a query (USES CREDITS).

    Args:
        query_id: Dune query ID
        params: Query parameters
        output_format: table, json, csv, or dataframe
    """
    print(f"Executing query {query_id}...", file=sys.stderr)
    print("WARNING: This execution will consume API credits!", file=sys.stderr)

    query = QueryBase(query_id=query_id, params=params or [])

    if output_format == "dataframe" and HAS_PANDAS:
        df = dune.run_query_dataframe(query)
        return df.to_string()
    elif output_format == "csv":
        return dune.run_query_csv(query).data
    else:
        results = dune.run_query(query)
        if output_format == "json":
            return format_json(results)
        return format_table(results)


def execute_sql(
    dune: DuneClient,
    sql: str,
    output_format: str = "table"
) -> str:
    """
    Execute ad-hoc SQL query (USES CREDITS).

    Note: This creates a temporary query and executes it.
    For repeated queries, save them on Dune and use query ID instead.
    """
    print("Executing ad-hoc SQL query...", file=sys.stderr)
    print("WARNING: This execution will consume API credits!", file=sys.stderr)
    print("TIP: For repeated queries, save on Dune and use --cached with query ID", file=sys.stderr)

    # Create and execute query
    query = dune.create_query(
        name=f"adhoc_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        query_sql=sql,
        is_private=True
    )

    print(f"Created temporary query ID: {query.query_id}", file=sys.stderr)

    results = dune.run_query(QueryBase(query_id=query.query_id))

    if output_format == "json":
        return format_json(results)
    elif output_format == "csv":
        return format_csv(results)
    elif output_format == "dataframe" and HAS_PANDAS:
        if results.result and results.result.rows:
            df = pd.DataFrame(results.result.rows)
            return df.to_string()
        return "Empty DataFrame"
    return format_table(results)


def main():
    parser = argparse.ArgumentParser(
        description="Dune Analytics Query Tool - Datapoint-conscious",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get results (uses DATAPOINTS from your quota)
  python dune_query.py 1215383

  # Limit rows to reduce datapoint usage
  python dune_query.py 1215383 --limit 10

  # Force fresh execution (USES EXECUTION CREDITS)
  python dune_query.py 1215383 --execute

  # Execute with parameters
  python dune_query.py 1215383 --execute -p "address:text:0x1494..." -p "days:number:30"

  # Output formats
  python dune_query.py 1215383 --format json
  python dune_query.py 1215383 --format csv > output.csv

IMPORTANT - Datapoint Costs:
  Dune charges for DATAPOINTS (rows × columns) even for cached results!
  Use --limit to reduce costs. Check usage at dune.com/settings/api
        """
    )

    parser.add_argument(
        "query_id",
        type=int,
        nargs="?",
        help="Dune query ID"
    )

    parser.add_argument(
        "--sql",
        type=str,
        help="Execute ad-hoc SQL query (USES CREDITS)"
    )

    parser.add_argument(
        "--execute", "-x",
        action="store_true",
        help="Force fresh execution instead of using cached results (USES CREDITS)"
    )

    parser.add_argument(
        "--max-age",
        type=int,
        help="Max age in hours for cached results. Re-executes if older (may use credits)"
    )

    parser.add_argument(
        "--param", "-p",
        action="append",
        default=[],
        help="Query parameter in format 'name:type:value'. Can be used multiple times"
    )

    parser.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv", "dataframe"],
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of rows returned (reduces datapoint usage)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.query_id and not args.sql:
        parser.error("Either query_id or --sql is required")

    if args.sql and args.query_id:
        parser.error("Cannot use both query_id and --sql")

    if args.param and not args.execute and not args.sql:
        print("Note: Parameters only apply when using --execute or --sql", file=sys.stderr)
        print("Using --execute mode to apply parameters...", file=sys.stderr)
        args.execute = True

    # Initialize client
    dune = get_client()

    try:
        if args.sql:
            # Ad-hoc SQL execution
            result = execute_sql(dune, args.sql, args.format)
        elif args.execute:
            # Fresh execution with optional parameters
            params = parse_parameters(args.param) if args.param else None
            result = execute_query(dune, args.query_id, params, args.format)
        else:
            # Cached results (still uses datapoints!)
            result = get_cached_result(dune, args.query_id, args.max_age, args.format, args.limit)

        print(result)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
