---
name: dune-analytics
description: DuneSQL queries for Index Coop blockchain analytics. Use when writing or reviewing DuneSQL queries, fetching on-chain data, or working with Index Coop product addresses.
---

# Dune Analytics Skill

Execute Dune Analytics queries for blockchain data analysis, DeFi metrics, and on-chain analytics for Index Coop.

## Index Coop Saved Queries & Materialized Views

**PREFER materialized views** (`dune.index_coop.result_*`) over `query_XXXXX` for better performance.
**Only use materialized views that are confirmed to exist** - don't assume.

### Queries WITH Materialized Views
| Query ID | Materialized View | Description |
|----------|-------------------|-------------|
| **5140527** | `result_multichain_indexcoop_tokenlist` | Product registry with decimals (PREFERRED) |
| **4771298** | `result_index_coop_leverage_suite_tokens` | Leverage token configs |
| **3713252** | `result_allchain_lev_suite_tokens_nav_hourly` | Leverage suite hourly NAV/price |
| **2646506** | `result_index_coop_issuance_events_all_products` | Issuance events all products |
| **2812068** | `result_index_coop_token_prices_daily` | Token prices daily |
| **3668275** | `result_index_coop_product_core_kpi_daily` | Product Core KPIs daily |
| **5196255** | `result_multichain_all_active_tokens_nav_hourly` | All active tokens NAV hourly |
| **5140966** | `result_multichain_components_with_hardcoded_values` | Component tokens with base_symbol (replaces 3018988) |
| **5140916** | `result_multichain_composition_changes_product_events` | Composition changes per token (upstream for NAV) |
| **3808728** | `result_hyeth_yield` | hyETH NAV and APY |
| **3994496** | `result_hyeth_nav_by_minute` | hyETH NAV by minute |
| **3457583** | `result_fli_token_nav_lr` | FLI tokens (ETH2x-FLI, BTC2x-FLI) NAV hourly |

### Queries WITHOUT Materialized Views
| Query ID | Description |
|----------|-------------|
| **5298403** | Latest open exposure by asset |
| **3982525** | Weekly KPI report |
| **2364999** | Unit supply daily |
| **2621012** | Fee structure daily (gap-filled) |
| **4153359** | Staked PRT share |
| **2878827** | Fee split structure |
| **3989545** | Post-merge staking yield (CL + EL) |
| **2364870** | Product registry (legacy) |
| **4007736** | PENDLE hyETH Swap & Hold Incentive Tracker |
| **3806801** | hyETH composition NAV ETH (minute) |
| **3806854** | LRT exchange rates (minute) |

### Materialized View Usage

**Always use materialized views** when available:
```sql
-- GOOD: Use materialized view (faster)
from dune.index_coop.result_multichain_indexcoop_tokenlist t  -- query_5140527
from dune.index_coop.result_index_coop_leverage_suite_tokens  -- query_4771298
from dune.index_coop.result_allchain_lev_suite_tokens_nav_hourly  -- query_3713252

-- AVOID: Direct query reference (slower)
from query_5140527
```

### Token Registry Notes

**Prefer `result_multichain_indexcoop_tokenlist`** (query_5140527) over legacy:
- Has `decimals` column
- Clean symbols without chain suffix (`ETH2x` not `ETH2x-ARB`)
- Same symbol exists on multiple chains (ETH2x on ethereum/arbitrum/base)

**Important**: Always join on BOTH `contract_address` AND `blockchain`:
```sql
inner join dune.index_coop.result_multichain_indexcoop_tokenlist t
    on t.contract_address = s.address
    and t.blockchain = s.blockchain
```

**Migration Caution**: ASK before migrating existing queries from 2364870 to 5140527 - check downstream compatibility for:
- Symbol format change (`ETH2x-ARB` → `ETH2x`)
- Column name change (`address` → `contract_address`)
- Join logic changes

### File Naming Convention

```
queries/{query_id}_{description}.sql
```

Example: `5140527_multichain_tokenlist.sql`

### Query File Header

