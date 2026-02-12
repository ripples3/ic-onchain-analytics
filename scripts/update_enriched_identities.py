#!/usr/bin/env python3
"""
Add identity column to whale_top200_enriched.csv based on investigation findings.
"""

import csv
from pathlib import Path

# Same identity mappings from update_identities.py
IDENTITY_UPDATES = {
    # Trend Research cluster
    "0xfaf1358fe6a9fa29a169dfc272b14e709f54840f": "Trend Research (LD Capital)",
    "0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c": "Trend Research (LD Capital)",
    "0x85e05c10db73499fbdecab0dfbb794a446feeec8": "Trend Research (LD Capital)",
    "0x6e9e81efcc4cbff68ed04c4a90aea33cb22c8c89": "Trend Research (LD Capital)",
    "0x34780c209d5c575cc1c1ceb57af95d4d2a69ddcf": "Trend Research (LD Capital)",
    "0x1778767436111ec0adb10f9ba4f51a329d0e7770": "Trend Research (LD Capital)",
    "0x00a2913501c4b09b92b825dc8a2937efdad9953b": "Trend Research (LD Capital)",
    "0x06185ca50a8ab43726b08d8e65c6f2173fb2b236": "Trend Research (LD Capital)",
    "0x0ad500d23a43ae9b26a570cfb02b68c48a866565": "Trend Research (LD Capital)",
    "0x0eb4add4ba497357546da7f5d12d39587ca24606": "Trend Research (LD Capital)",
    "0x0f1dfef1a40557d279d0de6e49ab306891a638b8": "Trend Research (LD Capital)",
    "0x1111567e0954e74f6ba7c4732d534e75b81dc42e": "Trend Research (LD Capital)",
    "0x171c53d55b1bcb725f660677d9e8bad7fd084282": "Trend Research (LD Capital)",
    "0x1e17f8876b175d37ebe08849434973c051261461": "Trend Research (LD Capital)",
    "0x1e2ac461edc05bdc7b471cf93aeceec91f32ed29": "Trend Research (LD Capital)",
    "0x3c9ea5c4fec2a77e23dd82539f4414266fe8f757": "Trend Research (LD Capital)",
    "0x4093fbe60ab50ab79a5bd32fa2adec255372f80e": "Trend Research (LD Capital)",
    "0x4196c40de33062ce03070f058922baa99b28157b": "Trend Research (LD Capital)",
    "0x4352cc849b33a936ad93bb109afdec1c89653b4f": "Trend Research (LD Capital)",
    "0x4740fa6b32c5b41ebbf631fe1af41e6fff6e2388": "Trend Research (LD Capital)",
    "0x4deb3edd991cfd2fcdaa6dcfe5f1743f6e7d16a6": "Trend Research (LD Capital)",
    "0x531e08e19e54ea655822d62f160e27af727b6e9f": "Trend Research (LD Capital)",
    "0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26": "Trend Research (LD Capital)",
    "0x564b1a055d9caaaff7435dce6b5f6e522b27de7d": "Trend Research (LD Capital)",
    "0x691cb02bf62a0bb2397bfae9a55f7380d415fff2": "Trend Research (LD Capital)",
    "0x6ece8a1cd8ce927a69b023cbac2b0cf5636cca3a": "Trend Research (LD Capital)",
    "0x712d0f306956a6a4b4f9319ad9b9de48c5345996": "Trend Research (LD Capital)",
    "0x716034c25d9fb4b38c837afe417b7f2b9af3e9ae": "Trend Research (LD Capital)",
    "0x71a91c9202c8091c62c630ca2de44b333ddcd0d7": "Trend Research (LD Capital)",
    "0x73a9ee34eaa91046b12e7598a540f28fa1b590a6": "Trend Research (LD Capital)",
    "0x81d0ac9a5f91188074fd753a03885162bec74246": "Trend Research (LD Capital)",
    "0x84d34f4f83a87596cd3fb6887cff8f17bf5a7b83": "Trend Research (LD Capital)",
    "0x8879ae6c281495a5d40dce8015bc3bbf7b109233": "Trend Research (LD Capital)",
    "0x8889ff5b6323e71c28c26d2c34b8bb52654f00a6": "Trend Research (LD Capital)",
    "0x90d443b372b2a1212dda03c9b56c4e622688e981": "Trend Research (LD Capital)",
    "0x97137466bc8018531795217f0ecc4ba24dcba5c1": "Trend Research (LD Capital)",
    "0x9d783e9b0b19cc1bf4f6bf36169fc004ce8fa9d0": "Trend Research (LD Capital)",
    "0xa312114b5795dff9b8db50474dd57701aa78ad1e": "Trend Research (LD Capital)",
    "0xa76b6a7aa1b4501e6edcb29898e1ce4b9784e81c": "Trend Research (LD Capital)",
    "0xc08b122fb1057149f55d49d3d5cea0d083b37ffb": "Trend Research (LD Capital)",
    "0xc1914872a1dd8e7a39ac6d5ee0d6fa9fcecf001e": "Trend Research (LD Capital)",
    "0xc37704a457b1ee87eb657cae584a34961e86acac": "Trend Research (LD Capital)",
    "0xc803698a4be31f0b9035b6eba17623698f3e2f82": "Trend Research (LD Capital)",
    "0xca08371f6e9204dd6927dcc2db5504ea062b2998": "Trend Research (LD Capital)",
    "0xcd40532686b94abc88b06b9705aacbc14c8364d6": "Trend Research (LD Capital)",
    "0xd275e5cb559d6dc236a5f8002a5f0b4c8e610701": "Trend Research (LD Capital)",
    "0xd8495b95a3a6a85f4e3baa003e8b7ed1ed85562d": "Trend Research (LD Capital)",
    "0xdde0d6e90bfb74f1dc8ea070cfd0c0180c03ad16": "Trend Research (LD Capital)",
    "0xddf725d2ebd795748dd8c6b700b7c98d1dfb8ce5": "Trend Research (LD Capital)",
    "0xeb2a1125f1e14822d0708464b795baad6b9038ce": "Trend Research (LD Capital)",
    "0xf0cf6b2af598c1f2909e148cbc5f5cc7c27b878b": "Trend Research (LD Capital)",
    "0xf368d43f148e1803ec793670183b0ca6a07d3898": "Trend Research (LD Capital)",
    "0xf929122994e177079c924631ba13fb280f5cd1f9": "Trend Research (LD Capital)",
    "0xfadb1e5913c439e5bde92826a5b820475f58d24c": "Trend Research (LD Capital)",

    # Verified entities
    "0xed0c6079229e2d407672a117c22b62064f4a4312": "Abraxas Capital",
    "0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5": "Abraxas Capital",
    "0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3": "Aave Genesis Team",
    "0x517ce9b6d1fcffd29805c3e19b295247fcd94aef": "FalconX Client",
    "0x197f0a20c1d96f7dffd5c7b5453544947e717d66": "Copper Custodian Client",
    "0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912": "Coinbase 2 Institutional",
    "0x3edc842766cb19644f7181709a243e523be29c4c": "Garrett Jin / HyperUnit (AVOID)",
    "0x50fc9731dace42caa45d166bff404bbb7464bf21": "Paxos/Singapore Institutional",
    "0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0": "7 Siblings",
    "0x741aa7cfb2c7bf2a1e7d4da2e3df6a56ca4131f3": "7 Siblings",
    "0x7a16ff8270133f063aab6c9977183d9e72835428": "Michael Egorov (llamalend.eth)",

    # === NEW IDENTIFICATIONS (Feb 2026) ===
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": "Justin Sun (TRON/HTX)",
    "0x5be9a4959308a0d0c7bc0870e319314d8d957dbb": "World Liberty Financial (Trump)",
    "0x97f1f8003ad0fb1c99361170310c65dc84f921e3": "World Liberty Financial (Trump)",
    "0x99fd1378ca799ed6772fe7bcdc9b30b389518962": "Hodlnaut (historical)",
}

def update_enriched(input_path: Path, output_path: Path):
    """Add identity column to enriched CSV."""
    rows = []

    with open(input_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) + ['identity']

        for row in reader:
            address = row.get('address', '').lower()
            row['identity'] = IDENTITY_UPDATES.get(address, '')
            rows.append(row)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    identified = sum(1 for r in rows if r['identity'])
    return identified, len(rows)

def main():
    input_path = Path("whale_top200_enriched.csv")
    output_path = input_path

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return

    identified, total = update_enriched(input_path, output_path)
    print(f"Added identity to {identified} of {total} rows in whale_top200_enriched.csv")

if __name__ == "__main__":
    main()
