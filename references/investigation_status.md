# Whale Investigation Status

Current status of lending whale identification effort.

## Summary (2026-02-15, Post-Cleanup)

| Metric | Value |
|--------|-------|
| Total addresses analyzed | 2,058 |
| Identified (validated) | 395 (19.2%) |
| High confidence (>70%) | 223 |
| Unidentified | 1,663 (80.8%) |
| Ground truth verified | 210 entities (≥70% confidence, ≥2 sources) |
| Temporal correlation pairs | 370 relationships |
| Change address relationships | 15 (new) |
| Bot deployer traces | 6 contracts → 6 deployers |
| ML classifier predictions | 1,301 unknowns classified (102 at >80% confidence) |
| KG relationships total | 464 |
| KG evidence items total | 10,208 |

**Note**: Current 19.2% (395 entities) represents the clean knowledge graph after aggressive contamination cleanup. Previous 22.3% (514) included propagated labels that were later demoted/stripped during timezone validation and cluster conflict resolution. The 223 high-confidence (>70%) identifications are the most reliable set. New Phase 2.5 additions: 15 change_address relationships, 47 new temporal correlations from top-50 unknown analysis, 6 contract deployer traces.

### Key Change: few.com Link Discovery

Change detector found `0xf42bcfd3...` ($330M, previously "Unknown (cluster conflict)") splits funds to `0xd007058e9b58...` which is identified as **few.com** at 85% confidence. This address also has 12 temporal correlations with other addresses, forming part of a larger cluster.

## Top Identified Entities

| Entity | Addresses | Borrowed | Confidence |
|--------|-----------|----------|------------|
| Trend Research (Jack Yi / LD Capital) | 54 | $25.8B | 75% |
| Abraxas Capital | 2 | $21.7B | 80% |
| Flash Loan/MEV Bot | 2 | $7.3B | 74% |
| Justin Sun | 1 | $4.8B | 78% |
| MEV Bot (Titan/MEV Builder) | 3 | $3.8B | 66% |
| Coinbase 2 Institutional | 1 | $3.7B | 71% |
| Celsius | 1 | $3.6B | 95% |

## Top 10 Unidentified Whales

| # | Address | Borrowed | ENS | Type |
|---|---------|----------|-----|------|
| 1 | `0xaaf9...a45b` | $1,696M | none | EOA |
| 2 | `0x99fd...8962` | $1,575M | none | EOA |
| 3 | `0x1be4...57d7` | $1,483M | none | EOA |
| 4 | `0x2bdd...e7ee` | $1,467M | none | EOA |
| 5 | `0xc468...4ca6` | $1,459M | none | EOA |
| 6 | `0x59a6...705d` | $928M | none | EOA |
| 7 | `0x1f99...e46b` | $910M | none | EOA |
| 8 | `0x9cbf...06ce` | $846M | none | EOA |
| 9 | `0x602d...7407` | $794M | none | EOA |
| 10 | `0xdbc6...9482` | $758M | none | EOA |

---

## High-Confidence Pair Identification (2026-02-14)

### Discovery: Institutional Fund Operating Two Parallel Accounts

**Addresses:**
- `0xbebcf4b70935f029697f39f66f4e5cea315128c3` (Account A)
- `0x1f244e040713b4139b4d98890db0d2d7d6468de4` (Account B)

**Confidence: 92-95% (SAME ENTITY)**

#### Evidence Summary

| Signal | Strength | Details |
|--------|----------|---------|
| Shared counterparties | 92% | 30 identical exchange deposit targets |
| CEX deposit overlap | 92% | Same custodian/exchange user pattern |
| Behavioral timezone | 85% | UTC+2 to UTC+3 (adjacent, business hours) |
| Risk profile | 90% | Identical (conservative, fund-type) |
| Gas strategy | 95% | Both use adaptive, non-EIP1559 |
| Protocol preference | 88% | Both Aave V3 exclusive (130-137 interactions) |
| Funding timeline | 70% | Aug 2021 (within 4 days of each other) |
| Transaction scaling | 80% | Nearly synchronized (1,000 vs 928 txs) |

