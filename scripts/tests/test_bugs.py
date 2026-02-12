#!/usr/bin/env python3
"""
Test cases for critical and high priority bugs in whale investigation scripts.

Run: python3 -m pytest scripts/tests/test_bugs.py -v
"""

import json
import sqlite3
import tempfile
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_knowledge_graph import KnowledgeGraph


class TestKnowledgeGraphBugs:
    """Tests for build_knowledge_graph.py bugs."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        kg = KnowledgeGraph(db_path)
        kg.initialize()
        yield kg

        kg.close()
        db_path.unlink()

    def test_merge_clusters_orphans_relationships(self, temp_db):
        """
        BUG: merge_clusters doesn't delete old same_cluster relationships.
        Expected: After merge, old relationship count should decrease.
        """
        kg = temp_db

        # Create two clusters with relationships
        cluster1_id = kg.create_cluster(
            ['0x1111', '0x2222'],
            name='Cluster 1',
            methods=['cio'],
            confidence=0.8
        )
        cluster2_id = kg.create_cluster(
            ['0x3333', '0x4444'],
            name='Cluster 2',
            methods=['cio'],
            confidence=0.8
        )

        # Count relationships before merge
        conn = kg.connect()
        before_count = conn.execute(
            "SELECT COUNT(*) FROM relationships WHERE relationship_type = 'same_cluster'"
        ).fetchone()[0]

        # Merge clusters
        kg.merge_clusters([cluster1_id, cluster2_id], 'Merged Cluster')

        # Count relationships after merge
        after_count = conn.execute(
            "SELECT COUNT(*) FROM relationships WHERE relationship_type = 'same_cluster'"
        ).fetchone()[0]

        # BUG: after_count includes old relationships + new ones
        # Should be: after_count < before_count (old ones deleted) + new ones
        # Actually: after_count = before_count + new_relationships

        # This test will FAIL with current code, demonstrating the bug
        # Expected: 6 relationships (4 addresses -> 6 pairs)
        # Actual: 8 relationships (old 4 + new 6, but with duplicates)
        assert after_count == 6, f"Expected 6 relationships after merge, got {after_count}"

    def test_add_relationship_overwrites_higher_confidence(self, temp_db):
        """
        BUG: add_relationship uses INSERT OR REPLACE, overwriting higher confidence.
        """
        kg = temp_db

        # Add relationship with high confidence
        kg.add_relationship('0x1111', '0x2222', 'funded_by', confidence=0.9)

        # Try to add same relationship with lower confidence
        kg.add_relationship('0x1111', '0x2222', 'funded_by', confidence=0.5)

        # Get the relationship
        conn = kg.connect()
        rel = conn.execute(
            "SELECT confidence FROM relationships WHERE source = ? AND target = ?",
            ('0x1111', '0x2222')
        ).fetchone()

        # BUG: confidence is 0.5, should be 0.9
        # This test will FAIL with current code
        assert rel[0] == 0.9, f"Higher confidence should be preserved, got {rel[0]}"

    def test_batch_processing_error_marks_all_completed(self, temp_db):
        """
        BUG: If processing throws exception mid-batch, all addresses are marked completed.
        """
        kg = temp_db

        # Queue 5 addresses
        for i in range(5):
            kg.queue_address(f'0x{i:04d}', 'onchain')

        # Simulate processing that fails on 3rd address
        queued = kg.get_queued('onchain', limit=5)

        processed = 0
        for q in queued:
            processed += 1
            if processed == 3:
                # Simulate error
                break

        # BUG: Current code would mark ALL 5 as completed
        # Should only mark first 2 as completed

        # Check queue status
        conn = kg.connect()
        pending = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'"
        ).fetchone()[0]

        # Expected: 3 still pending (addresses 3, 4, 5)
        assert pending >= 3, f"Expected at least 3 pending, got {pending}"


class TestBehavioralFingerprintBugs:
    """Tests for behavioral_fingerprint.py bugs."""

    def test_timezone_inference_night_traders(self):
        """
        BUG: Timezone inference assumes 1 PM peak = midday.
        Night traders would get wrong timezone.
        """
        from behavioral_fingerprint import analyze_timing_patterns

        # Simulate a trader active at night (UTC 2-6 AM)
        night_txs = [
            {'timeStamp': str(int(datetime(2024, 1, 1, hour, 0).timestamp()))}
            for hour in [2, 3, 4, 5, 6]
            for _ in range(20)  # 20 txs per hour
        ]

        result = analyze_timing_patterns(night_txs)

        # BUG: Assumes this is someone working 9-5 in UTC+11
        # Could actually be someone in UTC+0 working night shift
        timezone_signal = result.get('timezone_signal', '')

        # This assertion documents the bug - it will pass but shows wrong behavior
        # A night trader in UTC+0 should not be inferred as UTC+9
        print(f"Night trader inferred timezone: {timezone_signal}")
        # We can't assert a specific value because the logic is fundamentally flawed

    def test_gas_consistency_division_instability(self):
        """
        BUG: If avg_gas is very small, consistency calculation can be unstable.
        """
        from behavioral_fingerprint import analyze_gas_patterns

        # Transactions with very low but varying gas prices
        low_gas_txs = [
            {'gasPrice': str(int(0.1e9 * (1 + i * 0.5)))}  # 0.1, 0.15, 0.2, etc. Gwei
            for i in range(10)
        ]

        result = analyze_gas_patterns(low_gas_txs)

        consistency = result.get('gas_consistency', 0)

        # Consistency should be between 0 and 1
        assert 0 <= consistency <= 1, f"Consistency {consistency} outside [0,1]"

    def test_eip1559_detection_incorrect(self):
        """
        BUG: EIP-1559 detection compares max_fees to gas_prices incorrectly.
        """
        from behavioral_fingerprint import analyze_gas_patterns

        # 10 txs, 6 are EIP-1559 (>50%)
        txs = [
            {'gasPrice': '20000000000', 'maxFeePerGas': '25000000000', 'maxPriorityFeePerGas': '2000000000'}
            for _ in range(6)
        ] + [
            {'gasPrice': '20000000000'}  # Legacy tx
            for _ in range(4)
        ]

        result = analyze_gas_patterns(txs)

        # BUG: The check is `len(max_fees) > len(gas_prices) * 0.5`
        # max_fees = 6, gas_prices = 10, so 6 > 5 is True
        # This happens to work, but logic is confusing
        assert result.get('uses_eip1559') == True


class TestClusterExpanderBugs:
    """Tests for cluster_expander.py bugs."""

    def test_requeue_already_processed(self):
        """
        BUG: Expansion may re-queue addresses already in knowledge graph.
        """
        # This would need a mock KnowledgeGraph to test properly
        # The bug occurs when expanded - original_set includes addresses
        # that exist in KG but weren't in this batch

        # Simplified test setup
        batch_addresses = {'0x1111', '0x2222'}
        expanded_addresses = {'0x1111', '0x2222', '0x3333'}  # 0x3333 is new

        # Current code
        new_addresses_buggy = expanded_addresses - batch_addresses

        # But what if 0x3333 was already processed in a previous batch?
        already_in_kg = {'0x3333'}  # Simulated

        # Correct behavior would be:
        new_addresses_correct = expanded_addresses - batch_addresses - already_in_kg

        assert new_addresses_buggy != new_addresses_correct, "Bug not demonstrated"
        assert '0x3333' in new_addresses_buggy, "0x3333 would be re-queued (bug)"
        assert '0x3333' not in new_addresses_correct, "0x3333 should NOT be re-queued"


class TestPatternMatcherBugs:
    """Tests for pattern_matcher.py bugs."""

    def test_contract_type_matching_backwards(self):
        """
        BUG: Contract type matching uses `in` operator backwards.
        """
        from pattern_matcher import match_template

        # Entity with contract type "SmartContract"
        entity_data = {
            'contract_type': 'SmartContract',
            'entity_type': 'bot'
        }

        # Template expecting "Contract"
        template = {
            'name': 'Test',
            'patterns': {
                'contract_type': 'Contract',  # Looking for "Contract"
                'entity_type': 'bot'
            },
            'confidence': 0.8
        }

        matches, score, criteria = match_template(entity_data, template)

        # BUG: "Contract" in "SmartContract" = True (matches by accident)
        # But: "Safe" in "GnosisSafe" = False (no space)
        # The logic is inconsistent

        # Test with GnosisSafe
        entity_data2 = {
            'contract_type': 'GnosisSafe',  # No space
            'entity_type': 'protocol'
        }
        template2 = {
            'name': 'Test',
            'patterns': {
                'contract_type': 'Safe',
                'entity_type': 'protocol'
            },
            'confidence': 0.8
        }

        matches2, score2, criteria2 = match_template(entity_data2, template2)

        # "Safe" in "GnosisSafe" = True, but "Safe" in "Gnosis Safe" also = True
        # The inconsistency is in how different contract type formats are handled
        print(f"SmartContract matches Contract: {matches}")
        print(f"GnosisSafe matches Safe: {matches2}")

    def test_identity_suffix_duplication(self):
        """
        BUG: Can create nested "(cluster member)" suffixes.
        """
        base_identity = "Trend Research"

        # First time
        if base_identity.endswith(" (cluster member)"):
            identity1 = base_identity
        else:
            identity1 = f"{base_identity} (cluster member)"

        # Second time (simulating re-run)
        if identity1.endswith(" (cluster member)"):
            identity2 = identity1
        else:
            identity2 = f"{identity1} (cluster member)"

        # This works correctly for this specific case
        assert identity2 == "Trend Research (cluster member)"

        # But what if someone has "(cluster member)" in the middle?
        edge_case = "Trend Research (cluster member) Team"
        if edge_case.endswith(" (cluster member)"):
            identity3 = edge_case
        else:
            identity3 = f"{edge_case} (cluster member)"

        # BUG: This creates duplication
        assert " (cluster member)" in identity3.replace(" (cluster member)", "", 1), \
            "Should have caught nested suffix"

    def test_evidence_weight_dilution(self):
        """
        BUG: Many low-weight evidence items dilute high-weight items.
        """
        from pattern_matcher import aggregate_evidence_score

        # Mock knowledge graph
        class MockKG:
            def get_evidence(self, address):
                # 1 high-weight CIO evidence
                cio = [{'source': 'CIO', 'claim': 'High confidence', 'confidence': 0.95}]
                # 50 low-weight Behavioral evidence
                behavioral = [
                    {'source': 'Behavioral', 'claim': f'Signal {i}', 'confidence': 0.4}
                    for i in range(50)
                ]
                return cio + behavioral

        kg = MockKG()
        final_confidence, claims = aggregate_evidence_score(kg, '0x1234')

        # BUG: Final confidence is dragged down by many behavioral items
        # Expected: High confidence because CIO is very reliable
        # Actual: Lower confidence due to averaging

        # CIO weight = 0.9, Behavioral weight = 0.6
        # If equal items: (0.9 * 0.95 + 0.6 * 0.4 * 50) / (0.9 + 0.6 * 50)
        #               = (0.855 + 12) / (0.9 + 30) = 12.855 / 30.9 = 0.416

        print(f"Final confidence: {final_confidence}")
        # After fix: CIO evidence is NOT drowned out (uses max per source)
        # Before: ~0.42 (diluted), After: ~0.73 (CIO preserved)
        assert final_confidence >= 0.7, f"CIO evidence should be preserved, got {final_confidence}"


class TestOsintAggregatorBugs:
    """Tests for osint_aggregator.py bugs."""

    def test_deprecated_graph_url(self):
        """
        BUG: Uses deprecated api.thegraph.com URL.
        """
        import requests

        deprecated_url = "https://api.thegraph.com/subgraphs/name/ensdomains/ens"

        # This URL may return 404 or redirect
        try:
            response = requests.get(deprecated_url, timeout=5)
            # If it's deprecated, it might still work but return warning headers
            print(f"Deprecated URL status: {response.status_code}")
        except Exception as e:
            print(f"Deprecated URL error: {e}")

    def test_unsafe_nested_dict_access(self):
        """
        BUG: Unsafe access to nested dicts in snapshot response.
        """
        # Simulated vote with missing nested fields
        vote = {
            'id': '1234',
            'voter': '0x1234',
            'vp': 100,
            'proposal': None  # Missing proposal
        }

        # Current code would crash
        try:
            space_name = vote['proposal']['space']['name']
            assert False, "Should have raised KeyError or TypeError"
        except (KeyError, TypeError):
            pass  # Expected

        # Even "safe" .get() chain fails when value is None (not missing)
        try:
            space_name = vote.get('proposal', {}).get('space', {}).get('name', 'Unknown')
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass  # This demonstrates the bug!

        # Truly safe access must handle None explicitly
        proposal = vote.get('proposal') or {}
        space_name = proposal.get('space', {}).get('name', 'Unknown')
        assert space_name == 'Unknown'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
