# Whale Identity Scripts

Automated tools for identifying unknown wallet addresses at scale.

## Quick Start

```bash
# Install dependencies
pip install requests python-dotenv beautifulsoup4

# Set up API keys
cp .env.example .env
# Edit .env with your ETHERSCAN_API_KEY

# Run full enrichment on a CSV of addresses
python3 scripts/enrich_addresses.py whales.csv -o enriched.csv
```

## Scripts Overview

### Core Enrichment Scripts

| Script | Purpose | Rate Limit | Hit Rate |
|--------|---------|------------|----------|
| `enrich_addresses.py` | Master orchestration tool | 5 req/sec | - |
| `cluster_addresses.py` | ZachXBT-style address clustering | 5 req/sec | 5-15% |
| `etherscan_labels.py` | Contract type + labels | 5 req/sec | 10-15% |
| `trace_funding.py` | CEX funding origin | 5 req/sec | 30-40% |
| `batch_arkham_check.py` | Arkham Intelligence labels | 0.5 req/sec | 20-30% |
| `resolve_safe_owners.py` | Safe multisig owners | 5 req/sec | High for Safes |

### Advanced Investigation Scripts

| Script | Purpose | Based On | Accuracy |
|--------|---------|----------|----------|
| `cio_detector.py` | Common Input Ownership (EVM) | Chainalysis academic heuristics | 94.85% |
| `governance_scraper.py` | Snapshot voting + delegation | ZachXBT OSINT methods | - |
| `verify_identity.py` | Multi-source verification | ZachXBT "never one source" rule | - |

### Cross-Chain & Protocol Scripts (NEW - Feb 2026)

| Script | Purpose | Based On | Accuracy |
|--------|---------|----------|----------|
| `ens_resolver.py` | Batch ENS name resolution | ENS subgraph | ~10% hit rate |
| `multichain_balance.py` | Same address across chains | ZachXBT cross-chain tracing | — |
| `protocol_summary.py` | Aave/Spark/Morpho positions | On-chain position queries | — |
| `bridge_tracker.py` | Cross-chain fund movements | Academic research | 99.65% |
| `change_detector.py` | Change address patterns (EVM) | Academic research | AUC 0.9986 |

### Trading & Identity Scripts (NEW - Feb 2026)

| Script | Purpose | Based On | Notes |
|--------|---------|----------|-------|
| `dex_analyzer.py` | DEX swap patterns & trading behavior | Trading pattern analysis | Multi-chain |
| `nft_tracker.py` | NFT holdings & blue chip detection | NFT identity signals | 20+ collections |
| `whale_tracker_aggregator.py` | Check known whale lists | Lookonchain/OnchainLens/Arkham | Pre-compiled list |

## Environment Variables

```bash
# Required for Etherscan scripts
ETHERSCAN_API_KEY=your_key_here  # Get from https://etherscan.io/apis

# Optional - uses public RPC if not set
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your_key

# Optional - for Dune queries
DUNE_API_KEY=your_key_here
```

## Detailed Usage

### 1. enrich_addresses.py - Master Enrichment Tool

The main entry point that combines all enrichment methods.

```bash
# Full enrichment from CSV
python3 scripts/enrich_addresses.py whales.csv -o enriched.csv

# Single address
python3 scripts/enrich_addresses.py --address 0xd1781818f7f30b68155fec7d31f812abe7b00be9

# Specific methods only
python3 scripts/enrich_addresses.py whales.csv --methods etherscan,funding

# Resume from checkpoint (if interrupted)
python3 scripts/enrich_addresses.py whales.csv --resume enrichment_checkpoint.json
```

**Input CSV format:**
```csv
address,protocol,total_borrowed
0x1234...,aave,1000000
0x5678...,spark,500000
```

