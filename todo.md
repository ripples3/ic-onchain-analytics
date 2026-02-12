# Dune Analytics TODO

## Open

### Priority

- [ ] **Query 3806801 still timing out** - `ethereum.logs` scan is the bottleneck. Options:
  1. Check Dune for decoded Pendle tables (`pendle_ethereum.*_evt_SwapPtAndToken`)
  2. Check Dune for decoded Across tables
  3. Restructure like 3806854 (remove gap-fill, have 3994496 do it)
  4. Run on larger engine if it's a materialized view with scheduled refresh

- [ ] **Fix Arbitrum iBTC2x/iETH2x missing components** - Composition events only track `aArbUSDCn`, missing collateral (aArbWETH/aArbWBTC) and debt (variableDebtArbUSDCn). This causes `debt=0` and `leverage_ratio=1`.

  **Root cause**: Query 5140916 (`result_multichain_composition_changes_product_events`) pulls from SetToken event tables, but **Arbitrum products have NO position edit events**.

  **Investigation findings**:
  | Chain | Creation Components | Position Events |
  |-------|---------------------|-----------------|
  | Base iBTC2x | ? | defaultposition (aBasUSDC) + externalposition (cbBTC) ✅ |
  | Arbitrum iBTC2x | Only aArbUSDCn | **NONE** ❌ |

  - Base uses `externalpositionunitedited` for collateral tracking (cbBTC)
  - Arbitrum has ZERO events in `defaultpositionunitedited` or `externalpositionunitedited`
  - Only component tracked is from `settokencreator_call_create` (aArbUSDCn)

  **Next steps**:
  1. Check if Arbitrum uses different event tables (`componentadded`, `externalpositionmoduleadded`, etc.)
  2. May need to query Aave directly for Arbitrum leverage positions
  3. Or Arbitrum products use a completely different architecture

  **Addresses**:
  - Arbitrum iBTC2x: `0x304f3eb3b77c025664a7b13c3f0ee2f97f9743fd`
  - Arbitrum iETH2x: `0x6a21af139b440f0944f9e03375544bb3e4e2135f`
  - Base iBTC2x (working): `0x3b73475EDE04891AE8262680D66A4f5A66572EB0`

  **Local file**: `queries/5140916_composition_changes_product_events.sql`

### Future

- [ ] **Monitor Dune `prices.usd` deprecation** - When deprecated, either accept 7x cost increase with `prices.minute` or create materialized view for token prices.

### Borrower Research (2025-02-04)

