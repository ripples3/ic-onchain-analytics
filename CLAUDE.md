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

| Script | What It Does | Status (2026-02-13) |
|--------|--------------|---------------------|
| `trace_funding.py` | CEX funding origin | ✅ Run on top 10 + Safe signers |
| `cio_detector.py` | CIO clustering | ✅ Run - 0 clusters in top 10 |
| `governance_scraper.py` | Snapshot votes | ✅ Run - 1/10 has activity |
| `resolve_safe_owners.py` | Safe multisig owners | ✅ Run - found clusters |
| `behavioral_fingerprint.py` | Timing/gas patterns | ✅ Run on all |
| `temporal_correlation.py` | **Same-operator detection** | 🆕 NEW |
| `counterparty_graph.py` | **Shared counterparty analysis** | 🆕 NEW |
| `label_propagation.py` | **Identity propagation** | 🆕 NEW |
| `verify_identity.py` | Multi-source check | ✅ Run |
| `whale_tracker_aggregator.py` | Known whale lookup | ✅ Run - 0 matches |
| `investigate_safes.py` | **Integrated Safe pipeline** | 🆕 NEW |

**Safe Investigation Results (2026-02-13)**:
- Cluster A ($709M): Tornado-funded entity (65% confidence)
- Cluster B ($476M): Coinbase Prime custody client (75% confidence)
- $544M Safe: OG DeFi whale from 2021 (55% confidence)