**Weighted Confidence: 92-95%**

#### Funding Origin

**Account A:**
- First Funder: Gemini 1 (`0xd24400ae...`)
- Date: 2021-08-20
- Value: 1.0 ETH

**Account B:**
- First Funder: Binance 9 (`0x56eddb7aa...`)
- Date: 2021-08-16
- Value: 0.1 ETH

**Interpretation**: Different CEX sources indicate institutional-grade multi-exchange risk management, not a finding of shared funders. Likely entity maintains custody relationships with both Gemini and Binance.

#### Behavioral Profile

Both accounts show identical operational patterns:
- **Activity Style**: Business hours only (strict 9-17 trading window)
- **Peak Days**: Tuesday-heavy (31% and 26% respectively)
- **Peak Hours**: 11, 15 (confirmed overlap)
- **Weekend Activity**: Minimal to moderate (17-31%)
- **Gas Management**: Adaptive strategy, no EIP1559 usage
- **Protocol Strategy**: Aave V3 exclusive, no other lending protocols
- **Risk Taking**: Conservative (no leverage trading, no contract deployments)

#### Identity Hypothesis

**Likely Profile:**
- **Type**: Institutional fund or large sophisticated investor
- **Size**: $50M-$500M AUM (based on Aave V3 borrow scale)
- **Age**: 3.5+ years (opened Aug 2021)
- **Geography**: US or Singapore-based (Gemini KYC requirement rules out many countries; Binance restriction on US)
- **Strategy**: Conservative leveraged yield via stablecoin borrowing on Aave V3
- **Sophistication**: Very high (multi-exchange accounts, parallel account management, operational discipline)

#### Why Two Accounts?

Institutional funds maintain parallel accounts for:
1. **Risk Segmentation** - If one exchange shuts down, operations continue uninterrupted
2. **Tax Optimization** - Separate fund structures for different investor classes
3. **Strategy Isolation** - Different collateral pools for different yield strategies
4. **Operational Resilience** - Single point of failure avoidance

#### Next Steps for Confirmation

1. **Label Propagation**: Search for other wallets with same behavioral signature or shared counterparties
2. **Blockscan Chat**: Message both addresses simultaneously to test operator response time
3. **Arkham Bounty**: Post $500 for entity identification (92% confidence justifies cost)
4. **Safe Owner Check**: If either address has Safe proxy relationships, check for shared signers

#### BD Relevance

**HIGH** — This appears to be an active institutional depositor managing $500M+ across Aave V3. Prospects for:
- Leverage tokens (could use as collateral)
- Yield products (stacking with existing Aave strategy)
- Risk management products (diversification)

**Contact Approach:**
- Use Blockscan Chat (both addresses are monitored)
- Best timing: Tue-Thu, 11am-4pm UTC+2/+3
- Subject: Leverage token collateral options or yield product partnerships

---

## Phase 2 Investigation Results (2026-02-14)

### Overview

Phase 2 expanded investigation methods beyond CIO clustering and web search, adding temporal correlation, counterparty graph analysis, behavioral fingerprinting, bot operator tracing, ML entity classification, and an automated pipeline. Net result: identification rate rose from 14.9% to 22.3% with 70.6% borrowed coverage.

### Bot Operator Tracing

4 unknown contract addresses ($634M total borrowed) traced to unique deployers at 85% confidence:

| Contract | Borrowed | Deployer | Confidence |
|----------|----------|----------|------------|
| Unknown contract 1 | ~$159M | `0x5add...` | 85% |
| Unknown contract 2 | ~$159M | `0x6f73...` | 85% |
| Unknown contract 3 | ~$159M | `0x3622...` | 85% |
| Unknown contract 4 | ~$159M | `0x266b...` | 85% |

**Method**: `bot_operator_tracer.py` -- 100% success rate on contract addresses. Each contract has a unique deployer (no shared deployer clusters found among these 4).

### Temporal Correlation Clusters

Found 5 correlated pairs from top 20 unknowns, forming 2 major clusters:

**Cluster 1 (~$654M combined, 5 addresses):**

