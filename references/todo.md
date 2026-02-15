# Investigation TODO

Priority items for improving whale identification rate.

## P0 -- External API Integrations (Blocked on subscriptions/approvals)

- [ ] **Nansen API Integration** ($49/mo) -- Expected +30-40% identification
  - 500M+ labeled addresses; batch lookup 445 unknowns
  - ROI: ~$7B in newly-identified borrowers for $49
  - Action: Subscribe at nansen.ai, build `nansen_lookup.py`

- [ ] **Arkham API Integration** -- Expected +10-20% identification
  - Applied 2026-02-12, pending approval
  - `batch_arkham_check.py` already exists, needs API key
  - Action: Follow up on application at intel.arkm.com/api

## P1 -- Script Improvements

- [x] Expand CEX hot wallet exclusion list (Bybit, KuCoin, Gate.io, MEXC) -- Added 49 addresses (2026-02-14)
- [x] Fix profile_classifier: add `is_contract` check before routing (2026-02-14)
- [x] Counterparty graph: filter top-20 DeFi protocols before overlap calculation (2026-02-14)
- [x] Build `run_investigation.sh` automated pipeline with checkpointing (2026-02-14)
- [x] Build incremental update pipeline -- `scripts/incremental_update.py` with diff, apply, investigate modes (2026-02-14)

## P2 -- Analysis Runs

- [x] Run `bot_operator_tracer` on unknown contracts ($634M+ total) -- 4 deployers found at 85% confidence (2026-02-14)
- [x] Run temporal correlation on top unknowns -- Found 5 pairs, 2 clusters ($654M + $375M) (2026-02-14)
- [x] Run label propagation (full layer) -- 1 label applied, 135 rejected by timezone (2026-02-14)
- [x] Run `smart_investigator.py` batch on top 50 unknowns -- 50 profiled, 21 contracts + 29 EOAs, timezone fingerprints for all (2026-02-14)
- [x] Multi-chain correlation (Arbitrum + Base) -- Key addresses profiled across 7 chains (2026-02-14)

## P3 -- Infrastructure

- [x] ML entity classifier trained on 739 labeled entities -- F1=0.833, 1301 unknowns classified (2026-02-14)
- [x] Reconcile CSV and knowledge graph -- KG is source of truth, CSV contaminated by CIO (2026-02-14)
- [x] Consolidate duplicate CSVs into single source of truth -- `references/top_lending_protocol_borrowers_consolidated.csv` (2026-02-14)
- [x] Create ground truth validation set -- `data/ground_truth_validation.csv`, 210 entities at >=70% conf (2026-02-14)
- [x] Update investigation_status.md with all Phase 2 findings (2026-02-14)

## P4 -- Rate Limit Mitigations

- [ ] Etherscan API: consider $199/mo plan or multiple keys for batch operations
- [ ] Safe API: implement request queuing with exponential backoff

## Key Discoveries (2026-02-14)

- **Cluster 1 ($654M)**: Hub `0xd383...` connected to 4 wallets at 75-98% temporal confidence, active on 7 chains
- **Cluster 2 ($375M)**: `0x926e...` <-> `0x909b...` corroborated by temporal (87%) AND counterparty (55% + 10 shared deposits)
- **ML classifier**: 765 unknowns predicted as "fund" type (BD targets), 529 as individual
- **4 bot deployers** identified controlling $634M in contract-based borrowing

## Completed

- [x] CIO detector v2 rebuild (2026-02-13)
- [x] Cluster contamination cleanup (2026-02-13)
- [x] Phase 2 creative investigation (2026-02-14)
- [x] High-confidence institutional fund pair identification (2026-02-14)
- [x] CEX hot wallet expansion: +49 addresses (2026-02-14)
- [x] Profile classifier fix: is_contract error handling (2026-02-14)
- [x] Automated pipeline: run_investigation.sh (2026-02-14)
- [x] Temporal correlation: 2 clusters found (2026-02-14)
- [x] Counterparty graph with filtering (2026-02-14)
- [x] Multi-chain correlation profiling (2026-02-14)
- [x] ML entity classifier (F1=0.833) (2026-02-14)
- [x] CSV/KG reconciliation (2026-02-14)
- [x] Consolidated CSV export (2026-02-14)
- [x] Ground truth validation set (210 entities) (2026-02-14)
- [x] Label propagation run (conservative, 1 label) (2026-02-14)
- [x] Bot operator tracing: 4 deployers found (2026-02-14)
- [x] Smart investigator batch: 50 unknowns profiled (2026-02-14)
- [x] Incremental update pipeline: `incremental_update.py` (2026-02-14)
- [x] Investigation status updated with all Phase 2 findings (2026-02-14)

---
Last updated: 2026-02-14
