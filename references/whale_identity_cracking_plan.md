# Plan: Whale Identity Cracking System

## Problem Statement
- **2,274 unknown addresses** with $10M+ borrowed from Aave/Spark/Compound
- Current method: Manual WebSearch at **40K tokens per address** (~$10-20 each)
- Only **36 identified** so far (1.6%)
- BD team needs **contactable identities** (name, Twitter, company)

## Current Gaps

| Gap | Impact |
|-----|--------|
| No `cast`/Foundry integration | Can't batch-detect contract types |
| No Etherscan API | Can't trace funding origins at scale |
| No Safe API | 156 Safe wallets ($9.9B) with unknown owners |
| No batch processing | Each address requires manual investigation |
| No Nansen access | Missing 500M+ labels (highest coverage) |

## Success Patterns (from research)

| Method | Hit Rate | Scalable? |
|--------|----------|-----------|
| Arkham labels | 20-30% | Yes (scrape) |
| Etherscan labels | 10-15% | Yes (API) |
| ENS resolution | 10% (230 addresses) | Yes (API) |
| CEX funding trace | 30-40% | Yes (first-tx trace) |
| Safe signer resolution | High for DAOs | Yes (Safe API) |
| Manual OSINT | Case-by-case | No |

## Proposed Solution: 4-Phase Approach

### Phase 1: Build Automation (Week 1, $0)

**Scripts to create in `scripts/`:**

```
scripts/
├── enrich_addresses.py      # Core batch enrichment tool
├── batch_arkham_check.py    # Scrape Arkham labels (20-30% hit)
├── trace_funding.py         # CEX origin detection (30-40% hit)
├── resolve_safe_owners.py   # Safe API signer lookup
├── etherscan_labels.py      # Etherscan label API
└── README.md                # Documentation
```

**Required .env additions:**
```
ETHERSCAN_API_KEY=xxx        # Free tier: 5 req/sec, 100K/day
ETH_RPC_URL=xxx              # Alchemy/Infura for cast calls
```

**Token cost reduction:** 40K → ~100 tokens per address (400x cheaper)

### Phase 2: Batch Enrichment (Week 2, $0)

Run scripts on all 2,274 addresses:

| Script | Time | Expected Output |
|--------|------|-----------------|
| `etherscan_labels.py` | 12 min | 200-300 labels (10-15%) |
| ENS resolution | 20 sec | 230 ENS names |
| `trace_funding.py` | 30-60 min | 600-800 CEX traces (30-40%) |
| `batch_arkham_check.py` | 20-40 min | 400-600 labels (20-30%) |
| `resolve_safe_owners.py` | 5-10 min | 50-100 Safe identities |

**Expected outcome:** 300-500 identified (15-25%)

### Phase 3: Paid Tools (Week 3, $73/mo)

| Tool | Cost | Value |
|------|------|-------|
| **Nansen** | $49/mo | 500M+ labels, highest ROI |
| **LeakPeek** | $10/mo | ENS→email→social lookup |
| **OSINT Industries** | $24/mo | 1000+ source aggregator |

**Expected outcome:** +200-400 identified (10-20% of remaining)

### Phase 4: High-Value Targets (Week 4, $150-400)

- Post **5-10 Arkham bounties** @ $30-80 each for top unknowns
- Manual OSINT playbook for Tier 1 targets ($100M+)
- Expected: 10-20 institutional contacts

## Expected Outcomes

| Phase | Identified | Cumulative | Cost |
|-------|------------|------------|------|
| Phase 1-2 | 300-500 | 15-25% | $0 |
| Phase 3 | +200-400 | 25-45% | $73 |
| Phase 4 | +10-50 | 30-50% | $150-400 |
| **Total** | **600-1,000** | **30-50%** | **$223-473** |

**Remaining unknown:** 1,274-1,674 (50-70%) — privacy-conscious OGs, unreachable without subpoena

## Files to Create/Modify

### New Scripts (Priority Order)

1. **`scripts/enrich_addresses.py`**
   - Input: CSV of addresses
   - Output: Enriched CSV with contract_type, ens, labels, first_funder
   - Uses: Etherscan API, ENS resolver, web3.py

2. **`scripts/batch_arkham_check.py`**
   - Scrape `intel.arkm.com/explorer/address/{addr}` for labels
   - Rate limit: 1-2 req/sec (avoid IP ban)
   - Cache results for 7 days

3. **`scripts/trace_funding.py`**
   - Get first incoming ETH tx via Etherscan API
   - Match against CEX hot wallet database
   - Recurse up to 3 hops if needed

4. **`scripts/resolve_safe_owners.py`**
   - Call Safe Transaction Service API
   - Get `getOwners()` for each Safe
   - Cross-reference signers with known entities

5. **`scripts/etherscan_labels.py`**
   - Batch fetch Etherscan community + partner labels
   - 5 req/sec rate limit

### Config Updates

**`.env.example`** — add:
```
ETHERSCAN_API_KEY=your_key_here
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your_key
```

### Documentation

**`scripts/README.md`** — document:
- Required env vars
- Rate limits per API
- Usage examples
- Resuming failed runs

## Verification Plan

1. **Test on 50 addresses first** before full batch
2. **Compare with manual investigations** — should match findings
3. **Verify CEX traces** — spot-check against Etherscan
4. **Measure coverage** — track % identified per method

## Alternative Considered

**Continue manual WebSearch:**
- Cost: 2,274 × 40K tokens × $0.015 = **$1,364**
- Time: 2,274 hours
- Same 30-50% success rate

**This plan:** $223-473 total, 60-80 hours, **reusable automation**

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Arkham rate limits/IP ban | 1-2 req/sec, exponential backoff |
| Low Nansen ROI | Test on 100 addresses first, cancel if <5% new |
| Arkham bounty low response | Higher bounties ($50-80), detailed context |
| API changes break scripts | Version-pin deps, health checks |

## Success Criteria

**Minimum Viable:**
- 400+ identified (20%)
- 100+ contactable (name + Twitter/website)
- Scripts working end-to-end

**Target:**
- 600-1,000 identified (30-50%)
- 200+ contactable
- Full CRM export for BD team