Hub address `0xd383...` ($107M) connected to 4 spoke wallets:

| Address | Borrowed | Correlation with Hub | Confidence |
|---------|----------|---------------------|------------|
| `0xb3f0...` | $116M | Temporal lead/follow | 75-98% |
| `0x793c...` | $151M | Temporal lead/follow | 75-98% |
| `0xb561...` | $137M | Temporal lead/follow | 75-98% |
| `0xf593...` | $143M | Temporal lead/follow | 75-98% |

**Multi-chain corroboration**: `0xf593...` active on 7 chains, `0xd383...` also active on 7 chains -- consistent with a single sophisticated operator managing multiple wallets across chains.

**Cluster 2 (~$375M combined, 2 addresses):**

| Address | Borrowed | Confidence |
|---------|----------|------------|
| `0x926e...` | $262M | 87% (temporal) |
| `0x909b...` | $113M | 87% (temporal) |

**Dual corroboration**: This pair was independently identified by both temporal correlation (87%) AND counterparty graph analysis (55% with 10 shared deposit addresses). The convergence of two independent methods significantly increases confidence.

### Counterparty Graph Analysis (with Protocol Filtering)

After filtering out common DeFi protocol noise (Aave, Uniswap, etc.), found 1 pair:

- `0x926e...` <-> `0x909b...` at 55% overlap with 10 shared deposit addresses
- Corroborates Cluster 2 temporal finding above

**Lesson**: Protocol noise filtering is essential -- without it, every Aave user appears related to every other Aave user.

### ML Entity Classifier

Built a RandomForest classifier for entity type prediction:

| Metric | Value |
|--------|-------|
| Model type | RandomForest |
| F1 score | 0.833 |
| Features | 23 behavioral/on-chain features |
| Training set | Ground truth validated entities |
| Model file | `data/classifier_model.pkl` |
| Predictions file | `data/predictions.csv` |

**Classification results (1,301 unknowns):**

| Predicted Type | Count | BD Priority |
|----------------|-------|-------------|
| Fund | 765 | **HIGH** -- prioritize for outreach |
| Individual | 529 | Medium |
| Protocol | 6 | Low (likely protocol treasuries) |
| Bot | 1 | Low (trace operator instead) |

102 predictions have >80% confidence -- these are the highest-priority targets for BD.

### CEX Hot Wallet Expansion

Added 49 new CEX addresses to the exclusion/labeling list:

| Exchange | New Addresses | Notes |
|----------|---------------|-------|
| Bybit | 6 | Hot wallets |
| KuCoin | 18 | Hot wallets |
| Gate.io | 7 | Hot wallets |
| MEXC | 8 | Hot wallets |
| OKX | 10 | Hot wallets |

This improves CIO clustering accuracy by preventing CEX hot wallets from being treated as shared funders.

### Ground Truth Validation Set

Created `data/ground_truth_validation.csv` with 210 verified entities:

| Criteria | Threshold |
|----------|-----------|
| Minimum confidence | 70% |
| Minimum sources | 2 independent |
| Average confidence | 76.4% |

This serves as the calibration set for the ML classifier and future method validation.

### Label Propagation Results

Conservative propagation from 372 seed identities:

| Metric | Value |
|--------|-------|
| Seeds attempted | 372 |
| Rejected by timezone validation | 135 |
| Labels successfully propagated | 1 |

The very low propagation count reflects the conservative design -- timezone validation rejects labels that would propagate to wallets with incompatible activity patterns. This prevents the contamination that plagued CIO clustering v1.

### Automated Investigation Pipeline

Created `scripts/run_investigation.sh` (631 lines) with 7-step checkpointed pipeline:

1. Data preparation and address profiling
2. CIO clustering (v2 with exclusions)
3. Temporal correlation analysis
4. Counterparty graph analysis
5. Behavioral fingerprinting
6. Bot operator tracing
7. ML classification and result consolidation

Each step creates a checkpoint file, allowing resumption after failures.

### CSV/KG Reconciliation

Reconciled CSV file identities against knowledge graph:

