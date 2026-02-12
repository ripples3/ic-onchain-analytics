# Whale Investigation Status

Current status of lending whale identification effort.

## Summary (2026-02-12)

| Metric | Value |
|--------|-------|
| Total addresses analyzed | 1,205 |
| Identified (HIGH confidence) | 867 (72%) |
| Unidentified | 338 (28%) |
| Top 10 unidentified | 10 (see below) |

## Top 10 Unidentified Whales

These are the largest unidentified borrowers by total borrowed amount.

| # | Address | Best Signal | Confidence | Notes |
|---|---------|-------------|------------|-------|
| 1 | `0xee55...0bfc` | UTC-2, fund pattern | 58% | No governance, no NFTs |
| 2 | `0xc468...4ca6` | Multi-chain (2), UTC+7 | 67% | Active on ETH + Arb |
| 3 | `0xf72d...6bf4` | UTC+3 only | 60% | Single chain |
| 4 | `0x3aa3...3187` | UTC+0, spot trader | 60% | Weekday only |
| 5 | `0x6c2a...4777` | UTC+2, fund pattern | 58% | Conservative |
| 6 | `0x5814...8de4` | UTC+4 only | 60% | Single chain |
| 7 | `0xc362...5fb7` | UTC+4 only | 60% | Single chain |
| **8** | **`0xccee...6fa7`** | **FTX-funded + WLFI voter** | **85%** | **STRONG LEAD** |
| 9 | `0xd938...48dd` | Binance-funded, multi-chain | 67% | Active on 3 chains |
| 10 | `0x50fc...bf21` | UTC-3, multi-chain | 71% | Active on 2 chains |

## Best Lead: WLFI Whale (#8)

**Address**: `0xccee77e74c4466df0da0ec85f2d3505956fd6fa7`

| Finding | Detail |
|---------|--------|
| Funding | FTX 2 → June 11, 2022 (5 months before collapse) |
| Borrowed | $624M on Aave |
| Governance | WLFI voter (8.67M voting power) |
| Timezone | UTC+7 (Thailand/Vietnam/Indonesia) |
| Entity Type | Sophisticated institutional fund |
| Pattern | Irregular weekday activity only |

**Likely Profile**: Asian fund that:
1. Exited FTX before collapse (smart money)
2. Invested in Trump's World Liberty Financial
3. Possibly one of two whales controlling 56% of WLFI governance

## Scripts Run on Top 10

| Script | Result |
|--------|--------|
| `governance_scraper.py` | 1/10 with activity (only WLFI whale) |
| `cio_detector.py` | 0 clusters (no funding connections between them) |
| `resolve_safe_owners.py` | 0 Safe wallets (all EOAs) |
| `trace_funding.py` | Found: Coinbase, FTX, Binance funders |
| `behavioral_fingerprint.py` | All have patterns but no identities |
| `whale_tracker_aggregator.py` | 0 matches in known whale databases |

## Why Most Remain Unidentified

1. **No governance footprint** — No DAO votes, no ENS names
2. **No cross-wallet links** — CIO clustering found 0 connections
3. **All EOAs** — No multisig ownership to trace
4. **Deliberately anonymous** — Large DeFi borrowers with zero public traces

## Next Steps

| Action | Status | Expected Impact |
|--------|--------|-----------------|
| Arkham API access | Applied (waiting) | Entity-level lookups |
| Nansen subscription | Not started | +30-40% identification |
| WLFI investor research | In progress | May ID whale #8 |
| Monitor for liquidations | Ongoing | Identity surfaces in news |

## API Access Status

| Platform | Status | Notes |
|----------|--------|-------|
| Arkham API | **Applied 2026-02-12** | Waiting for approval (1-3 days) |
| Nansen | Not subscribed | $49/mo, considering |
| Etherscan | Active | Free tier |
| Dune | Active | Free tier |

## Historical Identifications

### Trend Research (2026-02-10)
- **Method**: CIO clustering → Binance funders → WebSearch → Arkham confirm
- **Result**: 55 wallets, Jack Yi / LD Capital
- **Confidence**: 95%

### Justin Sun (2026-02-11)
- **Method**: WebSearch for large Aave positions
- **Result**: Multiple wallets confirmed
- **Confidence**: 90%

### World Liberty Financial (2026-02-11)
- **Method**: WebSearch for WLFI governance
- **Result**: 2 addresses linked to WLFI project
- **Confidence**: 85%

## Last Updated

2026-02-12 — Completed all script runs on top 10, applied for Arkham API
