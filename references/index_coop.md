# Index Coop Contract Reference

Quick reference for Index Coop product addresses and common query patterns across chains.

## Saved Dune Queries

| Query ID | Name | Usage |
|----------|------|-------|
| **2364870** | Index Coop - Tokens | `python3 scripts/dune_query.py 2364870 --limit 10` |
| **4771298** | Index Coop - Leverage Suite Tokens | `python3 scripts/dune_query.py 4771298 --limit 10` |
| **5140527** | multichain-indexcoop-tokenlist | `python3 scripts/dune_query.py 5140527 --limit 10` |

SQL files stored in `queries/` folder.

## Product Addresses

### Ethereum Mainnet

#### Leverage Tokens

| Product | Symbol | Address | Base Asset |
|---------|--------|---------|------------|
| 2x Leveraged ETH | ETH2X | `0x65c4c0517025ec0843c9146af266a2c5a2d148` | WETH |
| 3x Leveraged ETH | ETH3x | `0x23c3e5b3d001e17054603269edfc703603adef` | WETH |
| 2x Leveraged BTC | BTC2X | `0xd2ac55ca3bbd2dd1e9936ec640dcb4b745fde7` | WBTC |
| 3x Leveraged BTC | BTC3x | `0xc7068657fd7ec85ea8db928af980fc088aff6d` | WBTC |
| 3x Leveraged Gold | GOLD3x | `0x1d86fbad389068e19fa665eba12a0ebd4c68bb` | XAUt |
| icETH (earn) | icETH | `0x7c07f7abe10ce8e33dc6c5ad68fe033085256a` | - |

#### Index Products (Strategies)

| Product | Symbol | Address | Status |
|---------|--------|---------|--------|
| DeFi Pulse Index | DPI | `0x1494ca1f11d487c2bbe4543e90080aeba4ba3c` | Active |
| Metaverse Index | MVI | `0x72e364f2abdc788b7e918bc238b21f109cd634` | Active |
| Bankless BED Index | BED | `0x2af1df3ab0ab157e1e2ad8f88a7d04fbea0c7d` | Active |
| Index Coop 21 | ic21 | `0x1b5e16c5b20fb5ee87c61fe9afe735cca3b21a` | Active |
| CoinDesk ETI | cdETI | `0x55b2cfcfe99110c773f00b023560dd9ef6c8a1` | Active |

#### Earn Products

| Product | Symbol | Address | Status |
|---------|--------|---------|--------|
| Diversified Staked ETH | dsETH | `0x341c05c0e9b33c0e38d64de76516b2ce970bb3` | Active |
| Gitcoin Staked ETH | gtcETH | `0x36c833eed0d376f75d1ff9dfdee26019133606` | Active |
| High Yield ETH | hyETH | `0xc4506022fb8090774e8a628d5084eed61d9b99` | Ended 2025-01-07 |
| Morpho hyETH | mhyETH | `0x701907283a57ff77e255c3f1aad790466b8ce4` | Active |

#### PRT Tokens

| Product | Symbol | Address |
|---------|--------|---------|
| Staked PRT hyETH | sPrtHyETH | `0xbe03026716a4d5e0992f22a3e6494b4f2809a9` |
| PRT hyETH | prtHyETH | `0x99f6539df9840592a862ab916ddc3258a1d7a7` |

#### Deprecated (FLI Products)

| Product | Symbol | Address | End Date |
|---------|--------|---------|----------|
| ETH 2x FLI | ETH2x-FLI | `0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665` | 2024-03-11 |
| BTC 2x FLI | BTC2x-FLI | `0x0b498ff89709d3838a063f1dfa463091f9801c` | 2024-03-11 |

---

### Arbitrum

#### Leverage Tokens

| Product | Symbol | Address | Base Asset |
|---------|--------|---------|------------|
| 3x Leveraged ETH | ETH3x | `0xa0a17b2a015c14be846c5d309d076379ccdfa5` | WETH |
| 2x Leveraged ETH | ETH2x | `0x26d7d3728c6bb762a5043a1d0cef660988bca4` | WETH |
| 1x Inverse ETH | iETH1x | `0x749654601a286833ad30357246400d2933b1c8` | WETH |
| 2x Inverse ETH | iETH2x | `0x6a21af139b440f0944f9e03375544bb3e4e213` | WETH |
| 3x Leveraged BTC | BTC3x | `0x3bdd0d5c0c795b2bf076f5c8f177c58e42bec0` | WBTC |
| 2x Leveraged BTC | BTC2x | `0xeb5be62e6770137beaa0cc712741165c594f59` | WBTC |
| 1x Inverse BTC | iBTC1x | `0x80e58aea88bccaae19bca7f0e420c1387cc087` | WETH |
| 2x Inverse BTC | iBTC2x | `0x304f3eb3b77c025664a7b13c3f0ee2f97f9743` | WBTC |
| ETH/BTC Ratio 2x | ETH2xBTC | `0xe7b1ce8dfee3d7417397cd4f56dbfc0d49e43e` | WETH |
| BTC/ETH Ratio 2x | BTC2xETH | `0x77f69104145f94a81cec55747c7a0fc9cb7712` | WBTC |
| 2x Leveraged LINK | LINK2x | `0xaf0408c1cc4b41cf8781434230159370328789` | LINK |
| 2x Leveraged AAVE | AAVE2x | `0x9ba1d6c651624977435bc6e2c98d4c7407112e` | AAVE |
| 2x Leveraged ARB | ARB2x | `0xfc01f273126b3d515e6ce6cab9e53d5c6990d6` | ARB |

