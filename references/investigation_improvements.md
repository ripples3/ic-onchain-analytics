# Investigation Improvements (2026-02-13)

## Priority 1: Pre-filtering Pipeline

### Problem
Started with $6.8B "whale" that was a flash loan bot with $0 current balance.

### Solution
Add pre-filtering step before investigation:

```python
def get_bd_ready_targets(addresses_df):
    """Filter and rank addresses for BD investigation."""

    # 1. Exclude bots
    df = addresses_df[
        ~(
            (addresses_df['borrowed_assets'].apply(lambda x: x == ['USDC'])) &
            (addresses_df['current_balance'] < 100)
        )
    ]

    # 2. Exclude MEV bots (funded by known builders)
    MEV_BUILDERS = [
        '0xd87f76e8a4f4c0eb5d4fcb1ec1da4e8f2c4e5b96',  # MEV Builder
        '0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97',  # Titan Builder
        '0x95222290dd7278aa3ddd389cc1e1d165cc4bafe5',  # Flashbots
    ]
    df = df[~df['funder'].isin(MEV_BUILDERS)]

    # 3. Exclude inactive (no activity in 1 year)
    df = df[df['days_since_last_tx'] < 365]

    # 4. Rank by current collateral, not cumulative borrowed
    df = df.sort_values('current_collateral_usd', ascending=False)

    return df
```

### Implementation
Add to `scripts/build_knowledge_graph.py`:
- New `--filter-bots` flag
- Export filtered list before investigation

---

## Priority 2: Bot Operator Tracing

### Problem
Classified bots as "not BD targets" instead of tracing their operators.

### Solution
New script: `scripts/trace_bot_operator.py`

```python
def trace_bot_operator(bot_address: str) -> dict:
    """Trace the human operator behind a bot contract."""

    # 1. Get contract deployer
    deployer = get_contract_creator(bot_address)

    # 2. Get deployer's other contracts
    other_contracts = get_contracts_by_creator(deployer)

    # 3. Trace profit destinations (large outflows from bot)
    outflows = get_transactions(bot_address, direction='out')
    large_outflows = [tx for tx in outflows if tx['value'] > 1e18]
    profit_destinations = set(tx['to'] for tx in large_outflows)

    # 4. Check if profit destinations are EOAs (likely operator wallets)
    operator_candidates = []
    for addr in profit_destinations:
        if is_eoa(addr) and not is_exchange(addr):
            operator_candidates.append(addr)

    return {
        'deployer': deployer,
        'other_bots': other_contracts,
        'profit_destinations': list(profit_destinations),
        'operator_candidates': operator_candidates
    }
```

### Etherscan API Call
```bash
# Get contract creator
curl "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getcontractcreation&contractaddresses=${BOT_ADDRESS}&apikey=${KEY}"
```

---

## Priority 3: BD Readiness Score

### Problem
No single metric to prioritize investigation targets.

### Solution
Composite score combining multiple signals:

```python
def calculate_bd_score(address_data: dict) -> float:
    """Calculate BD readiness score (0-100)."""
    score = 0

    # Current position size (0-40 points)
    collateral = address_data.get('current_collateral_usd', 0)
    if collateral > 100_000_000:  # $100M+
        score += 40
    elif collateral > 10_000_000:  # $10M+
        score += 30
    elif collateral > 1_000_000:  # $1M+
        score += 20

    # Reachability (0-30 points)
    if address_data.get('ens_name'):
        score += 15  # Has ENS = more reachable
    if address_data.get('governance_activity'):
        score += 10  # Votes = engaged in ecosystem
    if address_data.get('is_safe'):
        score += 5   # Safe = likely org, not bot

    # Activity recency (0-20 points)
    days_inactive = address_data.get('days_since_last_tx', 999)
    if days_inactive < 7:
        score += 20
    elif days_inactive < 30:
        score += 15
    elif days_inactive < 90:
        score += 10

    # Negative signals (subtract)
    if address_data.get('is_bot'):
        score -= 20  # Bot = harder to reach (but operator still valid)
    if address_data.get('is_exchange'):
        score -= 30  # Exchange address = not a user

    return max(0, min(100, score))
```

### Output
```
| Address | Collateral | BD Score | Reason |
|---------|------------|----------|--------|
| 0x1234  | $45M       | 75       | Active, has ENS, Safe multisig |
| 0x5678  | $120M      | 60       | Large but no ENS, EOA |
| 0x9abc  | $200M      | 35       | Bot - trace operator instead |
```

---

## Priority 4: Known Entities Database

### Problem
Spent time investigating addresses that are already known (7 Siblings, Coinbase Prime).

### Solution
SQLite table of known entities for quick lookup:

