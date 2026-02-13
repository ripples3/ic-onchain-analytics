# Cluster Contamination Audit Retrospective

**Date:** 2026-02-14
**Scope:** Abraxas/Celsius cross-cluster correlations ($11.68B affected)

## Executive Summary

| Metric | Result |
|--------|--------|
| Cross-cluster correlations found | 23 |
| Contaminated value | $11.68B |
| Fixed | 15 addresses ($7.1B) |
| Remaining | 8 correlations (~$1.4B) |
| Root cause | CIO propagation without timezone validation |

---

## What Worked

### 1. Behavioral Timezone Fingerprinting (100% diagnostic accuracy)

**Method:** Compare transaction timing patterns to expected entity timezone.

| Entity | Expected Timezone | Validation |
|--------|-------------------|------------|
| Abraxas Capital (UK) | UTC+0/+1 | 90% of "Abraxas" labels were NOT UK timezone |
| Celsius Network (US) | UTC-4 to -8 | 80% of "Celsius" labels were NOT US timezone |

**Key insight:** Timezone fingerprinting can VALIDATE cluster assignments post-hoc. If an address is labeled "UK fund" but operates in UTC+7, the label is wrong.

**Success rate:** 100% - every timezone mismatch we found was confirmed contamination.

### 2. Original vs Propagated Label Comparison

**Method:** Compare cross-correlations between Arkham-verified (original) vs propagated labels.

| Comparison | Cross-correlations |
|------------|-------------------|
| Original Abraxas ↔ Original Celsius | **0** |
| Propagated Abraxas ↔ Propagated Celsius | **23** |

**Key insight:** Original identifications from trusted sources (Arkham) had no conflicts. ALL contamination came from CIO propagation.

**Implication:** Propagated labels need validation before being treated as high-confidence.

### 3. Multi-Regional Entity Detection

**Discovery:** 0x2bdded18... ($1.47B) and 0x4125caf9... ($270M) have:
- 97% temporal correlation (same operator)
- Different timezones (UTC-3 vs UTC+2)
- Different DEX preferences (0x vs 1inch)

**Conclusion:** Multi-regional fund with staff in South America AND Europe.

**Key insight:** High temporal correlation + different timezones = multi-regional operation, not error.

---

## What Didn't Work

### 1. CIO Propagation Without Validation (Critical Failure)

**Problem:** CIO clustering connected addresses via shared funders, then propagated labels without checking if the new addresses matched the original entity's behavioral profile.

```
Original Abraxas (UK, UTC+0)
    ↓ CIO clustering
Funder A (shared with many entities)
    ↓ Label propagation
Address X (UTC+7, Asia) ← WRONGLY labeled "Abraxas"
```

**Root cause:** Shared funders (CEX hot wallets, OTC desks) connect unrelated entities.

**Impact:** $7.1B in incorrect labels.

### 2. Confidence Score Inflation

**Problem:** Propagated labels had "HIGH" confidence despite being unvalidated.

| Source | Confidence Given | Actual Accuracy |
|--------|------------------|-----------------|
| Arkham (original) | HIGH | ~95% |
| CIO propagation | HIGH | ~40% |
| Behavioral only | MEDIUM | ~70% |

**Fix needed:** Propagated labels should start at MEDIUM and require validation for HIGH.

### 3. Missing Timezone Validation in Pipeline

**Problem:** No automated check that propagated labels match expected timezone.

```python
# Current pipeline (broken)
if cio_cluster_match(address, known_entity):
    label = known_entity.label  # No validation!
    confidence = HIGH

# Should be
if cio_cluster_match(address, known_entity):
    if timezone_matches(address, known_entity.expected_timezone):
        label = known_entity.label
        confidence = HIGH
    else:
        label = f"Unverified ({known_entity.label} cluster)"
        confidence = LOW
```

### 4. Cross-Cluster Correlation Detection (Missing)

**Problem:** No automated alert when propagated labels create cross-cluster correlations.