- [x] **Identify unknown Spark borrowers** - Deep investigation completed

  **Deep Investigation Results (5 Unknown Addresses):**

  | Rank | Address | Debt | CEX Origin | Identity Lead | Risk |
  |------|---------|------|------------|---------------|------|
  | 7 | `0xcaf1943ce973c1de423fe6e9f1a255049e51666e` | $50.4M | **Poloniex 4** (Oct 2023) | Possibly DeFi Saver's "biggest Spark whale" | - |
  | 12 | `0x7f7f0e44a00a5d7c052ce925b557f07b2f24ee4b` | $31.75M | **Poloniex** (2016) | DSProxy owner: `0x72181c27...` | **HF 1.03** |
  | 13 | `0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26` | $30.83M | **Binance 16** (Jan 2024) | Verified Binance user, deposits ETH back | **HF 1.02** |
  | 14 | `0x26ad4f84cd20102c4a7fb9d14bd2661a0d66f96d` | $28.36M | **Binance 14** (Jan 2024) | 800 ETH withdrawal customer | - |
  | 25 | `0xdcbe94c3d101553ac7d40a8515aa18b9534adfcd` | $13.71M | **Kraken 4** (Dec 2022) | Summer.fi Vault #1631, likely family office | - |

  **Key Findings:**
  - All 5 trace to major CEXs (Poloniex 2, Binance 2, Kraken 1)
  - **$53M at liquidation risk** - #12 and #13 have health factors ~1.02-1.03 (2-3% buffer)
  - No public identities - all deliberately anonymous, no ENS, no governance participation
  - #25 is **Summer.fi Institutional** tier user (Vault ID 1631)

  **Detailed Findings Per Address:**

  **#7 (0xcaf1943...) - $50.4M - POLONIEX WHALE**
  - First funded from Poloniex 4 (Oct 2023)
  - 756 transactions, last active 2 days ago
  - Uses Spark, Fluid, Lido, Uniswap V3/V4
  - May be DeFi Saver's "biggest Spark whale" (June 2025 newsletter)
  - No ENS, no governance, no social footprint

  **#12 (0x7f7f0e44...) - $31.75M - DSPROXY OWNER FOUND**
  - DSProxy #221,933, owner: `0x72181c2739928976e82d1Cc1786b09F9A59b52De`
  - Funding chain: Poloniex (2016) → intermediary → owner
  - Position: 8,971 wstETH collateral / 9,914 WETH debt
  - **CRITICAL: Health Factor 1.0318** (3% from liquidation)
  - Uses DeFi Saver automation (DSGuard detected)

  **#13 (0x55ea3e38...) - $30.83M - BINANCE POWER USER**
  - Funded by Binance Hot Wallet 16 (Jan 2024)
  - Position: $23.4M collateral / $21.4M debt
  - **CRITICAL: Health Factor 1.0171** (1.7% from liquidation)
  - Key: Regularly deposits large ETH back to Binance (2,097 ETH = $4.67M in Nov 2025)
  - Verified Binance user, likely trading firm or HNW

  **#14 (0x26ad4f84...) - $28.36M - BINANCE 14 CUSTOMER**
  - Funded by Binance 14: received 800 ETH (Jan 2024)
  - 808 transactions on Ethereum
  - Uses Spark, Lido, Aave, 1inch, Angle Protocol, Polygon Bridge

  **#25 (0xdcbe94c3...) - $13.71M - SUMMER.FI INSTITUTIONAL**
  - Summer.fi Smart Account (Vault ID 1631)
  - Creator: `0xB400aBa2b84825cc5acf8ffeb26c1028d6dd270f`
  - Creator funded by **Kraken 4**: 1,000 ETH ($2.18M) Dec 2022
  - 91 txs over 2+ years (manual, not bot)
  - Likely: Family office, HNW individual, or small fund

