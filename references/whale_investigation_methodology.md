# Whale Investigation Methodology

> Systematic approach for identifying 1,955 unknown whale addresses ($200B+ borrowed)
> Based on ZachXBT, Chainalysis, Nansen, and academic research (Feb 2026)

---

## Executive Summary

**Goal:** Identify institutional whales for BD outreach from 1,955 unidentified addresses.

**Expected yield:**
- 50-100 medium+ confidence identifications
- 10-20 viable BD targets
- 2-5 partnership conversations

**Core principle:** Layer multiple heuristics. Single method = 70% accuracy. Combined = 90%+.

---

## Phase 1: Triage & Quick Labeling (Day 1-2)

### 1.1 Prioritize by Value

```sql
-- Top 100 unidentified by borrowed amount
SELECT address, total_borrowed_m, protocol
FROM whale_data
WHERE identity IS NULL OR identity = ''
ORDER BY total_borrowed_m DESC
LIMIT 100;
```

**Why:** $1B whale worth 100x the effort of $10M whale for BD.

### 1.2 Quick Label Pass

**Tool priority:**
1. **Etherscan labels** — Free, instant, 20-30% hit rate
2. **Arkham entity lookup** — Best free tool, 40-50% hit rate
3. **DeBank profile** — Shows DeFi positions, sometimes has names

**Batch approach:**
```bash
# For each address, check in parallel:
- intel.arkm.com/explorer/address/{addr}
- etherscan.io/address/{addr}
- debank.com/profile/{addr}
```

**Output:** Categorize as:
- `LABELED` — Known entity (Abraxas, Celsius, etc.)
- `PROTOCOL` — DeFi protocol/vault (skip for BD)
- `CEX_LINKED` — Funded by known CEX (investigate further)
- `UNKNOWN` — No labels found (deep investigation needed)

---

## Phase 2: Clustering Analysis (Day 3-5)

### 2.1 Common Input Ownership (CIO) - EVM Adapted

**Bitcoin CIO:** Multiple inputs in same tx = same owner (100% accurate)

**EVM equivalent heuristics:**

| Method | Description | Confidence |
|--------|-------------|------------|
| **Circular funding** | A→B→C→A pattern | HIGH |
| **Common funder** | Same source within 24h | MEDIUM-HIGH |
| **Coordinated activity** | Same block transactions | MEDIUM |
| **Shared deposits** | Same CEX deposit address | HIGH |

**Script:** `scripts/cio_detector.py`

```bash
python3 scripts/cio_detector.py addresses.csv --methods circular,common_funder,shared_deposits
```

### 2.2 Funding Chain Analysis

**Most reliable signal:** Trace back to CEX withdrawal.

```
Whale Address
    ↓ trace backwards
Intermediate wallet (optional)
    ↓
CEX Hot Wallet (Binance 14, Kraken 4, etc.)
```

**Known CEX hot wallets:**

| CEX | Address | Label |
|-----|---------|-------|
| Binance | 0x28c6...9d60 | Binance 14 |
| Binance | 0x21a3...8549 | Binance 15 |
| Binance | 0xdfd5...0f16 | Binance 16 |
| Binance | 0x56ed...1b49 | Binance 17 |
| Binance | 0x9696...1c34 | Binance 18 |
| Binance | 0xf977...8317 | Binance 20 |
| Kraken | 0x267b...fdc0 | Kraken 4 |
| Coinbase | 0x7cd0...c912 | Coinbase 2 |
| Poloniex | 0x5e57...52a4 | Poloniex 4 |

**What it tells us:**
- Same CEX funder = likely same entity (or same OTC desk client)
- Funding timing correlation strengthens the link
- Withdrawal amounts can indicate position sizing strategy

### 2.3 Deposit Address Reuse

**Most effective clustering technique** (per academic research).

If two wallets deposit to the SAME exchange deposit address → same user.

```sql
-- Find wallets depositing to same address
SELECT
  t1.from as wallet_1,
  t2.from as wallet_2,
  t1.to as shared_deposit,
  'deposit_reuse' as method
FROM erc20_transfers t1
JOIN erc20_transfers t2
  ON t1.to = t2.to
  AND t1.from != t2.from
  AND ABS(date_diff('hour', t1.block_time, t2.block_time)) < 24
WHERE t1.to IN (SELECT address FROM known_exchange_deposits)
  AND t1.from IN (SELECT address FROM target_whales);
```

---

## Phase 3: Cross-Chain Correlation (Day 6-7)

### 3.1 Same Address on Multiple Chains

Check if whale address exists on:
- Arbitrum
- Base
- Polygon
- Optimism

**Why:** Activity on multiple chains reveals more about entity type.

### 3.2 Bridge Transaction Matching

**ABCTracer methodology:**
1. Find deposits to bridge contracts on source chain
2. Match withdrawals on destination chain by:
   - Time window: ±1 hour
   - Amount variance: ±2%
   - Token type match

**Major bridges to track:**
- Stargate (institutional)
- Across
- Native L2 bridges (Arbitrum, Optimism, Base)

---

## Phase 4: Off-Chain Correlation (Day 8-10)

### 4.1 ENS Reverse Lookup

```bash
# Check if address has ENS
cast call 0x231b0Ee14048e9dCcD1d247744d114a4EB5E8E63 \
  "getName(address)(string)" <ADDRESS> --rpc-url $ETH_RPC_URL
```

**ENS → Identity pipeline:**
1. Resolve ENS name
2. Google search the name
3. Check Twitter for .eth username
4. Check governance voting with that ENS

### 4.2 Governance Voting Analysis

**Key protocols to check:**
- Aave (large whales often vote)
- Compound
- ENS DAO
- Uniswap