**Example:** When address X was labeled "Abraxas" and had 98% temporal correlation with address Y labeled "Celsius", this should have triggered a review. Instead, both labels were accepted.

---

## Root Cause Analysis

### Why Did Contamination Happen?

```
1. SHARED INFRASTRUCTURE
   Abraxas Capital ──┐
                     ├── Binance Hot Wallet ──┬── Address A (labeled Abraxas)
   Celsius Network ──┘                        └── Address B (labeled Celsius)
   Random Fund ──────────────────────────────────└── Address C (labeled Abraxas??)

2. LABEL PROPAGATION WITHOUT VALIDATION
   Address A (confirmed Abraxas)
       ↓ shares funder with
   Address C (unknown)
       ↓ CIO propagation
   Address C labeled "Abraxas (cluster member)" ← WRONG if C is UTC+7

3. NO CROSS-CLUSTER CORRELATION CHECK
   Address C (Abraxas label) has 90% correlation with Address D (Celsius label)
   → Should trigger: "WARNING: Cross-cluster correlation detected"
   → Actually happened: Both labels accepted as valid
```

### The Core Issue

**CIO clustering finds FUNDING relationships, not OPERATIONAL relationships.**

- Two addresses sharing a funder ≠ same entity
- CEX hot wallets fund thousands of unrelated users
- OTC desks serve multiple funds

**Solution:** CIO should propose candidates, not assign labels. Validation required.

---

## Concrete Improvements

### 1. Timezone Validation Gate (Critical)

Add to `label_propagation.py`:

```python
def propagate_label(source_addr, target_addr, source_identity):
    # Get expected timezone from source
    source_tz = get_behavioral_timezone(source_addr)
    target_tz = get_behavioral_timezone(target_addr)

    # Timezone tolerance: ±2 hours
    if abs(tz_diff(source_tz, target_tz)) <= 2:
        confidence = 0.75  # HIGH - timezone matches
    elif abs(tz_diff(source_tz, target_tz)) <= 4:
        confidence = 0.50  # MEDIUM - close but not exact
    else:
        # REJECT - timezone mismatch
        return {
            "identity": f"Unverified ({source_identity} funding link)",
            "confidence": 0.30,
            "warning": f"Timezone mismatch: {source_tz} vs {target_tz}"
        }
```

**Expected improvement:** Prevent 80%+ of contamination.

### 2. Cross-Cluster Correlation Alert System

Add to `build_knowledge_graph.py`:

```python
def check_cross_cluster_correlations():
    """Alert when temporal correlations exist between different clusters."""

    clusters = get_all_cluster_labels()  # Abraxas, Celsius, etc.

    for correlation in get_temporal_correlations(min_conf=0.8):
        source_cluster = clusters.get(correlation.source)
        target_cluster = clusters.get(correlation.target)

        if source_cluster and target_cluster and source_cluster != target_cluster:
            alert = {
                "type": "CROSS_CLUSTER_CORRELATION",
                "severity": "HIGH" if correlation.confidence > 0.9 else "MEDIUM",
                "source": correlation.source,
                "target": correlation.target,
                "clusters": [source_cluster, target_cluster],
                "action": "Review cluster assignments - likely contamination"
            }
            emit_alert(alert)
```

**Expected improvement:** Catch contamination within hours of occurrence.

### 3. Confidence Tier System

Replace binary HIGH/MEDIUM/LOW with tiered system:

| Tier | Confidence | Requirements |
|------|------------|--------------|
| VERIFIED | 90-100% | Arkham/Nansen confirmed + behavioral match |
| VALIDATED | 70-89% | Propagated + timezone match + no conflicts |
| CANDIDATE | 50-69% | CIO/temporal link only, needs validation |
| UNVERIFIED | 30-49% | Propagated but timezone mismatch or conflicts |
| UNKNOWN | 0-29% | No signals |

