#!/usr/bin/env python3
"""
Governance/Snapshot Scraper

Scrapes governance activity to identify wallet owners through:
1. Snapshot voting history - which DAOs they vote in
2. Delegation patterns - who delegates to whom
3. Forum cross-reference - link votes to forum usernames

People who vote on governance often reveal identity through:
- ENS names on votes
- Forum posts discussing their votes
- Delegation relationships

Usage:
    python3 governance_scraper.py addresses.csv -o governance.csv
    python3 governance_scraper.py --address 0x1234...
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set
import requests
from dotenv import load_dotenv

load_dotenv()

SNAPSHOT_GRAPHQL_URL = "https://hub.snapshot.org/graphql"

# Rate limiting
RATE_LIMIT = 2  # requests per second
last_request_time = 0

def rate_limit():
    """Enforce rate limiting."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / RATE_LIMIT:
        time.sleep(1 / RATE_LIMIT - elapsed)
    last_request_time = time.time()

def snapshot_query(query: str, variables: dict = None) -> dict:
    """Execute a Snapshot GraphQL query."""
    rate_limit()

    try:
        response = requests.post(
            SNAPSHOT_GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        data = response.json()
        return data.get("data", {})
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return {}

def get_votes_by_voter(address: str, limit: int = 100) -> List[dict]:
    """Get all votes cast by an address."""
    query = """
    query Votes($voter: String!, $first: Int!) {
        votes(
            where: { voter: $voter }
            first: $first
            orderBy: "created"
            orderDirection: desc
        ) {
            id
            voter
            created
            choice
            vp
            proposal {
                id
                title
                state
                space {
                    id
                    name
                }
            }
        }
    }
    """

    result = snapshot_query(query, {"voter": address.lower(), "first": limit})
    return result.get("votes", [])

def get_delegations_for_address(address: str) -> dict:
    """Get delegation info - who this address delegates to and who delegates to them."""
    # Query delegations FROM this address
    query_from = """
    query Delegations($delegator: String!) {
        delegations(
            where: { delegator: $delegator }
            first: 100
        ) {
            id
            delegator
            delegate
            space
            timestamp
        }
    }
    """

    # Query delegations TO this address
    query_to = """
    query Delegations($delegate: String!) {
        delegations(
            where: { delegate: $delegate }
            first: 100
        ) {
            id
            delegator
            delegate
            space
            timestamp
        }
    }
    """

    result_from = snapshot_query(query_from, {"delegator": address.lower()})
    result_to = snapshot_query(query_to, {"delegate": address.lower()})

    return {
        "delegates_to": result_from.get("delegations", []),
        "delegated_from": result_to.get("delegations", [])
    }

def get_space_info(space_id: str) -> dict:
    """Get details about a Snapshot space."""
    query = """
    query Space($id: String!) {
        space(id: $id) {
            id
            name
            about
            network
            symbol
            members
            admins
            moderators
            website
            twitter
        }
    }
    """

    result = snapshot_query(query, {"id": space_id})
    return result.get("space", {})

def analyze_governance_activity(address: str) -> dict:
    """Analyze all governance activity for an address."""
    print(f"  Fetching votes for {address[:10]}...")
    votes = get_votes_by_voter(address)

    print(f"  Fetching delegations...")
    delegations = get_delegations_for_address(address)

    # Aggregate by space
    spaces_voted: Dict[str, List[dict]] = defaultdict(list)
    for vote in votes:
        if vote.get("proposal") and vote["proposal"].get("space"):
            space_id = vote["proposal"]["space"]["id"]
            spaces_voted[space_id].append(vote)

    # Calculate metrics
    total_votes = len(votes)
    unique_spaces = len(spaces_voted)
    total_vp = sum(v.get("vp", 0) for v in votes)

    # Get space details for top spaces
    space_details = {}
    for space_id in list(spaces_voted.keys())[:5]:
        info = get_space_info(space_id)
        if info:
            space_details[space_id] = {
                "name": info.get("name"),
                "twitter": info.get("twitter"),
                "website": info.get("website"),
                "vote_count": len(spaces_voted[space_id])
            }

    # Analyze delegation patterns
    delegates_to = []
    for d in delegations.get("delegates_to", []):
        delegates_to.append({
            "delegate": d.get("delegate"),
            "space": d.get("space")
        })

    delegated_from = []
    for d in delegations.get("delegated_from", []):
        delegated_from.append({
            "delegator": d.get("delegator"),
            "space": d.get("space")
        })

    return {
        "address": address.lower(),
        "total_votes": total_votes,
        "unique_spaces": unique_spaces,
        "total_voting_power": total_vp,
        "spaces": space_details,
        "delegates_to": delegates_to,
        "delegated_from": delegated_from,
        "recent_votes": [
            {
                "proposal": v["proposal"]["title"] if v.get("proposal") else "Unknown",
                "space": v["proposal"]["space"]["name"] if v.get("proposal", {}).get("space") else "Unknown",
                "created": v.get("created"),
                "vp": v.get("vp", 0)
            }
            for v in votes[:5]
        ],
        "identity_signals": extract_identity_signals(votes, delegations)
    }

def extract_identity_signals(votes: List[dict], delegations: dict) -> List[str]:
    """Extract potential identity signals from governance activity."""
    signals = []

    # Check for high voting power (institutional)
    total_vp = sum(v.get("vp", 0) for v in votes)
    if total_vp > 1000000:
        signals.append(f"High voting power ({total_vp:,.0f}) - likely institutional")

    # Check for DAO admin/moderator roles (would need separate query)

    # Check delegation patterns
    delegates_to = delegations.get("delegates_to", [])
    delegated_from = delegations.get("delegated_from", [])

    if len(delegated_from) > 10:
        signals.append(f"Receives delegation from {len(delegated_from)} addresses - likely known entity")

    if len(delegates_to) > 0:
        # Check if they delegate to known entities
        for d in delegates_to:
            delegate = d.get("delegate", "")
            space = d.get("space", "")
            signals.append(f"Delegates to {delegate[:10]}... in {space}")

    # Check for specific space patterns
    spaces = set()
    for v in votes:
        if v.get("proposal", {}).get("space"):
            spaces.add(v["proposal"]["space"]["id"])

    # Known institutional spaces
    institutional_spaces = {"aave.eth", "uniswap", "compound-governance.eth", "ens.eth", "gitcoin.eth"}
    matched_institutional = spaces & institutional_spaces

    if matched_institutional:
        signals.append(f"Active in major DAOs: {', '.join(matched_institutional)}")

    return signals

def find_related_voters(addresses: List[str]) -> Dict[str, Set[str]]:
    """Find addresses that vote together (same proposals, same choices)."""
    print("\nAnalyzing voting patterns for relationships...")

    # Build proposal -> voters mapping
    proposal_voters: Dict[str, Dict[str, int]] = defaultdict(dict)  # proposal_id -> {voter: choice}

    for addr in addresses:
        votes = get_votes_by_voter(addr, limit=50)
        for vote in votes:
            if vote.get("proposal"):
                proposal_id = vote["proposal"]["id"]
                choice = vote.get("choice")
                proposal_voters[proposal_id][addr.lower()] = choice

    # Find addresses that vote together frequently
    vote_together: Dict[tuple, int] = defaultdict(int)

    for proposal_id, voters in proposal_voters.items():
        voter_list = list(voters.keys())
        for i in range(len(voter_list)):
            for j in range(i + 1, len(voter_list)):
                if voters[voter_list[i]] == voters[voter_list[j]]:  # Same choice
                    pair = tuple(sorted([voter_list[i], voter_list[j]]))
                    vote_together[pair] += 1

    # Group addresses that vote together frequently
    clusters: Dict[str, Set[str]] = {}
    cluster_id = 0

    for (addr1, addr2), count in vote_together.items():
        if count >= 3:  # Voted same way on 3+ proposals
            # Find or create cluster
            found = False
            for cid, members in clusters.items():
                if addr1 in members or addr2 in members:
                    members.add(addr1)
                    members.add(addr2)
                    found = True
                    break

            if not found:
                clusters[f"voting_cluster_{cluster_id}"] = {addr1, addr2}
                cluster_id += 1

    return clusters

def main():
    parser = argparse.ArgumentParser(description="Governance/Snapshot Scraper")
    parser.add_argument("input", nargs="?", help="Input CSV file with addresses")
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("--address", help="Single address to analyze")
    parser.add_argument("--find-related", action="store_true",
                        help="Find addresses that vote together")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Get addresses
    if args.address:
        addresses = [args.address]
    elif args.input:
        with open(args.input) as f:
            reader = csv.DictReader(f)
            addresses = [row.get("address") or row.get("borrower") for row in reader]
            addresses = [a for a in addresses if a]
    else:
        print("Error: Provide input CSV or --address", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing governance activity for {len(addresses)} addresses...")
    print()

    results = []

    for i, addr in enumerate(addresses):
        print(f"[{i+1}/{len(addresses)}] {addr[:10]}...")
        activity = analyze_governance_activity(addr)
        results.append(activity)

        if activity["total_votes"] > 0:
            print(f"  → {activity['total_votes']} votes in {activity['unique_spaces']} spaces")
            if activity["identity_signals"]:
                for signal in activity["identity_signals"]:
                    print(f"  → {signal}")
        else:
            print(f"  → No governance activity found")

    # Find related voters if requested
    voting_clusters = {}
    if args.find_related and len(addresses) > 1:
        voting_clusters = find_related_voters(addresses)
        if voting_clusters:
            print(f"\nFound {len(voting_clusters)} voting clusters:")
            for cluster_id, members in voting_clusters.items():
                print(f"  {cluster_id}: {len(members)} addresses vote together")

    # Output
    if args.json:
        output = {
            "results": results,
            "voting_clusters": {k: list(v) for k, v in voting_clusters.items()}
        }
        print(json.dumps(output, indent=2))

    # Save to CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "address", "total_votes", "unique_spaces", "total_voting_power",
                "top_spaces", "delegates_to", "delegated_from_count",
                "identity_signals", "voting_cluster"
            ])

            # Map addresses to clusters
            addr_to_cluster = {}
            for cluster_id, members in voting_clusters.items():
                for member in members:
                    addr_to_cluster[member] = cluster_id

            for r in results:
                top_spaces = "|".join([
                    f"{s['name']}({s['vote_count']})"
                    for s in r.get("spaces", {}).values()
                ][:3])

                delegates_to = "|".join([
                    d["delegate"][:10] for d in r.get("delegates_to", [])
                ][:3])

                writer.writerow([
                    r["address"],
                    r["total_votes"],
                    r["unique_spaces"],
                    r["total_voting_power"],
                    top_spaces,
                    delegates_to,
                    len(r.get("delegated_from", [])),
                    "|".join(r.get("identity_signals", [])),
                    addr_to_cluster.get(r["address"].lower(), "")
                ])

        print(f"\nSaved to {args.output}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    active_voters = [r for r in results if r["total_votes"] > 0]
    high_vp = [r for r in results if r["total_voting_power"] > 100000]
    with_signals = [r for r in results if r["identity_signals"]]

    print(f"Total addresses: {len(results)}")
    print(f"Active voters: {len(active_voters)} ({100*len(active_voters)/len(results):.1f}%)")
    print(f"High voting power (>100K): {len(high_vp)}")
    print(f"With identity signals: {len(with_signals)}")

    if voting_clusters:
        print(f"Voting clusters found: {len(voting_clusters)}")

if __name__ == "__main__":
    main()
