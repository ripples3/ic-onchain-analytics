-- Query: multichain-components-with-hardcoded-values
-- Dune ID: 5140966
-- URL: https://dune.com/queries/5140966
-- Materialized View: dune.index_coop.result_multichain_components_with_hardcoded_values
-- Description: Component tokens with base_symbol for price lookups. Replaces query_3018988.
-- Parameters: none
--
-- Columns: contract_address, blockchain, symbol, base_symbol, decimals, price_address

with

all_components (contract_address, blockchain, symbol, base_symbol, decimals, price_address) as (
    values
    -- ========================================================================
    -- ic21 components
    -- ========================================================================
    --contract_address                             blockchain   symbol                  base_symbol  dec  price_address
    (0x1B5E16C5b20Fb5EE87C61fE9Afe735Cca3B21A65, 'ethereum', 'ic21',                 'ic21',      18, 0x1B5E16C5b20Fb5EE87C61fE9Afe735Cca3B21A65),
    (0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2, 'ethereum', 'WETH',                 'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0, 'ethereum', 'MATIC',                'MATIC',     18, 0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0),
    (0x3f67093dfFD4F0aF4f2918703C92B60ACB7AD78b, 'ethereum', '21BTC',                '21BTC',      8, 0x3f67093dfFD4F0aF4f2918703C92B60ACB7AD78b),
    (0xFf4927e04c6a01868284F5C3fB9cba7F7ca4aeC0, 'ethereum', '21BCH',                '21BCH',      8, 0xFf4927e04c6a01868284F5C3fB9cba7F7ca4aeC0),
    (0x1bE9d03BfC211D83CFf3ABDb94A75F9Db46e1334, 'ethereum', '21BNB',                '21BNB',      8, 0x1bE9d03BfC211D83CFf3ABDb94A75F9Db46e1334),
    (0x9c05d54645306d4C4EAd6f75846000E1554c0360, 'ethereum', '21ADA',                '21ADA',      6, 0x9c05d54645306d4C4EAd6f75846000E1554c0360),
    (0x9F2825333aa7bC2C98c061924871B6C016e385F3, 'ethereum', '21LTC',                '21LTC',      8, 0x9F2825333aa7bC2C98c061924871B6C016e385F3),
    (0xF4ACCD20bFED4dFFe06d4C85A7f9924b1d5dA819, 'ethereum', '21DOT',                '21DOT',     10, 0xF4ACCD20bFED4dFFe06d4C85A7f9924b1d5dA819),
    (0xb80a1d87654BEf7aD8eB6BBDa3d2309E31D4e598, 'ethereum', '21SOL',                '21SOL',      9, 0xb80a1d87654BEf7aD8eB6BBDa3d2309E31D4e598),
    (0x0d3bd40758dF4F79aaD316707FcB809CD4815Ffe, 'ethereum', '21XRP',                '21XRP',      6, 0x0d3bd40758dF4F79aaD316707FcB809CD4815Ffe),
    (0x399508A43d7E2b4451cd344633108b4d84b33B03, 'ethereum', '21AVAX',               '21AVAX',    18, 0x399508A43d7E2b4451cd344633108b4d84b33B03),
    (0x514910771AF9Ca656af840dff83E8264EcF986CA, 'ethereum', 'LINK',                 'LINK',      18, 0x514910771AF9Ca656af840dff83E8264EcF986CA),

    -- ========================================================================
    -- icSMMT components
    -- ========================================================================
    (0xc30FBa978743a43E736fc32FBeEd364b8A2039cD, 'ethereum', 'icSMMT',               'icSMMT',    18, 0xc30FBa978743a43E736fc32FBeEd364b8A2039cD),
    (0xA5269A8e31B93Ff27B887B56720A25F844db0529, 'ethereum', 'maUSDC',               'USDC',      18, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),
    (0x36F8d0D0573ae92326827C4a82Fe4CE4C244cAb6, 'ethereum', 'maDAI',                'DAI',       18, 0x6B175474E89094C44Da98b954EedeAC495271d0F),
    (0xAFe7131a57E44f832cb2dE78ade38CaD644aaC2f, 'ethereum', 'maUSDT',               'USDT',      18, 0xdAC17F958D2ee523a2206206994597C13D831ec7),
    (0xC2A4fBA93d4120d304c94E4fd986e0f9D213eD8A, 'ethereum', 'mcUSDT',               'USDT',      18, 0xdAC17F958D2ee523a2206206994597C13D831ec7),
    (0x278039398A5eb29b6c2FB43789a38A84C6085266, 'ethereum', 'wfDAI:1695168000',     'DAI',        8, 0x6B175474E89094C44Da98b954EedeAC495271d0F),
    (0xe09B1968851478f20a43959d8a212051367dF01A, 'ethereum', 'wfUSDC:1695168000',    'USDC',       8, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),

    -- ========================================================================
    -- icETH components
    -- ========================================================================
    (0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84, 'ethereum', 'icETH',                'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0xF63B34710400CAd3e044cFfDcAb00a0f32E33eCf, 'ethereum', 'variableDebtWETH',     'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x1982b2F5814301d4e9a8b0201555376e62F82428, 'ethereum', 'aSTETH',               'stETH',     18, 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84),

    -- ========================================================================
    -- icRETH components
    -- ========================================================================
    (0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5, 'ethereum', 'icRETH',               'rETH',      18, 0xae78736Cd615f374D3085123A210448E74Fc6393),
    (0xCc9EE9483f662091a1de4795249E24aC0aC2630f, 'ethereum', 'aEthrETH',             'rETH',      18, 0xae78736Cd615f374D3085123A210448E74Fc6393),
    (0xeA51d7853EEFb32b6ee06b1C12E6dcCA88Be0fFE, 'ethereum', 'variableDebtEthWETH',  'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),

    -- ========================================================================
    -- cdETI components
    -- ========================================================================
    (0x55b2CFcfe99110C773f00b023560DD9ef6C8A13B, 'ethereum', 'cdETI',                'cdETI',     18, 0x55b2CFcfe99110C773f00b023560DD9ef6C8A13B),
    (0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48, 'ethereum', 'USDC',                 'USDC',       6, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),

    -- ========================================================================
    -- dsETH components
    -- ========================================================================
    (0xf1c9acdc66974dfb6decb12aa385b9cd01190e38, 'ethereum', 'osETH',                'osETH',     18, 0xf1c9acdc66974dfb6decb12aa385b9cd01190e38),

    -- ========================================================================
    -- Ethereum Leverage Suite (ETH2X, BTC2X, ETH3X, BTC3X, GOLD3X)
    -- ========================================================================
    (0x65c4C0517025Ec0843C9146aF266A2C5a2D148A2, 'ethereum', 'ETH2X',                'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0xD2AC55cA3Bbd2Dd1e9936eC640dCb4b745fDe759, 'ethereum', 'BTC2X',                'WBTC',      18, 0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599),
    (0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8, 'ethereum', 'aEthWETH',             'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x5Ee5bf7ae06D1Be5997A1A72006FE6C607eC6DE8, 'ethereum', 'aEthWBTC',             'WBTC',       8, 0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599),
    (0x72E95b8931767C79bA4EeE721354d6E99a61D004, 'ethereum', 'variableDebtEthUSDC',  'USDC',       6, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),
    (0x8A2b6f94Ff3A89a03E8c02Ee92b55aF90c9454A2, 'ethereum', 'aEthXAUt',             'XAUt',       6, 0x68749665FF8D2d112Fa859AA293F07A622782F38),

    -- ========================================================================
    -- Arbitrum Leverage Suite
    -- ========================================================================
    (0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8, 'arbitrum', 'aArbWETH',             'WETH',      18, 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1),
    (0x078f358208685046a11C85e8ad32895DED33A249, 'arbitrum', 'aArbWBTC',             'WBTC',       8, 0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f),
    (0x191c10Aa4AF7C30e871E70C95dB0E4eb77237530, 'arbitrum', 'aArbLINK',             'LINK',      18, 0xf97f4df75117a78c1A5a0DBb814Af92458539FB4),
    (0xf329e36C7bF6E5E86ce2150875a84Ce77f477375, 'arbitrum', 'aArbAAVE',             'AAVE',      18, 0xba5DdD1f9d7F570dc94a51479a000E3BCE967196),
    (0x6533afac2E7BCCB20dca161449A13A32D391fb00, 'arbitrum', 'aArbARB',              'ARB',       18, 0x912CE59144191C1204E64559FE8253a0e49E6548),
    (0x724dc807b04555b71ed48a6896b6F41593b8C637, 'arbitrum', 'aArbUSDCn',            'USDC',       6, 0xaf88d065e77c8cC2239327C5EDb3A432268e5831),
    (0xFCCf3cAbbe80101232d343252614b6A3eE81C989, 'arbitrum', 'variableDebtArbUSDCn', 'USDC',       6, 0xaf88d065e77c8cC2239327C5EDb3A432268e5831),
    (0x0c84331e39d6658Cd6e6b9ba04736cC4c4734351, 'arbitrum', 'variableDebtArbWETH',  'WETH',      18, 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1),
    (0xaf88d065e77c8cc2239327c5edb3a432268e5831, 'arbitrum', 'USDC',                 'USDC',       6, 0xaf88d065e77c8cc2239327c5edb3a432268e5831),
    (0x82aF49447D8a07e3bd95BD0d56f35241523fBab1, 'arbitrum', 'WETH',                 'WETH',      18, 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1),
    (0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f, 'arbitrum', 'WBTC',                 'WBTC',       8, 0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f),

    -- ========================================================================
    -- Base Leverage Suite
    -- ========================================================================
    (0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7, 'base',     'aBasWETH',             'WETH',      18, 0x4200000000000000000000000000000000000006),
    (0xbdb9300b7cde636d9cd4aff00f6f009ffbbc8ee6, 'base',     'aBascbBTC',            'cbBTC',      8, 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf),
    (0x4e65fe4dba92790696d040ac24aa414708f5c0ab, 'base',     'aBasUSDC',             'USDC',       6, 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913),
    (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, 'base',     'USDC',                 'USDC',       6, 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913),
    (0x4200000000000000000000000000000000000006, 'base',     'WETH',                 'WETH',      18, 0x4200000000000000000000000000000000000006),
    (0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf, 'base',     'cbBTC',                'cbBTC',      8, 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf),

    -- ========================================================================
    -- Base Wrapped Alt Tokens (Universal tokens - prices available directly on Base)
    -- uSOL, uSUI, uXRP have direct prices in prices.hour on Base chain
    -- ========================================================================
    (0x9b8df6e244526ab5f6e6400d331db28c8fdddb55, 'base',     'uSOL',                 'SOL',       18, 0x9b8df6e244526ab5f6e6400d331db28c8fdddb55),
    (0xb0505e5a99abd03d94a1169e638b78edfed26ea4, 'base',     'uSUI',                 'SUI',       18, 0xb0505e5a99abd03d94a1169e638b78edfed26ea4),
    (0x2615a94df961278DcbC41Fb0a54fEc5f10a693aE, 'base',     'uXRP',                 'XRP',       18, 0x2615a94df961278DcbC41Fb0a54fEc5f10a693aE),

    -- ========================================================================
    -- hyETH components
    -- ========================================================================
    (0xc4506022Fb8090774E8A628d5084EED61D9B99Ee, 'ethereum', 'hyETH',                'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0, 'ethereum', 'wstETH',               'wstETH',    18, 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0),
    (0x1c085195437738d73d75dc64bc5a3e098b7f93b1, 'ethereum', 'PT-weETH-26SEP2024',   'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x6ee2b5E19ECBa773a352E5B21415Dc419A700d1d, 'ethereum', 'PT-weETH-26DEC2024',   'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0xf7906f274c174a52d444175729e3fa98f9bde285, 'ethereum', 'PT-ezETH-26DEC2024',   'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x7aa68E84bCD8d1B4C9e10B1e565DB993f68a3E09, 'ethereum', 'PT-agETH-26DEC2024',   'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78, 'ethereum', 'iETHv2',               'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x28F77208728B0A45cAb24c4868334581Fe86F95B, 'ethereum', 'ACX-WETH-LP',          'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0, 'ethereum', 'Re7WETH',              'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0xc554929a61d862F2741077F8aafa147479c0b308, 'ethereum', 'mhyETH-old',           'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
    (0x701907283a57FF77E255C3f1aAD790466B8CE4ef, 'ethereum', 'mhyETH',               'WETH',      18, 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2)
)

-- Pre-compute component addresses for faster filtering against tokens.erc20
, component_addresses as (
    select distinct contract_address, blockchain
    from all_components
)

-- Hardcoded components with base_symbol and price_address mappings
select
    contract_address
    , blockchain
    , symbol
    , base_symbol
    , decimals
    , price_address
from all_components

union all

-- Fallback: tokens not in hardcoded list use contract_address as price_address
-- Uses left join + is null (faster than not exists on large tables)
select
    e.contract_address
    , e.blockchain
    , e.symbol
    , e.symbol as base_symbol
    , e.decimals
    , e.contract_address as price_address
from tokens.erc20 e
left join component_addresses c
    on e.contract_address = c.contract_address
    and e.blockchain = c.blockchain
where e.blockchain in ('ethereum', 'arbitrum', 'base')
and c.contract_address is null