```sql
-- Query: {query-name}
-- Dune ID: {query_id}
-- URL: https://dune.com/queries/{query_id}
-- Description: {description}
-- Parameters: {params or none}
--
-- Columns: {output columns}
```

### Local Query Templates

| File | Description |
|------|-------------|
| `queries/5140527_multichain_tokenlist.sql` | Product registry with decimals |
| `queries/4771298_leverage_suite_tokens.sql` | Leverage token configs (decimals, tlr, maxlr, minlr) |
| `queries/3713252_allchain_lev_suite_tokens_nav_hourly.sql` | Leverage suite hourly NAV/price |
| `queries/2646506_issuance_events_all_products.sql` | Token issuance/redemption events |
| `queries/2364999_unit_supply_daily.sql` | Daily unit supply for all products |
| `queries/2621012_fee_structure_daily.sql` | Fee structure daily (gap-filled) |
| `queries/4153359_staked_prt_share.sql` | Staked PRT share |
| `queries/2812068_token_prices_daily.sql` | Token prices from multiple NAV sources |
| `queries/5140966_components_with_base_symbol.sql` | Component tokens with base_symbol (replaces 3018988) |
| `queries/5140916_composition_changes_product_events.sql` | Composition changes per token (upstream for NAV) |
| `queries/3668275_product_core_kpis_daily.sql` | Product Core KPIs (TVL, NSF, revenue) |
| `queries/3982525_weekly_kpi_report.sql` | Weekly KPI report |
| `queries/5298403_latest_open_exposure_by_asset.sql` | Latest open exposure by asset |
| `queries/2878827_fee_split_structure.sql` | Fee split structure (IC share) |
| `queries/3989545_post_merge_staking_yield.sql` | ETH staking yield (CL + EL) |
| `queries/2364870_index_coop_tokens.sql` | Product registry (legacy) |
| `queries/3808728_hyeth_yield.sql` | hyETH NAV and APY |
| `queries/3802258_lrt_eth_exchange_rates.sql` | LRT exchange rates (weETH, rswETH, rsETH, ezETH, agETH) |
| `queries/3805243_hyeth_composition_nav_eth.sql` | hyETH composition NAV in ETH |
| `queries/4007736_pendle_hyeth_swap_hold_incentive.sql` | PENDLE hyETH Swap & Hold Incentive Tracker |
| `queries/3994496_hyeth_nav_by_minute.sql` | hyETH NAV by minute |
| `queries/3806801_hyeth_composition_nav_eth_minute.sql` | hyETH composition NAV ETH (minute) |
| `queries/3806854_lrt_eth_exchange_rates_minute.sql` | LRT exchange rates (minute) |

## CLI Usage

```bash
python3 scripts/dune_query.py <query_id>           # Cached (FREE)
python3 scripts/dune_query.py <query_id> --execute  # Fresh (USES CREDITS)
python3 scripts/dune_query.py <query_id> --format json
python3 scripts/dune_query.py <query_id> --format csv > output.csv
```

---

# DuneSQL Code Style

## Keywords & Case

All SQL keywords lowercase:
```sql
with, select, from, where, join, on, and, or, as, union, group by, order by, having, case, when, then, else, end, cast, inner, left, values
```

## CTE Structure

First CTE without comma, subsequent CTEs with leading comma:
```sql
with

first_cte as (
    select *
    from table
)

, second_cte as (
    select *
    from first_cte
)

select * from second_cte
```

## Column Selection

Leading commas, one column per line, 4-space indent:
```sql
select
    'ethereum' as blockchain
    , _recipient as user_address
    , contract_address as fl_contract
    , 'Redeem' as tx_type
    , _outputToken as token_address
    , evt_block_time
    , evt_block_number
    , evt_index
    , evt_tx_hash
    , (cast(_amountSetRedeemed as DECIMAL(38,0))/1e18) as ic_amount
from table
```

## Aliases

Always use `as` keyword:
```sql
-- RIGHT
select column as alias
from table t

-- WRONG
select column alias
```

## Addresses

