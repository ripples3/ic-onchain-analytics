-- Query: Index Coop - Tokens
-- Dune ID: 2364870
-- URL: https://dune.com/queries/2364870
-- Description: All Index Coop tokens across chains
-- Parameters: none
--
-- Columns: address, blockchain, category, composite, end_date, is_bridged, leverage, product_segment, symbol

with

token(blockchain, address, symbol, product_segment, composite, leverage, category, end_date, is_bridged) as (
--category setprotocol_v2,  indexprotocol
VALUES
-- ethereum
('ethereum', 0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b, 'DPI',        'strategies',   TRUE,    FALSE,    'setprotocol_v2',   null,         FALSE),
('ethereum', 0x72e364f2abdc788b7e918bc238b21f109cd634d7, 'MVI',        'strategies',   TRUE,    FALSE,    'setprotocol_v2',   null,         FALSE),
('ethereum', 0x2af1df3ab0ab157e1e2ad8f88a7d04fbea0c7dc6, 'BED',        'strategies',   TRUE,    FALSE,    'setprotocol_v2',   null,         FALSE),
('ethereum', 0x33d63ba1e57e54779f7ddaeaa7109349344cf5f1, 'DATA',       'strategies',   TRUE,    FALSE,    'setprotocol_v2',   '2022-10-27', FALSE),
('ethereum', 0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd, 'ETH2x-FLI',  'leverage',     FALSE,   TRUE,     'setprotocol_v2',   '2024-03-11', FALSE),
('ethereum', 0x0b498ff89709d3838a063f1dfa463091f9801c2b, 'BTC2x-FLI',  'leverage',     FALSE,   TRUE,     'setprotocol_v2',   '2024-03-11', FALSE),
('ethereum', 0x47110d43175f7f2c2425e7d15792acc5817eb44f, 'GMI',         'strategies',  TRUE,    FALSE,    'setprotocol_v2',   '2022-10-27', FALSE),
('ethereum', 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84, 'icETH',       'earn',        FALSE,   TRUE,     'setprotocol_v2',   null,         FALSE),
('ethereum', 0x02e7ac540409d32c90bfb51114003a9e1ff0249c, 'JPG',         'strategies',  FALSE,   FALSE,    'setprotocol_v2',   '2022-10-31', FALSE),
('ethereum', 0x341c05c0E9b33C0E38d64de76516b2Ce970bB3BE, 'dsETH',       'earn',        FALSE,   FALSE,    'indexprotocol',    null,         FALSE),
('ethereum', 0x36c833Eed0D376f75D1ff9dFDeE260191336065e, 'gtcETH',      'earn',        FALSE,   FALSE,    'indexprotocol',    null,         FALSE), 
--('ethereum',  0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5, 'icRETH',        FALSE,   TRUE,     'indexprotocol',   null      , FALSE),
('ethereum', 0xc30FBa978743a43E736fc32FBeEd364b8A2039cD, 'icSMMT',     'earn',         FALSE,   FALSE,    'indexprotocol',    '2023-12-20', FALSE), 
('ethereum', 0x1B5E16C5b20Fb5EE87C61fE9Afe735Cca3B21A65, 'ic21',       'strategies',   TRUE,    FALSE,    'indexprotocol',     null,        FALSE),
('ethereum', 0x55b2CFcfe99110C773f00b023560DD9ef6C8A13B, 'cdETI',      'strategies',   TRUE,    FALSE,    'indexprotocol',     null,        FALSE),
('ethereum', 0xD2AC55cA3Bbd2Dd1e9936eC640dCb4b745fDe759, 'BTC2X',      'leverage',     FALSE,    TRUE,    'indexprotocol',     null,        FALSE),
('ethereum', 0x65c4C0517025Ec0843C9146aF266A2C5a2D148A2, 'ETH2X',      'leverage',     FALSE,    TRUE,    'indexprotocol',     null,        FALSE), 
('ethereum', 0xc4506022Fb8090774E8A628d5084EED61D9B99Ee, 'hyETH',      'earn',         FALSE,    FALSE,   'indexprotocol',    '2025-01-07', FALSE), 
('ethereum', 0xBe03026716a4D5E0992F22A3e6494b4F2809a9C6, 'sPrtHyETH',  'prt',          FALSE,    FALSE,   'indexprotocol',     null,        FALSE), 
('ethereum', 0x99F6539Df9840592a862ab916dDc3258a1D7a773, 'prtHyETH',   'prt',          FALSE,    FALSE,   'indexprotocol',     null,        FALSE), 
('ethereum', 0x701907283a57FF77E255C3f1aAD790466B8CE4ef, 'mhyETH',     'earn',         FALSE,    FALSE,    'morpho',           null,        FALSE),
('ethereum', 0x23C3e5B3d001e17054603269EDFC703603AdeFd8, 'ETH3X',      'leverage',     FALSE,    TRUE,    'indexprotocol',     null,        FALSE),
('ethereum', 0xc7068657FD7eC85Ea8Db928Af980Fc088aff6De5, 'BTC3X',      'leverage',     FALSE,    TRUE,    'indexprotocol',     null,        FALSE),
('ethereum', 0x1d86FBAd389068E19fa665Eba12A0Ebd4c68BB08, 'GOLD3X',      'leverage',     FALSE,    TRUE,    'indexprotocol',     null,        FALSE),
  


-- arbitrum
('arbitrum', 0xA0A17b2a015c14BE846C5d309D076379cCDfa543, 'ETH3x-ARB',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE), 
('arbitrum', 0x26d7D3728C6bb762a5043a1d0CeF660988Bca43C, 'ETH2x-ARB',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0x749654601a286833aD30357246400D2933b1C89b, 'iETH1x-ARB',   'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE), 
('arbitrum', 0x3bDd0d5c0C795b2Bf076F5C8F177c58e42beC0E6, 'BTC3x-ARB',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0xeb5bE62e6770137beaA0cC712741165C594F59D7, 'BTC2x-ARB',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE), 
('arbitrum', 0x80e58AEA88BCCaAE19bCa7f0e420C1387Cc087fC, 'iBTC1x-ARB',   'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0xE7b1Ce8DfEE3D7417397cd4f56dBFc0d49E43Ed1, 'ETH2XBTC-ARB', 'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0x77F69104145f94a81cEC55747C7a0Fc9CB7712C3, 'BTC2XETH-ARB', 'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0x9737C658272e66Faad39D7AD337789Ee6D54F500, 'DPI',          'strategies', TRUE,     FALSE,    null,                 null,        TRUE),
('arbitrum', 0x0104a6FA30540DC1d9F45D2797F05eEa79304525, 'MVI',          'strategies', TRUE,     FALSE,    null,                 null,        TRUE),
('arbitrum', 0x8b5D1d8B3466eC21f8eE33cE63F319642c026142, 'hyETH',        'earn',       FALSE,    FALSE,    null,                 null,        TRUE),
('arbitrum', 0xaF0408C1Cc4b41cf878143423015937032878913, 'LINK2x',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0x9ba1d6C651624977435bc6E2c98D4c7407112e15, 'AAVE2x',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0xFc01f273126B3d515e6ce6CaB9e53d5C6990D6CB, 'ARB2x',    'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE),
('arbitrum', 0x6a21af139B440f0944f9e03375544bB3E4E2135f, 'iETH2x-ARB',   'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE), 
('arbitrum', 0x304F3eB3b77C025664a7b13c3f0eE2f97F9743fD, 'iBTC2x-ARB',   'leverage',   FALSE,    TRUE,    'indexprotocol_arb',   null,        FALSE), 

-- base
('base',     0x329f6656792c7d34D0fBB9762FA9A8F852272acb, 'ETH3x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE), 
('base',     0xC884646E6C88d9b172a23051b38B0732Cc3E35a6, 'ETH2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
('base',     0x1F4609133b6dAcc88f2fa85c2d26635554685699, 'BTC3x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
('base',     0x186F3d8BB80DFF50750bABc5A4bcC33134c39cDe, 'BTC2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
--('base',     0xF06A59348712a11e7823Ad8BFc45c59f7EAFCc60, 'icUSD-BASE',     FALSE,    FALSE,   'indexprotocol_base', null,        FALSE),
('base',     0xC73e76Aa9F14C1837CDB49bd028E8Ff5a0a71dAD, 'hyETH',        'earn',       FALSE,    FALSE,    null,                 null,       TRUE),
('base',     0x0A0Fbd86d2dEB53D7C65fecF8622c2Fa0DCdc9c6, 'uSOL2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0x16c469F88979e19A53ea522f0c77aFAD9A043571, 'uSOL3x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0x2F67e4bE7fBF53dB88881324AAc99e9D85208d40, 'uSUI2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0x8D08CE52e217aD61deb96dFDcf416B901cA2dC22, 'uSUI3x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0xc8DF827157AdAf693FCb0c6f305610C28De739FD, 'wstETH15x',      'earn',      FALSE,    FALSE,   null,                 null,       FALSE),
('base',     0x32BB8FF692A2F14C05Fe7a5ae78271741bD392fC, 'uXRP2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0x5c600527d2835f3021734504e53181e54fa48f73, 'uXRP3x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base', null,       FALSE),
('base',     0xCF4AC08635c12226659c7E10B1C1ad3d1bDc3C58, 'iETH1x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
('base',     0xe18f4002fB4855022332Cfab2393a22649bb86B9, 'iBTC1x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
('base',     0x563c4f95D1D4372fA64803E9B367f14a7Ff28b1a, 'iETH2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE),
('base',     0x3b73475EDE04891AE8262680D66A4f5A66572EB0, 'iBTC2x-BASE',   'leverage',   FALSE,    TRUE,    'indexprotocol_base',  null,       FALSE)
)

select
blockchain, address, symbol, product_segment, composite, leverage, category, cast(end_date as date) as end_date, is_bridged
from token