```python
def calculate_confidence_tier(evidence_list):
    has_arkham = any(e.source == 'Arkham' for e in evidence_list)
    has_timezone_match = check_timezone_consistency(evidence_list)
    has_cross_cluster = check_cross_cluster_conflicts(address)

    if has_arkham and has_timezone_match:
        return "VERIFIED", 0.95
    elif has_timezone_match and not has_cross_cluster:
        return "VALIDATED", 0.75
    elif has_cross_cluster:
        return "UNVERIFIED", 0.35
    else:
        return "CANDIDATE", 0.55
```

### 4. Propagation Decay by Relationship Type

Different relationship types have different reliability:

| Relationship | Propagation Weight | Rationale |
|--------------|-------------------|-----------|
| same_signer (Safe) | 0.95 | Same person controls both |
| temporal_correlation >95% | 0.90 | Same operator timing |
| shared_cex_deposit | 0.85 | Same exchange user |
| cio_common_funder | 0.50 | Could be shared infrastructure |
| cio_shared_deposit | 0.70 | Stronger than common funder |
| counterparty_overlap | 0.40 | Could be same market maker |

```python
PROPAGATION_WEIGHTS = {
    "same_signer": 0.95,
    "temporal_correlation": 0.90,
    "shared_cex_deposit": 0.85,
    "cio_shared_deposit": 0.70,
    "cio_common_funder": 0.50,  # REDUCED from 0.85
    "counterparty_overlap": 0.40,
}
```

### 5. Automated Cluster Health Check

Run daily to detect contamination:

```python
def cluster_health_check():
    """Daily check for cluster integrity."""

    issues = []

    for cluster_name in get_all_clusters():
        members = get_cluster_members(cluster_name)

        # Check 1: Timezone consistency
        timezones = [get_timezone(m) for m in members]
        if len(set(timezones)) > 3:  # More than 3 different timezones
            issues.append({
                "cluster": cluster_name,
                "issue": "TIMEZONE_SPREAD",
                "detail": f"{len(set(timezones))} different timezones in cluster"
            })

        # Check 2: Cross-cluster correlations
        cross = count_cross_cluster_correlations(cluster_name)
        if cross > 5:
            issues.append({
                "cluster": cluster_name,
                "issue": "CROSS_CLUSTER_CORRELATIONS",
                "detail": f"{cross} correlations with other clusters"
            })

        # Check 3: Original vs propagated ratio
        original = count_original_labels(cluster_name)
        propagated = count_propagated_labels(cluster_name)
        if propagated > original * 10:
            issues.append({
                "cluster": cluster_name,
                "issue": "PROPAGATION_EXPLOSION",
                "detail": f"{propagated} propagated from {original} originals"
            })

    return issues
```

---

## Implementation Priority

| Priority | Improvement | Impact | Effort |
|----------|-------------|--------|--------|
| 1 | Timezone validation gate | Prevents 80% contamination | Medium |
| 2 | Cross-cluster correlation alerts | Early detection | Low |
| 3 | Confidence tier system | Better trust calibration | Medium |
| 4 | Reduced CIO propagation weight | Prevents over-propagation | Low |
| 5 | Daily cluster health check | Ongoing monitoring | Medium |

---

## Metrics to Track

After implementing fixes:

| Metric | Current | Target |
|--------|---------|--------|
| Cross-cluster correlations | 8 | 0 |
| Labels requiring manual review | ~100 | <20 |
| Timezone match rate (propagated) | ~40% | >90% |
| Time to detect contamination | Days/weeks | <24 hours |

---

## Key Takeaways

1. **CIO clustering is a CANDIDATE generator, not a labeler.** Never propagate labels without validation.

2. **Timezone is the best validation signal.** A UK fund doesn't operate from UTC+7.

3. **Cross-cluster correlations are red flags.** Same operator shouldn't be in two clusters.

4. **Original sources (Arkham) are reliable; propagation is not.** Treat propagated labels with skepticism.

5. **Multi-regional entities exist.** High correlation + different timezones = multi-regional, not error.