Lowercase hex, no quotes:
```sql
where contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b
and "to" = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
```

## Timestamps

Use `timestamp` keyword with single quotes:
```sql
where evt_block_time >= timestamp '2024-03-13'
```

## Type Casting

Use `cast()` with explicit types, divide by scientific notation:
```sql
(cast(_amountSetRedeemed as DECIMAL(38,0))/1e18) as ic_amount
cast(value as DECIMAL(38,0))
```

## WHERE Clauses

First condition on same line as `where`, subsequent with leading `and`:
```sql
where evt_block_time >= timestamp '2024-03-13'
and contract_address = 0x1234...
and blockchain = 'ethereum'
```

## JOINs

Join keyword and table on same line, conditions after `on`:
```sql
inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'

-- Or for complex conditions:
inner join tx_hashes tx on tr.evt_tx_hash = tx.evt_tx_hash
    and (
        (tx.tx_type = 'Issue' and tr."from" = tx.user_address) or
        (tx.tx_type = 'Redeem' and tr."to" = tx.user_address)
    )
```

## UNION

`union` or `union all` on its own line:
```sql
select * from table1
where condition

union all

select * from table2
where condition
```

## Comments

Inline comments with `--`:
```sql
from indexprotocol_base.flashmintleveragedmorphov2_evt_flashredeem fm --redeem event
```

Section dividers:
```sql
-- ========================
-- Redeem Contracts =======
-- ========================
-- == Ethereum ==
```

## CASE Statements

```sql
case
    when tx.tx_type = 'Issue' and tr."from" = tx.user_address then cast(value as DECIMAL(38,0))
    when tx.tx_type = 'Redeem' and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
    else amount
end as amount
```

## Nested CTEs

For complex queries, nest `with` inside a CTE:
```sql
, complex_cte as (
with

inner_cte as (
    select * from table
)

, another_inner as (
    select * from inner_cte
)

select * from another_inner
)
```

## VALUES Syntax

For inline data, align columns:
```sql
lev_suite (blockchain, base, product_symbol, token_address) as (
    values

    ('ethereum', 'WBTC', 'BTC2X',          0xD2AC55cA3Bbd2Dd1e9936eC640dCb4b745fDe759 ),
    ('ethereum', 'WBTC', 'BTC3x',          0xc7068657FD7eC85Ea8Db928Af980Fc088aff6De5 ),
    ('ethereum', 'WETH', 'ETH2X',          0x65c4C0517025Ec0843C9146aF266A2C5a2D148A2 )
)
```

## GROUP BY / ORDER BY

Use column numbers for brevity:
```sql
group by 1, 2, 3, 4, 5, 6
order by 1, 2
```

## Price Joins

Standard pattern for hourly prices (recommended):
```sql
left join prices.hour p
    on p.contract_address = tr.contract_address
    and p.blockchain = tr.blockchain
    and p.timestamp = date_trunc('hour', tr.evt_block_time)
where p.blockchain in ('ethereum', 'base', 'arbitrum')
```

For daily aggregations:
```sql
left join prices.day p
    on p.contract_address = tr.contract_address
    and p.blockchain = tr.blockchain
    and p.timestamp = date_trunc('day', tr.evt_block_time)
```

## Naming Conventions

- CTEs: `snake_case` descriptive names (`all_flasmint_events`, `levsuite_tokens`, `eth_transfers`)
- Aliases: Short lowercase (`fm`, `lp`, `tr`, `tx`, `p`, `s`)
- Output columns: `snake_case` (`user_address`, `token_address`, `evt_block_time`)

---

# DuneSQL Reference

## Common Tables

| Category | Table | Key Columns |
|----------|-------|-------------|
| Transactions | `ethereum.transactions` | `block_time`, `from`, `to`, `value`, `hash`, `gas_price`, `gas_used` |
| Blocks | `ethereum.blocks` | `time`, `number`, `base_fee_per_gas`, `gas_used` |
| ERC20 Transfers | `erc20_ethereum.evt_Transfer` | `evt_block_time`, `from`, `to`, `value`, `contract_address` |
| Staking Flows | `staking_ethereum.flows` | `block_time`, `amount_staked`, `amount_full_withdrawn`, `validator_index`, `entity` |

