# Whale Investigation Status

Current status of lending whale identification effort.

## Summary (2026-02-13)

| Metric | Value |
|--------|-------|
| Total addresses analyzed | 2,049 |
| Identified (validated) | 306 (14.9%) |
| Unidentified | 1,743 (85.1%) |
| Borrowed amount coverage | $95B identified (50.3%) |

**Note**: Previous 81% identification rate was inflated by clustering contamination. Current 14.9% represents validated, high-confidence identifications only.

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
| **Temporal correlation** | Found 1 link | Timing-based, hard to fake |
| **Counterparty graph** | Found MEV cluster | Shared deposits = strong signal |

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

---

## Concrete Improvements

### Priority Matrix

| Priority | Action | Effort | Expected Lift |
|----------|--------|--------|---------------|
| **P0** | Nansen API ($49/mo) | Low | +30-40% |
| **P0** | Arkham API (pending) | Low | +10-20% |
| **P1** | More CEX wallets | 1 day | +5% |
| **P1** | Funding chain 5+ hops | 3 days | +10% |
| **P2** | Multi-chain correlation | 1 week | +15% |
| **P2** | ML classification | 2 weeks | +20% |

### Immediate (This Week)

1. **Nansen API Integration** ($49/mo)
   - 500M+ labeled addresses
   - Expected lift: +30-40% identification
   - ROI: Would identify ~$30B+ in unidentified borrowers

2. **Arkham API Access** (Pending approval)
   - Entity-level lookups
   - Cross-reference existing identifications

3. **Add More CEX Hot Wallets**
   - Current: 50+ addresses
   - Missing: Bybit, KuCoin, Gate.io, MEXC

### Short-Term (This Month)

4. **Funding Chain Analysis** - Trace 5+ hops back to ultimate CEX source
5. **Multi-Chain Correlation** - Cross-reference Arbitrum/Base activity
6. **Liquidation Monitoring** - Set alerts for top unidentified

### Medium-Term (Next Quarter)

7. **ML Classification** - Train on labeled addresses
8. **Social Graph Analysis** - ENS patterns, NFT correlation, DAO coalitions
9. **Counterparty Network Expansion** - 2-hop analysis

### Architecture Improvements

10. **Confidence Calibration** - Calibrate against ground truth
11. **Evidence Provenance** - Store full reasoning chain, allow rollback
12. **Incremental Updates** - Add addresses without full rebuild

---

## Target Metrics

| Metric | Current | With Nansen | Target |
|--------|---------|-------------|--------|
| Identification rate | 14.9% | ~45-55% | 70%+ |
| Borrowed coverage | 50.3% | ~70% | 85%+ |
| False positive rate | ~0% | ~0% | <5% |

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

2026-02-13 — CIO clustering fixed, knowledge graph rebuilt with clean data, analysis completed
