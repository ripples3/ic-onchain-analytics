# Bug Report: Whale Investigation Scripts

Generated: 2026-02-12

## Summary

| Script | Critical | High | Medium | Low |
|--------|----------|------|--------|-----|
| build_knowledge_graph.py | 2 | 2 | 2 | 0 |
| cluster_expander.py | 1 | 2 | 3 | 0 |
| behavioral_fingerprint.py | 1 | 3 | 3 | 0 |
| osint_aggregator.py | 1 | 3 | 4 | 0 |
| pattern_matcher.py | 1 | 2 | 3 | 0 |

---

## build_knowledge_graph.py

### CRITICAL-1: Batch processing marks all addresses completed even on error
**Location:** Lines 757-759
**Impact:** If processing throws exception mid-batch, unprocessed addresses are still marked "completed"
```python
# Current code - marks ALL as completed after processing
for q in queued:
    kg.update_queue_status(q['address'], layer, 'completed')
```
**Fix:** Mark each address completed immediately after successful processing, or use try/except per address.

### CRITICAL-2: merge_clusters leaves orphaned relationships
**Location:** Lines 362-385
**Impact:** When merging clusters, old `same_cluster` relationships are not deleted, leading to database bloat and incorrect relationship counts.
```python
# Current: deletes clusters but not their relationships
for cid in cluster_ids:
    conn.execute("DELETE FROM clusters WHERE id = ?", (cid,))
```
**Fix:** Add `DELETE FROM relationships WHERE ... cluster_id IN (...)` before deleting clusters.

### HIGH-1: add_relationship overwrites with lower confidence
**Location:** Lines 400-410
**Impact:** `INSERT OR REPLACE` replaces existing relationships regardless of confidence score.
```python
# If existing relationship has 0.9 confidence, this could replace with 0.5
conn.execute("INSERT OR REPLACE INTO relationships...")
```
**Fix:** Use `INSERT OR IGNORE` or add `WHERE confidence < ?` to only update if new confidence is higher.

### HIGH-2: N+1 query problem in export
**Location:** Lines 907-918
**Impact:** For each entity, executes separate `get_evidence()` query. For 2000 entities = 2000 extra queries.
**Fix:** Use JOIN query to fetch all evidence at once.

### MEDIUM-1: Silent skip on missing address column
**Location:** Line 690
**Impact:** If CSV has no matching column, silently continues without warning.

### MEDIUM-2: `attempts` always incremented
**Location:** Line 596
**Impact:** Even "completed" status increments attempts counter, making it unreliable for tracking failures.

---

## cluster_expander.py

### CRITICAL-1: Re-queueing already-processed addresses
**Location:** Lines 570-583
**Impact:** `expanded - original_set` may include addresses already in knowledge graph from previous batches, causing them to be re-queued.
```python
new_addresses = expanded - original_set  # original_set is just this batch
```
**Fix:** Query knowledge graph to check if address already exists before queueing.

### HIGH-1: Expensive API calls in change_address detection
**Location:** Lines 420-428
**Impact:** Makes extra API call for EVERY small outgoing transaction to check target address.
```python
for tx in outgoing:
    if 0 < value < 1:
        target_txs = get_transactions(to_addr, chain_id, limit=10)  # Extra API call per tx!
```
**Fix:** Batch these requests or skip change address detection by default.

### HIGH-2: Duplicate evidence for clustered addresses
**Location:** Lines 543-552
**Impact:** Each address in a cluster gets evidence added, but if cluster is detected by multiple methods, evidence is duplicated.

### MEDIUM-1: Inefficient transaction fetching
**Location:** Lines 146-159
**Impact:** Fetches transactions for ALL addresses even if they have no edges to other addresses in the set.

### MEDIUM-2: Limited exchange exclusion list
**Location:** Lines 289-296
**Impact:** Only 6 exchange addresses are excluded from shared deposit detection. Many more exchange addresses exist.

### MEDIUM-3: Silent return on missing API key
**Location:** Lines 510-512
**Impact:** Returns silently without processing when `ETHERSCAN_API_KEY` not set.

---

## behavioral_fingerprint.py

### CRITICAL-1: Flawed timezone inference
**Location:** Lines 169-175
**Impact:** Assumes peak activity is during business hours (1 PM midday). Crypto traders often work night hours. Timezone could be off by 6+ hours.
```python
assumed_work_midday = 13  # 1 PM local time is typical peak
timezone_offset = int(round(assumed_work_midday - avg_peak_hour))
```
**Fix:** Use multiple heuristics or mark timezone as "uncertain" for non-business-hours patterns.

### HIGH-1: Deprecated datetime function
**Location:** Line 154
**Impact:** `datetime.utcfromtimestamp()` is deprecated in Python 3.12+, will cause warnings.
```python
dt = datetime.utcfromtimestamp(ts)
```
**Fix:** Use `datetime.fromtimestamp(ts, tz=timezone.utc)`.

### HIGH-2: Division instability in consistency calculation
**Location:** Line 252
**Impact:** If `avg_gas` is very small, `std_dev / avg_gas` could be very large, making consistency negative.
```python
consistency = max(0, 1 - (std_dev / avg_gas)) if avg_gas > 0 else 0
```
**Fix:** Add minimum threshold for `avg_gas` or cap the ratio.

