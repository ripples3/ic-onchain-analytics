#!/usr/bin/env python3
"""
Update identity CSV with investigation findings from whale research.
Run from dune-analytics root directory.

Usage:
    python3 scripts/update_identities.py
"""

import csv
from pathlib import Path

# Investigation findings to apply
# Format: address -> identity string
IDENTITY_UPDATES = {
    # Trend Research cluster (55 wallets) - from CIO clustering
    "0xfaf1358fe6a9fa29a169dfc272b14e709f54840f": ("Trend Research (LD Capital)", "HIGH"),
    "0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c": ("Trend Research (LD Capital)", "HIGH"),
    "0x85e05c10db73499fbdecab0dfbb794a446feeec8": ("Trend Research (LD Capital)", "HIGH"),
    "0x6e9e81efcc4cbff68ed04c4a90aea33cb22c8c89": ("Trend Research (LD Capital)", "HIGH"),
    "0x34780c209d5c575cc1c1ceb57af95d4d2a69ddcf": ("Trend Research (LD Capital)", "HIGH"),
    "0x1778767436111ec0adb10f9ba4f51a329d0e7770": ("Trend Research (LD Capital)", "HIGH"),
    "0x00a2913501c4b09b92b825dc8a2937efdad9953b": ("Trend Research (LD Capital)", "HIGH"),
    "0x06185ca50a8ab43726b08d8e65c6f2173fb2b236": ("Trend Research (LD Capital)", "HIGH"),
    "0x0ad500d23a43ae9b26a570cfb02b68c48a866565": ("Trend Research (LD Capital)", "HIGH"),
    "0x0eb4add4ba497357546da7f5d12d39587ca24606": ("Trend Research (LD Capital)", "HIGH"),
    "0x0f1dfef1a40557d279d0de6e49ab306891a638b8": ("Trend Research (LD Capital)", "HIGH"),
    "0x1111567e0954e74f6ba7c4732d534e75b81dc42e": ("Trend Research (LD Capital)", "HIGH"),
    "0x171c53d55b1bcb725f660677d9e8bad7fd084282": ("Trend Research (LD Capital)", "HIGH"),
    "0x1e17f8876b175d37ebe08849434973c051261461": ("Trend Research (LD Capital)", "HIGH"),
    "0x1e2ac461edc05bdc7b471cf93aeceec91f32ed29": ("Trend Research (LD Capital)", "HIGH"),
    "0x3c9ea5c4fec2a77e23dd82539f4414266fe8f757": ("Trend Research (LD Capital)", "HIGH"),
    "0x4093fbe60ab50ab79a5bd32fa2adec255372f80e": ("Trend Research (LD Capital)", "HIGH"),
    "0x4196c40de33062ce03070f058922baa99b28157b": ("Trend Research (LD Capital)", "HIGH"),
    "0x4352cc849b33a936ad93bb109afdec1c89653b4f": ("Trend Research (LD Capital)", "HIGH"),
    "0x4740fa6b32c5b41ebbf631fe1af41e6fff6e2388": ("Trend Research (LD Capital)", "HIGH"),
    "0x4deb3edd991cfd2fcdaa6dcfe5f1743f6e7d16a6": ("Trend Research (LD Capital)", "HIGH"),
    "0x531e08e19e54ea655822d62f160e27af727b6e9f": ("Trend Research (LD Capital)", "HIGH"),
    "0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26": ("Trend Research (LD Capital)", "HIGH"),
    "0x564b1a055d9caaaff7435dce6b5f6e522b27de7d": ("Trend Research (LD Capital)", "HIGH"),
    "0x691cb02bf62a0bb2397bfae9a55f7380d415fff2": ("Trend Research (LD Capital)", "HIGH"),
    "0x6ece8a1cd8ce927a69b023cbac2b0cf5636cca3a": ("Trend Research (LD Capital)", "HIGH"),
    "0x712d0f306956a6a4b4f9319ad9b9de48c5345996": ("Trend Research (LD Capital)", "HIGH"),
    "0x716034c25d9fb4b38c837afe417b7f2b9af3e9ae": ("Trend Research (LD Capital)", "HIGH"),
    "0x71a91c9202c8091c62c630ca2de44b333ddcd0d7": ("Trend Research (LD Capital)", "HIGH"),
    "0x73a9ee34eaa91046b12e7598a540f28fa1b590a6": ("Trend Research (LD Capital)", "HIGH"),
    "0x81d0ac9a5f91188074fd753a03885162bec74246": ("Trend Research (LD Capital)", "HIGH"),
    "0x84d34f4f83a87596cd3fb6887cff8f17bf5a7b83": ("Trend Research (LD Capital)", "HIGH"),
    "0x8879ae6c281495a5d40dce8015bc3bbf7b109233": ("Trend Research (LD Capital)", "HIGH"),
    "0x8889ff5b6323e71c28c26d2c34b8bb52654f00a6": ("Trend Research (LD Capital)", "HIGH"),
    "0x90d443b372b2a1212dda03c9b56c4e622688e981": ("Trend Research (LD Capital)", "HIGH"),
    "0x97137466bc8018531795217f0ecc4ba24dcba5c1": ("Trend Research (LD Capital)", "HIGH"),
    "0x9d783e9b0b19cc1bf4f6bf36169fc004ce8fa9d0": ("Trend Research (LD Capital)", "HIGH"),
    "0xa312114b5795dff9b8db50474dd57701aa78ad1e": ("Trend Research (LD Capital)", "HIGH"),
    "0xa76b6a7aa1b4501e6edcb29898e1ce4b9784e81c": ("Trend Research (LD Capital)", "HIGH"),
    "0xc08b122fb1057149f55d49d3d5cea0d083b37ffb": ("Trend Research (LD Capital)", "HIGH"),
    "0xc1914872a1dd8e7a39ac6d5ee0d6fa9fcecf001e": ("Trend Research (LD Capital)", "HIGH"),
    "0xc37704a457b1ee87eb657cae584a34961e86acac": ("Trend Research (LD Capital)", "HIGH"),
    "0xc803698a4be31f0b9035b6eba17623698f3e2f82": ("Trend Research (LD Capital)", "HIGH"),
    "0xca08371f6e9204dd6927dcc2db5504ea062b2998": ("Trend Research (LD Capital)", "HIGH"),
    "0xcd40532686b94abc88b06b9705aacbc14c8364d6": ("Trend Research (LD Capital)", "HIGH"),
    "0xd275e5cb559d6dc236a5f8002a5f0b4c8e610701": ("Trend Research (LD Capital)", "HIGH"),
    "0xd8495b95a3a6a85f4e3baa003e8b7ed1ed85562d": ("Trend Research (LD Capital)", "HIGH"),
    "0xdde0d6e90bfb74f1dc8ea070cfd0c0180c03ad16": ("Trend Research (LD Capital)", "HIGH"),
    "0xddf725d2ebd795748dd8c6b700b7c98d1dfb8ce5": ("Trend Research (LD Capital)", "HIGH"),
    "0xeb2a1125f1e14822d0708464b795baad6b9038ce": ("Trend Research (LD Capital)", "HIGH"),
    "0xf0cf6b2af598c1f2909e148cbc5f5cc7c27b878b": ("Trend Research (LD Capital)", "HIGH"),
    "0xf368d43f148e1803ec793670183b0ca6a07d3898": ("Trend Research (LD Capital)", "HIGH"),
    "0xf929122994e177079c924631ba13fb280f5cd1f9": ("Trend Research (LD Capital)", "HIGH"),
    "0xfadb1e5913c439e5bde92826a5b820475f58d24c": ("Trend Research (LD Capital)", "HIGH"),

    # Verified entities from investigation
    "0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3": ("Aave Genesis Team", "HIGH"),
    "0x197f0a20c1d96f7dffd5c7b5453544947e717d66": ("Copper custodian client (lead)", "MEDIUM-HIGH"),
    "0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912": ("Coinbase 2 institutional (lead)", "MEDIUM"),
    "0x3edc842766cb19644f7181709a243e523be29c4c": ("Garrett Jin / HyperUnit (AVOID)", "MEDIUM"),
    "0x50fc9731dace42caa45d166bff404bbb7464bf21": ("Paxos/Singapore institutional (lead)", "MEDIUM"),

    # Protocol vaults
    "0xf0bb20865277abd641a307ece5ee04e79073416c": ("Ether.fi LIQUIDETH", "HIGH"),
    "0x9600a48ed0f931d0c422d574e3275a90d8b22745": ("Fluid (Instadapp)", "HIGH"),
    "0x3a0dc3fc4b84e2427ced214c9ce858ea218e97d9": ("Fluid (Instadapp)", "HIGH"),
    "0xef417fce1883c6653e7dc6af7c6f85ccde84aa09": ("Lido GG Vault", "HIGH"),
    "0x893aa69fbaa1ee81b536f0fbe3a3453e86290080": ("Mellow strETH Sub Vault 2", "HIGH"),

    # DeFi protocols
    "0x5ae0e44de96885702bd99a6914751c952d284938": ("Treehouse Finance", "HIGH"),
    "0x3883d8cdcdda03784908cfa2f34ed2cf1604e4d7": ("Mellow Protocol", "HIGH"),
    "0xba7fdd2630f82458b4369a5b84d6438352ba4531": ("EtherFi", "HIGH"),
    "0x5f39a6fb00b3e4bd7369cb40b22cf7088044136b": ("Summer.fi", "HIGH"),
    "0x84d113c540fe1109af6d629cd24ff143d743a279": ("Summer.fi", "HIGH"),
    "0x6762276585c193c840c20c492a7b63df8b28b0ae": ("Summer.fi", "HIGH"),

    # ENS whales
    "0x7a16ff8270133f063aab6c9977183d9e72835428": ("Michael Egorov (llamalend.eth)", "HIGH"),
    "0x9026a229b535ecf0162dfe48fdeb3c75f7b2a7ae": ("czsamsunsb.eth (Sophisticated Whale)", "MEDIUM"),
    "0xa0f75491720835b36edc92d06ddc468d201e9b73": ("analytico.eth (DeFi Whale)", "MEDIUM"),
    "0xa1175a219dac539f2291377f77afd786d20e5882": ("mandalacapital.eth (Possibly VC)", "LOW"),
    "0xa53a13a80d72a855481de5211e7654fabdfe3526": ("greenfund.eth (DeFi Whale)", "LOW"),

    # === NEW IDENTIFICATIONS (Feb 2026 Investigation) ===

    # Justin Sun - TRON founder, major DeFi whale
    # Confirmed via Etherscan label + multiple news sources
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": ("Justin Sun (TRON/HTX)", "HIGH"),

    # World Liberty Financial - Trump family DeFi project
    # Addresses confirmed via Etherscan labels
    "0x5be9a4959308a0d0c7bc0870e319314d8d957dbb": ("World Liberty Financial (Trump)", "HIGH"),
    "0x97f1f8003ad0fb1c99361170310c65dc84f921e3": ("World Liberty Financial (Trump)", "HIGH"),

    # Hodlnaut - Historical association from Terra Luna analysis
    # LOW confidence - company ceased operations, address may be transferred
    "0x99fd1378ca799ed6772fe7bcdc9b30b389518962": ("Hodlnaut (historical)", "LOW"),

    # BitcoinOG (1011short) - Major whale, $4B+ holdings
    # Tracked by Arkham and Lookonchain, known for Oct 2025 BTC short
    "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae": ("BitcoinOG (1011short)", "HIGH"),
    "0x2ea18c23f72a4b6172c55b411823cdc5335923f4": ("BitcoinOG (1011short)", "HIGH"),
    "0x4b70525ecf8819a6d1422ba878be87e602f8b42e": ("BitcoinOG (1011short)", "HIGH"),
}