**Result**: Top 10 EOA whales remain unidentified. Best lead: WLFI whale (#8) with FTX funding + 8.67M WLFI voting power.

## Temporal Correlation Engine (NEW)

Detects wallets operated by the same person by finding temporally correlated actions.

**Why it works**: When one operator controls multiple wallets, actions happen in rapid succession (deposit from A → borrow on B within seconds). This is nearly impossible to fake while maintaining operational efficiency.

**Confidence thresholds**:
| Correlations | Window | Confidence |
|--------------|--------|------------|
| 3-4 | 30s | 65-70% |
| 5-9 | 30s | 80-85% |
| 10+ | 30s | 90-95% |
| Any | <10s | +10% boost |

```bash
# Standalone usage
python3 scripts/temporal_correlation.py addresses.csv -o correlations.csv

# Analyze specific target against pool
python3 scripts/temporal_correlation.py addresses.csv --target 0xccee...6fa7

# Use tighter window (10s instead of 30s)
python3 scripts/temporal_correlation.py addresses.csv --window 10

# Integrate with knowledge graph
python3 scripts/build_knowledge_graph.py run --layer temporal
```

**Output example**:
```
🔴 HIGH [92%] 0x1234... ↔ 0x5678...
    10 correlations, addr1 leads, near-simultaneous (avg 8s)
```

## Counterparty Graph Analysis (NEW)

Finds related wallets by analyzing WHO they transact with, even without direct funding links.

**Why it works**: Whales have consistent counterparties (OTC desks, market makers). If two unknown wallets have 70%+ counterparty overlap, they're likely related - CIO won't find this because there's no direct funding connection.

**Signal types**:
| Signal | Strength | Description |
|--------|----------|-------------|
| Shared deposit addresses | Very strong | Both send to same CEX deposit (unique per user) |
| Shared counterparties | Strong | Both transact with same addresses repeatedly |
| Protocol overlap | Weak | Everyone uses Aave/Uniswap (filtered out) |

```bash
# Standalone usage
python3 scripts/counterparty_graph.py addresses.csv -o counterparty.csv

# Profile single address
python3 scripts/counterparty_graph.py --profile 0x1234...

# Lower threshold for more results
python3 scripts/counterparty_graph.py addresses.csv --min-overlap 0.15

# Integrate with knowledge graph
python3 scripts/build_knowledge_graph.py run --layer counterparty
```

**Output example**:
```
🔴 HIGH [85%] 0x1234... ↔ 0x5678...
    Overlap: 65% weighted, 12 shared counterparties
    ⚠️ SHARED DEPOSITS: 2 (strong signal)
```

## Label Propagation Algorithm (NEW)

When you identify one wallet, automatically propagate that identity through the relationship graph with confidence decay. This is how Chainalysis scales - one identification unlocks many.

**Why it works**: If wallet A is identified as "Trend Research" and wallet B has 90% temporal correlation with A + is in the same cluster, B should inherit the label with decayed confidence.

**Relationship weights** (confidence decay per hop):
| Relationship | Weight | Rationale |
|--------------|--------|-----------|
| same_entity | 0.95 | Verified same entity |
| same_cluster | 0.90 | Detected cluster membership |
| shared_deposits | 0.90 | Same exchange user |
| temporal_correlation | 0.85 | Same operator timing |
| counterparty_overlap | 0.80 | Similar counterparties |
| funded_by | 0.75 | Funding relationship |

```bash
# Propagate from a newly identified address
python3 scripts/label_propagation.py --seed 0x1234... --identity "Trend Research"

# Run full propagation from all identified entities
python3 scripts/label_propagation.py --full

# Check what identities an unknown might inherit
python3 scripts/label_propagation.py --check 0x5678...

# Suggest identity for unknown based on graph connections
python3 scripts/label_propagation.py --suggest 0x5678...

# Integrate with knowledge graph
python3 scripts/build_knowledge_graph.py run --layer propagation
```

**Output example**:
```
Propagating 'Trend Research' from 0x1234...
  → 0x5678... = 'Trend Research (propagated)' (76%)
  → 0x9abc... = 'Trend Research (propagated)' (58%)

Propagation complete:
  Addresses reached: 12
  Labels applied: 4
```

## Safe Investigation Pipeline (NEW)

Integrated pipeline for Safe multisig investigation: signer clustering + multi-hop funding trace + pattern classification.

**Key insight**: Trace **signers**, not Safes. Shared signers reveal entity clusters.

```bash
# Investigate Safes from CSV
python3 scripts/investigate_safes.py safes.csv -o investigation.csv

# Single Safe (deep trace)
python3 scripts/investigate_safes.py --address 0x23a5e... --max-hops 10

# Update knowledge graph with findings
python3 scripts/investigate_safes.py safes.csv --update-kg
```

**What it does**:
1. Gets signers for each Safe via Safe API (rate limited to avoid 429s)
2. Clusters Safes by shared signers
3. Traces funding chain for each shared signer (multi-hop)
4. Classifies funding patterns (Coinbase Prime, Tornado, Binance, etc.)
5. Generates identity + confidence for each cluster

**Funding patterns detected**:
| Pattern | Confidence | Evidence |
|---------|------------|----------|
| coinbase_prime | 75% | Etherscan label "Coinbase Prime: Custody Deposit Funder" |
| tornado | 65% | Tornado.Cash contract in funding chain |
| circular | 55% | Safe funds its own signers |
| binance/ftx/etc. | 70% | CEX hot wallet in funding chain |

**Gotcha**: Safe API has aggressive rate limiting (~5 req then 429). Script includes 2s delay per request.

## Whale Investigation Workflow

Full methodology: `/on-chain-query` skill. See `references/investigation_status.md` for current progress.

```bash
# Quick pipeline
source .venv/bin/activate
python3 scripts/enrich_addresses.py addresses.csv -o enriched.csv
python3 scripts/cio_detector.py enriched.csv -o clusters.csv
python3 scripts/investigate_safes.py enriched.csv -o safes.csv  # NEW - for Safes
python3 scripts/temporal_correlation.py enriched.csv -o temporal.csv
python3 scripts/counterparty_graph.py enriched.csv -o counterparty.csv
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

### 2026-02-13: Safe Multisig Investigation Patterns

**Context**: Investigating top Safe wallets by borrowed amount.

**Key finding**: Trace **signers**, not just the Safe. Shared signers reveal entity clusters.

**Pattern discovered:**
```
Cluster A ($709M): 3 Safes with shared signer 0x67ef
  └── Funding: Tornado.Cash → 5 hops → signer
  └── Identity: Privacy-conscious institutional entity

Cluster B ($476M): 2 Safes with 3 shared signers
  └── Funding: Coinbase Prime Custody → signer
  └── Identity: US institutional client
```

**Etherscan labels that help:**
- "Coinbase Prime: Custody Deposit Funder" → institutional US client (75% confidence)
- "Smart Account by Safe" → multisig signer (no identity value)

**Investigation script:**
```bash
# Get Safe signers
cast call <SAFE> "getOwners()(address[])" --rpc-url $ETH_RPC_URL

# Trace each signer's first funder
curl "https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address=<SIGNER>&sort=asc&page=1&offset=5"

# Check funder for CEX labels
```

**Gotcha:** Use `txlistinternal` for addresses that interact via DeFi protocols. Regular `txlist` may show 0 transactions.

### 2026-02-13: Top "Whales" Are Often Bots - But Operators Are Still Targets

**Context**: Investigated top 5 addresses by cumulative borrowed ($6.8B, $1.4B, $1.3B, $1.2B, $1.1B).

**Finding**: 4 of 5 were bots or closed positions - but bots have operators:

| Rank | Borrowed | Type | BD Approach |
|------|----------|------|-------------|
| #1 | $6.8B | Flash loan bot | Trace deployer/operator |
| #2 | $1.4B | Known retail user | Already known |
| #3 | $1.3B | MEV bot | Trace Titan Builder relationship |
| #4 | $1.2B | Inactive since 2021 | Low priority |
| #5 | $1.1B | Active trader | Direct target |

**Key insight**: A $6.8B flash loan bot or MEV operation represents a sophisticated DeFi operator. The bot itself isn't the BD target, but the **operator** is. Different investigation approach:

| Target Type | Investigation Approach |
|-------------|------------------------|
| EOA wallet | Trace funding chain, check governance, ENS |
| Flash loan bot | Trace contract deployer, check other deployed contracts |
| MEV bot | Trace builder relationship, check MEV profits destination |
| Safe multisig | Trace signers, find shared signer clusters |

**Bot operator investigation pattern**:
```python
# For contract/bot addresses, trace the deployer
deployer = get_contract_creator(bot_address)  # From Etherscan API
other_contracts = get_contracts_deployed_by(deployer)  # Pattern of activity
profit_destination = trace_outflows(bot_address)  # Where do profits go?
```

**Bot detection heuristics** (for prioritization, not exclusion):
```python
is_flash_bot = borrowed_assets == ['USDC'] and current_balance < 100
is_mev_bot = funder in KNOWN_MEV_BUILDERS or account_age < 60
is_inactive = last_activity > timedelta(days=365)
```

### 2026-02-13: Behavioral Timezone Analysis Works

**Context**: $1.09B whale with no ENS, no governance, 10+ hop funding chain.

**Method**: Analyzed 100 transactions for timing patterns.

**Result**:
- Peak activity: 5-7 AM UTC
- Heavy Sunday activity (34 txs vs 3 on Saturday)
- Conclusion: **Asia-Pacific timezone** (HK/Singapore likely)

**Why it works**: 5-7 AM UTC = 1-3 PM in Hong Kong/Singapore (afternoon trading). Sunday activity = Monday morning Asia (first day of week).

**Timezone inference table**:
| Peak UTC | Sunday Heavy? | Likely Region |
|----------|---------------|---------------|
| 5-8 AM | Yes | Asia-Pacific |
| 13-16 | No | Americas |
| 8-12 | No | Europe |

### 2026-02-13: Known Whale Entities Reference

Discovered during investigation:

| Entity | Addresses | Holdings | Notes |
|--------|-----------|----------|-------|
| 7 Siblings | `0x28a55c4b...`, `0xf8de75c7...` | 1.21M ETH (~$5.6B) | Buys dips with leverage |
| Coinbase Prime 1 | `0xcd531ae9efcce...` | Varies | Institutional custody |

**7 Siblings strategy**: Deposits ETH on Spark, borrows USDC, buys more ETH on 10%+ dips. Tracked by Lookonchain.

### 2026-02-13: Bug Fix Session - Run Tests First

**Context**: BUG_REPORT.md listed 33 bugs as "NOT FIXED". Spent 30+ min re-reading code.

**Finding**: Most bugs (80%+) were already fixed. Documentation was stale.

**What wasted time**:
- Reading already-fixed code
- "Bugs" that were actually design choices or not bugs
- Tests that document behavior but don't assert correctness

**New workflow for bug fix sessions**:
```
1. pytest scripts/tests/test_bugs.py -v   # Run tests FIRST
2. Note which tests FAIL (actual bugs)
3. Fix only failing tests
4. Update BUG_REPORT.md in same commit as fix
```

**Prevention**: Keep BUG_REPORT.md in sync. Tests should fail when bug exists, pass when fixed.

See `references/bug_fix_retrospective.md` for full analysis.

### 2026-02-05: Skills = Methodology, References = Data

Skills became bloated with addresses. Now: methodology in skills, changing data in references.

## Resources

- [DuneSQL Functions](https://docs.dune.com/query-engine/Functions-and-operators)
- `.claude/skills/dune-analytics.md` — Full DuneSQL syntax guide
- `references/index_coop.md` — Product addresses
- `references/lending_whales.md` — Whale identities
- `references/cex_hot_wallets.md` — CEX address labels
- `/on-chain-query` skill — Full investigation methodology