## Price Tables

Dune has multiple price tables with different granularities.

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

**Performance tip**: Use the coarsest granularity that meets your needs. Minute-level queries over long periods are resource-intensive.

**Schema for prices.hour/day/minute:**
```
timestamp, blockchain, contract_address, symbol, price, decimals, volume, source
```

**Schema for prices.usd:**
```
minute, blockchain, contract_address, symbol, price, decimals
```

### Price Table Usage

```sql
-- prices.usd (minute column) - LEGACY but can be faster for common tokens
select date_trunc('hour', p.minute) as hour, avg(p.price) as price
from prices.usd p
where p.blockchain = 'ethereum'
and p.minute >= timestamp '2024-01-01'
group by 1

-- prices.hour (timestamp column) - recommended for hourly
select p.timestamp as hour, p.price
from prices.hour p
where p.blockchain = 'ethereum'
and p.timestamp >= timestamp '2024-01-01'
```

**IMPORTANT**: Test performance before replacing `prices.usd`. It can be 7x faster due to smaller table size.

**⚠️ `prices.minute` optimization attempts - TESTED & FAILED:**

Tested on query_4781646 (Leverage FlashMint events). None matched `prices.usd` performance:
- **Semi-join with dynamic token list** - Timed out on free engine
- **Explicit token list filter** - Timed out on free engine
- **prices.hour fallback** - Not viable when minute precision needed

**Conclusion:** Stick with `prices.usd` until Dune deprecates it. When deprecated:
1. Accept ~7x higher query cost with `prices.minute`
2. Create materialized view to pre-filter prices for specific tokens
3. Request Dune improve `prices.minute` indexing

## Time Difference Calculations

DuneSQL does NOT support `EXTRACT(epoch FROM interval)`. Use `date_diff`:
```sql
date_diff('second', earlier_timestamp, later_timestamp)
date_diff('day', timestamp1, timestamp2)

-- With window functions
date_diff('second', LAG(time) OVER (ORDER BY number), time) as interval_seconds
```

## Row Filtering (No QUALIFY)

DuneSQL doesn't support QUALIFY. Use subquery:
```sql
-- WRONG
select * from table QUALIFY ROW_NUMBER() OVER (...) = 1

-- RIGHT
select * from (
    select *, ROW_NUMBER() OVER (PARTITION BY x ORDER BY y) as rn
    from table
) where rn = 1
```

## Multichain Tables

For cross-chain queries, use `evms.*` tables:
```sql
from evms.erc20_transfers e
where e.blockchain in ('ethereum', 'arbitrum', 'base')
```

## Optimization Patterns

