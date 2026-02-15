# Whale Investigation — Next Steps

**Last updated:** 2026-02-16
**Current state:** 524/2,328 rows identified (22.5%), $153B/$221B borrowed (69.1%)
**Remaining:** 1,659 unknown addresses, ~$64B borrowed
**Isolated unknowns:** 1,549 (no graph edges — local scripts exhausted)

---

## Priority 1: Nansen API ($49/mo) — Highest ROI

**Status:** Not started
**Expected impact:** 500-650 new identifications (30-40% of unknowns)

500M+ labeled wallets. Query all 1,659 unknowns programmatically in one batch. This single action would more than double our identification rate.

**Steps:**
- [ ] Sign up at https://www.nansen.ai/plans ($49/mo annual)
- [ ] Get API key, review credit system (https://docs.nansen.ai/about/credits-and-pricing-guide)
- [ ] Write `scripts/nansen_lookup.py` — batch query all unknowns
- [ ] Ingest results into knowledge_graph.db
- [ ] Re-run label propagation to spread new identities through graph

---

## Priority 2: Background Deep Investigation (Top 20 Unknowns)

**Status:** Script ready (`scripts/deep_investigate.sh`)
**Expected impact:** 5-10 identifications on $5.5B in borrowed value
**Cost:** ~$3-5 on haiku, ~$20-30 on sonnet

Launch parallel Claude agents, each spending 20+ turns on one address (ZachXBT-style deep dive):

- Trace every significant in/out transaction via Etherscan API
- Follow money chains to final destination (not stop at 3 hops)
- Search Twitter/X for the address or its counterparties
- Check DeBank profile for current portfolio context
- Cross-reference every counterparty against our KG
- Check OFAC/sanctions lists
- Search for mentions in liquidation events, governance forums

**Top 20 targets:**

| Address | Borrowed ($M) |
|---------|--------------|
| `0xe051fb91ec09eefb77e7f7a599291bf921eb504d` | 502 |
| `0x9b4772e59385ec732bccb06018e318b7b3477459` | 430 |
| `0x701bd63938518d7db7e0f00945110c80c67df532` | 349 |
| `0x3ba21b6477f48273f41d241aa3722ffb9e07e247` | 331 |
| `0x3ee505ba316879d246a8fd2b3d7ee63b51b44fab` | 300 |
| `0x8af700ba841f30e0a3fcb0ee4c4a9d223e1efa05` | 273 |
| `0xdb7030beb1c07668aa49ea32fbe0282fe8e9d12f` | 265 |
| `0x6761826e71fa2f47fbd2db2eb9f94fbbd49a9e8a` | 263 |
| `0x11b50686d3983c14c0d0972a5e46e38e0d9b2e14` | 242 |
| `0x183c9077fb7b74f02d3badda6c85a19c92b1f648` | 231 |
| `0x3f3e305c4ad49271ebda489dd43d2c8f027d2d41` | 224 |
| `0xe84a061897afc2e7ff5fb7e3686717c528617487` | 206 |
| `0x32dd0756316b31d731aa6ae0f60b9b560e0ed92c` | 190 |
| `0x08c14b32c8a48894e4b933090ebcc9ce33b21135` | 190 |
| `0xd72626b46c6a94808365c0803f92903db87aa83c` | 188 |
| `0xcaf1943ce973c1de423fe6e9f1a255049e51666e` | 185 |
| `0xa25a9b7c73158b3b34215925796ce6aa8100c13a` | 179 |
| `0x3edc842766cb19644f7181709a243e523be29c4c` | 175 |
| `0x6e26d91c264ab73a0062ccb5fb00becfab3acc6b` | 171 |
| `0x7835b58a709f22f2aea9466f32f3f7fd4d46f777` | 170 |

**Run:**
```bash
cd ~/Projects/IndexCoop/dune-analytics
./scripts/deep_investigate.sh                    # Top 5, haiku
./scripts/deep_investigate.sh --model sonnet     # Top 5, better reasoning
./scripts/deep_investigate.sh 0xe051f... 0x9b47... 0x701bd...  # Specific addresses
```

---

## Priority 3: Arkham API

**Status:** Applied 2026-02-12, pending approval
**Expected impact:** 20-30% hit rate on unknowns

- [ ] Check approval status at intel.arkm.com/api
- [ ] Write `scripts/arkham_lookup.py` — batch query
- [ ] Ingest results into KG

---

## Priority 4: Free OSINT Sources

**Status:** Not systematically exploited yet

| Source | What It Has | How To Query | Hit Rate |
|--------|-------------|--------------|----------|
| Twitter/X advanced search | Whale trackers post addresses | `"0xABCD" site:twitter.com` | 15-20% for top whales |
| Lookonchain / OnchainLens | Track known whales daily | Search their feeds for address | 10-15% |
| OFAC SDN List | Sanctioned addresses | https://www.chainalysis.com/free-cryptocurrency-sanctions-screening-tools/ | Low but critical |
| Court filings (PACER/CourtListener) | Bankruptcy, SEC actions | Search for addresses in filings | 5% but high confidence |
| Etherscan comments | Community labels | Check address page comments | 5-10% |
| DeFi governance forums | DAO proposal discussions | Search Snapshot, Tally, forum posts | 5% |
| Liquidation trackers | Big liquidations go viral | Search "liquidated" + protocol name | Event-driven |
| DeBank social | Web3 profiles linked to addresses | Paste address into DeBank | 10% have profiles |

**Key insight:** Instead of searching for hex addresses (10% hit rate), search for the address's **counterparties**, **deployers**, and **funding sources** — which are more likely to be publicly known.

**Steps:**
- [ ] Build OSINT checklist into `deep_investigate.sh` prompt
- [ ] Scrape Etherscan comments for top 100 unknowns
- [ ] Check DeBank profiles for top 100 unknowns
- [ ] Cross-reference top 20 with OFAC sanctions screening

---

## Priority 5: MetaSleuth Address Label API (Free Tier)

**Status:** Not started
**Expected impact:** Supplementary to Nansen, covers 25+ chains

- [ ] Register at https://metasleuth.io/
- [ ] Review API docs: https://docs.metasleuth.io/blocksec-aml-api/address-label-api
- [ ] Write `scripts/metasleuth_lookup.py`
- [ ] Batch query unknowns

---

## Paid Tools Reference

| Tool | Cost | Labels | Best For | API |
|------|------|--------|----------|-----|
| [Nansen](https://www.nansen.ai/plans) | $49/mo (annual) | 500M+ wallets | Bulk lookup, smart money | Yes (credit-based) |
| [Arkham](https://www.arkham.com) | Free core + ARKM token | AI entity clustering | Individual deep dives | Intel Exchange + API |
| [Chainalysis](https://www.chainalysis.com/) | Enterprise ($$$$) | Largest DB (gov/law enforcement) | Compliance, AML | Contract only |
| [MetaSleuth](https://metasleuth.io/) | Free tier + paid | 25+ chains, label API | Fund tracing, forensics | Yes |
| [Breadcrumbs](https://www.breadcrumbs.app) | Free tier + paid | Fund flow visualization | Visual investigation | Limited |
| [DeBank](https://debank.com) | Free | DeFi positions, portfolio | Quick wallet inspection | Yes |
| [Zerion](https://zerion.io/api) | Free tier + paid | Portfolio, DeFi, NFTs | Developer API, positions | Yes (self-serve) |

**Recommendation:** Nansen ($49/mo) is the single highest-ROI spend. DeBank and MetaSleuth free tiers are useful supplements.

---

## Improvements Made (2026-02-16)

- [x] Fixed label propagation timezone gate (hard block → confidence penalty)
- [x] Fixed circular timezone reasoning
- [x] Made temporal correlations exempt from timezone validation
- [x] Added 47 new temporal correlation relationships (top 50 unknowns)
- [x] Added 15 change_address relationships from change detector
- [x] Traced 6 contract deployers
- [x] Cleaned 40 contaminated propagated labels
- [x] Removed 13 dead scripts and 12 orphaned docs
- [x] Updated CLAUDE.md, README.md, on-chain-query skill
- [x] Regenerated CSV: 503 → 524 identified rows (22.5%)

## Improvements Needed

- [ ] **Super-cluster validation:** Cross-cluster temporal correlations (90-98%) suggest "Asia-Pacific VC", "Atlantic/Brazil DeFi Fund", "European Institutional Fund" may be the SAME operator — needs manual validation
- [ ] **Pattern Match cleanup:** 888 evidence items at 1.6% hit rate — audit entity_templates in pattern_matcher.py, tighten or remove low-signal templates
- [ ] **few.com link resolution:** `0xf42bcfd3...` ($330M) has both change_address link to few.com (85%) and propagated "Asia-Pacific VC" label — needs manual resolution
- [ ] **Dead-end graph components:** 25 components with 56 addresses ($2.7B) have no seed identity — only external data (Nansen/Arkham) can unlock these
- [ ] **27 unknowns adjacent to identified:** Label propagation should have caught these — investigate why it didn't
- [ ] **Refresh Dune data:** CSV is from 2026-02-13 — borrowed amounts may have changed
- [ ] **Script consolidation:** `enrich_addresses.py` still tries to import deleted `cluster_addresses.py` (falls back gracefully, but should clean the import)
