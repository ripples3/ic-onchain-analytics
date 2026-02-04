-- Query: components-with-hardcoded-values
-- Dune ID: 3018988
-- URL: https://dune.com/queries/3018988
-- Description: Component tokens with hardcoded base_symbol for price lookups
-- Parameters: none
--
-- Columns: contract_address, blockchain, symbol, base_symbol, decimals

with

ic21_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0x1B5E16C5b20Fb5EE87C61fE9Afe735Cca3B21A65, 'ethereum', 'ic21',   'ic21',  18),
    (0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2, 'ethereum', 'WETH',   'WETH',  18),
    (0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0, 'ethereum', 'MATIC',  'WETH',  18),
    (0x3f67093dfFD4F0aF4f2918703C92B60ACB7AD78b, 'ethereum', '21BTC',  '21BTC',  8),
    (0xFf4927e04c6a01868284F5C3fB9cba7F7ca4aeC0, 'ethereum', '21BCH',  '21BCH',  8),
    (0x1bE9d03BfC211D83CFf3ABDb94A75F9Db46e1334, 'ethereum', '21BNB',  '21BNB',  8),
    (0x9c05d54645306d4C4EAd6f75846000E1554c0360, 'ethereum', '21ADA',  '21ADA',  6),
    (0x9F2825333aa7bC2C98c061924871B6C016e385F3, 'ethereum', '21LTC',  '21LTC',  8),
    (0xF4ACCD20bFED4dFFe06d4C85A7f9924b1d5dA819, 'ethereum', '21DOT',  '21DOT', 10),
    (0xb80a1d87654BEf7aD8eB6BBDa3d2309E31D4e598, 'ethereum', '21SOL',  '21SOL',  9),
    (0x0d3bd40758dF4F79aaD316707FcB809CD4815Ffe, 'ethereum', '21XRP',  '21XRP',  6),
    (0x399508A43d7E2b4451cd344633108b4d84b33B03, 'ethereum', '21AVAX', '21AVAX',18),
    (0x514910771AF9Ca656af840dff83E8264EcF986CA, 'ethereum', 'LINK',   'LINK',  18)
)

, icsmmt_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0xc30FBa978743a43E736fc32FBeEd364b8A2039cD, 'ethereum', 'icSMMT',           'icSMMT', 18),
    (0xA5269A8e31B93Ff27B887B56720A25F844db0529, 'ethereum', 'maUSDC',           'USDC',   18),
    (0x36F8d0D0573ae92326827C4a82Fe4CE4C244cAb6, 'ethereum', 'maDAI',            'DAI',    18),
    (0xAFe7131a57E44f832cb2dE78ade38CaD644aaC2f, 'ethereum', 'maUSDT',           'USDT',   18),
    (0xC2A4fBA93d4120d304c94E4fd986e0f9D213eD8A, 'ethereum', 'mcUSDT',           'USDT',   18),
    (0x278039398A5eb29b6c2FB43789a38A84C6085266, 'ethereum', 'wfDAI:1695168000', 'DAI',     8),
    (0xe09B1968851478f20a43959d8a212051367dF01A, 'ethereum', 'wfUSDC:1695168000','USDC',    8)
)

, iceth_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84, 'ethereum', 'icETH',             'WETH',  18),
    (0xF63B34710400CAd3e044cFfDcAb00a0f32E33eCf, 'ethereum', 'variableDebtWETH',  'WETH',  18),
    (0x1982b2F5814301d4e9a8b0201555376e62F82428, 'ethereum', 'aSTETH',            'stETH', 18)
)

, icreth_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5, 'ethereum', 'icRETH',              'rETH', 18),
    (0xCc9EE9483f662091a1de4795249E24aC0aC2630f, 'ethereum', 'aEthrETH',            'WETH', 18),
    (0xeA51d7853EEFb32b6ee06b1C12E6dcCA88Be0fFE, 'ethereum', 'variableDebtEthWETH', 'WETH', 18)
)

, cdeti_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0x55b2CFcfe99110C773f00b023560DD9ef6C8A13B, 'ethereum', 'cdETI', 'cdETI', 18),
    (0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48, 'ethereum', 'USDC',  'USDC',   6),
    (0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2, 'ethereum', 'WETH',  'WETH',  18)
)

, dseth_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0xf1c9acdc66974dfb6decb12aa385b9cd01190e38, 'ethereum', 'osETH', 'WETH', 18)
)

, eth2x_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0x65c4C0517025Ec0843C9146aF266A2C5a2D148A2, 'ethereum', 'ETH2X',                'WETH', 18),
    (0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8, 'ethereum', 'aEthWETH',             'WETH', 18),
    (0x72E95b8931767C79bA4EeE721354d6E99a61D004, 'ethereum', 'variableDebtEthUSDC',  'USDC',  6)
)

