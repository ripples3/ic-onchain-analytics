-- ============================================================================
-- Query: hyeth-composition-nav-eth-minute
-- Dune ID: 3806801
-- URL: https://dune.com/queries/3806801
-- Description: NAV in ETH for hyETH composition components (minute granularity)
-- Parameters: none
--
-- Columns: minute, contract_address, symbol, nav_eth
-- Depends on: result_composition_changes_indexprotocolbased_products_events, query_3806854 (LRT exchange rates minute)
--
-- Optimizations (logic preserved):
--   1. Added time filters on ethereum.logs for partition pruning
--   2. Used UNION ALL where safe (different symbols/contracts)
--   3. ethereum.blocks replaced with utils.minutes
--   4. Minutes range bounded by hyeth_comp_current (reduces from 600K+ to actual range)
--   5. Single gap-fill at end instead of multiple gap-fills
--   6. WETH handled without row expansion
--   7. Filter by current components BEFORE gap-fill
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
        , symbol
        , contract_address
        , units
        , quotient
        , lead(date_trunc('minute', minute), 1, now()) over (partition by contract_address order by minute) as next_minute
    from (
        select
            pt.symbol as product_symbol
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

-- Current hyETH components with time bounds
, hyeth_comp_current as (
    select
        symbol
        , contract_address
        , first_minute
        , last_next_minute
    from (
        select
            symbol
            , contract_address
            , row_number() over (partition by symbol order by minute desc) as rnb
            , first_value(minute) over (partition by symbol order by minute) as first_minute
            , last_value(next_minute) over (partition by symbol order by minute rows between unbounded preceding and unbounded following) as last_next_minute
        from composition
        where units > 0
    )
    where rnb = 1
)

-- Minutes bounded by actual component time range (optimization: reduces row count)
, minutes as (
    select timestamp as minute
    from utils.minutes
    where timestamp >= (select min(first_minute) from hyeth_comp_current)
    and timestamp < (select max(last_next_minute) from hyeth_comp_current)
)

-- Pendle PT token parameters
, pt_param (pt_address, pt_symbol, base_symbol, market_address, maturity) as (
    values
    (0x1c085195437738d73d75dc64bc5a3e098b7f93b1, 'PT-weETH-26SEP2024', 'weETH', 0xc8edd52d0502aa8b4d5c77361d4b3d300e8fc81c, 1727308800),
    (0x6ee2b5E19ECBa773a352E5B21415Dc419A700d1d, 'PT-weETH-26DEC2024', 'weETH', 0x7d372819240d14fb477f17b964f95f33beb4c704, 1735171200),
    (0xf7906f274c174a52d444175729e3fa98f9bde285, 'PT-ezETH-26DEC2024', 'ezETH', 0xd8f12bcde578c653014f27379a6114f67f0e445f, 1735171200),
    (0x7aa68E84bCD8d1B4C9e10B1e565DB993f68a3E09, 'PT-agETH-26DEC2024', 'rsETH', 0x6010676Bc2534652aD1Ef5Fa8073DcF9AD7EBFBe, 1735171200)
)

, routers_param (router_address, router_name) as (
    values
    (0x41FAD93F225b5C1C95f2445A5d7fcB85bA46713f, 'Pendle: RouterV3'),
    (0x0000000001e4ef00d069e71d6ba041b0a16f7ea0, 'Pendle: RouterV3'),
    (0x00000000005BBB0EF59571E58418F9a4357b68A0, 'Pendle: RouterV3'),
    (0x888888888889758F76e7103c6CbF23ABbF58F946, 'Pendle: RouterV4')
)

-- Pendle PT swap data
, pt_swap_data as (
    select
        block_time
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 1 * 32, 32)) as double) as netPtToAccount
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 2 * 32, 32)) as double) as netTokenToAccount
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 3 * 32, 32)) as double) as netSyInterm
        , pt_address
        , pt_symbol
        , base_symbol
        , index
    from ethereum.logs el
    inner join routers_param rp
        on el.contract_address = rp.router_address
    inner join pt_param pp
        on bytearray_substring(el.topic2, 13, 20) = pp.market_address
    where el.block_time >= timestamp '2024-04-10'  -- Partition pruning
    and topic0 = 0xd3c1d9b397236779b29ee5b5b150c1110fc8221b6b6ec0be49c9f4860ceb2036 -- SwapPtAndToken
)

-- PT token prices (rate change events with next_minute)
, pt_prices as (
    select
        minute
        , pt_address as contract_address
        , pt_symbol as symbol
        , base_symbol
        , price_inbasetoken
        , lead(minute, 1, now()) over (partition by pt_address order by minute) as next_minute
    from (
        select
            date_trunc('minute', block_time) as minute
            , pt_address
            , pt_symbol
            , base_symbol
            , abs(netTokenToAccount / netPtToAccount) as price_inbasetoken
            , row_number() over (partition by pt_address, date_trunc('minute', block_time) order by block_time desc, index desc) as rnb
        from pt_swap_data
        where abs(netTokenToAccount) = abs(netSyInterm)
    )
    where rnb = 1
)