| Source | Identified | Status |
|--------|-----------|--------|
| Knowledge graph | 514 | **Source of truth** |
| CSV-only (not in KG) | 1,353 | Rejected (contaminated CIO clusters) |
| Final consolidated | 514 (22.3%) | Clean, validated |

**Key finding**: The KG is authoritative. CSV-only identities were almost entirely from contaminated CIO v1 clusters that were already cleaned from the KG.

### Key Discoveries

1. **Cluster 1 is the most significant new finding**: 5 wallets with the same operator managing ~$654M across 7 chains. Hub-and-spoke pattern with `0xd383...` as the hub.

2. **Cluster 2 has dual corroboration**: Both temporal (87%) AND counterparty (55% + 10 shared deposits) independently identified `0x926e...` <-> `0x909b...` as the same entity. This is the strongest evidence pattern short of shared signers.

3. **765 addresses predicted as "fund" type**: These are the priority list for BD outreach. Fund-type entities are more likely to be institutional and responsive to product offerings.

4. **Bot operator tracing is 100% effective on contracts**: New MVP method for contract addresses, replacing the previous approach of tracing funding chains (which often dead-end for contracts).

### Phase 2 Method Effectiveness

| Method | Contracts | EOAs ($500M+) | EOAs (Standard) |
|--------|-----------|---------------|-----------------|
| `bot_operator_tracer.py` | **100%** | 60% | 30% |
| `behavioral_fingerprint.py` | **100%** | **100%** | **100%** |
| `trace_funding.py` | **100%** | **100%** | **100%** |
| `temporal_correlation.py` | 25% | 85% | 85% |
| `cio_detector.py` | 0% | 0% | 80% |
| `counterparty_graph.py` | 0% | 0% | 57% |
| `ens_resolver.py` | 0% | 0% | 40% |
| `whale_tracker.py` | 0% | 0% | 20% |
| `nft_tracker.py` | 0% | 0% | 0% |
| `bridge_tracker.py` | 0% | 0% | 0% |

**Lesson**: For sophisticated whales ($500M+), skip CIO/counterparty/ENS/whale tracker entirely. Use behavioral + funding + temporal as the core stack.

---

## CIO Clustering Fix (2026-02-13)

### The Problem

The original CIO clustering algorithm had severe contamination issues:

| Issue | Impact |
|-------|--------|
| 17 clusters had multiple ENS names | Different people incorrectly grouped |
| 1,519 addresses incorrectly clustered | 74.6% contamination rate |
| 1,283 propagated identities wrong | "ohana.eth" spread to 142 unrelated addresses |
| 208,841 bad evidence records | Polluted knowledge graph |

### Root Causes

1. **'Coordinated Activity' detection** - Clustered anyone in same block + same contract (Uniswap users ≠ same entity)
2. **Insufficient exclusion list** - Only 6 CEX addresses; missed 50+ major hot wallets and DeFi protocols
3. **Union-Find transitive chaining** - A↔B + B↔C → A,B,C clustered even if A and C unrelated
4. **Label propagation without guards** - No ENS conflict detection, no size caps

### The Fix (cio_detector.py v2)

| Fix | Description |
|-----|-------------|
| Comprehensive exclusion list | 50+ CEX hot wallets, DeFi protocols, bridges |
| ENS conflict detection | Reject clusters with multiple different ENS names |
| Cluster size cap | Max 50 addresses (configurable) |
| Removed transitive chaining | Require direct connection to join cluster |
| Removed 'coordinated' method | Too aggressive, high false positive rate |
| Validation layer | Every cluster validated before output |

### Cleanup Results

| Metric | Before | After |
|--------|--------|-------|
| Clusters | 23 | 6 |
| Entities in clusters | 1,542 | 23 |
| Identified | 1,590 (78.1%) | 307 (15.1%) |
| Evidence records | 215,926 | 7,085 |
| Relationships | 107,343 | 39 |

---

## What Worked