- [x] **Query large borrowers from Aave, Morpho, Maple** - Cross-reference with Spark list

  **Major Aave Whales Identified:**
  | Entity | Holdings | Borrowed | Notes |
  |--------|----------|----------|-------|
  | **Trend Research (LD Capital)** | 618K ETH (~$1.4B) | $958M stables | Jack Yi founder. Liq price ~$1,830 |
  | **BitcoinOG (1011short)** | 783K ETH + 30K BTC | $240M+ | October 2025 short whale. Liq price ~$2,261 |
  | **Abraxas Capital** | $216M+ (wstETH, eETH) | Active | `0xEd0C6079229E2d407672a117c22b62064f4a4312` |

  **Morpho:** $6.68B TVL, 2nd largest lender. Coinbase integration ($250M+ active loans). No public borrower list.

  **Maple Finance:** 28 institutional borrowers (KYC'd), $12B+ originated, 99% repayment. Borrowers not public.

- [x] **Research borrower identities** - Check Maple/Sky forums, Arkham, Etherscan labels

  **Spark CRM Known Entities (Identified):**
  | Rank | Entity | Address | Debt | What They Are |
  |------|--------|---------|------|---------------|
  | 1 | **Treehouse Finance** | `0x5aE0e44DE96885702bD99A6914751C952d284938` | $133M | tETH Spark Strategy - leveraged staking protocol |
  | 2 | **Sky/Maker** | `0xd178...e7b00b` | $103M | MakerDAO ecosystem |
  | 3-4 | **Fluid** | `0x9600...`, `0x3a0d...` | $170M | Instadapp's lending protocol |
  | 5,8 | **Abraxas Capital** | `0xb99a...`, `0xEd0C...` | $109M | Crypto hedge fund |
  | 6 | **Mellow Protocol** | `0x3883...` | $57M | Modular LRT vault protocol |
  | 9,19,20 | **Summer.fi** | Multiple DSProxies | $79M | MakerDAO frontend (formerly Oasis) |
  | 11 | **EtherFi** | `0xba7f...` | $32M | Liquid restaking protocol |

  **Conclusion:** Most large Spark borrowers are **protocols** (Treehouse, Fluid, Mellow, EtherFi) or **known funds** (Abraxas). The truly anonymous mega-whales are on **Aave** (Trend Research, BitcoinOG). Individual whale identity requires CEX KYC records (subpoena access).

- [x] **Investigate Aave unknown borrowers** - Deep investigation completed (WebSearch agents)

### BD Borrower Research (2026-02-05) - Tasks 5-6

- [x] **Query top borrowers from Aave, Compound, Morpho, Spark ($10M+)** - Built unified query using `lending.borrow` table, saved as [query 6654792](https://dune.com/queries/6654792)
- [x] **Focus on hybrid and on-chain borrowers (Task 5)** - 312 multi-protocol borrowers found, 198 unknown, 44 use 3+ protocols. Strategy patterns: stablecoin-only (56%), ETH leverage (12%), ETH looping (11%), multi-asset (11%), BTC leverage (8%)
- [x] **Identify missing users/lanes (Task 6)** - Full analysis in `references/lending_whales.md`. Top gaps: L2 borrowers ($0 data), unlabeled whales ($238B/391 addresses), DAO treasuries ($9.9B/157 Safe wallets), emerging yield protocols (Veda $2.4B, Cian $1.7B)
- [x] **Cross-reference addresses with identity labels** - Query 6654792 includes: owner_key, ENS, CEX labels, Safe, DAO, DeFi protocol, MEV, Bridge, L2, OFAC, staking entity
- [x] **Compile findings into references/lending_whales.md** - Added top unlabeled whales, labeled entities, MEV bots, ENS leads
- [x] **Query Fluid, Maple borrowers** - Researched: Fluid NOT in Dune `lending.borrow` spellbook (need raw contract queries, ~$6B TVL). Maple is KYC-gated (80+ borrowers, identities not public). See `references/lending_whales.md` Task 6 section for details and dashboard links.
- [ ] **Build Lending Whales CRM** - Enrich data for BD outreach:
  - Create CSV export with: address, protocol, borrowed, net_position, entity_type, twitter, website, ens, bd_status, priority, notes
  - Add entity categorization (protocol vault, fund, individual, MEV, unknown)
  - Extract social/contact info from Dune labels (social_links, project_website)
  - Consider Notion/Airtable import for filtering/tracking

- [ ] **Deep investigation with cast/curl** - Token-efficient follow-up for remaining unknowns

  **Why:** WebSearch agents cost ~40K tokens each. Cast/curl cost ~100 tokens per call (30x cheaper).

  **Remaining Unknowns to Investigate (16 Aave addresses):**
  ```
  0xc468315a2df54f9c076bd5cfe5002ba211f74ca6  $348M
  0x23a5e45f9556dc7ffb507db8a3cfb2589bc8adad  $203M
  0xef417fce1883c6653e7dc6af7c6f85ccde84aa09  $200M
  0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912  $172M  (cbBTC+RLUSD, likely institutional)
  0x9cbf099ff424979439dfba03f00b5961784c06ce  $166M
  0x893aa69fbaa1ee81b536f0fbe3a3453e86290080  $165M
  0x517ce9b6d1fcffd29805c3e19b295247fcd94aef  $148M
  0x197f0a20c1d96f7dffd5c7b5453544947e717d66  $143M
  0x3edc842766cb19644f7181709a243e523be29c4c  $136M
  0x99926ab8e1b589500ae87977632f13cf7f70f242  $131M
  0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0  $106M  (large wNXM+COMP)
  0xe40d278afd00e6187db21ff8c96d572359ef03bf  $103M  (Safe multisig)
  0x78cca58ceeebf201555a3c0f3daeb55d1f1ca564  $101M  (Safe proxy)
  0x741aa7cfb2c7bf2a1e7d4da2e3df6a56ca4131f3  $98M   (large wNXM, 10+ chains)
  0xfa5484533acf47bc9f5d9dc931fcdbbdcefb4011  $97M   (Instadapp DSA, 96% WBTC)
  0x50fc9731dace42caa45d166bff404bbb7464bf21  $97M   (89% WBTC + USDG)
  ```

  **Investigation Process (per address):**
  ```bash
  # 1. Check if EOA or contract (~50 tokens)
  cast code <ADDRESS> --rpc-url $ETH_RPC_URL | head -c 100

  # 2. If contract, identify type (~50 tokens each)
  # DSProxy:
  cast call <ADDRESS> "owner()(address)" --rpc-url $ETH_RPC_URL

  # Safe multisig:
  cast call <ADDRESS> "getOwners()(address[])" --rpc-url $ETH_RPC_URL
  cast call <ADDRESS> "getThreshold()(uint256)" --rpc-url $ETH_RPC_URL

  # 3. Get first transaction - funding origin (~100 tokens)
  curl -s "https://api.etherscan.io/api?module=account&action=txlist&address=<ADDRESS>&startblock=0&endblock=99999999&sort=asc&page=1&offset=1&apikey=$ETHERSCAN_API_KEY" | jq '.result[0] | {from, hash, timeStamp}'

  # 4. If Safe, investigate signers recursively
  # 5. Cross-reference first funder with known CEX hot wallets
  ```

  **CEX Hot Wallet Reference:**
  - Binance 14: `0x28c6c062...`
  - Binance 16: `0xdfd5293d8e347dfe59e90efd55b2956a1343963d`
  - Kraken 4: `0x267be1C1...`
  - Poloniex 4: `0xa910f92acdaf488fa6ef02174fb86208ad7722ba`

  **Priority targets:**
  1. Safe multisigs (`0xe40d2...`, `0x78cca...`) - can get signer addresses
  2. Large wNXM holders (`0x28a55...`, `0x741aa...`) - may be same entity
  3. WBTC-heavy positions (`0xfa548...`, `0x50fc9...`) - unusual pattern

  **Output:** Update `references/lending_whales.md` with findings.

  **Aave CRM Unknowns (5 investigated):**

  | Rank | Address | Debt | Collateral | Finding |
  |------|---------|------|------------|---------|
  | 3 | `0xc468...` | $348M | - | **Invalid** - zero activity on mainnet |
  | 4 | `0xe5c2...` | $266M | - | **Invalid** - zero activity on mainnet |
  | 5 | `0xfaf1...` | $238M | - | **Confirmed: Trend Research** (LD Capital) |
  | 6 | `0x23a5...` | $203M | - | **Invalid** - zero activity on mainnet |
  | 8 | `0x7cd0b7ed...` | $172M | $378M | **Unknown - likely institutional** |

  **Key Finding: 0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912**

  | Field | Value |
  |-------|-------|
  | Rank | #8 on Aave |
  | Debt | $172M (USDC $99.6M, PYUSD $72M) |
  | Collateral | $378M (cbBTC $300M, RLUSD $30M) |
  | LTV | 45.44% (healthy) |
  | First Txn | Jan 2025 |
  | Tx Count | 2,205 |

  **Identity Assessment: Likely Institutional**
  - cbBTC ($300M) — Coinbase Prime product
  - RLUSD ($30M) — Ripple stablecoin, institutional focus
  - PYUSD ($72M borrowed) — PayPal stablecoin
  - Pattern suggests: Trading firm, OTC desk, or market maker with TradFi integration

  **CRM Data Quality Issue:** 4 of 5 "unknown" addresses had zero on-chain activity — likely truncated or incorrect addresses in source data.

### Other

- [ ] **Validate consolidated staking yield query** - Verify `queries/3989545_post_merge_staking_yield.sql` output matches original 10 separate queries.

- [ ] **Update query_2621012 on Dune** - Add blockchain column to match local file.

## Completed

- [x] **Fix KPI report duplicate values** - Added blockchain joins to query_3668275; root cause was missing blockchain in multichain joins
- [x] **Fix Weekly KPI Report duplicates** - Created query_3982525 using blockchain column directly instead of deriving from symbol suffix
- [x] **Fix query_3713252 duplicates** - Added `s.blockchain = p.blockchain` to product_token join
- [x] **Fix query_3713252 NaN values** - Added `not is_nan(leverage_ratio)` filter for missing price data
- [x] **Fix iETH2x collateral=0** - Added aBasUSDC to query_3018988 with `base_symbol = 'USDC'`
- [x] Add NAV configs to query_4771298 (decimals, supply_dec, debt_dec, tlr, maxlr, minlr)
- [x] Create query_3713252 file using query_4771298 materialized view
- [x] Create query_3018988 file with NOT EXISTS optimization
- [x] Create query_3668275 file with blockchain joins
- [x] Create query_2812068 file with leverage token filter
- [x] Consolidate 10 staking yield queries into single query
- [x] Migrate DuneSQL style guide to project skill (`.claude/skills/dune-analytics.md`)
- [x] Add ARB2x to query_5140527 tokenlist
- [x] Optimize query_2646506 (issuance events) - single scan
- [x] Optimize query_2364999 (unit supply daily) - pre-aggregate events
- [x] Optimize query_2621012 (fee structure) - single scan + utils.days
- [x] Optimize query_4153359 (staked PRT share) - utils.days + blockchain column
- [x] Add blockchain column to fee structure and staked PRT queries
- [x] Update CLAUDE.md and skills with multichain join patterns, is_nan filter, NOT EXISTS
- [x] Optimize query_5298403 (latest open exposure) - removed dead CTEs, added parameters, materialized views
- [x] Create query_3808728 (hyETH yield) - utils.days, reused query_3805243, prices.usd time filter
- [x] Optimize query_3802258 (LRT exchange rates) - utils.days, self-join for agETH, added contract_address
- [x] Optimize query_3805243 (hyETH composition NAV ETH) - utils.days, UNION ALL, time filters on logs
- [x] Add query_4007736 (PENDLE hyETH Swap & Hold Incentive) to docs
- [x] Create query_3994496 (hyETH NAV by minute) - prices.usd→prices.minute, time filter
- [x] Create query_3806801 (hyETH composition NAV ETH minute) - UNION ALL, time filters on logs
- [x] Add optimization verification guidelines to CLAUDE.md and skills
- [x] Create query_3806854 (LRT exchange rates minute) - UNION ALL, added contract_address, agETH
- [x] Optimize query_3806854 - removed ethereum.blocks gap-fill, moved to consuming query (3806801)
- [x] Add utils.minutes and utils.hours to CLAUDE.md and skills
- [x] Update query_3994496 and query_3806801 to use utils.minutes instead of ethereum.blocks
- [x] Optimize query_3806801 - bounded minutes range, early component filter, single gap-fill per source
- [x] Create query_3672187 (Daily KPI Report TVL & NSF) - added price is not null filter
- [x] Create query_4135813 (All chain lev suite trades) - user holding periods, already optimized
- [x] Create query_547552 (icETH yield) - ethereum.blocks→utils.hours, prices.usd→prices.hour
- [x] Create query_4781646 (Leverage FlashMint events) - v1 + v2 contracts, kept prices.usd (prices.minute 7x slower)
- [x] Update CLAUDE.md and skills - added prices.minute, clarified prices.usd is legacy
- [x] Investigate prices.minute optimization - tested semi-join, explicit token list, prices.hour; all failed to match prices.usd performance
