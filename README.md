# IC On-Chain Analytics

On-chain investigation and analytics for Index Coop. Identifies top DeFi lending protocol borrowers across Aave, Compound, Spark, Morpho, and more.

## What's Here

- **queries/** — DuneSQL queries for Index Coop products and lending analytics
- **scripts/** — Investigation pipeline (clustering, temporal correlation, label propagation, behavioral fingerprinting)
- **data/** — Knowledge graph database and investigation outputs
- **references/** — CEX labels, whale identities, investigation status
- **docs/** — Dashboard (GitHub Pages)

## Quick Start

```bash
# Set up
cp .env.example .env  # Add your API keys
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run investigation
python3 scripts/build_knowledge_graph.py stats
python3 scripts/build_knowledge_graph.py export -o data/final/bd_contact_list.csv
```

## Data Sources

| Source | Status |
|--------|--------|
| Dune Analytics | Active |
| Etherscan API | Active |
| Snapshot (governance) | Active |
| Nansen API | Planned |
| Arkham API | Pending approval |