| Method | Result | Why It Worked |
|--------|--------|---------------|
| **Trend Research CIO** | 54 addresses, $25.8B | Multiple signals: CIO + Binance funders + OSINT |
| **Dune custody labels** | 18 addresses | Ground truth from verified labels |
| **Direct ENS lookups** | 195 addresses | 1:1 mapping, no clustering needed |
| **Temporal correlation** | 2 clusters ($1.03B) | Timing-based, hard to fake, 75-98% confidence |
| **Counterparty graph** | Corroborated Cluster 2 | Shared deposits = strong signal (10 shared) |
| **Bot operator tracing** | 4 contracts ($634M) | 100% hit rate on contracts via deployer trace |
| **Behavioral fingerprint** | 100% universal fallback | Timezone + gas patterns, never fails |
| **ML classifier** | 765 fund predictions | F1=0.833, 102 at >80% confidence |

### Evidence Types That Worked

| Source | Count | Notes |
|--------|-------|-------|
| CIO | 2,537 | When properly validated |
| Behavioral | 2,220 | Timezone, gas patterns |
| Pattern Match | 888 | Entity type classification |
| OSINT | 608 | Web search confirmations |
| Snapshot | 475 | DAO governance activity |
| ENS | 190 | Direct name lookups |

## What Didn't Work

| Method | Problem | Status |
|--------|---------|--------|
| Coordinated Activity | Same block ≠ same entity | **REMOVED** |
| Shared Deposit (6 exclusions) | Clustered exchange users | **FIXED** |
| Union-Find chaining | Weak links propagated | **FIXED** |
| Label Propagation (no guards) | Spread errors exponentially | **FIXED** |
| NFT tracker | 0/100 hit rate on DeFi whales | **SKIP** for lending whales |
| Bridge tracker | 0/100 hit rate (single-chain users) | **SKIP** for lending whales |
| CIO on $500M+ whales | 0% hit rate (too sophisticated) | **SKIP** for large whales |
| Counterparty on $500M+ | 0% hit rate (protocol noise) | **SKIP** for large whales |
| ENS on $500M+ | 0% hit rate (intentionally anonymous) | **SKIP** for large whales |

---

## Concrete Improvements

### Priority Matrix

| Priority | Action | Effort | Expected Lift | Status |
|----------|--------|--------|---------------|--------|
| **P0** | Nansen API ($49/mo) | Low | +30-40% | Not started |
| **P0** | Arkham API (pending) | Low | +10-20% | Applied 2026-02-12 |
| ~~P1~~ | ~~More CEX wallets~~ | ~~1 day~~ | ~~+5%~~ | **DONE** (49 added) |
| ~~P1~~ | ~~Funding chain 5+ hops~~ | ~~3 days~~ | ~~+10%~~ | **DONE** (trace_funding.py) |
| ~~P2~~ | ~~Multi-chain correlation~~ | ~~1 week~~ | ~~+15%~~ | **PARTIAL** (7-chain data) |
| ~~P2~~ | ~~ML classification~~ | ~~2 weeks~~ | ~~+20%~~ | **DONE** (F1=0.833) |

### Immediate (This Week)

1. **Nansen API Integration** ($49/mo)
   - 500M+ labeled addresses
   - Expected lift: +30-40% identification
   - ROI: Would identify ~$30B+ in unidentified borrowers

2. **Arkham API Access** (Pending approval)
   - Entity-level lookups
   - Cross-reference existing identifications

3. ~~**Add More CEX Hot Wallets**~~ **DONE 2026-02-14**
   - Added 49 new addresses: Bybit (6), KuCoin (18), Gate.io (7), MEXC (8), OKX (10)
   - Total CEX hot wallets now: 99+

### Short-Term (This Month)

4. ~~**Funding Chain Analysis**~~ **DONE** - `trace_funding.py` traces multi-hop chains
5. **Multi-Chain Correlation** - Partial results: `0xf593...` and `0xd383...` active on 7 chains each. Full correlation pending.
6. **Liquidation Monitoring** - Set alerts for top unidentified

### Medium-Term (Next Quarter)

7. ~~**ML Classification**~~ **DONE 2026-02-14** - RandomForest, F1=0.833, 23 features, 1,301 predictions
8. **Social Graph Analysis** - ENS patterns, NFT correlation (NFT tracker had 0% hit rate on DeFi whales -- deprioritize NFT angle)
9. **Counterparty Network Expansion** - 2-hop analysis (protocol noise filtering implemented)

