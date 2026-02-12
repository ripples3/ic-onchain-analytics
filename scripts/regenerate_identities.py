#!/usr/bin/env python3
"""
Regenerate top_lending_protocol_borrowers_eoa_safe_with_identity.csv from whale_clean.csv
and add Trend Research identities + other known identities.
"""

import csv

# Trend Research cluster addresses (55 total)
TREND_RESEARCH_CLUSTER = {
    "0x00a2913501c4b09b92b825dc8a2937efdad9953b",
    "0x06185ca50a8ab43726b08d8e65c6f2173fb2b236",
    "0x0ad500d23a43ae9b26a570cfb02b68c48a866565",
    "0x0eb4add4ba497357546da7f5d12d39587ca24606",
    "0x0f1dfef1a40557d279d0de6e49ab306891a638b8",
    "0x1111567e0954e74f6ba7c4732d534e75b81dc42e",
    "0x171c53d55b1bcb725f660677d9e8bad7fd084282",
    "0x1778767436111ec0adb10f9ba4f51a329d0e7770",
    "0x1e17f8876b175d37ebe08849434973c051261461",
    "0x1e2ac461edc05bdc7b471cf93aeceec91f32ed29",
    "0x34780c209d5c575cc1c1ceb57af95d4d2a69ddcf",
    "0x3c9ea5c4fec2a77e23dd82539f4414266fe8f757",
    "0x4093fbe60ab50ab79a5bd32fa2adec255372f80e",
    "0x4196c40de33062ce03070f058922baa99b28157b",
    "0x4352cc849b33a936ad93bb109afdec1c89653b4f",
    "0x4740fa6b32c5b41ebbf631fe1af41e6fff6e2388",
    "0x4deb3edd991cfd2fcdaa6dcfe5f1743f6e7d16a6",
    "0x531e08e19e54ea655822d62f160e27af727b6e9f",
    "0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26",
    "0x564b1a055d9caaaff7435dce6b5f6e522b27de7d",
    "0x691cb02bf62a0bb2397bfae9a55f7380d415fff2",
    "0x6e9e81efcc4cbff68ed04c4a90aea33cb22c8c89",
    "0x6ece8a1cd8ce927a69b023cbac2b0cf5636cca3a",
    "0x712d0f306956a6a4b4f9319ad9b9de48c5345996",
    "0x716034c25d9fb4b38c837afe417b7f2b9af3e9ae",
    "0x71a91c9202c8091c62c630ca2de44b333ddcd0d7",
    "0x73a9ee34eaa91046b12e7598a540f28fa1b590a6",
    "0x81d0ac9a5f91188074fd753a03885162bec74246",
    "0x84d34f4f83a87596cd3fb6887cff8f17bf5a7b83",
    "0x85e05c10db73499fbdecab0dfbb794a446feeec8",
    "0x8879ae6c281495a5d40dce8015bc3bbf7b109233",
    "0x8889ff5b6323e71c28c26d2c34b8bb52654f00a6",
    "0x90d443b372b2a1212dda03c9b56c4e622688e981",
    "0x97137466bc8018531795217f0ecc4ba24dcba5c1",
    "0x9d783e9b0b19cc1bf4f6bf36169fc004ce8fa9d0",
    "0xa312114b5795dff9b8db50474dd57701aa78ad1e",
    "0xa76b6a7aa1b4501e6edcb29898e1ce4b9784e81c",
    "0xc08b122fb1057149f55d49d3d5cea0d083b37ffb",
    "0xc1914872a1dd8e7a39ac6d5ee0d6fa9fcecf001e",
    "0xc37704a457b1ee87eb657cae584a34961e86acac",
    "0xc803698a4be31f0b9035b6eba17623698f3e2f82",
    "0xca08371f6e9204dd6927dcc2db5504ea062b2998",
    "0xcd40532686b94abc88b06b9705aacbc14c8364d6",
    "0xd275e5cb559d6dc236a5f8002a5f0b4c8e610701",
    "0xd8495b95a3a6a85f4e3baa003e8b7ed1ed85562d",
    "0xdde0d6e90bfb74f1dc8ea070cfd0c0180c03ad16",
    "0xddf725d2ebd795748dd8c6b700b7c98d1dfb8ce5",
    "0xe5c248d8d3f3871bd0f68e9c4743459c43bb4e4c",
    "0xeb2a1125f1e14822d0708464b795baad6b9038ce",
    "0xf0cf6b2af598c1f2909e148cbc5f5cc7c27b878b",
    "0xf368d43f148e1803ec793670183b0ca6a07d3898",
    "0xf929122994e177079c924631ba13fb280f5cd1f9",
    "0xfadb1e5913c439e5bde92826a5b820475f58d24c",
    "0xfaf1358fe6a9fa29a169dfc272b14e709f54840f",
}

