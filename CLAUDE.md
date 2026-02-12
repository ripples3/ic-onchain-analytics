# Dune Analytics - Index Coop

DuneSQL queries and analytics for Index Coop products across Ethereum, Arbitrum, and Base.

## Project Structure

```
dune-analytics/
├── queries/                    # SQL query files ({query_id}_{description}.sql)
├── scripts/
│   ├── dune_query.py          # CLI tool for Dune API
│   ├── build_knowledge_graph.py  # MASTER: Knowledge graph forensic system
│   ├── enrich_addresses.py    # Orchestrates whale enrichment pipeline
│   ├── cio_detector.py        # Common Input Ownership clustering (94.85%)
│   ├── governance_scraper.py  # Snapshot voting analysis
│   ├── verify_identity.py     # Multi-source verification
│   └── [17 more scripts]      # See scripts/README.md
├── data/
│   └── knowledge_graph.db     # SQLite knowledge graph database
├── references/
│   ├── index_coop.md          # Product addresses & query patterns
│   ├── lending_whales.md      # Whale identities, investigation findings
│   ├── cex_hot_wallets.md     # CEX address labels
│   └── investigation_status.md # Current investigation progress
├── .claude/skills/
│   └── dune-analytics.md      # Full DuneSQL syntax guide
└── CLAUDE.md                  # This file
```

## Quick Commands

```bash
# Dune queries
python3 scripts/dune_query.py 5140527              # Fetch cached (FREE)
python3 scripts/dune_query.py 5140527 --execute    # Fresh execution (USES CREDITS)
python3 scripts/dune_query.py 5140527 --format csv > out.csv

# Knowledge graph investigation
python3 scripts/build_knowledge_graph.py stats     # View statistics
python3 scripts/build_knowledge_graph.py run       # Run full pipeline
python3 scripts/build_knowledge_graph.py query --address 0x1234...
python3 scripts/build_knowledge_graph.py export -o results.csv
```

## Key Query IDs & Materialized Views

**PREFER materialized views** (`dune.index_coop.result_*`) over `query_XXXXX`.

### Queries WITH Materialized Views
| ID | Materialized View | Description |
|----|-------------------|-------------|
| **5140527** | `result_multichain_indexcoop_tokenlist` | Token registry (PREFERRED) |
| 4771298 | `result_index_coop_leverage_suite_tokens` | Leverage token configs |
| 3713252 | `result_allchain_lev_suite_tokens_nav_hourly` | Leverage suite NAV hourly |
| 5196255 | `result_multichain_all_active_tokens_nav_hourly` | All active tokens NAV |
| 3808728 | `result_hyeth_yield` | hyETH NAV and APY |

### Queries WITHOUT Materialized Views
| ID | Description |
|----|-------------|
| 5298403 | Latest open exposure by asset |
| 4781646 | Leverage FlashMint events (v1 + v2) |
| 6654792 | Top lending borrowers ($10M+) with identity labels |

## DuneSQL Quick Reference

### Addresses (no quotes)
```sql
where contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b
```

### Time Series (use utils tables, NOT ethereum.blocks)
```sql
select timestamp as day from utils.days where timestamp >= timestamp '2024-01-01'
select timestamp as hour from utils.hours where timestamp >= timestamp '2024-01-01'
```

### Row Filtering (no QUALIFY)
```sql
select * from (
    select *, row_number() over (partition by x order by y) as rn
    from table
) where rn = 1
```

### Multichain Joins (CRITICAL)
```sql
-- WRONG: Creates duplicates
left join prices p on s.address = p.token_address

-- RIGHT: Join on BOTH address AND blockchain
left join prices p on s.address = p.token_address and s.blockchain = p.blockchain
```

### Price Tables
| Table | Granularity | Notes |
|-------|-------------|-------|
| `prices.usd` | Per-minute | Legacy but can be 7x faster |
| `prices.hour` | Hourly | Recommended for hourly queries |
| `prices.day` | Daily | Fastest, broadest coverage |

## Investigation Scripts Status

| Script | What It Does | Status (2026-02-12) |
|--------|--------------|---------------------|
| `trace_funding.py` | CEX funding origin | ✅ Run on top 10 |
| `cio_detector.py` | CIO clustering | ✅ Run - 0 clusters in top 10 |
| `governance_scraper.py` | Snapshot votes | ✅ Run - 1/10 has activity |
| `resolve_safe_owners.py` | Safe multisig owners | ✅ Run - 0 Safes in top 10 |
| `behavioral_fingerprint.py` | Timing/gas patterns | ✅ Run on all |
| `verify_identity.py` | Multi-source check | ✅ Run |
| `whale_tracker_aggregator.py` | Known whale lookup | ✅ Run - 0 matches |

**Result**: Top 10 unidentified whales remain unidentified. Best lead: WLFI whale (#8) with FTX funding + 8.67M WLFI voting power.

## Whale Investigation Workflow

Full methodology: `/on-chain-query` skill. See `references/investigation_status.md` for current progress.

```bash
# Quick pipeline
source .venv/bin/activate
python3 scripts/enrich_addresses.py addresses.csv -o enriched.csv
python3 scripts/cio_detector.py enriched.csv -o clusters.csv
python3 scripts/governance_scraper.py enriched.csv -o governance.csv
python3 scripts/verify_identity.py enriched.csv -o verified.csv --report
```

## Lessons Learned

### 2026-02-12: Arkham Labels Require API Access

**Context**: Tried Playwright scraping of Arkham explorer pages.

**What happened**: Pages require login to see entity labels. Public explorer shows balance but not identity.

**Solution**: Applied for Arkham API access at intel.arkm.com/api. Waiting for approval.

**Pattern**: For Arkham lookups, use API or manual login. Web scraping won't work.

### 2026-02-11: Web Search Has ~10% Hit Rate for Addresses

50 addresses searched → 4 identified (8%). Most large DeFi borrowers are intentionally anonymous.

**What works for high-value unknowns:**
- Whale trackers (Lookonchain, OnchainLens) — often already track large wallets
- Wait for liquidation events — identity surfaces in news
- Paid tools (Nansen $49/mo) — 4x better hit rate

### 2026-02-11: Run Scripts Before Web Search

Scripts are free, have 40-50% combined hit rate. WebSearch costs tokens, has 10% hit rate.

**Workflow**: Local scripts → Aggregate → Web search last (high-value only)

### 2026-02-10: Successful 55-Wallet Cluster ID (Trend Research)

CIO clustering found 55 wallets with common Binance funders. WebSearch for "Trend Research wallet" matched address prefixes. Arkham confirmed entity.

**Pattern**:
```
1. CIO clustering → identify common funders
2. Etherscan → label CEX hot wallets
3. WebSearch → "[address prefix] whale"
4. Arkham entity page → confirm
```

### 2026-02-05: Skills = Methodology, References = Data

Skills became bloated with addresses. Now: methodology in skills, changing data in references.

## Resources

- [DuneSQL Functions](https://docs.dune.com/query-engine/Functions-and-operators)
- `.claude/skills/dune-analytics.md` — Full DuneSQL syntax guide
- `references/index_coop.md` — Product addresses
- `references/lending_whales.md` — Whale identities
- `references/cex_hot_wallets.md` — CEX address labels
- `/on-chain-query` skill — Full investigation methodology