, btc2x_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0xD2AC55cA3Bbd2Dd1e9936eC640dCb4b745fDe759, 'ethereum', 'BTC2X',               'WBTC', 18),
    (0x5Ee5bf7ae06D1Be5997A1A72006FE6C607eC6DE8, 'ethereum', 'aEthWBTC',            'WBTC',  8),
    (0x72E95b8931767C79bA4EeE721354d6E99a61D004, 'ethereum', 'variableDebtEthUSDC', 'USDC',  6)
)

, lev_suite_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    -- Ethereum
    (0x8A2b6f94Ff3A89a03E8c02Ee92b55aF90c9454A2, 'ethereum', 'aEthXAUt', 'XAUt', 6),

    -- Arbitrum - Aave aTokens
    (0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8, 'arbitrum', 'aArbWETH', 'WETH', 18),
    (0x078f358208685046a11C85e8ad32895DED33A249, 'arbitrum', 'aArbWBTC', 'WBTC',  8),
    (0x191c10Aa4AF7C30e871E70C95dB0E4eb77237530, 'arbitrum', 'aArbLINK', 'LINK', 18),
    (0xf329e36C7bF6E5E86ce2150875a84Ce77f477375, 'arbitrum', 'aArbAAVE', 'AAVE', 18),
    (0x6533afac2E7BCCB20dca161449A13A32D391fb00, 'arbitrum', 'aArbARB',  'ARB',  18),
    (0x724dc807b04555b71ed48a6896b6F41593b8C637, 'arbitrum', 'aArbUSDCn','USDC',  6),
    -- Arbitrum - Native tokens
    (0xaf88d065e77c8cc2239327c5edb3a432268e5831, 'arbitrum', 'USDC', 'USDC',  6),
    (0x82aF49447D8a07e3bd95BD0d56f35241523fBab1, 'arbitrum', 'WETH', 'WETH', 18),
    (0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f, 'arbitrum', 'WBTC', 'WBTC',  8),

    -- Base - Aave aTokens
    (0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7, 'base', 'aBasWETH',  'WETH',  18),
    (0xbdb9300b7cde636d9cd4aff00f6f009ffbbc8ee6, 'base', 'aBascbBTC', 'cbBTC',  8),
    (0x4e65fe4dba92790696d040ac24aa414708f5c0ab, 'base', 'aBasUSDC',  'USDC',   6),  -- FIX: was missing correct base_symbol
    -- Base - Native tokens
    (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, 'base', 'USDC', 'USDC',  6),
    (0x4200000000000000000000000000000000000006, 'base', 'WETH', 'WETH', 18)
)

, hyeth_components (contract_address, blockchain, symbol, base_symbol, decimals) as (
    values
    (0xc4506022Fb8090774E8A628d5084EED61D9B99Ee, 'ethereum', 'hyETH',              'WETH', 18),
    (0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0, 'ethereum', 'wstETH',             'WETH', 18),
    (0x1c085195437738d73d75dc64bc5a3e098b7f93b1, 'ethereum', 'PT-weETH-26SEP2024', 'WETH', 18),
    (0x6ee2b5E19ECBa773a352E5B21415Dc419A700d1d, 'ethereum', 'PT-weETH-26DEC2024', 'WETH', 18),
    (0xf7906f274c174a52d444175729e3fa98f9bde285, 'ethereum', 'PT-ezETH-26DEC2024', 'WETH', 18),
    (0x7aa68E84bCD8d1B4C9e10B1e565DB993f68a3E09, 'ethereum', 'PT-agETH-26DEC2024', 'WETH', 18),
    (0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78, 'ethereum', 'iETHv2',             'WETH', 18),
    (0x28F77208728B0A45cAb24c4868334581Fe86F95B, 'ethereum', 'ACX-WETH-LP',        'WETH', 18),
    (0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0, 'ethereum', 'Re7WETH',            'WETH', 18),
    (0xc554929a61d862F2741077F8aafa147479c0b308, 'ethereum', 'mhyETH-old',         'WETH', 18),
    (0x701907283a57FF77E255C3f1aAD790466B8CE4ef, 'ethereum', 'mhyETH',             'WETH', 18)
)

-- Combine all hardcoded components
, icproducts as (
select contract_address, blockchain, symbol, base_symbol, decimals from ic21_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from icsmmt_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from iceth_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from icreth_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from cdeti_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from dseth_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from eth2x_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from btc2x_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from lev_suite_components
union all
select contract_address, blockchain, symbol, base_symbol, decimals from hyeth_components
)

select * from icproducts

union all

-- Fallback: tokens not in hardcoded list use symbol as base_symbol
select
    e.contract_address
    , e.blockchain
    , e.symbol
    , e.symbol as base_symbol
    , e.decimals
from tokens.erc20 e
where e.blockchain in ('ethereum', 'arbitrum', 'base')
and not exists (
    select 1 from icproducts p
    where p.contract_address = e.contract_address
    and p.blockchain = e.blockchain
)
