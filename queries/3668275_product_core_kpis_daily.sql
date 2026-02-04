-- Query: product-core-kpis-daily
-- Dune ID: 3668275
-- URL: https://dune.com/queries/3668275
-- Description: Daily KPIs (TVL, NSF, revenue) for all Index Coop products
-- Parameters: none
--
-- Columns: day, blockchain, symbol, price, streaming_fee, issue_fee, redeem_fee, issue_units, redeem_units, unit_flow, unit_supply, tvl, nsf, rev_streaming, rev_issue, rev_redeem, revenue
-- Depends on: query_2364999 (unit supply), query_2812068 (token prices), query_2621012 (fee structure), query_4153359 (staked PRT share), query_4479575 (mhyETH)

with

base_data as (
select
    s.day
    , s.blockchain
    , s.symbol
    , s.address
    , p.price
    , f.streaming_fee
    , f.issue_fee
    , f.redeem_fee
    , ic.index_stakedprtshare
    , coalesce(s.issue_units, 0) as issue_units
    , -coalesce(s.redeem_units, 0) as redeem_units
    , coalesce(s.unit_flow, 0) as unit_flow
    , coalesce(s.unit_supply, 0) as unit_supply
from query_2364999 s -- Unit Supply, Daily
left join dune.index_coop.result_index_coop_token_prices_daily p -- query_2812068
    on s.day = p.day
    and s.address = p.token_address
    and s.blockchain = p.blockchain
left join query_2621012 f
    on s.address = f.token_address
    and s.day = f.day
    and s.blockchain = f.blockchain
left join query_4153359 ic
    on ic.symbol = s.symbol
    and ic.day = s.day
    and ic.blockchain = s.blockchain
where s.end_date is null or s.end_date >= s.day
)

-- Get mhyETH specific data
, mhyeth_data as (
select
    day
    , contract_address as address
    , symbol
    , apy
    , tvlUsd
    , case
        when day >= timestamp '2025-04-15' then ((apy * 0.1 * tvlUsd) * 0.3) / 365
        else 0
      end as revenue -- 10% performance fee - gauntlet/index split = 70/30
from query_4479575
)

-- Combine both datasets
, unified_data as (
select
    b.day
    , b.blockchain
    , b.symbol
    , b.address
    , b.price
    , b.streaming_fee
    , b.issue_fee
    , b.redeem_fee
    , b.issue_units
    , b.redeem_units
    , b.unit_flow
    , b.unit_supply
    , b.price * b.unit_supply as tvl
    , b.price * b.unit_flow as nsf
    , b.price * b.unit_supply * b.streaming_fee / 365 as rev_streaming
    , b.price * b.issue_units * b.issue_fee as rev_issue
    , b.price * b.redeem_units * b.redeem_fee as rev_redeem
    , case
        when b.symbol = 'mhyETH' then m.revenue * b.index_stakedprtshare
        else (b.price * b.unit_supply * b.streaming_fee / 365)
             + (b.price * b.issue_units * b.issue_fee)
             + (b.price * b.redeem_units * b.redeem_fee)
      end as revenue
from base_data b
left join mhyeth_data m on b.day = m.day and b.symbol = m.symbol
)

select
    day
    , blockchain
    , symbol
    , price
    , streaming_fee
    , issue_fee
    , redeem_fee
    , issue_units
    , redeem_units
    , unit_flow
    , unit_supply
    , tvl
    , nsf
    , rev_streaming
    , rev_issue
    , rev_redeem
    , revenue
from unified_data
order by day desc, blockchain, symbol
