# Lending Protocol Whales

Research conducted 2026-02-04. Addresses and positions may change.

## Known Entities

| Entity | Protocol | Debt | Collateral | Address |
|--------|----------|------|------------|---------|
| **Trend Research** (LD Capital) | Aave | ~$958M | 618K ETH | Multiple wallets |
| **BitcoinOG** (1011short) | Aave | ~$240M | 783K ETH + 30K BTC | Multiple wallets |
| **Abraxas Capital** | Aave/Spark | ~$216M | wstETH, eETH | `0xEd0C6079229E2d407672a117c22b62064f4a4312` |
| **Treehouse Finance** | Spark | ~$133M | tETH Strategy | `0x5aE0e44DE96885702bD99A6914751C952d284938` |
| **Fluid** | Spark | ~$170M | - | `0x9600...`, `0x3a0d...` |
| **Mellow Protocol** | Spark | ~$57M | - | `0x3883...` |
| **EtherFi** | Spark | ~$32M | - | `0xba7f...` |

## Unknown - Investigated

### Spark Unknowns

| Address | Debt | CEX Origin | Finding |
|---------|------|------------|---------|
| `0xcaf1943ce973c1de423fe6e9f1a255049e51666e` | $50.4M | Poloniex 4 | Possibly DeFi Saver's "biggest Spark whale" |
| `0x7f7f0e44a00a5d7c052ce925b557f07b2f24ee4b` | $31.75M | Poloniex | DSProxy owner: `0x72181c27...`, HF 1.03 |
| `0x55ea3e38fa0aa495b205fe45641a44ccc1c3df26` | $30.83M | Binance 16 | Verified Binance user, HF 1.02 |
| `0x26ad4f84cd20102c4a7fb9d14bd2661a0d66f96d` | $28.36M | Binance 14 | 800 ETH withdrawal customer |
| `0xdcbe94c3d101553ac7d40a8515aa18b9534adfcd` | $13.71M | Kraken 4 | Summer.fi Vault #1631, likely family office |

### Aave Unknowns

| Address | Debt | Collateral | Finding |
|---------|------|------------|---------|
| `0x7cd0b7ed790f626ef1bd42db63b5ebeb5970c912` | $172M | $378M (cbBTC $300M, RLUSD $30M) | Likely institutional (Coinbase Prime + TradFi stablecoins) |

## CEX Hot Wallet Labels

Used to trace funding origin.

| Label | CEX | Notes |
|-------|-----|-------|
| Binance 14 | Binance | `0x28c6c062...` |
| Binance 16 | Binance | `0xa180Fe01...` |
| Binance 20 | Binance | - |
| Kraken 4 | Kraken | `0x267be1C1...` — institutional users |
| Poloniex 4 | Poloniex | OG DeFi users (2016+) |

## Data Sources

- [Lending CRM - Spark](https://lending-crm.vercel.app/?source=spark)
- [Lending CRM - Aave](https://lending-crm.vercel.app/?source=aave)
- [Arkham Intelligence](https://intel.arkm.com/)
- [Etherscan](https://etherscan.io/)