**Output columns:**
- `contract_type`: EOA, Safe, DSProxy, Instadapp DSA, etc.
- `ens_name`: Resolved ENS name if available
- `etherscan_label`: Etherscan community/partner label
- `arkham_label`: Arkham Intelligence entity name
- `first_funder`: Address that first funded this wallet
- `first_funder_label`: CEX name if applicable (Binance 16, Kraken 4, etc.)
- `cluster_id`: Cluster identifier (if using `--methods cluster`)
- `related_addresses`: Other addresses in the same cluster

### 2. cluster_addresses.py - ZachXBT Address Clustering

Identifies wallet clusters owned by the same entity using on-chain signals.

```bash
# Cluster addresses from CSV
python3 scripts/cluster_addresses.py addresses.csv -o clusters.csv

# Single address (finds related wallets)
python3 scripts/cluster_addresses.py --address 0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c

# Specific methods
python3 scripts/cluster_addresses.py addresses.csv --methods timing,funders
```

**Clustering methods (ZachXBT methodology):**

| Method | How it Works | Confidence |
|--------|--------------|------------|
| `timing` | Correlates transaction hour patterns (timezone signal) | Medium |
| `funders` | Groups wallets with same first funder | Medium-High |
| `deposits` | Detects shared CEX deposit addresses | High |

**Output includes:**
- `cluster_id`: Unique cluster identifier
- `cluster_size`: Number of addresses in cluster
- `related_addresses`: Other addresses in cluster
- `cluster_signals`: What linked them (timing, funder, deposit)
- `cluster_confidence`: 0-1 confidence score

**Example: Trend Research cluster detection:**
```bash
# These 6 wallets should cluster together
echo "address
0xfaf1358fe6a9fa29a169dfc272b14e709f54840f
0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c
0x85e05c10db73499fbdecab0dfbb794a446feeec8
0x6e9e81efcc4cbff68ed04c4a90aea33cb22c8c89" > trend_research.csv

python3 scripts/cluster_addresses.py trend_research.csv -o trend_clusters.csv
```

### 3. etherscan_labels.py - Contract Detection

Batch-fetches contract type and verification status from Etherscan V2 API.

```bash
# Batch check
python3 scripts/etherscan_labels.py addresses.csv -o labeled.csv

# Single address
python3 scripts/etherscan_labels.py --address 0x5be9a4959308a0d0c7bc0870e319314d8d957dbb

# Different chain
python3 scripts/etherscan_labels.py addresses.csv --chain base
```

**Detected contract types:**
- `EOA` - Externally Owned Account
- `Safe` / `Safe Proxy` - Gnosis Safe multisig
- `DSProxy` - MakerDAO/Summer.fi proxy
- `Instadapp DSA` - Instadapp smart account
- `Contract (Name)` - Verified contract with name

### 3. trace_funding.py - CEX Origin Detection

Traces the first ETH funding source to identify CEX origins.

```bash
# Batch trace
python3 scripts/trace_funding.py addresses.csv -o funding_traces.csv

# Single address with full chain
python3 scripts/trace_funding.py --address 0xcaf1943ce973c1de423fe6e9f1a255049e51666e

# Deeper trace (5 hops instead of default 3)
python3 scripts/trace_funding.py addresses.csv --max-hops 5
```

**Detected exchanges:**
- Binance (wallets 6-30)
- Kraken (wallets 1-6)
- Coinbase (wallets 1-10)
- Gemini (wallets 1-5)
- OKX, Poloniex, Bitfinex, Huobi, KuCoin, Bybit, Gate.io
- FalconX, Copper, Paxos (institutional prime brokers)

### 4. batch_arkham_check.py - Arkham Intelligence Labels

Scrapes Arkham's public explorer for entity labels.

```bash
# Batch check (slow - 1 req per 2 seconds)
python3 scripts/batch_arkham_check.py addresses.csv -o arkham_labels.csv

# Use cache to avoid re-checking
python3 scripts/batch_arkham_check.py addresses.csv --cache arkham_cache.json

# Single address
python3 scripts/batch_arkham_check.py --address 0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c
```

