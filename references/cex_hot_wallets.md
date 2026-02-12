# CEX Hot Wallet Addresses

Common CEX hot wallets used for funding origin tracing. When CIO clustering finds common funders, check if they're CEX hot wallets — same CEX funder often indicates same entity.

## Major Exchange Hot Wallets

### Binance
| Label | Address | Notes |
|-------|---------|-------|
| Binance 14 | `0x28c6c06298d514db089934071355e5743bf21d60` | Main hot wallet, high volume |
| Binance 15 | `0x21a31ee1afc51d94c2efccaa2092ad1028285549` | |
| Binance 16 | `0xdfd5293d8e347dfe59e90efd55b2956a1343963d` | |
| Binance 17 | `0x56eddb7aa87536c09ccc2793473599fd21a8b17f` | |
| Binance 18 | `0x9696f59e4d72e237be84ffd425dcad154bf96976` | |
| Binance 20 | `0x4976a4a02f38326660d17bf34b431dc6e2eb2327` | |

### Kraken
| Label | Address | Notes |
|-------|---------|-------|
| Kraken 4 | `0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0` | Institutional users |
| Kraken Hot 2 | `0xf30ba13e4b04ce5dc4d254ae5fa95477800f0eb0` | |

### Coinbase
| Label | Address | Notes |
|-------|---------|-------|
| Coinbase 2 | `0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912` | Institutional |
| Coinbase 4 | `0xa090e606e30bd747d4e6245a1517ebe430f0057e` | |

### Others
| Label | Address | Notes |
|-------|---------|-------|
| Poloniex 4 | `0xa910f92acdaf488fa6ef02174fb86208ad7722ba` | OG DeFi users (2016+) |
| Bitfinex Hot | `0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec` | |
| FTX 2 | `0xc098b2a3aa256d2140208c3de6543aaef5cd3a94` | Defunct - historical only |

## Known Entity Clusters

Clusters identified through CIO analysis and confirmed via multiple sources.

### Trend Research (Jack Yi / LD Capital)
- **55 wallets** in cluster
- **Funding**: Binance 14, 16, 17, 18, 20
- **Activity**: Exited $1.83B ETH position with $747M loss
- **Confirmation**: Arkham entity page, Lookonchain mentions
- **Known prefixes**: 0x85e, 0xFaf, 0xE5C

### Justin Sun / Tron Foundation
- **Known addresses**:
  - `0x176F3DAb24a159341c0509bB36B833E7fdd0a132` (Justin Sun 4)
  - `0x3ddfa8ec3052539b6c9549f12cea2c295cff5296` (Justin Sun)
- **Activity**: $646M+ ETH withdrawn from Aave

### World Liberty Financial
- **Investors**: Justin Sun ($75M+), other whales
- **Governance**: Top 9 wallets control 60% of voting power
- **Cap**: 5% voting power per wallet

## Usage

```bash
# Check if funder is a known CEX
grep -i "0x28c6c06298d514db089934071355e5743bf21d60" references/cex_hot_wallets.md
# Result: Binance 14

# Find all Binance-funded wallets in your data
grep "Binance" data/funding_chains.csv
```

## Etherscan Labels API

```bash
# Get labels for address (if available)
curl -s "https://api.etherscan.io/api?module=account&action=txlist&address=<ADDR>&page=1&offset=1&sort=asc&apikey=$ETHERSCAN_API_KEY" | jq '.result[0].from'
```

## Last Updated

2026-02-12 — Added FTX 2, confirmed Trend Research cluster