-- Across WETH LP (rate change events)
, across_events as (
    select
        minute
        , contract_address
        , symbol
        , nav_eth
        , lead(minute, 1, now()) over (order by minute) as next_minute
    from (
        select
            date_trunc('minute', block_time) as minute
            , 'ACX-WETH-LP' as symbol
            , 0x28F77208728B0A45cAb24c4868334581Fe86F95B as contract_address
            , amount / lpTokens as nav_eth
            , row_number() over (partition by date_trunc('minute', block_time) order by block_time desc, index desc) as rnb
        from (
            select
                el.block_time
                , cast(bytearray_to_int256(bytearray_substring(el.data, 1, 32)) as double) as amount
                , cast(bytearray_to_int256(bytearray_substring(el.data, 33, 32)) as double) as lpTokens
                , index
            from ethereum.logs el
            where el.block_time >= timestamp '2024-04-10'  -- Partition pruning
            and contract_address = 0xc186fA914353c44b2E33eBE05f21846F1048bEda
            and topic0 in (
                0x3c69701a61c79a92ef9692903aaa0068bce8771361ecb09547391e4fb4df8537,  -- LiquidityAdded
                0xcda1185f28599e6bd14ab8a68b3c30a11e1dce4256b5e67e94dd3fd846a6c589   -- LiquidityRemoved
            )
            and bytearray_substring(topic1, 13, 20) = 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
        )
    )
    where rnb = 1
)

-- Instadapp iETHv2 (rate change events)
, instadapp_events as (
    select
        minute
        , contract_address
        , symbol
        , nav_eth
        , lead(minute, 1, now()) over (order by minute) as next_minute
    from (
        select
            date_trunc('minute', evt_block_time) as minute
            , contract_address
            , 'iETHv2' as symbol
            , cast(assets as double) / cast(shares as double) as nav_eth
            , row_number() over (partition by date_trunc('minute', evt_block_time) order by evt_block_time desc, evt_index desc) as rnb
        from (
            select evt_block_time, contract_address, assets, shares, evt_index
            from instadapp_lite_ethereum.iETHv2_evt_Deposit
            union all
            select evt_block_time, contract_address, assets, shares, evt_index
            from instadapp_lite_ethereum.iETHv2_evt_Withdraw
        )
    )
    where rnb = 1
)

-- Re7 MetaMorpho WETH (rate change events)
, re7weth_events as (
    select
        minute
        , contract_address
        , symbol
        , nav_eth
        , lead(minute, 1, now()) over (order by minute) as next_minute
    from (
        select
            date_trunc('minute', evt_block_time) as minute
            , contract_address
            , 'Re7WETH' as symbol
            , cast(assets as double) / cast(shares as double) as nav_eth
            , row_number() over (partition by date_trunc('minute', evt_block_time) order by evt_block_time desc) as rnb
        from (
            select evt_block_time, contract_address, assets, shares
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Deposit
            where contract_address = 0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0
            union all
            select evt_block_time, contract_address, assets, shares
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Withdraw
            where contract_address = 0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0
        )
    )
    where rnb = 1
)

-- wstETH exchange rate (rate change events)
, wsteth_events as (
    select
        date_trunc('minute', evt_block_time) as minute
        , 0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0 as contract_address
        , 'wstETH' as symbol
        , cast(postTotalPooledEther as double) / cast(totalShares as double) as nav_eth
        , lead(date_trunc('minute', evt_block_time), 1, now()) over (order by evt_block_time) as next_minute
    from lido_ethereum.LegacyOracle_evt_PostTotalShares
    where evt_block_time >= timestamp '2024-04-10'
)

-- All rate change events combined (excluding PT tokens which need LRT rate multiplication)
, all_nav_events as (
    select minute, contract_address, symbol, nav_eth, next_minute from across_events
    union all
    select minute, contract_address, symbol, nav_eth, next_minute from instadapp_events
    union all
    select minute, contract_address, symbol, nav_eth, next_minute from re7weth_events
    union all
    select minute, contract_address, symbol, nav_eth, next_minute from wsteth_events
)

-- Gap-fill for non-PT sources (single gap-fill)
, nav_gapfilled as (
    select
        m.minute
        , e.contract_address
        , e.symbol
        , e.nav_eth
    from minutes m
    inner join all_nav_events e
        on e.minute <= m.minute
        and m.minute < e.next_minute
    -- Filter early: only include current components
    inner join hyeth_comp_current hc
        on hc.contract_address = e.contract_address
        and m.minute >= hc.first_minute
        and m.minute < hc.last_next_minute
)

-- PT tokens: gap-fill and multiply by LRT exchange rate
, pt_nav_gapfilled as (
    select
        m.minute
        , p.contract_address
        , p.symbol
        , p.price_inbasetoken * er.rate as nav_eth
    from minutes m
    inner join pt_prices p
        on p.minute <= m.minute
        and m.minute < p.next_minute
    left join query_3806854 er  -- LRT exchange rates (gap-fill join)
        on er.minute <= m.minute
        and m.minute < er.next_minute
        and p.base_symbol = er.symbol
    -- Filter early: only include current components
    inner join hyeth_comp_current hc
        on hc.contract_address = p.contract_address
        and m.minute >= hc.first_minute
        and m.minute < hc.last_next_minute
)

-- WETH: only if in current composition, no row expansion needed
, weth_nav as (
    select
        m.minute
        , 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 as contract_address
        , 'WETH' as symbol
        , 1.0 as nav_eth
    from minutes m
    inner join hyeth_comp_current hc
        on hc.contract_address = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
        and m.minute >= hc.first_minute
        and m.minute < hc.last_next_minute
)

-- Final output
select minute, contract_address, symbol, nav_eth from nav_gapfilled
union all
select minute, contract_address, symbol, nav_eth from pt_nav_gapfilled
union all
select minute, contract_address, symbol, nav_eth from weth_nav