**Script:** `scripts/governance_scraper.py`

```bash
python3 scripts/governance_scraper.py addresses.csv --protocols aave,compound,ens
```

**What voting reveals:**
- Voting power = position size proxy
- Delegation patterns = institutional behavior
- Vote timing = timezone/entity type hints

### 4.3 Social Media Correlation

**Search pattern:**
```
"{address}" site:twitter.com
"{address}" site:etherscan.io/idm
"{ens_name}" crypto fund
```

**What to look for:**
- Fund managers posting addresses
- Protocol announcements mentioning whale
- Leaked screenshots with addresses

### 4.4 Leaked Database Search (Optional)

**Tools:** LeakPeek ($10/mo), Snusbase ($5-16/mo)

**When to use:** Only if ENS reveals email or username.

**Legal note:** Use for investigation only, not harassment.

---

## Phase 5: Verification & Confidence Scoring (Day 11-12)

### 5.1 Multi-Source Verification

**Rule:** Never trust single source. Cross-verify with 2+ methods.

| Sources Agreeing | Confidence |
|------------------|------------|
| 3+ sources | 85-95% |
| 2 sources | 60-75% |
| 1 source | 40-50% |
| Sources conflict | 20-30% |

### 5.2 Institutional vs Retail Classification

| Signal | Institutional | Retail |
|--------|--------------|--------|
| Wallet age | 2+ years | <1 year |
| Activity | Regular, scheduled | Sporadic |
| Position structure | Multi-wallet | Single wallet |
| Governance | Delegated, consistent | None/ad-hoc |
| Exchange usage | OTC desk | Retail exchange |
| Position size | >$50M single token | <$10M typical |
| Mixer usage | 0% | 5-30% |

### 5.3 Confidence Score Framework

```
HIGH (90%+):
- ENS domain matches fund name
- Official SEC 13F filing
- Verified Twitter with branding
- Multiple governance delegations

MEDIUM-HIGH (70-90%):
- Large positions across tokens (>$50M)
- Regular rebalancing pattern
- Specialized DeFi usage (Lido, etc.)
- Delegation to known VC delegates

MEDIUM (50-70%):
- Large holdings, recent wallet
- Some governance participation
- Clustered with other addresses

LOW (<50%):
- Single large transaction then inactive
- Heavy mixer usage
- No on-chain institutional signals
```

---

## Phase 6: Documentation & BD Handoff (Day 13-14)

### 6.1 Output Format

For each identified whale:

```markdown
## {Identity Name}

**Confidence:** HIGH/MEDIUM-HIGH/MEDIUM/LOW
**Address(es):** 0x...
**Total Borrowed:** $XXX M
**Protocol(s):** Aave, Spark, etc.

### Evidence
1. [Source 1]: Description
2. [Source 2]: Description
3. [Source 3]: Description

### BD Notes
- Contact method: LinkedIn / Twitter / Blockscan Chat
- Relevant products: ETH2x, BTC2x, etc.
- Potential interest: [Why they might want Index products]

### Red Flags (if any)
- [Any concerns about this entity]
```

### 6.2 BD Priority Tiers

| Tier | Criteria | Action |
|------|----------|--------|
| **A** | HIGH confidence + >$100M + institutional signals | Direct outreach |
| **B** | MEDIUM-HIGH + >$50M | Research more, then outreach |
| **C** | MEDIUM + >$20M | Monitor, opportunistic outreach |
| **D** | LOW or <$20M | Skip for now |

---

## Tools Summary

### Free (Use First)

| Tool | Purpose | URL |
|------|---------|-----|
| Etherscan | Labels, first funder | etherscan.io |
| Arkham | Entity labels, clustering | intel.arkm.com |
| DeBank | DeFi positions | debank.com |
| Dune | Custom queries | dune.com |
| Blockscan Chat | Direct wallet messaging | chat.blockscan.com |

### Paid (If Needed)

| Tool | Purpose | Cost |
|------|---------|------|
| Nansen | Smart money labels | $49-99/mo |
| Arkham API | Batch lookups | Variable |
| LeakPeek | Leaked DB search | $10/mo |

### Scripts (This Repo)

| Script | Purpose |
|--------|---------|
| `enrich_addresses.py` | Master orchestration |
| `cio_detector.py` | CIO clustering |
| `trace_funding.py` | CEX funding origin |
| `governance_scraper.py` | Snapshot voting |
| `verify_identity.py` | Multi-source verification |
| `update_identities.py` | Apply findings to CSV |

---

## Anti-Patterns (What NOT to Do)

1. **Single source attribution** — Always verify with 2+ methods
2. **Assuming Arkham/Nansen is complete** — They miss 30-50% of whales
3. **Ignoring cross-chain** — 40%+ of activity is multi-chain now
4. **Over-clustering** — Require 2+ heuristics before grouping
5. **Chasing mixers** — If whale uses mixers heavily, they're not institutional
6. **WebSearch for Arkham labels** — Labels aren't web-indexed, go direct

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Addresses processed | 200/week |
| Quick label hit rate | 40-50% |
| Deep investigation yield | 30-40% of unknowns |
| BD-ready identifications | 10-20/month |
| Partnership conversations | 2-5/quarter |

---

## Appendix: Academic References

- "Bitcoin address clustering method based on multiple heuristic conditions" (IET Blockchain, 2022)
- "Heuristic-Based Address Clustering in Bitcoin" (IEEE, 2020)
- "Track and Trace: Automatically Uncovering Cross-chain Transactions" (arxiv:2504.01822)
- "Analyzing voting power in decentralized governance" (ScienceDirect, 2024)
- "Heuristics for Detecting CoinJoin Transactions" (arxiv:2311.12491)