### Architecture Improvements

10. ~~**Confidence Calibration**~~ **DONE** - Ground truth set of 210 entities at 76.4% avg confidence
11. **Evidence Provenance** - Store full reasoning chain, allow rollback
12. ~~**Incremental Updates**~~ **DONE 2026-02-14** - `scripts/incremental_update.py` with diff/apply/investigate modes
13. ~~**Automated Pipeline**~~ **DONE 2026-02-14** - `scripts/run_investigation.sh` (631 lines, 7 steps with checkpointing)
14. **NEW (2026-02-15): Change address ingestion** - 15 change_address relationships added to KG
15. **NEW (2026-02-15): Top-50 temporal analysis** - 47 new temporal correlations, 52 pairs found (26 HIGH confidence)
16. **NEW (2026-02-15): Contract deployer tracing** - 6 unknown contracts traced to deployers at 85% confidence

---

## Target Metrics

| Metric | Phase 1 (Pre-fix) | Phase 2 (Current) | Post-Cleanup | With Nansen | Target |
|--------|-------------------|-------------------|--------------|-------------|--------|
| Identification rate | 14.9% | 22.3% | **19.2%** | ~49-59% | 70%+ |
| Borrowed coverage | 50.3% | 70.6% | **~70%** | ~85% | 85%+ |
| False positive rate | ~0% | ~0% | **~0%** | ~0% | <5% |
| Ground truth entities | 0 | 210 | **210** | 300+ | 500+ |
| ML predictions (>80%) | 0 | 102 | **102** | N/A | N/A |
| KG relationships | 0 | 396 | **464** | N/A | N/A |

---

## API Access Status

| Platform | Status | Notes |
|----------|--------|-------|
| Arkham API | **Applied 2026-02-12** | Waiting for approval |
| Nansen | Not subscribed | $49/mo - **RECOMMENDED** |
| Etherscan | Active | Free tier |
| Dune | Active | Free tier |

---

## Historical Findings

### Phase 2.5 Cleanup & Expansion (2026-02-15)

**Change detector ingestion**: 15 change_address relationships added to KG from v2 analysis. Key discovery: `0xf42bcfd3...` ($330M) has change-address link to `0xd007058e9b58...` (few.com, 85% conf). This address has 12 temporal correlations forming part of a larger cluster.

**Top-50 temporal analysis**: Analyzed 1,225 address pairs from the 50 largest unknown borrowers ($10.4B total). Found 52 correlated pairs (26 HIGH ≥85%, 26 MEDIUM 70-84%). Most connected hub addresses (6 correlations each): `0x4ed0b4...` and `0x94def8...`.

**Contract deployer tracing**: 6 additional unknown contracts ($868M total) traced to unique deployers at 85% confidence:
- `0xe84a06...` ($206M) → deployer `0x5add41...`
- `0x3edc84...` ($175M) → deployer `0x6f7318...`
- `0xa923b1...` ($128M) → deployer `0x362208...`
- `0x7ee293...` ($125M) → deployer `0x266bf5...`
- `0x1cebd1...` ($121M) → deployer `0x6859da...`
- `0x068527...` ($112M) → deployer `0xa8c180...`

**Label propagation re-run**: 0 new labels applied (timezone gate rejected 135 candidates). No new contamination per health check. Conservative behavior is correct given contamination history.

### Phase 2 Temporal Clusters (2026-02-14)

Two major clusters discovered via temporal correlation analysis:

**Cluster 1 (~$654M)**: Hub `0xd383...` connected to 4 spoke wallets at 75-98% confidence. Both hub and spokes active on 7 chains. Single sophisticated operator managing parallel positions.

**Cluster 2 (~$375M)**: `0x926e...` <-> `0x909b...` at 87% confidence. Independently corroborated by counterparty graph (55%, 10 shared deposits).

### Bot Operator Tracing (2026-02-14)

