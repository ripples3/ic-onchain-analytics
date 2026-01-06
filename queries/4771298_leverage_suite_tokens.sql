-- Query: Index Coop - Leverage Suite Tokens
-- Dune ID: 4771298
-- URL: https://dune.com/queries/4771298
-- Description: Leverage tokens mapped to their underlying base asset
-- Parameters: none
--
-- Columns: base, blockchain, product_symbol, token_address

with 

-- do not add non-leverage suite tokens.
-- this is used only to make token updates on leverage suite queries easier.
lev_suite (blockchain, base, product_symbol, token_address) as (
    values
    
    ('ethereum', 'WBTC', 'BTC2X',          0xD2AC55cA3Bbd2Dd1e9936eC640dCb4b745fDe759 ),    
    ('ethereum', 'WBTC', 'BTC3x',          0xc7068657FD7eC85Ea8Db928Af980Fc088aff6De5 ),   
    ('ethereum', 'WETH', 'ETH2X',          0x65c4C0517025Ec0843C9146aF266A2C5a2D148A2 ), 
    ('ethereum', 'WETH', 'ETH3x',          0x23C3e5B3d001e17054603269EDFC703603AdeFd8 ),    
    ('ethereum', 'XAUt', 'GOLD3x',         0x1d86FBAd389068E19fa665Eba12A0Ebd4c68BB08 ),     
    
    ('arbitrum', 'WBTC', 'BTC3x',          0x3bDd0d5c0C795b2Bf076F5C8F177c58e42beC0E6 ),
    ('arbitrum', 'WBTC', 'BTC2x',          0xeb5bE62e6770137beaA0cC712741165C594F59D7 ), 
    ('arbitrum', 'WETH', 'iBTC1x',         0x80e58AEA88BCCaAE19bCa7f0e420C1387Cc087fC ),
    ('arbitrum', 'WETH', 'ETH3x',          0xA0A17b2a015c14BE846C5d309D076379cCDfa543 ),
    ('arbitrum', 'WETH', 'ETH2x',          0x26d7D3728C6bb762a5043a1d0CeF660988Bca43C ),
    ('arbitrum', 'WETH', 'iETH1x',         0x749654601a286833aD30357246400D2933b1C89b ),
    ('arbitrum', 'WETH', 'ETH2xBTC',       0xe7b1ce8dfee3d7417397cd4f56dbfc0d49e43ed1 ), 
    ('arbitrum', 'WBTC', 'BTC2xETH',       0x77f69104145f94a81cec55747c7a0fc9cb7712c3 ),  
    ('arbitrum', 'LINK', 'LINK2x',         0xaF0408C1Cc4b41cf878143423015937032878913 ), 
    ('arbitrum', 'AAVE', 'AAVE2x',         0x9ba1d6C651624977435bc6E2c98D4c7407112e15 ), 
    ('arbitrum', 'ARB',  'ARB2x',          0xFc01f273126B3d515e6ce6CaB9e53d5C6990D6CB ),
    ('arbitrum', 'WETH', 'iETH2x',         0x6a21af139B440f0944f9e03375544bB3E4E2135f ),
    ('arbitrum', 'WBTC', 'iBTC2x',         0x304F3eB3b77C025664a7b13c3f0eE2f97F9743fD ),

    ('base',     'WBTC', 'BTC2x',          0x186F3d8BB80DFF50750bABc5A4bcC33134c39cDe ),  
    ('base',     'WBTC', 'BTC3x',          0x1F4609133b6dAcc88f2fa85c2d26635554685699 ),  
    ('base',     'WETH', 'ETH2x',          0xC884646E6C88d9b172a23051b38B0732Cc3E35a6 ),
    ('base',     'WETH', 'ETH3x',          0x329f6656792c7d34D0fBB9762FA9A8F852272acb ),  
    ('base',     'uSOL', 'uSOL2x',         0x0A0Fbd86d2dEB53D7C65fecF8622c2Fa0DCdc9c6 ),
    ('base',     'uSOL', 'uSOL3x',         0x16c469F88979e19A53ea522f0c77aFAD9A043571 ),
    ('base',     'uSUI', 'uSUI2x',         0x2F67e4bE7fBF53dB88881324AAc99e9D85208d40 ),
    ('base',     'uSUI', 'uSUI3x',         0x8D08CE52e217aD61deb96dFDcf416B901cA2dC22 ),
    ('base',     'uXRP', 'uXRP2x',         0x32BB8FF692A2F14C05Fe7a5ae78271741bD392fC ),
    ('base',     'uXRP', 'uXRP3x',         0x5c600527D2835F3021734504E53181E54fA48f73 ),
    ('base',     'WETH', 'iETH1x',         0xCF4AC08635c12226659c7E10B1C1ad3d1bDc3C58 ),
    ('base',     'WBTC', 'iBTC1x',         0xe18f4002fB4855022332Cfab2393a22649bb86B9 ),
    ('base',     'WETH', 'iETH2x',         0x563c4f95D1D4372fA64803E9B367f14a7Ff28b1a ),
    ('base',     'WBTC', 'iBTC2x',         0x3b73475EDE04891AE8262680D66A4f5A66572EB0 )
)


select * from lev_suite