```sql
CREATE TABLE known_entities (
    address TEXT PRIMARY KEY,
    entity_name TEXT NOT NULL,
    entity_type TEXT,  -- 'whale_cluster', 'exchange', 'protocol', 'fund'
    confidence REAL,
    source TEXT,       -- 'lookonchain', 'arkham', 'etherscan', 'manual'
    notes TEXT,
    updated_at TEXT
);

-- Seed data
INSERT INTO known_entities VALUES
('0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0', '7 Siblings', 'whale_cluster', 0.95, 'lookonchain', '1.21M ETH, buys dips', datetime('now')),
('0xf8de75c7b95edb6f1e639751318f117663021cf0', '7 Siblings', 'whale_cluster', 0.95, 'lookonchain', 'Recursive farmer address', datetime('now')),
('0xcd531ae9efcce479654c4926dec5f6209531ca7b', 'Coinbase Prime 1', 'exchange', 0.99, 'etherscan', 'Institutional custody', datetime('now'));
```

### Usage
```python
def check_known_entity(address: str) -> Optional[dict]:
    """Check if address belongs to known entity."""
    result = conn.execute(
        "SELECT * FROM known_entities WHERE address = ?",
        (address.lower(),)
    ).fetchone()
    if result:
        return dict(result)
    return None

# Before deep investigation
known = check_known_entity(target_address)
if known:
    print(f"Already known: {known['entity_name']} ({known['source']})")
    return  # Skip investigation
```

---

## Priority 5: Timezone Analysis Integration

### Problem
Timezone analysis worked but was done manually, not integrated into pipeline.

### Solution
Add to `behavioral_fingerprint.py`:

```python
def infer_timezone(transactions: list) -> dict:
    """Infer operator timezone from transaction timing patterns."""
    from collections import Counter
    from datetime import datetime, timezone

    hours = []
    days = []
    for tx in transactions:
        dt = datetime.fromtimestamp(int(tx['timeStamp']), tz=timezone.utc)
        hours.append(dt.hour)
        days.append(dt.weekday())

    hour_counts = Counter(hours)
    day_counts = Counter(days)

    peak_hours = [h for h, _ in hour_counts.most_common(3)]
    sunday_ratio = day_counts[6] / max(day_counts[5], 1)  # Sun vs Sat

    # Inference rules
    if 5 <= peak_hours[0] <= 8 and sunday_ratio > 1.5:
        region = "Asia-Pacific (HK/SG)"
        confidence = 0.7
    elif 13 <= peak_hours[0] <= 16:
        region = "Americas (US)"
        confidence = 0.6
    elif 8 <= peak_hours[0] <= 12:
        region = "Europe"
        confidence = 0.5
    else:
        region = "Unknown"
        confidence = 0.3

    return {
        'inferred_region': region,
        'confidence': confidence,
        'peak_hours_utc': peak_hours,
        'sunday_activity_ratio': round(sunday_ratio, 2)
    }
```

---

## Priority 6: Investigation Cost Tracking

### Problem
No visibility into time/API costs per investigation.

### Solution
Track investigation costs:

```python
class InvestigationTracker:
    def __init__(self):
        self.api_calls = 0
        self.start_time = None
        self.findings = []

    def start(self, address: str):
        self.address = address
        self.start_time = time.time()
        self.api_calls = 0

    def record_api_call(self, api: str):
        self.api_calls += 1

    def record_finding(self, finding: str, confidence: float):
        self.findings.append({'finding': finding, 'confidence': confidence})

    def finish(self) -> dict:
        duration = time.time() - self.start_time
        return {
            'address': self.address,
            'duration_minutes': round(duration / 60, 1),
            'api_calls': self.api_calls,
            'findings': self.findings,
            'cost_effectiveness': len(self.findings) / max(self.api_calls, 1)
        }
```

### Output
```
Investigation Summary:
- Address: 0x6c2a3559...
- Duration: 12.3 minutes
- API calls: 47
- Findings: 1 (Asia-Pacific timezone)
- Cost effectiveness: 0.02 findings/call

Recommendation: Low ROI - deprioritize similar profiles
```

---

## Implementation Order

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| P0 | Pre-filtering pipeline | 2 hours | Avoids wasting time on bots |
| P1 | Known entities database | 1 hour | Quick lookup before investigation |
| P1 | BD readiness score | 2 hours | Better target prioritization |
| P2 | Bot operator tracing | 3 hours | Captures bot operators as targets |
| P2 | Timezone analysis integration | 1 hour | Automated behavioral signal |
| P3 | Investigation cost tracking | 2 hours | ROI visibility |

---

## Metrics to Track

After implementing improvements:

| Metric | Current | Target |
|--------|---------|--------|
| Time to first filter (bot detection) | N/A | <1 min per 100 addresses |
| Investigation time per identity | ~30 min | <15 min |
| False positive rate (investigating bots) | 80% (4/5) | <20% |
| Known entity cache hits | 0% | >30% |
| BD score >70 identification rate | Unknown | >50% |

---

## Session Learnings Applied

1. **Cumulative ≠ Current**: Always check current positions first
2. **Bots have operators**: Trace deployer/profits, don't skip
3. **Known entities exist**: Check Lookonchain/Arkham before deep dive
4. **Timezone works**: Integrate into automated pipeline
5. **10+ hop chains = sophisticated**: Flag but don't abandon
6. **Web search is expensive**: Use local scripts first (40% vs 10% hit rate)