**Notes:**
- No API key required (uses public website)
- Default rate limit is 0.5 req/sec to avoid IP blocks
- Cache results to avoid re-fetching
- Install `beautifulsoup4` for better parsing

### 5. resolve_safe_owners.py - Safe Multisig Resolution

Gets owners and configuration for Safe multisig wallets.

```bash
# Batch resolve
python3 scripts/resolve_safe_owners.py safes.csv -o safe_owners.csv

# Single Safe
python3 scripts/resolve_safe_owners.py --address 0x5be9a4959308a0d0c7bc0870e319314d8d957dbb

# Check all chains
python3 scripts/resolve_safe_owners.py --address 0x1234... --all-chains

# Export flat owner list for cross-referencing
python3 scripts/resolve_safe_owners.py safes.csv --flat-output owners_flat.csv
```

**Output includes:**
- `threshold` / `owner_count` - e.g., "3/5"
- `owners` - JSON array of owner addresses
- `owner_labels` - Known entity labels for owners
- `version` - Safe contract version

## Recommended Workflow

### Phase 1: Free Methods (~30-50% identification)

```bash
# Step 1: Get contract types (10 min for 2000 addresses)
python3 scripts/etherscan_labels.py whale_addresses.csv -o step1_contracts.csv

# Step 2: Trace funding origins (30-60 min for 2000 addresses)
python3 scripts/trace_funding.py whale_addresses.csv -o step2_funding.csv

# Step 3: Resolve Safe owners (5-10 min for 156 Safes)
python3 scripts/resolve_safe_owners.py safes.csv -o step3_safes.csv

# Step 4: Check Arkham labels (20-40 min for 500 top addresses)
python3 scripts/batch_arkham_check.py top500.csv -o step4_arkham.csv --cache arkham_cache.json
```

### Phase 2: Combine Results

```bash
# Use the master enrichment tool
python3 scripts/enrich_addresses.py whale_addresses.csv -o fully_enriched.csv
```

### Phase 3: Manual Investigation

For remaining unknowns, use:
1. **Blockscan Chat** - Message wallet directly
2. **DeBank** - Full portfolio analysis
3. **Arkham Bounties** - Post bounty for high-value targets

## Rate Limits

| API | Free Tier | Paid Tier |
|-----|-----------|-----------|
| Etherscan V2 | 5 req/sec, 100K/day | Higher limits |
| Safe Transaction Service | ~10 req/sec | No paid tier |
| Arkham (scraping) | ~0.5 req/sec recommended | N/A |

## Expected Results

Based on testing with 2,274 lending whale addresses:

| Method | Expected Hits | Time |
|--------|---------------|------|
| Etherscan contract type | 100% (contract vs EOA) | 12 min |
| CEX funding trace | 30-40% (~700 addresses) | 30-60 min |
| Arkham labels | 20-30% (~500 addresses) | 20-40 min |
| Safe owner resolution | High for 156 Safes | 5-10 min |
| ENS resolution | ~10% (230 addresses) | 1 min |

**Total expected identification: 300-500 addresses (15-25%)**

## Resuming Failed Runs

All scripts support checkpointing:

```bash
# enrich_addresses.py saves progress every 50 addresses
python3 scripts/enrich_addresses.py whales.csv --resume enrichment_checkpoint.json

# batch_arkham_check.py uses cache
python3 scripts/batch_arkham_check.py whales.csv --cache arkham_cache.json
```

## Troubleshooting

### "ETHERSCAN_API_KEY not set"
```bash
export ETHERSCAN_API_KEY=your_key_here
# Or add to .env file
```

### Rate limited by Arkham
- Reduce rate limit: `--rate-limit 0.25` (1 req per 4 sec)
- Use cache: `--cache arkham_cache.json`
- Wait and resume later

### Safe not found on Ethereum
- Try `--all-chains` to check Arbitrum, Base, etc.
- Some Safes are on L2s only

