# Dune Analytics - Index Coop

DuneSQL queries and analytics for Index Coop products across Ethereum, Arbitrum, and Base.

## Project Structure

```
dune-analytics/
├── queries/                    # SQL query files ({query_id}_{description}.sql)
├── scripts/
│   └── dune_query.py          # CLI tool for Dune API
├── references/
│   └── index_coop.md          # Product addresses & query patterns
├── .claude/skills/
│   └── dune-analytics.md      # Full DuneSQL syntax guide & code style
└── CLAUDE.md                  # This file
```

## Quick Commands

```bash
# Fetch cached results (FREE)
python3 scripts/dune_query.py 5140527

# Export formats
python3 scripts/dune_query.py 5140527 --format csv > out.csv
python3 scripts/dune_query.py 5140527 --format json

# Fresh execution (USES CREDITS)
python3 scripts/dune_query.py 5140527 --execute
```

## Key Query IDs & Materialized Views

**PREFER materialized views** (`dune.index_coop.result_*`) over `query_XXXXX` for better performance.
**Only use materialized views that are confirmed to exist** - don't assume.

### Queries WITH Materialized Views
| ID | Materialized View | Description |
|----|-------------------|-------------|
| **5140527** | `result_multichain_indexcoop_tokenlist` | Token registry with decimals (PREFERRED) |
| 4771298 | `result_index_coop_leverage_suite_tokens` | Leverage token configs |
| 3713252 | `result_allchain_lev_suite_tokens_nav_hourly` | Leverage suite hourly NAV/price |
| 2646506 | `result_index_coop_issuance_events_all_products` | Issuance events all products |
| 2812068 | `result_index_coop_token_prices_daily` | Token prices daily |
| 3668275 | `result_index_coop_product_core_kpi_daily` | Product Core KPIs daily |
| 5196255 | `result_multichain_all_active_tokens_nav_hourly` | All active tokens NAV hourly |
| 5140966 | `result_multichain_components_with_hardcoded_values` | Component tokens with base_symbol (replaces 3018988) |
| 5140916 | `result_multichain_composition_changes_product_events` | Composition changes per token (upstream for NAV) |
| 3808728 | `result_hyeth_yield` | hyETH NAV and APY |
| 3994496 | `result_hyeth_nav_by_minute` | hyETH NAV by minute |
| 3457583 | `result_fli_token_nav_lr` | FLI tokens (ETH2x-FLI, BTC2x-FLI) NAV hourly |

### Queries WITHOUT Materialized Views
| ID | Description |
|----|-------------|
| 5298403 | Latest open exposure by asset |
| 3982525 | Weekly KPI report |
| 3672187 | Daily KPI report (TVL & NSF) |
| 4135813 | All chain lev suite trades (user holding periods) |
| 2364999 | Unit supply daily |
| 2621012 | Fee structure daily |
| 4153359 | Staked PRT share |
| 2878827 | Fee split structure |
| 3989545 | Post-merge staking yield |
| 2364870 | Token registry (legacy) |
| 4007736 | PENDLE hyETH Swap & Hold Incentive Tracker |
| 3806801 | hyETH composition NAV ETH (minute) |
| 3806854 | LRT exchange rates (minute) |
| 547552 | icETH yield (APY, parity value) |
| 4781646 | Leverage FlashMint events (v1 + v2) |

## Optimization Guidelines

When optimizing queries, **ALWAYS verify logic is intact** after changes:

1. **Don't assume optimizations** - Ask before making changes not explicitly requested
2. **Verify row counts** - Compare output before/after optimization
3. **Check aggregation behavior** - `avg(minute prices)` ≠ direct `hourly price` lookup
4. **UNION vs UNION ALL** - Only use UNION ALL when no duplicates possible (different contracts/events)
5. **Window function partitions** - Ensure partitions are preserved exactly

Common optimizations (apply carefully):
- `ethereum.blocks` → `utils.days`, `utils.hours`, or `utils.minutes`
- `prices.usd` → `prices.hour` or `prices.day` (but test - `prices.usd` can be faster)
- Add time filters on large tables for partition pruning
- `UNION` → `UNION ALL` where safe

**Always document optimizations in the file header.**

## DuneSQL Quick Reference

### Materialized Result Tables