#### Bridged Products

| Product | Symbol | Address |
|---------|--------|---------|
| DPI (bridged) | DPI | `0x9737c658272e66faad39d7ad337789ee6d54f5` |
| MVI (bridged) | MVI | `0x0104a6fa30540dc1d9f45d2797f05eea793045` |
| hyETH (bridged) | hyETH | `0x8b5d1d8b3466ec21f8ee33ce63f319642c0261` |

---

### Base

#### Leverage Tokens

| Product | Symbol | Address | Base Asset |
|---------|--------|---------|------------|
| 3x Leveraged ETH | ETH3x | `0x329f6656792c7d34d0fbb9762fa9a8f852272a` | WETH |
| 2x Leveraged ETH | ETH2x | `0xc884646e6c88d9b172a23051b38b0732cc3e35` | WETH |
| 1x Inverse ETH | iETH1x | `0xcf4ac08635c12226659c7e10b1c1ad3d1bdc3c` | WETH |
| 2x Inverse ETH | iETH2x | `0xe18f4002fb4855022332cfab2393a22649bb86` | WETH |
| 3x Leveraged BTC | BTC3x | `0x1f4609133b6dacc88f2fa85c2d266355546856` | WBTC |
| 2x Leveraged BTC | BTC2x | `0x186f3d8bb80dff50750babc5a4bcc33134c39c` | WBTC |
| 1x Inverse BTC | iBTC1x | `0x563c4f95d1d4372fa64803e9b367f14a7ff28b` | WBTC |
| 2x Inverse BTC | iBTC2x | `0x3b73475ede04891ae8262680d66a4f5a66572e` | WBTC |
| 2x Leveraged SOL | uSOL2x | `0x0a0fbd86d2deb53d7c65fecf8622c2fa0dcdc9` | uSOL |
| 3x Leveraged SOL | uSOL3x | `0x16c469f88979e19a53ea522f0c77afad9a0435` | uSOL |
| 2x Leveraged SUI | uSUI2x | `0x2f67e4be7fbf53db88881324aac99e9d85208d` | uSUI |
| 3x Leveraged SUI | uSUI3x | `0x8d08ce52e217ad61deb96dfdcf416b901ca2dc` | uSUI |
| 2x Leveraged XRP | uXRP2x | `0x32bb8ff692a2f14c05fe7a5ae78271741bd392` | uXRP |
| 3x Leveraged XRP | uXRP3x | `0x5c600527d2835f3021734504e53181e54fa48f` | uXRP |

#### Other Products

| Product | Symbol | Address |
|---------|--------|---------|
| hyETH (bridged) | hyETH | `0xc73e76aa9f14c1837cdb49bd028e8ff5a0a71d` |
| wstETH 1.5x | wstETH15x | `0xc8df827157adaf693fcb0c6f305610c28de739` |

---

## Chain-Specific Table Prefixes

| Chain | Transaction Table | ERC20 Transfer Table | Prices |
|-------|-------------------|---------------------|--------|
| Ethereum | `ethereum.transactions` | `erc20_ethereum.evt_Transfer` | `prices.usd` (blockchain='ethereum') |
| Arbitrum | `arbitrum.transactions` | `erc20_arbitrum.evt_Transfer` | `prices.usd` (blockchain='arbitrum') |
| Base | `base.transactions` | `erc20_base.evt_Transfer` | `prices.usd` (blockchain='base') |

---

## Common Query Templates

### Token Holders by Chain

```sql
-- Replace chain prefix and token address as needed
WITH transfers AS (
    SELECT "to" AS address, value AS amount
    FROM erc20_ethereum.evt_Transfer
    WHERE contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c
    UNION ALL
    SELECT "from" AS address, -value AS amount
    FROM erc20_ethereum.evt_Transfer
    WHERE contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c
)
SELECT address, SUM(amount) / 1e18 AS balance
FROM transfers
GROUP BY 1
HAVING SUM(amount) > 0
ORDER BY balance DESC
LIMIT 100
```

