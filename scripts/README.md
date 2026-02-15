# Whale Identity Scripts

Automated tools for identifying unknown wallet addresses at scale.

## Quick Start

```bash
# Install dependencies
pip install requests python-dotenv

# Set up API keys
export ETHERSCAN_API_KEY=your_key_here

# Smart investigation (recommended)
python3 scripts/smart_investigator.py addresses.csv -o results.csv

# Or full enrichment pipeline
python3 scripts/enrich_addresses.py whales.csv -o enriched.csv
```

## Scripts Overview

### Core Investigation Scripts

| Script | Purpose | Hit Rate | Recommendation |
|--------|---------|----------|----------------|
| `smart_investigator.py` | Routes to optimal methods per address type | — | **Start here** |
| `bot_operator_tracer.py` | Traces contract deployer/operator | 100% on contracts | Use first for contracts |
| `behavioral_fingerprint.py` | Timezone, activity, gas patterns | 100% universal | Always run |
| `trace_funding.py` | CEX funding origin chain | 100% universal | Always run |
| `temporal_correlation.py` | Same-operator detection via timing | 85% when partners exist | Best relationship method |
| `label_propagation.py` | Spread identities through graph | — | Force multiplier |
| `cio_detector.py` | Common Input Ownership clustering | 80% on standard EOAs | Skip for $500M+ |
| `counterparty_graph.py` | Shared counterparty overlap | 57% on standard EOAs | Skip for $500M+ |

### Support Scripts

| Script | Purpose |
|--------|---------|
| `build_knowledge_graph.py` | Master KG orchestrator (SQLite) |
| `enrich_addresses.py` | Pipeline orchestrator |
| `verify_identity.py` | Multi-source verification |
| `investigate_safes.py` | Safe multisig signer clustering + funding trace |
| `governance_scraper.py` | Snapshot voting analysis |
| `profile_classifier.py` | Routes addresses to correct investigation methods |

### Utility Scripts

| Script | Purpose |
|--------|---------|
| `dune_query.py` | Dune Analytics API client |
| `etherscan_labels.py` | Contract type detection |
| `resolve_safe_owners.py` | Safe multisig owner resolution |
| `multichain_balance.py` | Cross-chain balance checks |
| `protocol_summary.py` | Aave/Spark position summaries |
| `validate_queries.py` | SQL query validation |
| `update_csv_from_kg.py` | Export KG to CSV |
| `incremental_update.py` | Sync Dune data to KG |

### KG Pipeline Scripts (imported by build_knowledge_graph.py)

| Script | Layer | Purpose |
|--------|-------|---------|
| `cluster_expander.py` | 1 | CIO clustering + cross-chain expansion |
| `osint_aggregator.py` | 3 | ENS + Snapshot + whale tracker aggregation |
| `pattern_matcher.py` | Recognition | Template matching for entity identification |

## Investigation Routing

```
1. CHECK CONTRACT FIRST
   └── Yes → bot_operator_tracer (100%) + behavioral + funding
   └── No → continue

2. CHECK SOPHISTICATION ($500M+)
   └── Yes → behavioral + funding + temporal (skip CIO/counterparty)
   └── No → full pipeline

3. RUN UNIVERSAL METHODS
   └── behavioral_fingerprint → timezone = region
   └── trace_funding → CEX origin chain

4. RUN TEMPORAL CORRELATION
   └── >80% correlation → primary signal
   └── No correlation → isolated operator

5. PROPAGATE
   └── label_propagation → spread identities through graph
```

## Knowledge Graph System

```bash
# View statistics
python3 scripts/build_knowledge_graph.py stats

# Run full pipeline
python3 scripts/build_knowledge_graph.py run

# Query specific address
python3 scripts/build_knowledge_graph.py query --address 0x1234...

# Export results
python3 scripts/build_knowledge_graph.py export -o results.csv

# Health check
python3 scripts/build_knowledge_graph.py health
```

### Database Schema

```sql
entities(address, identity, entity_type, confidence, cluster_id, ens_name)
clusters(id, name, detection_methods, confidence)
relationships(source, target, relationship_type, confidence, evidence)
evidence(entity_address, source, claim, confidence, url)
behavioral_fingerprints(address, timezone_signal, gas_strategy, trading_style)
entity_templates(name, patterns, examples, confidence)
```

## Automated Pipeline

```bash
# Full pipeline with checkpointing
./scripts/run_investigation.sh addresses.csv

# Resume from checkpoint
./scripts/run_investigation.sh --resume

# Run single step
./scripts/run_investigation.sh --step behavioral
```

## Environment Variables

```bash
ETHERSCAN_API_KEY=your_key_here   # Required
ETH_RPC_URL=https://...           # Optional (uses public RPC)
DUNE_API_KEY=your_key_here        # Optional (for Dune queries)
```

## Dependencies

```
requests>=2.28.0
python-dotenv>=1.0.0
```