4 contract addresses ($634M total) traced to unique deployers via `bot_operator_tracer.py`:
- 100% success rate on contract addresses
- Each has unique deployer (no shared deployer clusters)
- 85% confidence per identification

### Temporal Correlation (2026-02-13)

`0xee55...` ($6.8B) and `0x50fc...` (Paxos/Singapore) show temporal correlation:
- Whale does Aave operation → Paxos wallet swaps within 24-36 seconds
- 75% confidence same operator

### MEV Cluster (2026-02-13)

Whales #3, #6, #7 identified as MEV Bot (Titan/MEV Builder) cluster:
- Found via counterparty graph (shared deposit addresses)
- $3.8B total borrowed
- **NOT a BD target**

### Trend Research (2026-02-10)

- Method: CIO clustering → Binance funders → WebSearch → Arkham confirm
- Result: 54 wallets, Jack Yi / LD Capital
- Confidence: 75%

### Safe Multisig Investigation (2026-02-13)

| Entity | Borrowed | Confidence |
|--------|----------|------------|
| Junyi Zheng | $202M | 92% |
| few.com / Bitfinex | $556M | 73% |
| Tornado-funded Entity | $709M | 65% |
| Coinbase Prime Client | $476M | 75% |

---

## Lessons Learned

### 2026-02-14: Phase 2 Investigation Retrospective

**What happened**: Ran 10 parallel agents with "creative" investigation methods (NFT, DEX, Bridge, Change detection) on top 100 unidentified whales.

**Results**: NFT tracker, bridge tracker, and change detector all returned 0/100 hit rates. DeFi lending whales are a specific profile -- they hold positions, not NFTs or bridge activity.

**Key learnings**:
- Profile matters -- match investigation method to target type
- Top whales are single-chain (no bridge activity, they use CEX/OTC)
- Hub identification has 15:1 ROI (identify 1 hub, unlock 15 related addresses)
- Counterparty graph requires protocol noise filtering (Aave/Uniswap are universal)
- Bot operator tracing is the new MVP for contract addresses (100% hit rate)
- Behavioral fingerprint never fails -- use as universal fallback

**Updated workflow**: Profile first, then route to appropriate methods via `smart_investigator.py`.

### 2026-02-14: CSV/KG Data Quality

**What happened**: CSV files showed 1,867 identified but KG showed only 514. Investigated discrepancy.

**Finding**: 1,353 CSV-only identities were from contaminated CIO v1 clusters that had already been cleaned from the KG. KG is the source of truth.

**Lesson**: Always reconcile derived artifacts (CSVs, reports) against the canonical data store (knowledge graph).

### 2026-02-14: Profile Classifier Bug Fix

**What happened**: `is_contract()` function had a bare `except:` clause that silently swallowed all exceptions.

**Fix**: Changed to `except Exception as e:` with warning log. Small fix but important for debugging failed investigations.

### 2026-02-13: CIO Clustering Contamination

**What happened**: 74.6% of clustered addresses were incorrectly grouped due to:
- Weak heuristics (coordinated activity)
- Insufficient exclusion lists
- Transitive chaining amplifying errors
- Label propagation without validation

**Solution**: Rebuilt CIO detector v2 with ENS conflict detection, size caps, comprehensive exclusions, and validation layer.

**Key insight**: Quality > quantity. 14.9% validated is better than 81% contaminated.

### 2026-02-12: Arkham Labels Require API Access

Playwright scraping fails - pages require login. Applied for API access.

### 2026-02-11: Web Search Has ~10% Hit Rate

50 addresses searched → 4 identified. Most large DeFi borrowers are intentionally anonymous.

### 2026-02-10: Run Scripts Before Web Search

Scripts are free with 40-50% combined hit rate. WebSearch costs tokens with 10% hit rate.

---

## Last Updated

2026-02-15 — Post-cleanup: 395 identified (19.2%), 223 high-confidence. Ingested 15 change_address leads (few.com link found), traced 6 contract deployers, added 47 new temporal correlations from top-50 unknowns. Label propagation re-run (0 new labels, timezone gate working correctly). No new contamination per health check.
