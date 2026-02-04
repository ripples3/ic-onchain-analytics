-- ============================================================================
-- Query: hyeth-nav-by-minute
-- Dune ID: 3994496
-- URL: https://dune.com/queries/3994496
-- Materialized View: dune.index_coop.result_hyeth_nav_by_minute
-- Description: hyETH NAV by minute for detailed tracking
-- Parameters: none
--
-- Columns: minute, product_symbol, address, hyeth_nav_usd, hyeth_nav_eth
-- Depends on: query_3806801 (hyeth-composition-nav-eth-minute), result_composition_changes_indexprotocolbased_products_events, prices.minute
--
-- Optimizations (logic preserved):
--   1. prices.usd (LEGACY) replaced with prices.minute
--   2. Added time filter on prices.minute for partition pruning
--   3. ethereum.blocks replaced with utils.minutes
--   4. Consistent formatting
--
-- Start date: 2024-04-10 (hyETH launch)
-- ============================================================================

with

-- Token parameters
product_token (address, symbol, decimals) as (
    values
    (0xc4506022Fb8090774E8A628d5084EED61D9B99Ee, 'hyETH', 18)
)

, composition as (
    select
        date_trunc('minute', minute) as minute
        , product_symbol
        , address
        , symbol
        , contract_address
        , units
        , quotient
        , lead(date_trunc('minute', minute), 1, now()) over (partition by contract_address order by minute) as next_minute
    from (
        select
            pt.symbol as product_symbol
            , pt.address
            , cp.symbol as symbol
            , cp.minute
            , cp.component as contract_address
            , cp.default_units as units
            , cp.quotient
            , row_number() over (partition by date_trunc('minute', cp.minute), cp.component order by minute desc) as rnb
        from dune.index_coop.result_composition_changes_indexprotocolbased_products_events cp
        inner join product_token pt
            on cp.token_address = pt.address
    )
    where rnb = 1
)

-- WETH prices by minute - using prices.minute instead of prices.usd (LEGACY)
, price_hyeth_comp as (
    select
        avg(t0.nav_eth) as nav_eth
        , avg(t0.nav_eth * price) as nav_usd
        , t0.minute
        , t0.symbol
    from query_3806801 t0
    inner join prices.minute p
        on date_trunc('minute', p.timestamp) = t0.minute
    where p.blockchain = 'ethereum'
    and p.symbol = 'WETH'
    and p.timestamp >= timestamp '2024-04-10'  -- Partition pruning
    group by 3, 4
)

-- Minutes from utils.minutes
, minutes as (
    select timestamp as minute
    from utils.minutes
    where timestamp >= timestamp '2024-04-10'
)

, composition_all as (
    select
        m.minute
        , c.symbol
        , c.product_symbol
        , c.address
        , c.contract_address
        , c.units
        , c.quotient
    from minutes m
    inner join composition c
        on c.minute <= m.minute
        and m.minute < c.next_minute
)

, hyeth_nav_perunit as (
    select
        minute
        , product_symbol
        , address
        , sum(nav_usd) as hyeth_nav_usd
        , sum(nav_eth) as hyeth_nav_eth
    from (
        select
            cf.minute
            , cf.product_symbol
            , cf.address
            , cf.symbol
            , cf.contract_address
            , cf.units * p.nav_usd * quotient as nav_usd
            , cf.units * he.nav_eth * quotient as nav_eth
        from composition_all cf
        left join price_hyeth_comp p
            on cf.minute = p.minute
            and cf.symbol = p.symbol
        left join query_3806801 he  -- hyeth-composition-nav-eth-minute
            on cf.minute = he.minute
            and cf.contract_address = he.contract_address
    )
    where nav_usd != 0
    group by 1, 2, 3
)

select *
from hyeth_nav_perunit
order by minute desc
