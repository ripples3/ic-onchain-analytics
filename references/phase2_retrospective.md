# Phase 2 Investigation Retrospective

**Date:** 2026-02-14

## What Worked

### Highly Effective (High ROI)

| Method | Hit Rate | Avg Confidence | Why It Worked |
|--------|----------|----------------|---------------|
| **Temporal Correlation** | 322 relationships | 85.8% | Detects same-operator wallets via coordinated timing. Nearly impossible to fake while maintaining operational efficiency. |
| **CIO Clustering** | 2,537 evidence items | 80.2% | Common Input Ownership from shared funders. Direct chain to exchange = identity anchor. |
| **ENS Resolution** | 190 items | 90.0% | Highest confidence when ENS exists. Many whales don't use ENS though. |
| **Snapshot Governance** | 475 items | 70.0% | Voting patterns reveal identity. Works for governance-active addresses. |
| **CrossChain Detection** | 149 items | 80.0% | Same address across chains confirms identity. |

### Moderately Effective

| Method | Hit Rate | Avg Confidence | Notes |
|--------|----------|----------------|-------|
| **Pattern Matching** | 888 items | 58.1% | Entity type classification works but doesn't give specific identity. |
| **Behavioral Analysis** | 2,220 items | 60.0% | Timezone/gas patterns useful for clustering, not identification. |
| **OSINT Web Search** | 608 items | 50.0% | ~10% hit rate on addresses. Only effective for known entities. |

## What Didn't Work

### Zero Results (Low ROI for DeFi Whales)

| Method | Result | Why It Failed |
|--------|--------|---------------|
| **NFT Tracker** | 0/100 | Top DeFi borrowers are institutional/bots - no PFP/status signaling. |
| **Bridge Tracker** | 0/100 | Single-chain Ethereum specialists. Cross-chain via CEX/OTC (off-chain). |
| **Change Detector** | 0/100 | Designed for ETH transfers, not token-based DeFi. |
| **DEX Analyzer** | 0 trades | These are position holders, not traders. No DEX activity to analyze. |

### Underperformed Expectations

| Method | Expected | Actual | Issue |
|--------|----------|--------|-------|
| **Label Propagation** | 30% expansion | 16.3% | Limited reach - most whales are isolated nodes without identified neighbors. |
| **Counterparty Graph** | 85%+ | 56.8% avg | Too many false positives from shared protocol interactions (Aave, Uniswap). |
| **Safe Signer Analysis** | Find shared signers | 0 Safes in top hubs | Top borrowers are EOAs, not multisigs. |

## Root Cause Analysis

### Why NFT/Bridge/Change Failed

**Profile mismatch:** These scripts were designed for general wallet investigation, not DeFi lending whales specifically.

- **DeFi lending whales** = Institutional funds, bots, professional operators
- **NFT holders** = Retail, influencers, collectors
- **Bridge users** = Cross-chain arbitrageurs, retail
- **Change patterns** = Bitcoin-style UTXOs, not token transfers

**Lesson:** Scripts need to match the target profile. Run a profile analysis BEFORE choosing investigation methods.

### Why Propagation Underperformed

**Network structure problem:** Top whales are deliberately isolated.

```
Normal user network:     Whale network:
    A---B                    A
    |\ /|                    |
    | X |                    B (CEX)
    |/ \|                    |
    C---D                    C (isolated)
```

Sophisticated operators minimize on-chain connections to prevent exactly this kind of analysis.

### Why Counterparty Graph Had Lower Confidence

**Protocol noise:** Everyone uses Aave, Uniswap, etc. Shared protocol interactions create false positive correlations.

**Fix needed:** Filter out common protocols (Aave, Uniswap, Curve, etc.) before calculating overlap. Only count unique counterparties like OTC desks, market makers.

## Concrete Improvements

### 1. Add Target Profile Classifier (HIGH PRIORITY)

```python
# scripts/profile_classifier.py
def classify_target(addresses):
    """Classify addresses BEFORE running investigation scripts."""
    profiles = []
    for addr in addresses:
        profile = {
            "is_defi_lender": check_aave_morpho_activity(addr),
            "is_nft_holder": check_nft_holdings(addr),
            "is_trader": check_dex_activity(addr),
            "is_bridge_user": check_bridge_history(addr),
            "is_governance_active": check_snapshot_votes(addr),
        }
        profiles.append(profile)

    # Return recommended scripts per address
    return recommend_scripts(profiles)
```

**ROI:** Avoid running useless scripts (0/100 hit rate). Save API calls and time.