**Always prefer materialized views** over `query_XXXXX` for faster execution:
```sql
-- GOOD: Use materialized view
from dune.index_coop.result_multichain_indexcoop_tokenlist  -- query_5140527
from dune.index_coop.result_index_coop_leverage_suite_tokens  -- query_4771298
from dune.index_coop.result_allchain_lev_suite_tokens_nav_hourly  -- query_3713252

-- AVOID: Direct query reference (slower)
from query_5140527
```

### Addresses (no quotes)
```sql
where contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b
```

### Time Differences
```sql
date_diff('second', timestamp1, timestamp2)
date_diff('day', timestamp1, timestamp2)
```

### Generate Time Series (use utils tables, NOT ethereum.blocks)
```sql
-- Daily
select timestamp as day from utils.days where timestamp >= timestamp '2020-09-10'

-- Hourly
select timestamp as hour from utils.hours where timestamp >= timestamp '2024-01-01'

-- Minute
select timestamp as minute from utils.minutes where timestamp >= timestamp '2024-04-10'
```

### Row Filtering (no QUALIFY)
```sql
select * from (
    select *, row_number() over (partition by x order by y) as rn
    from table
) where rn = 1
```

### Multichain Tables
```sql
from evms.erc20_transfers e
where e.blockchain in ('ethereum', 'arbitrum', 'base')
```

### Multichain Joins (CRITICAL)
**Always join on BOTH address AND blockchain** to prevent duplicate rows:
```sql
-- WRONG: Creates duplicates (same token on multiple chains)
left join prices p on s.address = p.token_address

-- RIGHT: Unique match per chain
left join prices p on s.address = p.token_address and s.blockchain = p.blockchain
```

### Price Tables
| Table | Time Column | Granularity | Notes |
|-------|-------------|-------------|-------|
| `prices.usd` | `minute` | Per-minute | ⚠️ **LEGACY** - but can be faster (smaller table) |
| `prices.minute` | `timestamp` | Per-minute | Broader coverage but larger table |
| `prices.hour` | `timestamp` | Hourly | ✅ **Recommended** for hourly queries |
| `prices.day` | `timestamp` | Daily | ✅ Fastest, broadest coverage |

**Price table selection:**
- `prices.usd` is LEGACY but can be **7x faster** if tokens are already in it (smaller table)
- `prices.minute` has broader coverage but scans more data
- Test both if performance matters - don't blindly replace `prices.usd`

**⚠️ `prices.minute` optimization attempts - TESTED & FAILED:**

Tested on query_4781646 (Leverage FlashMint events). None matched `prices.usd` performance:
- **Semi-join with dynamic token list** - Timed out on free engine
- **Explicit token list filter** - Timed out on free engine
- **prices.hour fallback** - Not viable when minute precision needed

**Conclusion:** Stick with `prices.usd` until Dune deprecates it. When deprecated:
1. Accept ~7x higher query cost with `prices.minute`
2. Create materialized view to pre-filter prices for specific tokens
3. Request Dune improve `prices.minute` indexing

### Base Wrapped Alt Tokens
Base tokens (uSOL, uSUI, uXRP) have **direct prices** in `prices.hour` on Base chain - no cross-chain lookup needed:
- uSOL: `0x9b8df6e244526ab5f6e6400d331db28c8fdddb55`
- uSUI: `0xb0505e5a99abd03d94a1169e638b78edfed26ea4`
- uXRP: `0x2615a94df961278DcbC41Fb0a54fEc5f10a693aE`

### Aave V3 Token Patterns
Leverage products use Aave V3 aTokens (collateral) and variableDebt tokens (debt):
- **Collateral**: `aEthWETH`, `aArbWBTC`, `aBasWETH` → price lookup uses underlying token
- **Debt**: `variableDebtEthUSDC`, `variableDebtArbUSDCn` → price lookup uses underlying token

Find Aave contract addresses at: [bgd-labs/aave-address-book](https://github.com/bgd-labs/aave-address-book)

### Filter NaN Values
```sql
where not is_nan(leverage_ratio)
```

## Resources

- [DuneSQL Functions](https://docs.dune.com/query-engine/Functions-and-operators)
- See `.claude/skills/dune-analytics.md` for complete syntax guide
- See `references/index_coop.md` for all product addresses
- For whale research: Use `/on-chain-query` skill (Arkham, Lending CRM, investigation workflow)