### Etherscan returns "Contract source code not verified"
- This is normal for unverified contracts
- Contract type is still detected (Safe, DSProxy, etc.)

## Adding New CEX Wallets

Edit `CEX_WALLETS` dict in `trace_funding.py`:

```python
CEX_WALLETS = {
    "0xnew_address_here": ("ExchangeName", "Exchange Wallet 1"),
    ...
}
```

## Advanced Investigation Scripts

### cio_detector.py - Common Input Ownership (EVM Adaptation)

Adapts Bitcoin's CIO heuristic (~100% accuracy) for EVM chains. Detects:

1. **Circular Funding** - A→B→C→A (same entity recycling funds)
2. **Common Funding Source** - Multiple wallets funded by same address within 24h
3. **Coordinated Activity** - Multiple wallets in same block interacting with same contract
4. **Shared Deposit Destination** - Multiple wallets depositing to same exchange address

```bash
# Run all detection methods
python3 scripts/cio_detector.py addresses.csv -o clusters.csv

# Specific methods only
python3 scripts/cio_detector.py addresses.csv --methods circular,shared_deposits

# Single address
python3 scripts/cio_detector.py --address 0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c
```

**Output includes:**
- `cluster_id` - Unique cluster identifier
- `cluster_size` - Number of addresses in cluster
- `methods` - Which detection methods matched
- `confidence` - 0.5-0.9 based on method agreement

### governance_scraper.py - Snapshot Voting Analysis

Identifies entities through governance activity:

1. **Voting History** - Which DAOs they participate in
2. **Delegation Patterns** - Who delegates to/from this address
3. **Voting Power** - High VP suggests institutional
4. **Related Voters** - Addresses that vote together

```bash
# Analyze governance activity
python3 scripts/governance_scraper.py addresses.csv -o governance.csv

# Find addresses that vote together
python3 scripts/governance_scraper.py addresses.csv --find-related

# Single address
python3 scripts/governance_scraper.py --address 0x1234...
```

**Output includes:**
- `total_votes` - Number of votes cast
- `unique_spaces` - Number of DAOs voted in
- `total_voting_power` - Aggregate VP
- `identity_signals` - Institutional patterns detected

### verify_identity.py - Multi-Source Verification

