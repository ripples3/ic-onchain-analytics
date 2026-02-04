-- ============================================================================
-- Query: hyeth-nav-and-apy
-- Dune ID: 3808728
-- URL: https://dune.com/queries/3808728
-- Materialized View: dune.index_coop.result_hyeth_yield
-- Description: hyETH NAV and APY calculations
-- Parameters: none
--
-- Columns: day, product_symbol, initial_value, hyeth_nav_eth, apy, apy_txt, gross_yield, net_yield, hyeth_nav_usd, roi, 7d APY, 30d APY, 60d APY, 90d APY, ETH Staking 7d APY
-- Depends on: query_3805243 (hyeth-composition-nav-eth), result_composition_changes_indexprotocolbased_products_events, result_hyeth_composition_apy, result_index_coop_fee_changes_all_products_events, result_post_merge_staking_yield
--
-- Optimizations (logic preserved):
--   1. Replaced ethereum.blocks with utils.days
--   2. query_3805243 called once, reused
--   3. prices.hour instead of prices.usd (LEGACY) - avg() preserved
--   4. Single WETH price CTE reused (was fetched twice)
--   5. All LEFT JOINs preserved
--   6. Window functions unchanged
--
-- Start date: 2024-04-10 (hyETH launch)
-- ============================================================================

with

-- Token parameters
product_token (address, symbol, decimals) as (
    values
    (0xc4506022Fb8090774E8A628d5084EED61D9B99Ee, 'hyETH', 18)
)

-- Use utils.days instead of ethereum.blocks
, days as (
    select timestamp as day
    from utils.days
    where timestamp >= timestamp '2024-04-10'
)

-- Load query_3805243 once and reuse
, hyeth_comp_nav_eth as (
    select
        day
        , symbol
        , contract_address
        , nav_eth
    from query_3805243 -- hyeth-composition-nav-eth
)

-- WETH daily prices (single lookup, reused) - avg from hourly to match original logic
, weth_daily_prices as (
    select
        date_trunc('day', timestamp) as day
        , avg(price) as price
    from prices.hour
    where symbol = 'WETH'
    and blockchain = 'ethereum'
    and timestamp >= timestamp '2024-04-10'
    group by 1
)

-- Composition changes with lead for range join
, composition as (
    select
        date_trunc('day', minute) as day
        , product_symbol
        , symbol
        , contract_address
        , units
        , quotient
        , lead(date_trunc('day', minute), 1, now()) over (
            partition by contract_address
            order by minute
        ) as next_day
    from (
        select
            pt.symbol as product_symbol
            , cp.symbol as symbol
            , cp.minute
            , cp.component as contract_address
            , cp.default_units as units
            , cp.quotient
            , row_number() over (
                partition by date_trunc('day', cp.minute), cp.component
                order by minute desc
            ) as rnb
        from dune.index_coop.result_composition_changes_indexprotocolbased_products_events cp
        inner join product_token pt
            on cp.token_address = pt.address
    )
    where rnb = 1
)

-- Component prices in USD (nav_eth * WETH price)
, price_hyeth_comp as (
    select
        t0.nav_eth * wp.price as price
        , t0.day
        , t0.symbol
    from hyeth_comp_nav_eth t0
    inner join weth_daily_prices wp
        on wp.day = t0.day
)

-- Gap-fill composition to all days
, composition_all as (
    select
        d.day
        , c.symbol
        , c.product_symbol
        , c.contract_address
        , c.units
        , c.quotient
    from days d
    inner join composition c
        on c.day <= d.day
        and d.day < c.next_day
)

-- Calculate NAV per unit (reusing hyeth_comp_nav_eth)
, hyeth_nav_perunit as (
    select
        day
        , product_symbol
        , symbol
        , contract_address
        , nav_usd
        , nav_usd / (sum(nav_usd) over (partition by day)) as nav_share_usd
        , sum(nav_usd) over (partition by day) as hyeth_nav_perunit_usd
        , nav_eth / (sum(nav_eth) over (partition by day)) as nav_share_eth
        , sum(nav_eth) over (partition by day) as hyeth_nav_perunit_eth
    from (
        select
            cf.day
            , cf.product_symbol
            , cf.symbol
            , cf.contract_address
            , cf.units * p.price * cf.quotient as nav_usd
            , cf.units * he.nav_eth * cf.quotient as nav_eth
        from composition_all cf
        left join price_hyeth_comp p
            on cf.day = p.day
            and cf.symbol = p.symbol
        left join hyeth_comp_nav_eth he  -- Reusing instead of calling query_3805243 again
            on cf.day = he.day
            and cf.contract_address = he.contract_address
    )
    where nav_usd != 0
)

