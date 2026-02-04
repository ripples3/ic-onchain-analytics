-- Query: staked-prt-share
-- Dune ID: 4153359
-- URL: https://dune.com/queries/4153359
-- Description: Staked PRT share for Index Coop wallet
-- Parameters: none
--
-- Columns: day, blockchain, symbol, prt_symbol, prt_address, wallet_balance, stakedprt_supply, index_stakedprtshare
-- Depends on: query_5140527 (tokenlist)

with

wallet_param (wallet_address) as (
    values (0xbf14566a37d96d55485bd281f5e7c547883a54c8)
)

, token_param as (
select
    blockchain
    , contract_address as address
    , symbol as prt_symbol
    , 'hyETH' as symbol
from dune.index_coop.result_multichain_indexcoop_tokenlist -- query_5140527
where symbol = 'sPrtHyETH'
)

, daily_transfers as (
select
    date_trunc('day', t.evt_block_time) as day
    , tp.blockchain
    , tp.prt_symbol
    , tp.address as prt_address
    , tp.symbol
    , sum(case
        when t."to" = wp.wallet_address then cast(t.value as decimal(38,0)) / 1e18
        when t."from" = wp.wallet_address then -cast(t.value as decimal(38,0)) / 1e18
        else 0
      end) as wallet_change
    , sum(case
        when t."from" = 0x0000000000000000000000000000000000000000 then cast(t.value as decimal(38,0)) / 1e18
        when t."to" = 0x0000000000000000000000000000000000000000 then -cast(t.value as decimal(38,0)) / 1e18
        else 0
      end) as supply_change
from erc20_ethereum.evt_Transfer t
inner join token_param tp on t.contract_address = tp.address
cross join wallet_param wp
where t."to" = wp.wallet_address
   or t."from" = wp.wallet_address
   or t."from" = 0x0000000000000000000000000000000000000000
   or t."to" = 0x0000000000000000000000000000000000000000
group by 1, 2, 3, 4, 5
)

, days as (
select timestamp as day
from utils.days
where timestamp >= (select min(day) from daily_transfers)
)

, gap_balance as (
select
    dt.day
    , dt.blockchain
    , dt.symbol
    , dt.prt_symbol
    , dt.prt_address
    , sum(dt.wallet_change) over (partition by dt.prt_symbol order by dt.day) as wallet_balance
    , sum(dt.supply_change) over (partition by dt.prt_symbol order by dt.day) as stakedprt_supply
    , sum(dt.wallet_change) over (partition by dt.prt_symbol order by dt.day)
      / nullif(sum(dt.supply_change) over (partition by dt.prt_symbol order by dt.day), 0) as index_stakedprtshare
    , lead(day, 1, now()) over (partition by dt.prt_symbol order by dt.day) as next_day
from daily_transfers dt
)

select
    d.day
    , b.blockchain
    , case
        when d.day >= timestamp '2025-01-03' then 'mhyETH'
        else b.symbol
      end as symbol
    , b.prt_symbol
    , b.prt_address
    , b.wallet_balance
    , b.stakedprt_supply
    , b.index_stakedprtshare
from days d
inner join gap_balance b
    on b.day <= d.day
    and d.day < b.next_day