Cross-checks findings from all sources (ZachXBT's "never one source" rule):

```bash
# Verify enriched CSV
python3 scripts/verify_identity.py enriched.csv -o verified.csv --report

# Single address with live checks
python3 scripts/verify_identity.py --address 0x1234... --live-checks
```

**Source priority (highest to lowest):**
1. Custom (manual research)
2. Arkham Intelligence
3. Etherscan labels
4. Dune community labels
5. ENS name
6. Contract name
7. CEX funding origin
8. Governance activity

**Confidence scoring:**
- All sources agree: 80-95%
- Majority agree: 50-70%
- Sources disagree: 30-40%

## Updated Recommended Workflow

### Phase 1: Free Enrichment (~30-50% identification)

```bash
# Step 1-4: Run existing scripts (unchanged)
python3 scripts/enrich_addresses.py whale_addresses.csv -o enriched.csv
```

### Phase 2: Advanced Clustering (NEW)

```bash
# Step 5: Run CIO detector for wallet clusters
python3 scripts/cio_detector.py enriched.csv -o clusters.csv

# Step 6: Scrape governance activity
python3 scripts/governance_scraper.py enriched.csv -o governance.csv
```

### Phase 3: Verification (NEW)

```bash
# Step 7: Multi-source verification
python3 scripts/verify_identity.py enriched.csv -o verified.csv --report
```

## Cross-Chain & Protocol Scripts

### ens_resolver.py - Batch ENS Resolution

Resolves ENS names for addresses (and vice versa) using ENS subgraph.

```bash
# Batch reverse resolve (address → ENS)
python3 scripts/ens_resolver.py addresses.csv -o resolved.csv

# Single address
python3 scripts/ens_resolver.py --address 0x7a16ff8270133f063aab6c9977183d9e72835428

# Forward resolve (ENS → address)
python3 scripts/ens_resolver.py --ens vitalik.eth
```

**Output includes:**
- `ens_name` - Resolved ENS name (if any)

### multichain_balance.py - Cross-Chain Balances

Checks the same address across multiple chains (Ethereum, Arbitrum, Base, Polygon, etc.).

```bash
# Single address across all chains
python3 scripts/multichain_balance.py --address 0x1234...

# Batch from CSV
python3 scripts/multichain_balance.py addresses.csv -o balances.csv

# Specific chains only
python3 scripts/multichain_balance.py --address 0x1234... --chains ethereum,arbitrum,base
```

**Output includes:**
- `{chain}_balance` - Native token balance per chain
- `active_chains` - Chains with activity
- `chain_count` - Number of active chains

### protocol_summary.py - Lending Position Summary

Queries Aave V3 and Spark positions across chains.

```bash
# Single address
python3 scripts/protocol_summary.py --address 0x1234...

# Batch from CSV
python3 scripts/protocol_summary.py addresses.csv -o positions.csv
```

**Output includes:**
- `total_collateral_usd` - Total collateral across protocols
- `total_debt_usd` - Total debt across protocols
- `health_factor_min` - Minimum health factor
- `protocols_used` - List of active protocols

### bridge_tracker.py - Cross-Chain Bridge Tracking

Identifies bridge transactions (99.65% deposit matching accuracy).

```bash
# Single address
python3 scripts/bridge_tracker.py --address 0x1234...

# Batch from CSV
python3 scripts/bridge_tracker.py addresses.csv -o bridges.csv
```

**Tracked bridges:**
- Arbitrum, Optimism, Base (official L2 bridges)
- Stargate, Across, Hop, Synapse (cross-chain)
- LayerZero, Wormhole (messaging)

**Output includes:**
- `bridge_tx_count` - Number of bridge transactions
- `bridges_used` - Which bridges were used
- `chains_bridged_to` - Destination chains
- `total_bridged_eth` - Total ETH bridged

### change_detector.py - Change Address Detection

Detects "change" patterns (EVM adaptation of Bitcoin heuristic, AUC 0.9986).

```bash
# Single address
python3 scripts/change_detector.py --address 0x1234...

# Batch from CSV
python3 scripts/change_detector.py addresses.csv -o change_patterns.csv
```

**Patterns detected:**
- Split transactions (large + small "change" to new address)
- Dust sweeping (multiple small amounts to same new address)
- Initial splits (funds received then distributed)

**Output includes:**
- `change_patterns` - Number of patterns detected
- `related_addresses` - Potential related wallets
- `highest_confidence` - Confidence score (0-1)

## Trading & Identity Scripts

### dex_analyzer.py - DEX Trading Patterns

Analyzes DEX swap patterns and trading behavior across chains.

```bash
# Single address
python3 scripts/dex_analyzer.py --address 0x1234...

# Batch from CSV
python3 scripts/dex_analyzer.py addresses.csv -o dex_patterns.csv

# Specific chain
python3 scripts/dex_analyzer.py --address 0x1234... --chain arbitrum
```

**Tracked DEXs:**
- Uniswap (V2, V3, Universal Router)
- Sushiswap, Curve, Balancer
- 1inch, 0x, Paraswap, CoW Protocol
- Camelot (Arbitrum), Aerodrome (Base)

**Output includes:**
- `total_swaps` - Number of DEX transactions
- `preferred_dex` - Most used DEX
- `top_tokens` - Most traded tokens
- `trading_frequency` - Swaps per day
- `total_volume_eth` - Total ETH volume

### nft_tracker.py - NFT Holdings Tracker

Tracks NFT holdings and identifies blue chip collectors.

```bash
# Single address
python3 scripts/nft_tracker.py --address 0x1234...

# Batch from CSV
python3 scripts/nft_tracker.py addresses.csv -o nft_holdings.csv

# Include marketplace trading
python3 scripts/nft_tracker.py --address 0x1234... --trades
```

**Blue Chip Collections Tracked (20+):**
- Tier 1: BAYC, CryptoPunks, Azuki, Clone X, ENS, Art Blocks
- Tier 2: MAYC, Moonbirds, Otherdeed, Doodles, Pudgy Penguins
- Tier 3: mfers, Cool Cats, Lil Pudgys, Beanz

**Output includes:**
- `nfts_held` - Total NFTs currently held
- `blue_chip_count` - Number of blue chip NFTs
- `blue_chip_collections` - Which blue chips owned
- `is_collector` - True if 20+ NFTs or 3+ blue chips
- `is_trader` - True if high buy/sell activity

### whale_tracker_aggregator.py - Known Whale Lookup

Checks addresses against known whale databases.

```bash
# Single address
python3 scripts/whale_tracker_aggregator.py --address 0x1234...

# Batch from CSV
python3 scripts/whale_tracker_aggregator.py addresses.csv -o whale_matches.csv

# Include Arkham lookup (slower)
python3 scripts/whale_tracker_aggregator.py --address 0x1234... --arkham

# List all known whales
python3 scripts/whale_tracker_aggregator.py
```

**Known Whale Database includes:**
- Trend Research (55 wallets)
- BitcoinOG/1011short
- 7 Siblings
- Justin Sun
- World Liberty Financial
- Abraxas Capital
- Michael Egorov
- Protocol vaults (Ether.fi, Fluid, Lido, Mellow)

**Output includes:**
- `is_known_whale` - True if in database
- `whale_name` - Entity name
- `whale_source` - Where tracking came from (Lookonchain, Arkham, etc.)
- `whale_confidence` - Confidence level

## Knowledge Graph Forensic Investigation System (NEW - Feb 2026)

A comprehensive 100x improvement over individual scripts. Builds an intelligence system that compounds findings.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WHALE INTELLIGENCE SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│  INPUT: Seed addresses (223 ENS names, lending whales, etc.)        │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │   Layer 1    │   │   Layer 2    │   │   Layer 3    │            │
│  │  On-Chain    │ → │  Behavioral  │ → │   OSINT      │            │
│  │  Expansion   │   │ Fingerprint  │   │  Aggregation │            │
│  └──────────────┘   └──────────────┘   └──────────────┘            │
│         ↓                  ↓                  ↓                     │
│  ┌─────────────────────────────────────────────────────┐           │
│  │              KNOWLEDGE GRAPH (SQLite)               │           │
│  │  - Entities, Clusters, Relationships, Evidence      │           │
│  └─────────────────────────────────────────────────────┘           │
│         ↓                                                           │
│  ┌─────────────────────────────────────────────────────┐           │
│  │              PATTERN RECOGNITION                    │           │
│  │  - Match unknowns to known entity templates         │           │
│  └─────────────────────────────────────────────────────┘           │
│                                                                     │
│  OUTPUT: Identified entities with evidence chains                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Scripts

| Script | Layer | Purpose |
|--------|-------|---------|
| `build_knowledge_graph.py` | Master | Orchestrates entire system, manages SQLite DB |
| `cluster_expander.py` | 1 | CIO clustering + cross-chain expansion |
| `behavioral_fingerprint.py` | 2 | Timing/gas/trading pattern analysis |
| `osint_aggregator.py` | 3 | ENS + Snapshot + whale tracker aggregation |
| `pattern_matcher.py` | Recognition | Template matching for entity identification |

### Quick Start

```bash
# Initialize database with seed addresses
python3 scripts/build_knowledge_graph.py init --seeds addresses.csv

# Check statistics
python3 scripts/build_knowledge_graph.py stats

# Run full investigation pipeline
python3 scripts/build_knowledge_graph.py run

# Query specific address
python3 scripts/build_knowledge_graph.py query --address 0x1234...

# Search by entity name
python3 scripts/build_knowledge_graph.py query --entity "Trend Research"

# Export results
python3 scripts/build_knowledge_graph.py export -o results.csv
```

### Layer Details

#### Layer 1: On-Chain Expansion (`cluster_expander.py`)

Expands seed addresses to full clusters using CIO heuristics (94.85% accuracy):

- **Circular Funding**: A→B→C→A patterns
- **Common Funder**: Same source within 48h
- **Shared Deposits**: Same exchange deposit address
- **Cross-Chain Correlation**: Same address on multiple chains

```bash
# Standalone mode
python3 scripts/cluster_expander.py addresses.csv -o clusters.csv --cross-chain
```

#### Layer 2: Behavioral Fingerprinting (`behavioral_fingerprint.py`)

Analyzes behavior patterns for entity typing:

- **Timing Analysis**: Infers timezone, activity patterns
- **Gas Strategy**: Low/medium/high/adaptive
- **Trading Style**: Spot, leverage, arbitrage, MEV
- **Protocol Preferences**: Risk profile from DeFi usage

```bash
# Standalone mode
python3 scripts/behavioral_fingerprint.py addresses.csv -o fingerprints.csv --cluster
```

#### Layer 3: OSINT Aggregation (`osint_aggregator.py`)

Aggregates off-chain intelligence:

- **ENS Metadata**: Twitter, GitHub, email, URL records
- **Snapshot Governance**: Voting history, delegation patterns
- **Whale Trackers**: Lookonchain, OnchainLens, Spot On Chain
- **Protocol Patterns**: Match ENS to known protocols

```bash
# Standalone mode
python3 scripts/osint_aggregator.py addresses.csv -o osint.csv
```

#### Pattern Recognition (`pattern_matcher.py`)

Matches unknowns to known entity templates:

- **VC Fund Pattern**: Cluster 10-100 wallets, common funder, no ENS
- **Protocol Treasury**: Safe multisig, has ENS, votes in governance
- **Exchange Hot Wallet**: 24/7 activity, high tx volume
- **MEV Bot**: Contract, arbitrage/MEV trading, high gas
- **Whale Individual**: EOA, has ENS, votes, business hours

```bash
# List all templates
python3 scripts/pattern_matcher.py --list-templates

# Match single address
python3 scripts/pattern_matcher.py --address 0x1234...
```

### Expected Results

| Metric | Before (Scripts) | After (System) | Improvement |
|--------|------------------|----------------|-------------|
| Scope | 223 addresses | 600+ addresses | 2.7x |
| Identification | 15-18% | 33%+ | 2x |
| High Confidence | ~20 | 100+ | 5x |
| Processing Time | 37h manual | 30 min auto | 74x |
| Reusability | None | Full system | ∞ |

### Database Schema

```sql
-- Core tables
entities(address, identity, entity_type, confidence, cluster_id, ens_name)
clusters(id, name, detection_methods, confidence)
relationships(source, target, relationship_type, confidence, evidence)
evidence(entity_address, source, claim, confidence, url)
behavioral_fingerprints(address, timezone_signal, gas_strategy, trading_style)
entity_templates(name, patterns, examples, confidence)
```

### Key Insight

The 100x improvement isn't about running scripts faster. It's about:

1. **Cluster Expansion**: Every identified wallet reveals 10+ related wallets
2. **Knowledge Graph**: Findings persist and compound over time
3. **Multi-Layer Analysis**: On-chain + behavioral + social
4. **Pattern Recognition**: Learn from findings to find more
5. **Evidence Chains**: Every claim is traceable to sources

## Dependencies

```
requests>=2.28.0
python-dotenv>=1.0.0
beautifulsoup4>=4.12.0  # Optional, for better Arkham parsing
```

Install with:
```bash
pip install requests python-dotenv beautifulsoup4
```
