-- ============================================================================
-- Query: icETH Yield
-- Dune ID: 547552
-- URL: https://dune.com/queries/547552
-- Description: Calculates icETH yield metrics, APY, and parity value vs ETH/stETH
-- Parameters: none
--
-- Columns: Hour, Leverage Ratio, Aave APY, Lido stETH APY, 7d/30d/60d/90d APY,
--          Net Yield vs ETH/stETH, Parity Value ETH/USD, Net Asset Value
-- Depends on: query_2511613 (wstETH APR Updates), query_2620080 (Aave V2 wETH Hourly Borrow Rates),
--             query_1581818 (icETH Composition Hourly), query_2621012 (Fee Structure)
--
-- Optimizations applied (logic preserved):
--   1. ethereum.blocks -> utils.hours (for time series generation)
--   2. prices.usd -> prices.hour (LEGACY table)
--   3. cast('...' as timestamp) -> timestamp '...' (DuneSQL syntax)
--
-- Note: Depends on queries that may need materialized views:
--   query_2511613, query_2620080, query_1581818, query_2621012
--
-- ============================================================================

-- Define hours in the specified time range
with

hours as (
    select timestamp as hour
    from utils.hours
    where timestamp >= timestamp '2022-04-01 16:00'
)

-- wstETH Hourly APR
, lido_rates as (
    select
        hour
        , pd_apr as apr
    from (
        select
            h.hour
            , a.pd_apr
            , row_number() over (partition by h.hour order by a.pd_start desc) as rn
        from hours h
        left join query_2511613 a  -- wstETH APR Updates
            on a.pd_start <= h.hour
            and a.pd_apr is not null
    )
    where rn = 1
)

-- Calculate rates for each hour
, rates as (
    select
        a.hour
        , a.rate as eth_borrow_rate
        , l.apr as steth_yield
        , power((a.rate + 1), 0.00011415525) as aave_rate
        , 1 + (l.apr / 365 / 24) as lido_rate
    from query_2620080 as a  -- Aave V2 wETH Average Hourly Borrow Rates
    left join lido_rates l
        on a.hour = l.hour
    where a.hour >= timestamp '2022-04-01 16:00'
)

-- Calculate summary metrics
, summary as (
    select
        hour
        , aave_apy
        , lido_apy
        , lev_ratio as leverage_ratio
        , exp(sum(ln(hour_rate)) over (order by hour rows between unbounded preceding and current row)) - 1 as roi_all_time
        , power((1 + roi_all_time - lag(roi_all_time, (24 * 7)) over (order by hour)), (365.0 / 7)) - f.streaming_fee - 1 as "7d APY"
        , power((1 + roi_all_time - lag(roi_all_time, (24 * 30)) over (order by hour)), (365.0 / 30)) - f.streaming_fee - 1 as "30d APY"
        , power((1 + roi_all_time - lag(roi_all_time, (24 * 60)) over (order by hour)), (365.0 / 60)) - f.streaming_fee - 1 as "60d APY"
        , power((1 + roi_all_time - lag(roi_all_time, (24 * 90)) over (order by hour)), (365.0 / 90)) - f.streaming_fee - 1 as "90d APY"
        , parity_value
        , parity_value - 1 as "Real Return"
        , iceth_apy - (f.streaming_fee) as "Net Yield vs ETH"
        , iceth_apy - lido_apy - (f.streaming_fee) as "Net Yield vs stETH"
        , iceth_apy as "Gross Yield vs ETH"
        , iceth_apy - lido_apy as "Gross Yield vs stETH"
        , f.streaming_fee as "Streaming Fee"
    from (
        select
            i.hour
            , i.lev_ratio
            , r.aave_rate
            , r.lido_rate
            , i.lev_ratio * r.lido_rate - (i.lev_ratio - 1) * r.aave_rate as hour_rate
            , exp(sum(ln((i.lev_ratio * r.lido_rate - (i.lev_ratio - 1) * r.aave_rate))) over (order by i.hour)) - 1 as roi_all_time
            , power(r.aave_rate, (365 * 24)) - 1 as aave_apy
            , power(r.lido_rate, (365 * 24)) - 1 as lido_apy
            , power((i.lev_ratio * r.lido_rate - (i.lev_ratio - 1) * r.aave_rate), (365 * 24)) - 1 as iceth_apy
            , parity_value
        from query_1581818 as i  -- icETH Composition Hourly
        left join rates as r
            on i.hour = r.hour
    ) as t1
    left join query_2621012 as f  -- Fee Structure
        on date_trunc('day', t1.hour) = f.day
    where f.token_address = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84  -- icETH Token Address
)

-- Calculate APY and other metrics
, apy_table as (
    select
        s.hour as "Hour"
        , s.leverage_ratio as "Leverage Ratio"
        , s.aave_apy as "Aave APY"
        , s.lido_apy as "Lido stETH APY"
        , (avg("Net Yield vs stETH") over (order by hour rows between 24 * 30 preceding and current row)) as "30d Net Yield vs stETH"
        , (avg("Net Yield vs ETH") over (order by hour rows between 24 * 30 preceding and current row)) / s.lido_apy as "30d Net Yield vs stETH Ratio"
        , s.roi_all_time as "Theoretical Return"
        , "7d APY"
        , "30d APY"
        , "60d APY"
        , "90d APY"
        , "Net Yield vs ETH"
        , "Net Yield vs stETH"
        , "Gross Yield vs ETH"
        , "Gross Yield vs stETH"
        , "Real Return"
        , "Streaming Fee"
        , case when s.hour <= timestamp '2022-09-16' then null else "Net Yield vs ETH" end as "Post-Merge APY"
        , round("Net Yield vs ETH" * 100, 2) as net_yield_eth_txt
        , round(s.aave_apy * 100, 2) as aave_apy_txt
        , round(s.lido_apy * 100, 2) as lido_apy_txt
        , round("Streaming Fee" * 100, 2) as streaming_fee_txt
        , parity_value as "Parity Value ETH"
        , parity_value * p.price as "Parity Value USD"
        , parity_value * p1.price as "Net Asset Value"
    from summary as s
    left join prices.hour as p
        on p.timestamp = s.hour
        and p.contract_address = 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2  -- WETH
    left join prices.hour as p1
        on p1.timestamp = s.hour
        and p1.contract_address = 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84  -- stETH
    where p.blockchain = 'ethereum'
    and p1.blockchain = 'ethereum'
)

select *
from apy_table
order by "Hour" desc