### Daily Volume with USD Pricing

```sql
SELECT
    DATE_TRUNC('day', t.evt_block_time) AS day,
    COUNT(*) AS transfers,
    SUM(t.value / 1e18) AS volume_tokens,
    SUM(t.value / 1e18 * p.price) AS volume_usd
FROM erc20_ethereum.evt_Transfer t
LEFT JOIN prices.usd p
    ON p.contract_address = t.contract_address
    AND p.blockchain = 'ethereum'
    AND p.minute = DATE_TRUNC('minute', t.evt_block_time)
WHERE t.contract_address = 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c
    AND t.evt_block_time > NOW() - INTERVAL '30' DAY
GROUP BY 1
ORDER BY 1 DESC
```

### Whale Activity (Top Holders with Labels)

```sql
WITH balances AS (
    SELECT
        CASE WHEN direction = 'in' THEN "to" ELSE "from" END AS holder,
        SUM(CASE WHEN direction = 'in' THEN value ELSE -value END) / 1e18 AS balance
    FROM (
        SELECT "to", "from", value, 'in' AS direction
        FROM erc20_ethereum.evt_Transfer
        WHERE contract_address = {{token_address}}
        UNION ALL
        SELECT "to", "from", value, 'out' AS direction
        FROM erc20_ethereum.evt_Transfer
        WHERE contract_address = {{token_address}}
    )
    GROUP BY 1
    HAVING SUM(CASE WHEN direction = 'in' THEN value ELSE -value END) > 0
)
SELECT
    b.holder,
    b.balance,
    COALESCE(l.name, e.name, 'Unknown') AS label,
    l.label_type
FROM balances b
LEFT JOIN labels.all l ON l.address = b.holder AND l.blockchain = 'ethereum'
LEFT JOIN ens.resolver_latest e ON e.address = b.holder
WHERE b.balance > 100  -- Whale threshold
ORDER BY b.balance DESC
LIMIT 50
```

### Net Token Flows

```sql
WITH daily_flows AS (
    SELECT
        DATE_TRUNC('day', evt_block_time) AS day,
        SUM(CASE WHEN "to" = {{target_address}} THEN value / 1e18 ELSE 0 END) AS inflow,
        SUM(CASE WHEN "from" = {{target_address}} THEN value / 1e18 ELSE 0 END) AS outflow
    FROM erc20_ethereum.evt_Transfer
    WHERE contract_address = {{token_address}}
        AND ("to" = {{target_address}} OR "from" = {{target_address}})
        AND evt_block_time > NOW() - INTERVAL '{{days}}' DAY
    GROUP BY 1
)
SELECT
    day,
    inflow,
    outflow,
    inflow - outflow AS net_flow,
    SUM(inflow - outflow) OVER (ORDER BY day) AS cumulative_flow
FROM daily_flows
ORDER BY day DESC
```

---

## Lending Protocol Tables

### Morpho Blue

```sql
SELECT * FROM morpho_ethereum.morpho_blue_evt_Supply
SELECT * FROM morpho_ethereum.morpho_blue_evt_Withdraw
SELECT * FROM morpho_ethereum.morpho_blue_evt_Borrow
SELECT * FROM morpho_ethereum.morpho_blue_evt_Repay
```

### Aave V3

```sql
SELECT * FROM aave_v3_ethereum.Pool_evt_Supply
SELECT * FROM aave_v3_ethereum.Pool_evt_Withdraw
SELECT * FROM aave_v3_ethereum.Pool_evt_Borrow
SELECT * FROM aave_v3_ethereum.Pool_evt_Repay
```

### Spark Protocol

```sql
SELECT * FROM spark_v1_ethereum.Pool_evt_Supply
SELECT * FROM spark_v1_ethereum.Pool_evt_Withdraw
SELECT * FROM spark_v1_ethereum.Pool_evt_Borrow
SELECT * FROM spark_v1_ethereum.Pool_evt_Repay
```

---

## CLI Quick Reference

```bash
# Get cached results (FREE)
python3 scripts/dune_query.py 2364870

# Export to CSV
python3 scripts/dune_query.py 2364870 --format csv > products.csv

# Get as JSON
python3 scripts/dune_query.py 4771298 --format json

# Re-execute only if cache older than 8 hours
python3 scripts/dune_query.py 2364870 --max-age 8

# Force fresh execution (USES CREDITS)
python3 scripts/dune_query.py 2364870 --execute
```
