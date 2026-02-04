-- Query: token-prices-daily
-- Dune ID: 2812068
-- URL: https://dune.com/queries/2812068
-- Description: Daily NAV/price for all Index Coop tokens from multiple sources
-- Parameters: none
--
-- Columns: day, blockchain, token_address, symbol, price

with

-- Main NAV source (excludes leverage tokens and tokens with dedicated sources)
nav_hourly as (
select
    date_trunc('day', n.hour) as day
    , n.blockchain
    , n.token_address
    , n.token_symbol as symbol
    , avg(n.nav) as price
from dune.index_coop.result_multichain_all_active_tokens_nav_hourly n
inner join dune.index_coop.result_multichain_indexcoop_tokenlist t -- query_5140527
    on t.contract_address = n.token_address
    and t.blockchain = n.blockchain
where t.leverage = false  -- exclude all leverage tokens
and n.token_address not in (
    0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5  -- icRETH (low volume)
    , 0xc30fba978743a43e736fc32fbeed364b8a2039cd  -- icSMMT (no volume)
    , 0xc4506022fb8090774e8a628d5084eed61d9b99ee  -- hyETH (dedicated source)
    , 0x7c07f7abe10ce8e33dc6c5ad68fe033085256a84  -- icETH (query_4891960)
)
group by 1, 2, 3, 4
)

-- icSMMT price
, icsmmmt_nav as (
select
    date_trunc('day', minute) as day
    , 'ethereum' as blockchain
    , 0xc30FBa978743a43E736fc32FBeEd364b8A2039cD as token_address
    , 'icSMMT' as symbol
    , avg(nav) as price
from query_2457409
group by 1, 2, 3, 4
)

-- icRETH price
, icreth_nav as (
select
    day
    , 'ethereum' as blockchain
    , 0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5 as token_address
    , 'icRETH' as symbol
    , nav_usd as price
from query_3006703
)

-- Leverage suite tokens (ETH2X, BTC2X, etc.)
, lev_suite_nav as (
select
    date_trunc('day', hour) as day
    , blockchain
    , contract_address as token_address
    , symbol
    , avg(price) as price
from dune.index_coop.result_allchain_lev_suite_tokens_nav_hourly
group by 1, 2, 3, 4
)

-- hyETH price
, hyeth_nav as (
select
    day
    , 'ethereum' as blockchain
    , 0xc4506022Fb8090774E8A628d5084EED61D9B99Ee as token_address
    , 'hyETH' as symbol
    , price
from dune.index_coop.result_hy_eth_tvl
)

-- mhyETH price
, mhyeth_nav as (
select
    day
    , 'ethereum' as blockchain
    , 0x701907283a57FF77E255C3f1aAD790466B8CE4ef as token_address
    , 'mhyETH' as symbol
    , mhyeth_price as price
from dune.index_coop.result_hy_eth_tvl
)

-- icETH price
, iceth_nav as (
select
    date_trunc('day', hour) as day
    , 'ethereum' as blockchain
    , contract_address as token_address
    , symbol
    , avg(price) as price
from query_4891960
group by 1, 2, 3, 4
)

select * from nav_hourly
union all
select * from icsmmmt_nav
union all
select * from icreth_nav
union all
select * from lev_suite_nav
union all
select * from hyeth_nav
union all
select * from mhyeth_nav
union all
select * from iceth_nav