### HIGH-3: Incorrect EIP-1559 detection
**Location:** Line 271
**Impact:** `len(max_fees) > len(gas_prices) * 0.5` compares count of EIP-1559 txs to ALL txs. Should compare to total tx count.
```python
uses_eip1559 = len(max_fees) > len(gas_prices) * 0.5  # gas_prices includes ALL txs
```
**Fix:** Compare `len(max_fees) / len(txs) > 0.5`.

### MEDIUM-1: O(n²) clustering algorithm
**Location:** Lines 536-563
**Impact:** Greedy clustering compares all fingerprints pairwise. For 2000 addresses = 2M comparisons.

### MEDIUM-2: Overwrites entity type from CIO
**Location:** Line 604
**Impact:** Updates entity type based on behavioral signal even if CIO clustering already set a more reliable type.

### MEDIUM-3: Duplicate timestamp extraction
**Location:** Line 340
**Impact:** Re-iterates through all transactions just to extract timestamps for MEV analysis.

---

## osint_aggregator.py

### CRITICAL-1: Deprecated Graph subgraph URL
**Location:** Lines 102, 153
**Impact:** `api.thegraph.com` is deprecated. Will fail when The Graph removes legacy endpoints.
```python
ens_subgraph = "https://api.thegraph.com/subgraphs/name/ensdomains/ens"
```
**Fix:** Use Studio URL or decentralized network endpoint.

### HIGH-1: Dead code / wasted API call
**Location:** Lines 91-99, 142-147
**Impact:** Builds Etherscan params but never uses them. Calls ENS metadata service but does nothing with response.

### HIGH-2: Unsafe nested dict access
**Location:** Line 327
**Impact:** `v['proposal']['space']['name']` will raise KeyError if any nested dict is missing.
```python
'space': v['proposal']['space']['name'] if v.get('proposal', {}).get('space') else 'Unknown'
```
**Fix:** Use `.get()` chain: `v.get('proposal', {}).get('space', {}).get('name', 'Unknown')`.

### HIGH-3: Placeholder text records
**Location:** Lines 175-176
**Impact:** Sets text record values to `[has {key}]` placeholder instead of actual values.
```python
records[key] = f"[has {key}]"  # Subgraph doesn't return values
```
**Fix:** Use RPC call or different API to get actual values.

### MEDIUM-1: Hardcoded/limited whale addresses
**Location:** Lines 471-486
**Impact:** Only 7 whale addresses in KNOWN_WHALES dict. Should load from external file.

### MEDIUM-2: Invalid entity_type value
**Location:** Line 627
**Impact:** Sets `entity_type='known_entity'` which is not a valid type (should be individual, fund, protocol, exchange, bot, or unknown).

### MEDIUM-3: Double function call
**Location:** Lines 581-582
**Impact:** Calls `match_protocol_pattern()` twice for same ENS name.

### MEDIUM-4: Rate limit too aggressive
**Location:** Line 44
**Impact:** `RATE_LIMIT = 2.0` (0.5s between requests) may be too slow for batch processing.

---

## pattern_matcher.py

### CRITICAL-1: Contract type matching is backwards
**Location:** Line 155
**Impact:** Checks if pattern is substring of entity value instead of vice versa.
```python
if patterns["contract_type"] in entity_data["contract_type"]:  # e.g., "Safe" in "Gnosis Safe"
```
This works for "Safe" in "Gnosis Safe" but fails for "Contract" in "SmartContract" (no space).

### HIGH-1: Identity suffix duplication
**Location:** Lines 498-506
**Impact:** Can create nested suffixes like "Name (cluster member) (cluster member)" if called multiple times.
```python
if base_identity.endswith(" (cluster member)"):
    new_identity = base_identity  # Still duplicates if called with different base
```
**Fix:** Strip all "(cluster member)" suffixes before adding new one.

### HIGH-2: Evidence weight dilution
**Location:** Lines 343-356
**Impact:** All evidence items weighted equally by count. 100 low-weight "Behavioral" items drown out 1 high-weight "CIO" item.
```python
total_weight += weight  # Each evidence adds weight
weighted_confidence += conf * weight
```
**Fix:** Use max confidence per source, not sum.

### MEDIUM-1: Variable shadowing in loop
**Location:** Line 260
**Impact:** `cluster = dict(cluster)` shadows outer loop variable, making code confusing.

### MEDIUM-2: Deprecated datetime function
**Location:** Line 582
**Impact:** `datetime.utcnow()` is deprecated in Python 3.12+.

### MEDIUM-3: Division by max without overlap check
**Location:** Line 309
**Impact:** If `len(cluster_methods)` is 0 and `method_overlap` is 0, similarity = 0.4 * size_ratio which may be unfairly high.

---

## Test Cases Required

### Critical Tests

1. **Batch processing error recovery** - Verify addresses aren't marked completed when processing fails
2. **Cluster merge cleanup** - Verify orphaned relationships are deleted
3. **Timezone inference accuracy** - Test with known timezone addresses
4. **Graph API migration** - Test ENS resolution with new endpoints

### High Priority Tests

1. **Confidence preservation** - Verify higher confidence isn't overwritten
2. **Re-queue prevention** - Verify processed addresses aren't re-queued
3. **Dict access safety** - Test with missing nested fields

See `scripts/tests/test_bugs.py` for implementation.