-- Summary with APY calculations
, summary as (
    select
        day
        , product_symbol
        , initial_value
        , hyeth_nav_perunit_eth as hyeth_nav_eth
        , sum(apy_share) as apy
        , sum(apy_share) * 100 as apy_txt
    from (
        select
            hn.day
            , hn.product_symbol
            , hn.symbol
            , hn.contract_address
            , hn.nav_share_usd
            , hn.hyeth_nav_perunit_eth
            , first_value(hyeth_nav_perunit_eth) over (order by hn.day asc) as initial_value
            , hn.nav_share_usd * ap.apy as apy_share
            , ap.apy
        from hyeth_nav_perunit hn
        left join dune.index_coop.result_hyeth_composition_apy ap
            on ap.day = hn.day
            and ap.contract_address = hn.contract_address
    )
    group by 1, 2, 3, 4
)

-- Daily fee rates with gap-fill
, daily_fee_rates as (
    select
        day
        , first_value(streaming_fee) over (partition by sf_part order by day asc) as streaming_fee
        , first_value(issue_fee) over (partition by if_part order by day asc) as issue_fee
        , first_value(redeem_fee) over (partition by rf_part order by day asc) as redeem_fee
    from (
        select
            d.day
            , x.streaming_fee
            , x.issue_fee
            , x.redeem_fee
            , sum(case when x.streaming_fee is null then 0 else 1 end) over (order by d.day asc) as sf_part
            , sum(case when x.issue_fee is null then 0 else 1 end) over (order by d.day asc) as if_part
            , sum(case when x.redeem_fee is null then 0 else 1 end) over (order by d.day asc) as rf_part
        from (
            select
                token_address
                , date_trunc('day', min(block_time)) as min_day
            from dune.index_coop.result_index_coop_fee_changes_all_products_events
            where token_address = 0xc4506022Fb8090774E8A628d5084EED61D9B99Ee
            group by 1
        ) t
        cross join days d
        left join (
            select
                date_trunc('day', block_time) as day
                , coalesce(streaming_fee, 0) as streaming_fee
                , coalesce(issue_fee, 0.001) as issue_fee
                , coalesce(redeem_fee, 0.001) as redeem_fee
                , row_number() over (
                    partition by date_trunc('day', block_time)
                    order by block_time desc, priority desc
                ) as rnb
            from dune.index_coop.result_index_coop_fee_changes_all_products_events
            where token_address = 0xc4506022Fb8090774E8A628d5084EED61D9B99Ee
        ) x
            on x.day = d.day
            and x.rnb = 1
        where d.day >= t.min_day
    ) t1
)

-- Final output
select
    s.day
    , product_symbol
    , initial_value
    , hyeth_nav_eth
    , apy
    , apy_txt
    , apy_txt as gross_yield
    , apy_txt - (df.streaming_fee * 100) as net_yield
    , hyeth_nav_eth * wp.price as hyeth_nav_usd
    , (hyeth_nav_eth - initial_value) / initial_value as roi
    , avg(apy) over (order by s.day rows between 6 preceding and current row) as "7d APY"
    , avg(apy) over (order by s.day rows between 29 preceding and current row) as "30d APY"
    , avg(apy) over (order by s.day rows between 59 preceding and current row) as "60d APY"
    , avg(apy) over (order by s.day rows between 89 preceding and current row) as "90d APY"
    , avg(staking_yield) over (order by s.day rows between 6 preceding and current row) as "ETH Staking 7d APY"
from summary s
left join daily_fee_rates df
    on df.day = s.day
left join dune.index_coop.result_post_merge_staking_yield es
    on es.day = s.day
left join weth_daily_prices wp
    on wp.day = s.day
order by s.day desc