### 2. Fix Counterparty Graph Protocol Filtering

```python
# In counterparty_graph.py
PROTOCOL_FILTER = {
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",  # Aave V2
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",  # Aave V3
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2
    # ... more common protocols
}

def get_unique_counterparties(address):
    """Only count counterparties that aren't common protocols."""
    counterparties = get_all_counterparties(address)
    return [c for c in counterparties if c not in PROTOCOL_FILTER]
```

**Expected improvement:** Counterparty confidence from 56.8% → 75%+

### 3. Implement Hub-First Investigation Strategy

Current flow:
```
All 100 addresses → Run all scripts → Hope for hits
```

Improved flow:
```
1. Find hub addresses (temporal correlation network analysis)
2. Deep investigate ONLY hubs (5-10 addresses)
3. Propagate identities to spoke addresses (30+ per hub)
```

**ROI:** 15:1 (identify 1 hub → unlock 15 related addresses)

### 4. Add Deployer Tracing for Bots

```python
# scripts/bot_operator_tracer.py
def trace_bot_operator(contract_address):
    """For flash loan/MEV bots, trace the operator instead."""
    deployer = get_contract_deployer(contract_address)
    other_contracts = get_contracts_by_deployer(deployer)
    profit_destinations = trace_outflows(contract_address)

    # The operator is the EOA receiving profits
    return {
        "deployer": deployer,
        "related_contracts": other_contracts,
        "likely_operator": profit_destinations[0] if profit_destinations else None
    }
```

**Applicable to:** Top 3 addresses ($6.8B, $2.4B, $1.4B) which are flash loan bots.

### 5. Improve Label Propagation with Path Diversity

Current: Single-path propagation with linear decay.

Improved:
```python
def propagate_with_path_diversity(seed_address, identity):
    """Boost confidence when multiple independent paths lead to same identity."""
    paths = find_all_paths_to_identified_entities(seed_address)

    if len(paths) >= 3:
        # Multiple independent sources = higher confidence
        confidence_boost = 0.15
    elif len(paths) >= 2:
        confidence_boost = 0.10
    else:
        confidence_boost = 0

    return base_confidence + confidence_boost
```

### 6. Add Investigation Effectiveness Tracking

```python
# scripts/track_effectiveness.py
def log_investigation_result(method, address, result, confidence):
    """Track which methods work for which address profiles."""
    db.execute("""
        INSERT INTO investigation_log
        (method, address_profile, result, confidence, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (method, get_profile(address), result, confidence, now()))

# Query later:
# SELECT method, address_profile, AVG(confidence), COUNT(*)
# FROM investigation_log
# WHERE result = 'identified'
# GROUP BY method, address_profile
```

**Purpose:** Build data on what works for which profiles → auto-recommend scripts.

## Updated Method Selection Matrix

| Target Profile | Use These | Skip These |
|----------------|-----------|------------|
| **DeFi Lender** | Temporal, CIO, Funding Trace, Pattern Match | NFT, Bridge, Change, DEX |
| **NFT Whale** | NFT Tracker, ENS, Governance | Bridge, Change |
| **DEX Trader** | DEX Analyzer, Temporal, Counterparty | NFT, Governance |
| **Bridge User** | Bridge Tracker, CrossChain | NFT, DEX |
| **Bot/Contract** | Deployer Trace, Funding Trace | All social methods |

## Summary

### Phase 2 Learnings

1. **Profile matters:** Match investigation method to target profile.
2. **Hub strategy wins:** 15:1 ROI on hub identification.
3. **Temporal correlation is gold:** 85.8% avg confidence, hardest to fake.
4. **Remove noise:** Protocol filtering needed for counterparty analysis.
5. **Bots need different approach:** Trace deployer/operator, not the contract.

### Recommended Changes to CLAUDE.md

Add to investigation workflow:
```
0. PROFILE FIRST: Run profile_classifier.py before any investigation
1. HUB IDENTIFICATION: Find temporal correlation hubs (network analysis)
2. DEEP INVESTIGATE HUBS: Only 5-10 addresses, full pipeline
3. PROPAGATE: Use hub identities to label 30+ spoke addresses
```

### Scripts to Deprecate for DeFi Whale Research

- `nft_tracker.py` (0% hit rate on lending whales)
- `bridge_tracker.py` (0% hit rate on lending whales)
- `change_detector.py` (not applicable to token transfers)

### Scripts to Improve

- `counterparty_graph.py` → Add protocol filtering
- `label_propagation.py` → Add path diversity scoring
- Add new: `profile_classifier.py`, `bot_operator_tracer.py`