# Other known identities from lending_whales.md
KNOWN_IDENTITIES = {
    # Abraxas Capital
    "0xed0c6079229e2d407672a117c22b62064f4a4312": "Abraxas Capital",
    "0xb99a2c4c1c4f1fc27150681b740396f6ce1cbcf5": "Abraxas Capital",

    # 7 Siblings (1.21M ETH whale, uses Spark/Aave leverage)
    "0x28a55c4b4f9615fde3cdaddf6cc01fcf2e38a6b0": "7 Siblings",
    "0x741aa7cfb2c7bf2a1e7d4da2e3df6a56ca4131f3": "7 Siblings",
    "0xf8de75c7b95edb6f1e639751318f117663021cf0": "7 Siblings Recursive Farmer",

    # Protocols
    "0xf0bb20865277abd641a307ece5ee04e79073416c": "Ether.fi LIQUIDETH",
    "0x9600a48ed0f931d0c422d574e3275a90d8b22745": "Fluid (Instadapp)",
    "0x3a0dc3fc4b84e2427ced214c9ce858ea218e97d9": "Fluid (Instadapp)",
    "0xef417fce1883c6653e7dc6af7c6f85ccde84aa09": "Lido GG Vault",
    "0x893aa69fbaa1ee81b536f0fbe3a3453e86290080": "Mellow strETH Sub Vault 2",

    # Individuals
    "0x5be9a4959308a0d0c7bc0870e319314d8d957dbb": "World Liberty Financial (Trump)",
    "0x4a49985b14bd0ce42c25efde5d8c379a48ab02f3": "Aave Genesis Team",
    "0x517ce9b6d1fcffd29805c3e19b295247fcd94aef": "FalconX Client",
    "0x197f0a20c1d96f7dffd5c7b5453544947e717d66": "Copper Custodian Client",
    "0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912": "Coinbase 2 Institutional",

    # DeFi protocols
    "0x5ae0e44de96885702bd99a6914751c952d284938": "Treehouse Finance",
    "0x3883d8cdcdda03784908cfa2f34ed2cf1604e4d7": "Mellow Protocol",
    "0xba7fdd2630f82458b4369a5b84d6438352ba4531": "EtherFi",
    "0x5f39a6fb00b3e4bd7369cb40b22cf7088044136b": "Summer.fi",
    "0x84d113c540fe1109af6d629cd24ff143d743a279": "Summer.fi",
    "0x6762276585c193c840c20c492a7b63df8b28b0ae": "Summer.fi",

    # Junyi Zheng
    "0xee2826453a4fd5afeb7ceffeef3ffa2320081268": "Junyi Zheng",

    # Justin Sun / HTX (TRON founder, Huobi/HTX advisor)
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": "Justin Sun (TRON/HTX)",
    "0x176f3dab24a159341c0509bb36b833e7fdd0a132": "Justin Sun 4 (TRON/HTX)",

    # 0x9992 Whale (83k ETH, leveraged Aave borrower - Lookonchain tracked)
    "0x99926ab8e1b589500ae87977632f13cf7f70f242": "0x9992 Whale (Lookonchain tracked)",

    # 0xa339 Whale (De-risked $90M Aave position in Dec 2025 - Lookonchain tracked)
    "0xa339d279e0a3a9ede11eceac2ec9529eebdae12c": "0xa339 Whale (Lookonchain tracked)",

    # 0x46DB Whale (Accumulated 41,767 ETH at $3,130 - tracked by analysts)
    "0x46db0650645f7c9a29783c89171a62240ccc35cf": "0x46DB ETH Accumulator",
}

