# Lending Protocol Whales

Research conducted 2026-02-04. Updated 2026-02-05 with Dune query 6654792, ENS whale identity research, and Task 6 missing lanes analysis. Updated 2026-02-06 with full EOA/Safe identity investigation (14 addresses).

**Data source:** [Dune Query 6654792](https://dune.com/queries/6654792) — Top borrowers ($10M+) from Aave, Compound, Morpho, Spark with identity labels.

**Stats (as of 2026-02-05):**
- Total borrowers ($10M+): 3,189
- Unlabeled (no identity): 2,266 (71%)
- With ENS names: 230
- Safe/Multisig wallets: 156

## Verified Entities (High Confidence)

Confirmed via Arkham Intelligence, Etherscan labels, or direct contract verification.

### Protocol Vaults

| Entity | Protocol | Debt | Address | Verification |
|--------|----------|------|---------|--------------|
| **Ether.fi LIQUIDETH** | Aave | ~$1.58B | `0xf0bb20865277abd641a307ece5ee04e79073416c` | Etherscan token contract |
| **Fluid** | Aave/Spark | ~$1.67B (Aave) + $170M (Spark) | `0x9600a48ed0f931d0c422d574e3275a90d8b22745` | Protocol identified |
| **Fluid** | Spark | ~$77M | `0x3a0dc3fc4b84e2427ced214c9ce858ea218e97d9` | Protocol identified |
| **Lido GG Vault** (Golden Goose) | Aave | ~$200M | `0xef417fce1883c6653e7dc6af7c6f85ccde84aa09` | Etherscan "Lido: GG Token", deployed by Royco |
| **Mellow strETH Sub Vault 2** | Aave | ~$165M | `0x893aa69fbaa1ee81b536f0fbe3a3453e86290080` | ERC-1967 Proxy, Lido stRATEGY vault |

### Funds & Institutions

| Entity | Protocol | Debt | Address | Verification |
|--------|----------|------|---------|--------------|
| **Trend Research** (LD Capital) | Aave | ~$266M | `0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c` | Arkham, 66k ETH whale cluster |
| **Trend Research** (LD Capital) | Aave | ~$156M | `0x85e05c10db73499fbdecab0dfbb794a446feeec8` | Arkham labeled "TOP3" |
| **Trend Research** (LD Capital) | Aave | ~$238M | `0xfaf1358fe6a9fa29a169dfc272b14e709f54840f` | Part of 6-wallet network |
| **Abraxas Capital** | Spark | ~$61M | `0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5` | Arkham labeled |
| **Abraxas Capital** | Spark | ~$49M | `0xed0c6079229e2d407672a117c22b62064f4a4312` | Arkham labeled |
| **World Liberty Financial** (Trump) | Aave | ~$112M | `0x5be9a4959308a0d0c7bc0870e319314d8d957dbb` | Etherscan "World Liberty: Multisig" |
| **7 Siblings** | Aave | ~$106M | `0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0` | Arkham entity, wNXM holder |
| **7 Siblings** | Aave | ~$98M | `0x741aa7cfb2c7bf2a1e7d4da2e3df6a56ca4131f3` | Arkham entity, largest wNXM holder, Kraken-funded |

### DeFi Protocols

| Entity | Protocol | Debt | Address | Verification |
|--------|----------|------|---------|--------------|
| **Treehouse Finance** | Spark | ~$133M | `0x5ae0e44de96885702bd99a6914751c952d284938` | Protocol identified |
| **Mellow Protocol** | Spark | ~$57M | `0x3883d8cdcdda03784908cfa2f34ed2cf1604e4d7` | Protocol identified |
| **EtherFi** | Spark | ~$32M | `0xba7fdd2630f82458b4369a5b84d6438352ba4531` | Protocol identified |
| **Summer.fi** | Spark | ~$43M | `0x5f39a6fb00b3e4bd7369cb40b22cf7088044136b` | Protocol identified |
| **Summer.fi** | Spark | ~$18M | `0x84d113c540fe1109af6d629cd24ff143d743a279` | Protocol identified |
| **Summer.fi** | Spark | ~$18M | `0x6762276585c193c840c20c492a7b63df8b28b0ae` | Protocol identified |

### Individuals

| Entity | Protocol | Debt | Address | Verification |
|--------|----------|------|---------|--------------|
| **Junyi Zheng** | Spark | ~$26M | `0xee2826453a4fd5afeb7ceffeef3ffa2320081268` | Arkham labeled |

## Trend Research Wallet Cluster (6 wallets, ~$958M total borrowed)

LD Capital affiliate. Founder: Jack Yi ("Yi Laoban"). Strategy: Leveraged ETH accumulation.

| Address | ETH Collateral | Borrowed | Liquidation Price |
|---------|----------------|----------|-------------------|
| `0xfaf1358fe6a9fa29a169dfc272b14e709f54840f` | 145,850 ETH | $216M | $1,791 |
| `0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c` | 114,899 ETH | $172M | $1,807 |
| `0x85e05c10db73499fbdecab0dfbb794a446feeec8` | 108,749 ETH | $163M | $1,808 |
| `0x6e9e81efcc4cbff68ed04c4a90aea33cb22c8c89` | 79,516 ETH | $117M | $1,781 |
| + 2 additional wallets | ~169,232 ETH | ~$290M | Various |

Total: ~618,246 ETH (~$1.33B collateral), ~$939M borrowed from Aave.

## Deep Investigated - Identity Unknown

Addresses that received thorough investigation (funding chain, NFTs, governance, social) but identity remains unknown.

### `0xd1781818f7f30b68155fec7d31f812abe7b00be9` — Spark $103M

**Investigation Date:** 2026-02-05

**Contract Type:** DSProxy #221,928 (Sky DS Proxy Factory)

**Funding Chain:**
```
Gemini (CEX, KYC'd) ──9 yrs ago──▶ 0x0bd9f5FF...
                                        │ 5 yrs ago
                                        ▼
                                  0xde77bb54...
                                        │ 4 yrs ago
                                        ▼
                                  0x2E0929bd... (OWNER)
                                        │ July 2024
                                        ▼
                                  DSProxy 0xd178...
```

**Owner Wallet Profile (`0x2E0929bd71c21cfc66dce799b132f979ff8db7a0`):**
- Holdings: ~$1.4M (stETH, USDC, wstETH, stkAAVE)
- NFTs: 1 Milady Maker + 63 others
- Airdrops: Omni Network (restricted in US — contradicts Gemini KYC)
- DeFi: Lido, Aave staking, Uniswap, CoW Protocol, zkSync, Blur Blend
- Transactions: 296 total

**Identity Signals:**
- OG crypto user (~2015-2016, 9 years)
- US connection via Gemini (historically required US residency)
- Privacy conscious — no ENS, no social links, clean funding chain
- Milady holder — may be in Remilia/CT communities

**Dead Ends:**
- No ENS name
- No Arkham label
- No governance forum posts (Aave, Sky)
- No Twitter/Telegram mentions
- No Snapshot voting identity
- OpenSea profile has no username

**Contact Options:**
1. Gemini KYC (legal/subpoena route)
2. Milady/Remilia Discord outreach
3. Spark BD team (@sparkdotfi)

**Verdict:** Privacy-conscious crypto OG who doesn't want to be found. CRM label "Sky/Maker?" is speculative — NOT a Sky DAO address.

---

## Unverified CRM Claims (Need Confirmation)

Listed in Lending CRM but not independently verified on Arkham.

| Entity (Claimed) | Protocol | Debt | Address | Notes |
|------------------|----------|------|---------|-------|
| Sky/Maker | Spark | ~$35M | `0xc1687c909690ec79fbc48a72f5ed9109e855d83c` | Listed as Sky |
| Sky/Maker | Spark | ~$18M | `0xda46f11ac5e394111d92f8879302a9347fe42259` | Listed as Sky |
| RockSolid Network | Spark | ~$23M | `0x9ca1d6e730eb9fbfd45c9ff5f0ac4e3d172d8f4d` | Not found on Arkham |
| Sentora | Spark | ~$20M | `0xb3e262ef1479ed8c66578baebf6356a08cee0904` | Not found on Arkham |
| SUI-Plasma Farmer | Spark | ~$15M each | 4 addresses (0x1cac..., 0xb213..., 0x219d..., 0x3048...) | Yield farming pattern |

## Unknown - Investigated

### Spark Unknowns (Investigated 2026-02-06, No Identity Found)

| Address | Debt | Contract Type | Funding Origin | Finding |
|---------|------|---------------|----------------|---------|
| `0xcaf1943ce973c1de423fe6e9f1a255049e51666e` | $50.4M | EOA | Poloniex 4 | OG DeFi user (2+ yrs). Now $1,154 balance — may have withdrawn. Active on Spark, Fluid, Lido. Poloniex suggests possible Asian market connection. No ENS, no Arkham label. |
| `0x7f7f0e44a00a5d7c052ce925b557f07b2f24ee4b` | $31.75M | DSProxy #221,933 | Owner: `0x72181c27...` | 9,560 wstETH initial deposit. Not EOA/Safe — DSProxy. |
| `0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26` | $30.83M | EOA | Binance 16 | 1,221 txs, now $1,447 balance — positions closed. Active on 8 chains (ETH, OP, Base, BSC, Unichain, Swellchain, Sonic, Monad). Last active 61 days ago. No ENS, no Arkham label. |
| `0x26ad4f84cd20102c4a7fb9d14bd2661a0d66f96d` | $28.36M | EOA | Unlabeled `0xFE99cC46...` (OTC?) | 808 txs, now $586 balance — positions closed. Active on Spark, Lido, Aave, Polygon. Last active 4 days ago. Most privacy-conscious — unlabeled funding source. No ENS, no Arkham label. |
| `0xdcbe94c3d101553ac7d40a8515aa18b9534adfcd` | $13.71M | Smart Account | Summer.fi Factory | Creator funded from Kraken. Not EOA/Safe — Summer.fi smart account. |

### Aave Unknowns — Investigated 2026-02-05, Re-investigated 2026-02-06

Addresses investigated via Etherscan, Arkham, WebSearch, and Etherscan page scraping. Institutional leads moved to "Institutional Leads" table above.

**Identified (moved to Verified Entities):**
- ~~`0xef41...aa09`~~ ($200M) → **Lido GG Vault** (Protocol Vaults)
- ~~`0x893a...0080`~~ ($165M) → **Mellow strETH Sub Vault 2** (Protocol Vaults)
- ~~`0x28a5...a6b0`~~ ($106M) → **7 Siblings** (Funds & Institutions)
- ~~`0x741a...31f3`~~ ($98M) → **7 Siblings** (Funds & Institutions)

**Institutional Leads — Contactable via Intermediary (Investigated 2026-02-06):**

| Address | Debt | Type | Lead | BD Approach |
|---------|------|------|------|-------------|
| `0x517ce9b6d1fcffd29805c3e19b295247fcd94aef` | $148M | EOA | **FalconX client** — regular large ETH transfers to FalconX 1 (`0x1157a2...`), $16.8M SYRUP (Maple), 83% aEthWETH. Maple/FalconX partnership confirmed (Cantor $100M+ facility) | Contact FalconX BD team ([falconx.io](https://falconx.io)) for intro. Highest-confidence institutional lead. |
| `0x197f0a20c1d96f7dffd5c7b5453544947e717d66` | $143M | EOA | **Copper custodian client** — funded by Copper 2 (`0xe5379345...`, institutional crypto custodian), 8,290 ETH single transfer, Aave staking, ether.fi LRT2 claims, KING tokens | Contact Copper BD team ([copper.co](https://copper.co)) for intro. Copper serves 600+ institutional participants. |
| `0x3edc842766cb19644f7181709a243e523be29c4c` | $136M | Safe Proxy | **Possible Garrett Jin / HyperUnit** — created Oct 2025, weETH leverage, KING tokens. Timeline aligns with Garrett Jin's 570K ETH staking operations via ereignis.eth. Circumstantial only. | If confirmed: [@GarrettBullish](https://x.com/garrettbullish) on X. Controversial figure (former BitForex CEO, fraud allegations). LOW-MEDIUM confidence. |
| `0x50fc9731dace42caa45d166bff404bbb7464bf21` | $97M | EOA | **Paxos/Singapore institutional** — funded by Paxos 4, holds USDG (Paxos Digital Singapore), 87% WBTC ($110M), active on 6 chains | Likely Singapore-based regulated entity. Contact Paxos BD or check Singapore crypto fund networks. |

## Investigation Status & Next Steps (2026-02-10)

### Summary: 24 Target Addresses Under Investigation

**Completion Status:**
- 7 addresses investigated via enrichment pipeline (2026-02-09): OK
- 13 addresses NEED investigation (Safe owner resolution, top unlabeled whales): IN PROGRESS
- All addresses documented with contract type, funding origin, and preliminary BD confidence

### Key Findings from Current Investigation (2026-02-09/10)

#### Already Investigated (7 addresses)

| Address | Debt | Type | Finding | BD Confidence |
|---------|------|------|---------|--------------|
| `0xc468315a2df54f9c076bd5cfe5002ba211f74ca6` | $348M | EOA | Retail DeFi power user, no identity. Funded by unlabeled address. | LOW |
| `0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912` | $172M | EOA | Institutional market maker. Funded by **Coinbase 2** — suggests regulated institution. | MEDIUM |
| `0x9cbf099ff424979439dfba03f00b5961784c06ce` | $166M | EOA | Multi-chain yield farmer (4yr old, 13k+ txs on 16 chains). Early protocol adopter. | LOW |
| `0x50fc9731dace42caa45d166bff404bbb7464bf21` | $97M | EOA | Paxos/Singapore institutional. Holds USDG (Paxos Digital Singapore). | MEDIUM |
| `0x3ddfa8ec3052539b6c9549f12cea2c295cff5296` | $4.8B | EOA | Multi-asset holder. Funded by **Poloniex 4** — likely OG DeFi user. | LOW |
| `0xd275e5cb559d6dc236a5f8002a5f0b4c8e610701` | $3.7B | EOA | Stablecoin-focused arbitrage. No clear identity. | LOW |
| `0x517ce9b6d1fcffd29805c3e19b295247fcd94aef` | $148M | EOA | **HIGH CONFIDENCE: FalconX client** — regular ETH transfers to FalconX 1, $16.8M SYRUP. | HIGH |

#### Still Need Investigation (13 addresses)

**Safe Multisigs (owners not yet resolved):**
- `0x3edc842766cb19644f7181709a243e523be29c4c` ($136M) — Possible Garrett Jin / HyperUnit (circumstantial)
- `0x99926ab8e1b589500ae87977632f13cf7f70f242` ($131M) — Unknown DAO/Fund (clean ETH long)
- `0xe40d278afd00e6187db21ff8c96d572359ef03bf` ($103M) — DAO treasury or fund (diversified)
- `0x78cca58ceeebf201555a3c0f3daeb55d1f1ca564` ($101M) — Possibly dormant (created Dec 2025, low activity)
- `0x23a5e45f9556dc7ffb507db8a3cfb2589bc8adad` ($203M) — Kelp DAO restaking (funded by Binance 15)
- `0xf20b3387fd3b6529ebc8caeed3a01f8f19e9a09c` ($557M) — Unknown DAO (large scale)
- `0xa976ea51b9ba7225a886cded813fa470a1b3e531` ($545M) — Unknown DAO (large scale)
- `0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3` ($505M) — Unknown DAO (large scale)

**Top Unlabeled Whales ($1B+ lifetime borrowed):**
- `0xe834274bb2098bb0c7e77098055f26b0ebba9fa8` ($19.9B) — Aave USDT/USDe holder
- `0xa7c624014699a8b537cc4b326eb65f00852ee2a3` ($9.5B) — DAI/cbBTC/multi-asset
- `0xba6d84cc7418a9c46133788c04f6a459e1fb669c` ($5.2B) — Multi-asset (20+ tokens)
- `0x1484485f1ba8ff4d88bb1a8e7f131dd6f1910edb` ($4.1B) — cbBTC/GHO focused

**Instadapp Smart Account (not resolvable):**
- `0xfa5484533acf47bc9f5d9dc931fcdbbdcefb4011` ($97M) — Instadapp DSA #N/A (retail user via DSA)

### Investigation Methodology Applied

For each address, the investigation checked:

1. **Contract Type Detection** — EOA vs Safe Proxy vs DSProxy vs Instadapp DSA
2. **Funding Origin** — First transaction funder (CEX label if available)
3. **Etherscan Labels** — Community and partner labels
4. **Arkham Label** — AI-powered entity detection
5. **ENS Registration** — Reverse ENS lookup
6. **Collateral Patterns** — Token holdings suggest use case (MM, DAO, staking, etc.)
7. **Multi-chain Activity** — Cross-chain patterns indicate sophistication level
8. **Safe Owner Resolution** — API call to Safe to identify signers (for Safe multisigs)

### Next Investigation Steps (Priority Order)

1. **Safe Owner Resolution** — 8 Safe addresses need `getOwners()` API call via Safe Transaction Service
2. **Top Unlabeled Whales** — 4 addresses with $5B+ borrowed need Arkham/Nansen label lookup
3. **Garrett Jin Confirmation** — Verify if `0x3edc...` can be confirmed as HyperUnit/ereignis.eth entity
4. **Blockscan Chat Outreach** — Direct messaging to Safe multisigs via chat.blockscan.com

### Previous Detailed Findings (2026-02-05/06)

**Investigated — No Identity Found (2026-02-06):**

| Address | Debt | Type | Investigation Findings |
|---------|------|------|----------------------|
| `0xc468315a2df54f9c076bd5cfe5002ba211f74ca6` | $348M | EOA | 2,189 txs since Jan 2024, heavy Aave V3 user, xSILO, GHO, Angle Protocol. Funded by `0x887fD380...`. No ENS, no Arkham label. Pattern: retail/individual DeFi power user. |
| `0x23a5e45f9556dc7ffb507db8a3cfb2589bc8adad` | $203M | Safe Proxy | Safe 1.4.1, created ~1yr ago by `0x67ef8370...`. Funded by Binance 15 (1,500 ETH Dec 2024). rsETH/Kelp DAO restaking, Lido staking. No ENS, no Arkham label. |
| `0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912` | $172M | EOA | 2,211 txs, $300M+ cbBTC + $30M RLUSD collateral, 115 tokens. Funded by Coinbase 2. Institutional scale but no identity. Pattern: market maker or institutional DeFi desk. |
| `0x9cbf099ff424979439dfba03f00b5961784c06ce` | $166M | EOA | 4yr old, 13,224 txs across 16 chains(!), $4.69M portfolio. ENA ($596K), stTAO ($408K). Uses Euler, Morpho, Aave, Uniswap, Curve, HyperEVM. Multi-chain yield farmer, early protocol adopter. |
| `0x99926ab8e1b589500ae87977632f13cf7f70f242` | $131M | Safe Proxy | Safe 1.3.0, created ~349 days ago. $196.5M in aEthWETH (100,824 tokens). Clean leveraged ETH long, 13 tokens. No public Safe owners identified. |
| `0xe40d278afd00e6187db21ff8c96d572359ef03bf` | $103M | Safe Multisig | Safe 1.3.0, created ~Mar 2024. Diversified: aEthWETH ($38.8M, 80%), aEthwstETH ($8.1M, 17%), aEthLINK ($2.7M, 4%). Multi-sig "Exec Transaction" calls suggest DAO treasury or fund. |
| `0x78cca58ceeebf201555a3c0f3daeb55d1f1ca564` | $101M | Safe Proxy | Safe 1.4.1, created ~57 days ago (Dec 2025). Only ~$5K visible. 36 txs. weETH + WETH variable debt. **Position closed or funds moved.** |
| `0xfa5484533acf47bc9f5d9dc931fcdbbdcefb4011` | $97M | Instadapp DSA | 96% aEthWBTC ($123M), 3.5% aEthWETH. Not EOA/Safe — Instadapp smart account. |
| `0xee55328d240d10b09f549dc3b2a6653c13f10bfc` | $6.8B | EOA | USDC only, currently $0 balance — likely automated/MEV/flash loan bot. Not a BD target. |

## Collateral Patterns (Identity Signals)

| Collateral Type | Likely Entity Type |
|-----------------|-------------------|
| cbBTC + RLUSD/PYUSD | Institutional (Coinbase Prime + TradFi stablecoins) |
| wstETH + eETH | DeFi-native yield strategies |
| Large wNXM + COMP | DeFi governance / insurance entity |
| tETH | Treehouse Finance strategy |
| WBTC-heavy (>90%) | BTC-focused fund or trading desk |
| USDG stablecoin | Singapore-regulated institutional |

## CEX Hot Wallet Labels

Used to trace funding origin.

| Label | CEX | Address (Partial) | Notes |
|-------|-----|-------------------|-------|
| Binance 14 | Binance | `0x28c6c062...` | Large withdrawals |
| Binance 16 | Binance | `0xdfd5293d8e347dfe59e90efd55b2956a1343963d` | Common funding source, $324M+ balance |
| Binance 20 | Binance | - | - |
| Kraken 4 | Kraken | `0x267be1C1...` | Institutional users |
| Poloniex 4 | Poloniex | `0xa910f92acdaf488fa6ef02174fb86208ad7722ba` | OG DeFi users (2016+) |

## Hybrid Borrowers (Multi-Protocol Users)

312 addresses borrow from 2+ protocols. 198 are unknown. 44 use 3+ protocols (most sophisticated).

### Protocol Combinations

| Combination | Count | Notes |
|-------------|-------|-------|
| Aave + Compound | 173 | Most common — legacy Compound users migrating |
| Aave + Spark | 63 | ETH-native strategies across markets |
| Aave + Aave Lido | 18 | Separate Lido market positions |
| Aave + Compound + Spark | 15 | Power users across 3 protocols |

### Top Unknown Hybrid Borrowers (BD Targets)

| Address | Total Borrowed | Protocols | Notes |
|---------|----------------|-----------|-------|
| `0x3c9ea5c4fec2a77e23dd82539f4414266fe8f757` | $3.1B | Aave+Compound+Spark | 3-protocol, unknown |
| `0x1be45fef92c4e2538fecd150757ed62b7b3757d7` | $2.4B | Spark+Aave | Unknown |
| `0x4deb3edd991cfd2fcdaa6dcfe5f1743f6e7d16a6` | $2.3B | Aave+Compound | Unknown |
| `0xaaf9f14f20145ad50db369e52b2793bfeb18a45b` | $2.2B | Aave+Spark+Aave Lido | 3-protocol, unknown |
| `0x171c53d55b1bcb725f660677d9e8bad7fd084282` | $1.3B | Aave+Spark+Lido+Compound | 4-protocol, unknown |
| `0xb8a451107a9f87fde481d4d686247d6e43ed715e` | $1.2B | Aave+Morpho+Aave Lido | 3-protocol, unknown |

### Borrowing Strategy Patterns

| Strategy | Count | Total Volume | Description |
|----------|-------|-------------|-------------|
| Stablecoin only | 1,782 | $177B | Borrow stables against stables (arb/yield) |
| ETH leverage/yield | 393 | $33B | Borrow stables against ETH (leveraged long) |
| ETH only | 360 | $68B | ETH-to-ETH strategies (looping wstETH/WETH) |
| Multi-asset | 346 | $156B | Diverse collateral and borrow mix |
| BTC leverage | 245 | $32B | Borrow stables against WBTC/cbBTC |

### Contract Project Breakdown (Labeled)

| Project | Borrowers | Volume | Notes |
|---------|-----------|--------|-------|
| Instadapp V2 | 245 | $27B | DeFi aggregation layer |
| 1inch | 129 | $8B | DEX aggregator users |
| MakerDAO | 92 | $5.5B | DSProxy borrowers |
| Summer.fi | 39 | $1.6B | MakerDAO frontend |
| Yearn | 16 | $10.8B | Vault strategies |
| Aave | 14 | $29B | Protocol contracts |
| Veda | 6 | $2.4B | Vault protocol (curates Lido GGV etc.) |
| Contango | 12 | $375M | Perp DEX users |
| Cian Protocol | 7 | $855M | Yield strategy platform |

## Dune Query Results (2026-02-05)

### Top Unlabeled Whales (No Identity)

Addresses with $1B+ lifetime borrowed, no Dune labels. Priority for Arkham investigation.

| Address | Protocol | Total Borrowed | Net Position | Assets |
|---------|----------|----------------|--------------|--------|
| `0xe834274bb2098bb0c7e77098055f26b0ebba9fa8` | aave | $19.9B | $34.8B | USDT, USDe |
| `0xed0c6079229e2d407672a117c22b62064f4a4312` | aave+spark | $14.4B + $7.7B | $28.9B | cbBTC, WBTC, stables |
| `0xa7c624014699a8b537cc4b326eb65f00852ee2a3` | aave | $9.5B | $19B | DAI, USDe, cbBTC, multi-asset |
| `0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5` | aave+spark | $7.3B + $5.7B | $14.8B | wstETH, WBTC, stables |
| `0xee55328d240d10b09f549dc3b2a6653c13f10bfc` | aave | $6.8B | $13.6B | USDC only |
| `0xba6d84cc7418a9c46133788c04f6a459e1fb669c` | aave | $5.2B | $10.4B | Multi-asset (20+ tokens) |
| `0x3ddfa8ec3052539b6c9549f12cea2c295cff5296` | aave | $4.8B | $9.7B | USDT, MKR, TUSD, USDC, DAI |
| `0x1484485f1ba8ff4d88bb1a8e7f131dd6f1910edb` | aave | $4.1B | $8.1B | cbBTC, GHO, multi-asset |
| `0xd275e5cb559d6dc236a5f8002a5f0b4c8e610701` | aave | $3.7B | $7.8B | USDT, DAI, USDC |
| `0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912` | aave | $3.6B | $7.3B | USDC, USDT, WETH, PYUSD, GHO |

**Note:** `0xed0c...` and `0xb99a...` are cross-protocol (Aave + Spark) — may be **Abraxas Capital** per earlier research.

### Labeled Entities (From Dune)

| Entity | Address | Protocol | Total Borrowed | Notes |
|--------|---------|----------|----------------|-------|
| **Instadapp/Fluid** | `0x9600a48ed0f931d0c422d574e3275a90d8b22745` | aave+spark+lido | $6B + $3B + $1.1B | InstaAccountV2 |
| **Celsius** (bankrupt) | `0x8aceab8167c80cb8b3de7fa6228b889bb1130ee8` | aave+compound | $3.6B + $1.7B | Celsius Network 9 |
| **EtherFi** | `0xf0bb20865277abd641a307ece5ee04e79073416c` | aave | $2.2B | liquidETH vault |
| **Yearn Finance** | Multiple | compound | $1.8B+ | yvault_strat contracts |
| **Set Protocol** | `0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd` | compound | $1.2B | SetToken |
| **SushiSwap** | `0xe08d97e151473a848c3d9ca3f323cb720472d015` | aave | $974M | |
| **Maker** | `0xccb06b8026cb33ee501476af87d5ccaf56883112` | compound+aave | $782M + $694M | DSProxy |

### MEV Bots

| Address | Total Borrowed | Protocol |
|---------|----------------|----------|
| `0x00000000032962b51589768828ad878876299e14` | $10.3B | aave |
| `0x1f2f10d1c40777ae1da742455c65828ff36df387` | $7.3B | aave |

### ENS Name Leads — Investigated 2026-02-05

| ENS | Address | Total Borrowed | Identity | Confidence |
|-----|---------|----------------|----------|------------|
| llamalend.eth | `0x7a16ff8270133f063aab6c9977183d9e72835428` | $247M | **Michael Egorov** (Curve Finance founder) | HIGH |
| notpunks.eth | `0xb1adceddb2941033a090dd166a462fe1c2029484` | $1.04B | **Jason Stone** / KeyFi (managed Celsius funds as 0xb1) | HIGH |
| czsamsunsb.eth | `0x9026a229b535ecf0162dfe48fdeb3c75f7b2a7ae` | $533M | Anon whale, sophisticated trader (OG since 2016) | MEDIUM |
| analytico.eth | `0xa0f75491720835b36edc92d06ddc468d201e9b73` | $254M | Anon whale, large LSD holder | LOW |
| mandalacapital.eth | `0xa1175a219dac539f2291377f77afd786d20e5882` | $111M | Possibly small crypto VC (sold CULT DAO tokens) | LOW |
| greenfund.eth | `0xa53a13a80d72a855481de5211e7654fabdfe3526` | $204M | Anon whale, Maker Vault owner, diverse DeFi portfolio | LOW |
| defunddao.eth | `0x66b870ddf78c975af5cd8edc6de25eca81791de1` | $1.77B | Unknown — no web presence found | LOW |
| pennilesswassie.sismo.eth | `0x9c5083dd4838e120dbeac44c052179692aa5dac5` | $813M | Anon whale, Sismo badge holder, NFT collector | LOW |

#### Detailed ENS Whale Profiles

**1. llamalend.eth — Michael Egorov (Curve Finance founder)** [HIGH CONFIDENCE]
- **Identity:** Michael Egorov, founder of Curve Finance and creator of LlamaLend/Curve Lend
- **Verification:** Etherscan labels address `0x7a16ff82...` as "Michael Egorov". CoinLive confirmed he acquired the llamalend.eth ENS domain to launch the Curve-based lending platform.
- **Twitter/X:** [@newmichwill](https://x.com/newmichwill)
- **History:** Used ~$141M CRV as collateral to borrow ~$95.7M stablecoins across Aave, Inverse, UwU Lend, Fraxlend, and LlamaLend. Suffered $140M liquidation in June 2024 when CRV price crashed. Settled Aave debt in Sept 2023 by depositing 68M CRV ($35M). Bad debt on LlamaLend repaid.
- **BD Relevance:** Founder of Curve ecosystem (~$2B+ TVL). Contactable via Twitter. Not a BD prospect for lending products (already deeply integrated in his own ecosystem).

**2. notpunks.eth — Jason Stone / KeyFi / 0xb1** [HIGH CONFIDENCE]
- **Identity:** Jason Stone, CEO of KeyFi Inc., managed the famous "0xb1" DeFi whale wallet that held $400M+ at peak
- **Verification:** Jason Stone publicly identified himself as the operator of 0xb1. Etherscan labels the address as "0x_b1". Multiple court filings (KeyFi vs Celsius lawsuit) confirm the connection.
- **Twitter/X:** [@0x_b1](https://x.com/0x_b1) (121K+ followers) — but note: Stone stated the team "no longer has any association with those funds"
- **LinkedIn:** [Jason Stone](https://www.linkedin.com/in/jason-stone-33396b161/)
- **History:** Managed ~$2B of Celsius customer deposits for DeFi yield farming (Aug 2020 - Apr 2021). Lost $61M in liquidations per Arkham. Purchased CryptoPunks and hundreds of NFTs with Celsius funds. Sued Celsius for fraud (Ponzi scheme allegation); Celsius counter-sued for theft. Settled in 2024 — KeyFi transferred tokens + NFTs to Celsius estate.
- **BD Relevance:** LOW — Stone's DeFi career is effectively over due to Celsius litigation fallout. The wallet's borrowed amounts are historical (Celsius era). The "notpunks.eth" ENS is likely a personal domain from his NFT collecting days. Not a current active borrower.

**3. czsamsunsb.eth — Anonymous Sophisticated Whale** [MEDIUM CONFIDENCE]
- **Identity:** Unknown individual, possibly a KOL (Key Opinion Leader). The name appears to reference CZ (Binance CEO) and SBF (Sam Bankman-Fried) but no confirmed link to either.
- **Linked wallet:** `0xaa1...` received 64,855 ETH from czsamsunsb.eth between Mar-Oct 2023
- **Twitter/X:** No known account
- **Tracked by:** Lookonchain, Spot On Chain (no identity disclosed)
- **Notable activity:**
  - Accumulated 42,708 ETH ($78.8M) from Binance/DEXs since Sep 2023 at avg $1,845
  - Exploited ezETH depeg: made 193 ETH ($600K) in 4 hours
  - Withdrew funds from FTX before withdrawal freeze
  - Deposited 33,067 ETH ($74.5M) to Binance over 2 days (June 2025)
  - Borrowed 8M USDC from Aave to buy 3,115 ETH at $1,926
- **BD Relevance:** MEDIUM — Active, sophisticated Aave user with large positions. No known contact method. Would need to use on-chain messaging (e.g., Blockscan Chat) or Arkham bounty.

**4. analytico.eth — Anonymous DeFi Whale** [LOW CONFIDENCE]
- **Identity:** Unknown. Described as "anon whale" by DeFi researcher Thor Hartvigsen.
- **Twitter/X:** [@Analytico__eth](https://x.com/Analytico__eth) and possibly [@cryptoanalytico](https://x.com/cryptoanalytico)
- **Tracked by:** Nansen (featured in stETH de-peg forensics report)
- **Notable activity:**
  - Deposited 6,129 stETH + 544 WETH into Curve stETH/ETH pool during 2022 depeg
  - Described by Thor Hartvigsen as "a large holder of LSD tokens"
  - Diverse DeFi portfolio: SNX, JPEG, JRT, PRISMA, RAI, Olympus tokens
- **BD Relevance:** MEDIUM — Active DeFi-native whale with LSD exposure. The Twitter accounts may be reachable for BD outreach. Could be interested in leverage products on LSD collateral.

**5. mandalacapital.eth — Possibly Small Crypto VC** [LOW CONFIDENCE]
- **Identity:** Unknown. CryptoRank lists a "Mandala Capital" as a Tier 4 crypto venture fund with 2 investments (Mind Network). Cult DAO community member @MrOmodulus identified the wallet as a "centralized VC investor" who sold 30B CULT tokens (~$1M) in mid-2022.
- **Twitter/X:** No confirmed account
- **Website:** No confirmed website (separate from mandala-capital.com, which is an agriculture PE firm)
- **Notable activity:**
  - Sold large CULT DAO position in 2022 creating sell pressure
  - Active on Aave with $111M borrowed
- **BD Relevance:** LOW-MEDIUM — If this is a crypto VC fund, they may be reachable through crypto VC networks. Very limited public information makes outreach difficult.

**6. greenfund.eth — Anonymous DeFi Whale** [LOW CONFIDENCE]
- **Identity:** Unknown individual or entity. Etherscan tags as "Maker Vault Owner."
- **Twitter/X:** No known account
- **OpenSea:** [greenfund](https://opensea.io/greenfund) (joined Sep 2019, ~50.55 ETH NFT portfolio)
- **Notable holdings:**
  - ~2,399 aEthMKR (~$3.4M) deposited in Aave
  - ~8,243 veCRV (Curve governance)
  - 100,000 GHO
  - Positions in Convex, Badger, Hegic, Saddle, Ribbon Finance
  - $6.3M portfolio across 13 chains, 17,830 transactions
- **BD Relevance:** LOW-MEDIUM — Clearly a DeFi power user with MKR/Curve governance participation. No known contact method. Long transaction history suggests OG DeFi participant.

**7. defunddao.eth — Unknown** [LOW CONFIDENCE]
- **Identity:** Unknown. No web presence found. Not the same as "DeFund Protocol" (@defund_io on Twitter, a Celestia-based project).
- **Twitter/X:** No account found matching "defunddao"
- **Notable:** $1.77B lifetime Aave borrowing is massive, but zero public footprint makes this highly unusual. Could be a protocol/vault masquerading as a personal ENS, or a very privacy-conscious entity.
- **BD Relevance:** LOW — No known contact method. The ENS name suggests a DAO structure but no governance forum, website, or social presence exists.

**8. pennilesswassie.sismo.eth — Anonymous Whale** [LOW CONFIDENCE]
- **Identity:** Unknown. The ".sismo.eth" subdomain indicates they received a Sismo protocol badge/attestation (Sismo is a privacy-focused attestation protocol).
- **Twitter/X:** No known account
- **NFT profile:** NFTGo ranks as "Blue Chip Holder" (#4215), holding 577 NFTs across 19 collections. 206 buys, 3 sells, 237 mints — net buyer/collector.
- **BD Relevance:** LOW — Privacy-focused user (Sismo subdomain). No known contact method. Heavy NFT collector profile alongside $813M Aave borrowing suggests sophisticated operator.

## Wallet Identity Tools (with Pricing)

Tools for identifying unknown wallet addresses. Updated 2026-02-06 with full pricing research.

### FREE — Use First

| Tool | Use For | URL | Notes |
|------|---------|-----|-------|
| **Arkham Intelligence** | Entity labels, wallet clustering, alerts | `intel.arkm.com` | Best free tool. AI-powered de-anonymization |
| **Etherscan/Basescan** | Labels, contract verification, first funder | `etherscan.io` | Community + partner labels |
| **Blockscan Chat** | **Message any wallet directly** | `chat.blockscan.com` | Free, off-chain, encrypted. Best for BD outreach |
| **DeBank** | DeFi positions, multi-chain portfolio | `debank.com/profile/{addr}` | Requires JS rendering |
| **MetaSleuth** | Visual fund flow tracing | `metasleuth.io` | Free tier has graph limits |
| **ENS Lookup** | Reverse resolve address → .eth name | `app.ens.domains` | Only if they registered one |
| **Snapshot** | Governance voting history | `snapshot.org` | Only if they voted |
| **DeFiLlama** | Protocol TVL, yields | `defillama.com` | No wallet-level identity |
| **Dune Analytics** | SQL queries, `labels.ens`, `labels.owner_addresses` | `dune.com` | Free tier limited executions |
| **Cielo** | Multi-chain wallet tracker, alerts | `cielo.finance` | Free + paid tiers |
| **Flipside Crypto** | Free SQL queries, Ethereum/Solana labels | `flipsidecrypto.xyz` | Good label coverage |
| **Lending CRM** | Spark/Aave top borrowers | `lending-crm.vercel.app` | Labels often speculative |
| **Lookonchain** | Whale alerts on Twitter | `@lookonchain` on X | Social monitoring |
| **Gitcoin Passport** | Sybil resistance scores | `passport.gitcoin.co` | Identity verification |

### CHEAP ($1–$80/month) — High Value for BD

| Tool | Use For | Cost | Sells Data? |
|------|---------|------|-------------|
| **LeakPeek** | Search leaked DBs (email, username) | $2 trial / $10/mo / $28/3mo | No — search their index |
| **Snusbase** | Search breached DBs (email, IP, hash) | $5–$16/mo or $333 lifetime | No — search their index |
| **OSINT Industries** | Email/phone/wallet → linked accounts (1000+ sources) | ~$24/mo (£19+) | Aggregates public data |
| **Nansen** | **500M+ labeled wallets**, smart money tracking | **$49/mo annual / $69/mo** | No — proprietary labels |
| **Breadcrumbs** | Fund flow visualization, risk scoring | $49–$79/mo | No |
| **Intelx** | Deep web and database search | Free tier + paid | No |

### MARKETPLACE — Data Buying/Selling

| Tool | Use For | Cost | Sells Data? |
|------|---------|------|-------------|
| **Arkham Intel Exchange** | Buy/sell wallet identity via ARKM token bounties | Varies ($50–$150K+) | **YES — literal data marketplace** |

Arkham takes 2.5% fee on bounties, 5% on payouts. 90-day exclusivity, then data goes public. Critics call it "Snitch-to-Earn."

### ENTERPRISE ($10K+/year) — Compliance/Law Enforcement

| Tool | Use For | Cost | Notes |
|------|---------|------|-------|
| **Chainalysis** | Court-grade forensics, KYT, sanctions | Custom ($50K–$500K+/yr) | Industry standard for compliance |
| **TRM Labs** | Transaction graphs, entity tracking | Custom (avg ~$693K/yr) | Used by law enforcement |
| **Elliptic** | AML screening, transaction monitoring | Custom (mid-to-high) | Compliance-focused |
| **Crystal Intelligence** | Blockchain analytics, compliance | Custom (enterprise only) | Bitfury spinoff |
| **Merkle Science** | Predictive risk scoring | Custom | Asia-focused |
| **Credora** | On-chain credit scoring | Custom | Used by Maple, Clearpool |
| **Spectral Finance** | ML-based credit scores (MACRO) | Custom | DeFi-native credit |

### Specialized / OSINT

| Tool | Use For | Cost | Notes |
|------|---------|------|-------|
| **Bitquery Coinpath** | Wallet clustering via fund flow analysis | Paid API | GraphQL API |
| **Covalent (GoldRush)** | Unified API for multi-chain wallet data | Free tier + paid | Good for batch lookups |
| **Wayback Machine** | Archived web pages | Free | Capture deleted content |
| **Archive Today** | Web page snapshots | Free | Preserve evidence |

### Investigation Priority Order (BD Outreach)

```
1. Blockscan Chat  → Message wallet directly (FREE, immediate)
2. Arkham          → Check existing labels (FREE)
3. Etherscan       → Contract type, labels, first funder (FREE)
4. DeBank          → Full portfolio and DeFi positions (FREE)
5. Dune labels     → labels.owner_addresses, labels.ens, cex.addresses (FREE)
6. MetaSleuth      → Visual tracing if funding chain is complex (FREE)
7. Nansen          → 500M+ labels ($49/mo) — highest ROI paid tool
8. OSINT Industries→ Reverse-search email/ENS (~$24/mo)
9. Arkham Bounty   → Post bounty for high-value targets (variable)
10. LeakPeek       → If you find email via ENS/governance ($10/mo)
```

**Skip for BD:** Chainalysis, TRM Labs, Elliptic — $50K+/yr compliance tools for exchanges and law enforcement

### Data Privacy Notes

| Tool | Data Practice |
|------|--------------|
| **Arkham Intel Exchange** | Users buy/sell identity data for ARKM tokens. Your identity research could be sold. |
| **LeakPeek / Snusbase** | Index existing leaked databases. Legal gray area in some jurisdictions. |
| **OSINT Industries** | Aggregates 1000+ public sources. Not selling data — surfacing what's already public. |
| **Nansen / Chainalysis / TRM** | Proprietary labels. Data stays private to subscribers. |

## Task 6: Missing Users/Lanes Analysis (2026-02-05)

Analysis of what borrower types and data gaps the BD team may be missing.

### Dataset Coverage

| Dimension | Coverage | Gap |
|-----------|----------|-----|
| **Protocols** | Aave, Compound, Spark, Morpho, Aave Lido, Aave Horizon | Missing: Fluid, Maple, Euler, Silo, Radiant, Moonwell, Seamless |
| **Chains** | Ethereum mainnet only | Missing: Arbitrum, Base, Optimism, Polygon (where Index has products) |
| **Threshold** | $10M+ lifetime borrowed | Smaller borrowers ($1M-$10M) may be emerging whales |
| **Time** | All-time cumulative | No recency filter — some positions are closed/historical |

### Priority BD Lanes (Ranked by Opportunity)

#### 1. Unlabeled Whales — CRITICAL ($238B, 391 addresses)

391 addresses with >$100M borrowed and **zero identity labels**. This represents 50.8% of all borrowed volume. Identifying even the top 50 would unlock more BD opportunity than any single labeled category.

**Top unlabeled (>$5B lifetime borrowed):**

| Address | Borrowed | Protocol | Assets |
|---------|----------|----------|--------|
| `0xe834274bb2098bb0c7e77098055f26b0ebba9fa8` | $19.9B | Aave | USDT, USDe |
| `0xa7c624014699a8b537cc4b326eb65f00852ee2a3` | $9.5B | Aave | DAI, USDe, cbBTC |
| `0xee55328d240d10b09f549dc3b2a6653c13f10bfc` | $6.8B | Aave | USDC only (likely bot) |
| `0xba6d84cc7418a9c46133788c04f6a459e1fb669c` | $5.2B | Aave | Multi-asset (20+ tokens) |

**Action**: Use Arkham/Nansen to label top 50. Use Safe API to resolve 156 "Safe Wallet" labels to actual entities.

#### 2. L2 Borrowers — CRITICAL GAP ($0 in dataset)

The dataset covers **Ethereum mainnet only**. Zero data on:
- Aave V3 on Arbitrum — where Index Coop has ETH2x, BTC2x
- Aave V3 on Base — where Index Coop has ETH2x, cbBTC2x, BTC3x, etc.
- Moonwell (Base) — major Base lending protocol
- Seamless (Base) — native Base lending
- Radiant (Arbitrum, Base) — cross-chain lending
- Silo Finance (Arbitrum) — isolated lending

**Action**: Build a parallel Dune query for L2 lending protocols. This is the single biggest data gap for BD since Index Coop's growth is on L2s.

#### 3. DAO Treasuries — HIGH ($9.9B, 157 addresses)

157 Safe multisig wallets borrowing $9.9B total. The labels only say "Safe Wallet" — we don't know **which DAOs** these are.

**Top Safe borrowers:**

| Address | Borrowed | Notes |
|---------|----------|-------|
| `0xf20b3387fd3b6529ebc8caeed3a01f8f19e9a09c` | $557M | Unknown DAO |
| `0xa976ea51b9ba7225a886cded813fa470a1b3e531` | $545M | Unknown DAO |
| `0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3` | $505M | Unknown DAO |
| `0x99926ab8e1b589500ae87977632f13cf7f70f242` | $454M | Unknown DAO |

**Action**: Use Safe API (`safe-transaction-service.safe.global/api/v1/safes/{address}/`) to get signer addresses, then cross-reference signers with known entities.

**BD Angle**: DAOs borrowing at scale need yield-bearing collateral and treasury management. Index Coop products (hyETH, dsETH) fit as productive treasury collateral.

#### 4. Emerging Yield Protocols — HIGH ($5.8B, ~20 addresses)

Protocols building leveraged yield strategies — natural Index Coop partners/integrators.

| Protocol | Addresses | Borrowed | Notes |
|----------|-----------|----------|-------|
| **Veda** (BoringVault) | 6 | $2,359M | Rapidly growing yield optimization, curates Lido GGV |
| **Cian Protocol** | 10 | $1,723M | Leveraged yield strategy platform |
| **Sturdy V2** | 1 | $577M | Structured yield |
| **Mellow Strategy** | 2 | $431M | Restaking vault strategy |
| **Contango** | 12 | $375M | Perp DEX (leveraged positions) |
| **Treehouse** | 2 | $497M | Institutional yield (tETH) |

**BD Angle**: These protocols are building exactly what Index Coop's leverage tokens automate. Partnership discussions could focus on integrating Index Coop tokens as vault strategies or collateral types.

#### 5. Staking Entities / Node Operators — MEDIUM ($349M, 7 labeled)

Only 7 addresses have staking labels — a severe labeling gap. Many of the 391 unlabeled whales likely run validators.

| Address | Borrowed | Staking Category |
|---------|----------|-----------------|
| `thomasg.eth` (0xb1e9d641...) | $195M + $25M | Solo Staker |
| Coinbase (0x11dbf181...) | $49M | CEX Staker |
| `anyfund.eth` (0x5c7c6d06...) | $33M | Solo Staker |
| `speed.eth` (0x4573cf12...) | $18M | Solo Staker |

Node operators (Lido, Rocketpool, SSV operators) are **completely absent** from labels.

**BD Angle**: Node operators borrowing stablecoins against staked ETH are natural fits for leveraged staking products (icETH, wsETH2x).

#### 6. Market Makers — LOW-MEDIUM ($29M, 1 labeled)

Only Wintermute found (1 address, $29M on Aave). Market makers typically borrow OTC or through prime brokerage rather than on-chain, or use unlabeled wallets.

**Not found in data**: Jump, GSR, Galaxy, DWF, Cumberland, Flow Traders, B2C2, QCP Capital, Amber Group.

### Lanes NOT Worth Pursuing

| Lane | Volume | Reason |
|------|--------|--------|
| **MEV Bots** | $18.4B (9 addresses) | Not BD targets — automated flash loan arb. Filter from analysis. |
| **Defunct CeFi** | $5.3B (Celsius) + others | Bankrupt entities (Celsius, Hotbit). Dead money. |
| **Exploit addresses** | $1.7B | Yearn exploiter, BT.Finance — not reachable. |

### Protocols Not in Dune Lending Tables

#### Fluid (Instadapp)

- **NOT in `lending.borrow` spellbook**. Fluid-specific smart contract queries would be needed.
- The Fluid addresses in our data (`0x9600...`, `0x3a0d...`) are Instadapp smart accounts borrowing **on** Aave/Spark — not Fluid-native lending.
- Fluid-native lending data: ~$6B TVL, cross-chain (Ethereum, Arbitrum, Base, Polygon).
- **Dune dashboards**: [Fluid DEX](https://dune.com/dknugo/fluid-dex), [Instadapp DSA](https://dune.com/shippooordao/Instadapp-DSA-Dashboard)
- **Analytics**: [Blockworks Fluid Analytics](https://blockworks.com/analytics/fluid)

#### Maple Finance

- **Institutional, KYC-gated** — 80+ borrowers, 1,500+ lenders, $2B+ originations.
- Borrower identities are **not public**. Managed through permissioned pool delegates.
- Products: syrupUSDC, syrupUSDT yield-bearing stablecoins.
- **Dune dashboards**: [Maple Finance](https://dune.com/maple-finance), [Maple Deposits](https://dune.com/scottincrypto/Maple-Deposits)
- **BD approach**: Contact Maple's network partners or pool delegates directly rather than on-chain investigation.
- **Network partners**: [maple.finance/news/maples-network-partners](https://maple.finance/news/maples-network-partners)

### Recommended Next Steps (Priority Order)

1. **Build L2 borrower query** — Add Aave V3 on Arbitrum + Base to Dune query 6654792. This fills the biggest data gap for Index Coop BD.
2. **Resolve Safe multisig identities** — Use Safe API for the 157 Safe wallets to identify which DAOs/funds they represent.
3. **Label top 50 unlabeled whales** — Batch Arkham/Nansen lookup. Even partial identification has high ROI.
4. **Partner outreach to yield protocols** — Veda, Cian, Contango, Sturdy are building leveraged yield strategies and are natural integration partners.
5. **Fluid borrower query** — Build protocol-specific query for Fluid's native lending markets (separate from Aave/Spark positions).
6. **Maple partnership** — Contact Maple pool delegates for institutional borrower introductions.

## Data Sources

- [Dune Query 6654792](https://dune.com/queries/6654792) - Top borrowers with labels
- [Lending CRM - Spark](https://lending-crm.vercel.app/?source=spark)
- [Lending CRM - Aave](https://lending-crm.vercel.app/?source=aave)
- [Arkham Intelligence](https://intel.arkm.com/)
- [Etherscan](https://etherscan.io/)
- [DeBank](https://debank.com/)
- [Chaos Labs Aave Risk Dashboard](https://community.chaoslabs.xyz/aave/ccar/overview)
- [Blockworks Fluid Analytics](https://blockworks.com/analytics/fluid)
- [Maple Finance Network Partners](https://maple.finance/news/maples-network-partners)
- [Fluid DEX Dashboard (Dune)](https://dune.com/dknugo/fluid-dex)
- [Maple Finance Dashboard (Dune)](https://dune.com/maple-finance)