> Reference: [Writing Efficient Queries - Dune Docs](https://docs.dune.com/query-engine/writing-efficient-queries)

### CRITICAL: Always Verify Logic is Intact

When optimizing queries, **ALWAYS double-check that logic is preserved**:

1. **Don't assume optimizations** - Ask before making changes not explicitly requested
2. **Verify row counts** - Compare output before/after optimization
3. **Check aggregation behavior** - `avg(minute prices)` ≠ direct `hourly price` lookup
   ```sql
   -- Original: averages minute prices to hourly
   select date_trunc('hour', minute) as hour, avg(price) as price
   from prices.usd

   -- WRONG optimization: loses averaging behavior
   select timestamp as hour, price from prices.hour

   -- CORRECT optimization: preserves averaging (if changing tables)
   select date_trunc('hour', timestamp) as hour, avg(price) as price
   from prices.minute group by 1

   -- OR: keep prices.usd if it's faster (test both!)
   ```
4. **UNION vs UNION ALL** - Only use UNION ALL when no duplicates possible:
   - Different event types (Deposit vs Withdraw) → UNION ALL safe
   - Different contracts → UNION ALL safe
   - Same source with overlapping conditions → keep UNION
5. **Window function partitions** - Ensure partitions are preserved exactly
6. **JOIN conditions** - Verify all join columns preserved, especially blockchain

**Common safe optimizations:**
- `ethereum.blocks` → `utils.days`, `utils.hours`, or `utils.minutes`
- `prices.usd` → `prices.hour` or `prices.day` (but test - `prices.usd` can be 7x faster!)
- Add time filters on large tables for partition pruning
- `UNION` → `UNION ALL` where provably no duplicates

**Always document optimizations in the file header.**

### Partition Pruning (CRITICAL for Performance)

Cross-chain tables (tokens.transfers, dex.trades, evms.*) are partitioned by **blockchain + time**. Always filter early:

```sql
-- GOOD: Enables partition pruning
from evms.erc20_transfers e
where e.blockchain in ('ethereum', 'arbitrum', 'base')
and e.block_time >= timestamp '2024-01-01'

-- BAD: Full table scan (no partition pruning)
from evms.erc20_transfers e
where date_trunc('day', e.block_time) >= timestamp '2024-01-01'  -- Function wrapping breaks pruning!
```

### Filter Before Joining

Apply filters in CTEs before joining to reduce row counts:

```sql
-- GOOD: Filter first, then join
, filtered_transfers as (
    select * from evms.erc20_transfers
    where blockchain = 'ethereum'
    and block_time >= timestamp '2024-01-01'
)
select * from filtered_transfers t
inner join tokens tok on t.contract_address = tok.address

-- BAD: Join then filter (processes more rows)
select * from evms.erc20_transfers t
inner join tokens tok on t.contract_address = tok.address
where t.blockchain = 'ethereum'
```

### Select Only Needed Columns

Avoid `SELECT *` on large tables (transactions, logs):

```sql
-- GOOD: Select specific columns
select block_time, "from", "to", value, contract_address
from evms.erc20_transfers

-- BAD: Selects all columns (slower)
select * from evms.erc20_transfers
```

### Debug with EXPLAIN ANALYZE

Check query plans for full table scans:

```sql
explain analyze
select ...
```

### Use utils Time Tables (NOT ethereum.blocks)

**NEVER use `ethereum.blocks` to generate time series.** Use `utils` tables instead:

| Table | Granularity | Column |
|-------|-------------|--------|
| `utils.days` | Daily | `timestamp` |
| `utils.hours` | Hourly | `timestamp` |
| `utils.minutes` | Per-minute | `timestamp` |

```sql
-- GOOD: Use utils tables
select timestamp as day from utils.days where timestamp >= timestamp '2020-09-10'
select timestamp as hour from utils.hours where timestamp >= timestamp '2024-01-01'
select timestamp as minute from utils.minutes where timestamp >= timestamp '2024-04-10'

-- NEVER: Scanning ethereum.blocks (slow, expensive)
select distinct date_trunc('day', time) as day from ethereum.blocks
```

### Pre-aggregate Before Joining

```sql
-- Pre-aggregate events to reduce join rows
, daily_events as (
select
    contract_address
    , date_trunc('day', evt_block_time) as day
    , sum(qty) filter (where qty > 0) as issue_qty
    , sum(qty) filter (where qty < 0) as redeem_qty
from events
group by 1, 2
)
-- Then join to daily_events (fewer rows)
```

### Gap-Fill Pattern with LEAD

```sql
, gap_balance as (
select
    day
    , value
    , lead(day, 1, now()) over (partition by token order by day) as next_day
from daily_changes
)

select d.day, b.value
from days d
inner join gap_balance b
    on b.day <= d.day
    and d.day < b.next_day
```

### Single Scan with CASE vs UNION ALL

**CAUTION**: May produce different row counts if transfers have both from=0x00 AND to=0x00.

```sql
-- UNION ALL: Exact match (two scans)
select value from transfers where "from" = 0x000...
union all
select -value from transfers where "to" = 0x000...

-- CASE: Single scan (may differ by edge cases)
select
    case
        when "from" = 0x000... then value
        when "to" = 0x000... then -value
    end as qty
from transfers
where "from" = 0x000... or "to" = 0x000...
```

**Always verify row counts when optimizing.**

### Zero Address Pattern

- **Mint**: `"from" = 0x0000000000000000000000000000000000000000`
- **Burn**: `"to" = 0x0000000000000000000000000000000000000000`

### Multichain Joins (CRITICAL)

**Always join on BOTH address AND blockchain** to prevent duplicate rows:
```sql
-- WRONG: Creates duplicates (same token on multiple chains)
left join query_2812068 p on s.address = p.token_address

-- RIGHT: Unique match per chain
left join query_2812068 p
    on s.address = p.token_address
    and s.blockchain = p.blockchain
```

### Filter NaN Values

When calculations may produce NaN (e.g., division by zero), filter them out:
```sql
where not is_nan(leverage_ratio)
```

### NOT EXISTS vs NOT IN

**Prefer NOT EXISTS** for better performance on large tables:
```sql
-- AVOID: NOT IN (slower on large tables)
where contract_address not in (select contract_address from icproducts)

-- PREFER: NOT EXISTS (faster)
and not exists (
    select 1 from icproducts p
    where p.contract_address = e.contract_address
    and p.blockchain = e.blockchain
)
```

## Component Token Mapping (query 5140966)

The `result_multichain_components_with_hardcoded_values` maps component tokens to their underlying price tokens:

```sql
-- contract_address, blockchain, symbol, base_symbol, decimals, price_address
(0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8, 'ethereum', 'aEthWETH', 'WETH', 18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
(0x72E95b8931767C79bA4EeE721354d6E99a61D004, 'ethereum', 'variableDebtEthUSDC', 'USDC', 6, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),
```

**Key mappings:**
- `aTokens` (collateral) → underlying token address for price lookup
- `variableDebt` tokens (debt) → underlying token address for price lookup
- Base wrapped tokens (uSOL, uSUI, uXRP) → same address (direct prices available)

## Aave V3 Token Addresses

Find Aave V3 contract addresses at: [bgd-labs/aave-address-book](https://github.com/bgd-labs/aave-address-book)

| Chain | aToken Example | variableDebt Example |
|-------|----------------|---------------------|
| Ethereum | `aEthWETH` 0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8 | `variableDebtEthUSDC` 0x72E95b8931767C79bA4EeE721354d6E99a61D004 |
| Arbitrum | `aArbWETH` 0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8 | `variableDebtArbUSDCn` 0xFCCf3cAbbe80101232d343252614b6A3eE81C989 |
| Base | `aBasWETH` 0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7 | `aBasUSDC` (for debt) 0x4e65fe4dba92790696d040ac24aa414708f5c0ab |

## Base Wrapped Alt Tokens

Base tokens have **direct prices** in `prices.hour` - no cross-chain lookup needed:

| Token | Address | Decimals |
|-------|---------|----------|
| uSOL | `0x9b8df6e244526ab5f6e6400d331db28c8fdddb55` | 18 |
| uSUI | `0xb0505e5a99abd03d94a1169e638b78edfed26ea4` | 18 |
| uXRP | `0x2615a94df961278DcbC41Fb0a54fEc5f10a693aE` | 18 |

## Key Index Coop Addresses

**Ethereum:** DPI `0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b`, ETH2X `0x65c4c0517025ec0843c9146af266a2c5a2d148a2`

**Arbitrum:** iETH2x `0x6a21af139b440f0944f9e03375544bb3e4e2135f`, iBTC2x `0x304f3eb3b77c025664a7b13c3f0ee2f97f9743fd`

**Base:** iETH2x `0x563c4f95D1D4372fA64803E9B367f14a7Ff28b1a`, iBTC2x `0x3b73475EDE04891AE8262680D66A4f5A66572EB0`

See `references/index_coop.md` for complete list.

---

**For whale research & identity investigation:** Use the global `/on-chain-query` skill which has Arkham Intel, Lending CRM, investigation workflows, and known whale addresses.