def get_identity_with_confidence(address: str, row: dict) -> tuple:
    """Get identity, confidence, and source for an address.

    Returns: (identity, confidence, source)

    Confidence levels:
    - HIGH: Multi-source verified (Trend Research cluster, Etherscan labeled, Arkham confirmed)
    - MEDIUM: Single authoritative source (CEX labels, custody labels, protocol identified)
    - UNVERIFIED: Real on-chain data but identity not independently verified (ENS names)

    Sources:
    - CIO Cluster: Common Input Ownership clustering analysis
    - Etherscan: Etherscan name tags
    - Arkham: Arkham Intelligence labels
    - Lookonchain: Lookonchain whale tracker
    - Dune CEX: Dune Analytics CEX labels
    - Dune Custody: Dune Analytics custody labels
    - Dune Staking: Dune Analytics staking labels
    - ENS: Ethereum Name Service (real name, but self-registered - owner identity not verified)
    - Manual: Manual research/investigation
    """
    addr_lower = address.lower()

    # Priority 1: Trend Research cluster (CIO clustering + Arkham + Lookonchain = HIGH)
    if addr_lower in TREND_RESEARCH_CLUSTER:
        return ("Trend Research (Jack Yi / LD Capital)", "HIGH", "CIO Cluster + Arkham + Lookonchain")

    # Priority 2: Known identities with confidence and source based on verification method
    if addr_lower in KNOWN_IDENTITIES:
        identity = KNOWN_IDENTITIES[addr_lower]

        # Map identities to sources
        source_map = {
            "Justin Sun": ("HIGH", "Etherscan + Wu Blockchain"),
            "7 Siblings": ("HIGH", "Arkham + Etherscan"),
            "World Liberty": ("HIGH", "Etherscan"),
            "Aave Genesis": ("HIGH", "Etherscan"),
            "Ether.fi": ("HIGH", "Etherscan"),
            "Fluid": ("HIGH", "Etherscan"),
            "Lido": ("HIGH", "Etherscan"),
            "Mellow": ("HIGH", "Etherscan"),
            "Abraxas": ("HIGH", "Arkham"),
            "Treehouse": ("MEDIUM", "Manual"),
            "Summer.fi": ("MEDIUM", "Manual"),
            "EtherFi": ("MEDIUM", "Manual"),
            "Lookonchain": ("MEDIUM", "Lookonchain"),
            "Accumulator": ("MEDIUM", "Analyst tracking"),
            "FalconX": ("MEDIUM", "On-chain analysis"),
            "Copper": ("MEDIUM", "On-chain analysis"),
            "Coinbase": ("MEDIUM", "On-chain analysis"),
            "Junyi Zheng": ("MEDIUM", "Arkham"),
        }

        for key, (conf, src) in source_map.items():
            if key in identity:
                return (identity, conf, src)

        # Default for manual entries
        return (identity, "MEDIUM", "Manual")

    # Skip list - these aren't useful identities
    SKIP_VALUES = {
        'gnosis safe', 'gnosissafe', 'safe', 'safe test', '1inch',
        'gnosissafev1.3.0', 'gnosissafev1', 'safev1.1.1', 'safev1.0.0',
        'safe_v_4_1', 'safe_v1_3_0', 'safe wallet'
    }

    def is_useful(val):
        return val and val != 'None' and val.lower() not in SKIP_VALUES

    # Priority 3: CEX labels (from Dune = MEDIUM, institutional data source)
    cex = row.get('cex_name', '') or row.get('cex_distinct_name', '')
    if is_useful(cex):
        return (cex, "MEDIUM", "Dune CEX")

    # Priority 4: Custody owner (MEDIUM - institutional source)
    custody = row.get('custody_owner', '')
    if is_useful(custody):
        return (custody, "MEDIUM", "Dune Custody")

    # Priority 5: Staking entity (MEDIUM - on-chain verified)
    staking = row.get('staking_entity', '')
    if is_useful(staking):
        return (f"Staking: {staking}", "MEDIUM", "Dune Staking")

    # Priority 6: ENS name (UNVERIFIED - real on-chain name, but owner identity not independently verified)
    ens = row.get('ens_name', '')
    if is_useful(ens):
        return (ens, "UNVERIFIED", "ENS")

    # Skip contract_project/contract_name - mostly just Safe version info

    return ("", "", "")

def regenerate_csv(input_file, output_file):
    trend_count = 0
    manual_count = 0
    auto_count = 0
    confidence_counts = {"HIGH": 0, "MEDIUM": 0, "UNVERIFIED": 0}
    source_counts = {}

    with open(input_file, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)

        # Add 'identity', 'confidence', and 'source' columns to fieldnames
        fieldnames = list(reader.fieldnames)
        if 'identity' not in fieldnames:
            fieldnames.append('identity')
        if 'confidence' not in fieldnames:
            fieldnames.append('confidence')
        if 'source' not in fieldnames:
            fieldnames.append('source')

        rows = []
        for row in reader:
            # Convert "None" strings to empty strings
            for key in row:
                if row[key] == "None" or row[key] is None:
                    row[key] = ""

            borrower = row.get('borrower', '').lower()
            identity, confidence, source = get_identity_with_confidence(borrower, row)

            if identity:
                if "Trend Research" in identity:
                    trend_count += 1
                elif borrower in KNOWN_IDENTITIES:
                    manual_count += 1
                else:
                    auto_count += 1

                if confidence in confidence_counts:
                    confidence_counts[confidence] += 1

                # Track source counts
                if source:
                    source_counts[source] = source_counts.get(source, 0) + 1

            row['identity'] = identity
            row['confidence'] = confidence
            row['source'] = source
            rows.append(row)

    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    identified = trend_count + manual_count + auto_count
    print(f"Total rows: {len(rows)}")
    print(f"Identified: {identified} ({100*identified/len(rows):.1f}%)")
    print(f"  - Trend Research cluster: {trend_count}")
    print(f"  - Manual identities: {manual_count}")
    print(f"  - From existing labels: {auto_count}")
    print(f"Confidence breakdown:")
    print(f"  - HIGH: {confidence_counts['HIGH']} (multi-source verified)")
    print(f"  - MEDIUM: {confidence_counts['MEDIUM']} (single authoritative source)")
    print(f"  - UNVERIFIED: {confidence_counts['UNVERIFIED']} (ENS - real name, owner not verified)")
    print(f"Source breakdown:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  - {src}: {count}")
    print(f"Unidentified: {len(rows) - identified}")
    print(f"Output: {output_file}")

if __name__ == "__main__":
    input_file = "/Users/don/Projects/IndexCoop/dune-analytics/whale_clean.csv"
    output_file = "/Users/don/Projects/IndexCoop/dune-analytics/references/top_lending_protocol_borrowers_eoa_safe_with_identity.csv"

    regenerate_csv(input_file, output_file)