def update_csv(input_path: Path, output_path: Path):
    """Update identity CSV with investigation findings."""
    rows = []
    updated_count = 0
    already_set_count = 0

    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            address = row.get('borrower', '').lower()

            if address in IDENTITY_UPDATES:
                identity_data = IDENTITY_UPDATES[address]
                # Handle both (identity, confidence) tuples and plain strings
                if isinstance(identity_data, tuple):
                    identity = identity_data[0]
                else:
                    identity = identity_data

                current_identity = row.get('identity', '').strip()

                # Only update if not already set
                if not current_identity:
                    row['identity'] = identity
                    updated_count += 1
                else:
                    already_set_count += 1

            rows.append(row)

    # Write updated CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated_count, already_set_count, len(rows)

def main():
    input_path = Path("references/top_lending_protocol_borrowers_eoa_safe_with_identity.csv")
    output_path = input_path  # Overwrite in place

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return

    updated, already_set, total = update_csv(input_path, output_path)
    print(f"Updated {updated} rows (newly identified)")
    print(f"Already had identity: {already_set} rows (skipped)")
    print(f"Total rows: {total}")
    print(f"\nIdentities applied from investigation findings ({len(IDENTITY_UPDATES)} addresses in mapping)")

if __name__ == "__main__":
    main()
