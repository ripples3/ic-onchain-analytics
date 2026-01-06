# Dune Query Templates

Store SQL queries here for version control and Claude context.

## Workflow (Cheapest)

1. Write SQL in this folder
2. Copy to Dune web UI and execute (uses web quota, not API)
3. Save on Dune to get a query ID
4. Document query ID in `references/index_coop.md`
5. Fetch via API only when needed

## File Naming

```
queries/
├── products/
│   ├── 2364870_product_registry.sql
│   └── 4771298_leverage_base_assets.sql
├── analytics/
│   ├── tvl_by_product.sql
│   └── whale_holders.sql
└── adhoc/
    └── temp_analysis.sql
```

## Template Format

```sql
-- Query: Product Registry
-- Dune ID: 2364870
-- Description: All Index Coop products across chains
-- Parameters: none

SELECT * FROM ...
```
