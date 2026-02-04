-- ============================================================================
-- Query: hyeth-composition-nav-eth
-- Dune ID: 3805243
-- URL: https://dune.com/queries/3805243
-- Description: NAV in ETH for hyETH composition components
-- Parameters: none
--
-- Columns: day, contract_address, symbol, nav_eth
-- Depends on: result_composition_changes_indexprotocolbased_products_events, query_3802258 (LRT exchange rates)
--
-- Optimizations (logic preserved):
--   1. Replaced ethereum.blocks with utils.days
--   2. Used UNION ALL where safe (no duplicates between different sources)
--   3. Added time filters on ethereum.logs for partition pruning
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
        date_trunc('day', minute) as day
        , product_symbol
        , symbol
        , contract_address
        , units
        , quotient
        , lead(date_trunc('day', minute), 1, now()) over (partition by contract_address order by minute) as next_day
    from (
        select
            pt.symbol as product_symbol
            , cp.symbol as symbol
            , cp.minute
            , cp.component as contract_address
            , cp.default_units as units
            , cp.quotient
            , row_number() over (partition by date_trunc('day', cp.minute), cp.component order by minute desc) as rnb
        from dune.index_coop.result_composition_changes_indexprotocolbased_products_events cp
        inner join product_token pt
            on cp.token_address = pt.address
    )
    where rnb = 1
)

, hyeth_comp_current as (
    select
        symbol
        , contract_address
        , first_day
        , last_next_day
    from (
        select
            symbol
            , contract_address
            , row_number() over (partition by symbol order by day desc) as rnb
            , first_value(day) over (partition by symbol order by day) as first_day
            , last_value(next_day) over (partition by symbol order by day rows between unbounded preceding and unbounded following) as last_next_day
        from composition
        where units > 0
    )
    where rnb = 1
)

-- Pendle PT token parameters
, pt_param (pt_address, pt_symbol, base_symbol, market_address, maturity) as (
    values
    (0x1c085195437738d73d75dc64bc5a3e098b7f93b1, 'PT-weETH-26SEP2024', 'weETH', 0xc8edd52d0502aa8b4d5c77361d4b3d300e8fc81c, 1727308800),
    (0x6ee2b5E19ECBa773a352E5B21415Dc419A700d1d, 'PT-weETH-26DEC2024', 'weETH', 0x7d372819240d14fb477f17b964f95f33beb4c704, 1735171200),
    (0xf7906f274c174a52d444175729e3fa98f9bde285, 'PT-ezETH-26DEC2024', 'ezETH', 0xd8f12bcde578c653014f27379a6114f67f0e445f, 1735171200),
    (0x7aa68E84bCD8d1B4C9e10B1e565DB993f68a3E09, 'PT-agETH-26DEC2024', 'agETH', 0x6010676Bc2534652aD1Ef5Fa8073DcF9AD7EBFBe, 1735171200)
)

, routers_param (router_address, router_name) as (
    values
    (0x41FAD93F225b5C1C95f2445A5d7fcB85bA46713f, 'Pendle: RouterV3'),
    (0x0000000001e4ef00d069e71d6ba041b0a16f7ea0, 'Pendle: RouterV3'),
    (0x00000000005BBB0EF59571E58418F9a4357b68A0, 'Pendle: RouterV3'),
    (0x888888888889758F76e7103c6CbF23ABbF58F946, 'Pendle: RouterV4')
)

-- Pendle PT swap data
, data as (
    select
        block_time
        , bytearray_substring(topic1, 13, 20) as caller
        , bytearray_substring(topic2, 13, 20) as market
        , bytearray_substring(topic3, 13, 20) as token
        , bytearray_substring(data, 13, 20) as receiver
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 1 * 32, 32)) as double) as netPtToAccount
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 2 * 32, 32)) as double) as netTokenToAccount
        , cast(bytearray_to_int256(bytearray_substring(data, 1 + 3 * 32, 32)) as double) as netSyInterm
        , pt_address
        , pt_symbol
        , base_symbol
        , from_unixtime(maturity) as maturity
    from ethereum.logs el
    inner join routers_param rp
        on el.contract_address = rp.router_address
    inner join pt_param pp
        on bytearray_substring(el.topic2, 13, 20) = pp.market_address
    where topic0 = 0xd3c1d9b397236779b29ee5b5b150c1110fc8221b6b6ec0be49c9f4860ceb2036 -- SwapPtAndToken
    and el.block_time >= timestamp '2024-04-10'  -- Partition pruning
)

-- Use utils.days instead of ethereum.blocks
, days as (
    select timestamp as day
    from utils.days
    where timestamp >= timestamp '2024-04-10'
)

, prices_maturity_data as (
    select
        day
        , pt_address
        , pt_symbol
        , base_symbol
        , maturity_date
        , price as price_inbasetoken
        , 1 as maturity_price
        , date_diff('day', day, maturity_date) as days_to_maturity
        , lead(day, 1, now()) over (partition by pt_address order by day) as next_day
    from (
        select
            date_trunc('day', block_time) as day
            , pt_address
            , pt_symbol
            , base_symbol
            , maturity as maturity_date
            , abs(netTokenToAccount / netPtToAccount) as price
            , row_number() over (partition by pt_address, date_trunc('day', block_time) order by block_time desc) as rnb
        from data
        where abs(netTokenToAccount) = abs(netSyInterm)
    )
    where rnb = 1
)

, summary as (
    select
        d.day
        , pd.pt_address
        , pd.pt_symbol
        , pd.base_symbol
        , pd.price_inbasetoken
        , pd.maturity_date
    from days d
    inner join prices_maturity_data pd
        on pd.day <= d.day
        and d.day < pd.next_day
)

, pt_tokens_naveth as (
    select
        s.day
        , pt_address as contract_address
        , pt_symbol as symbol
        , case
            when s.day >= maturity_date then 1
            else price_inbasetoken * rate
          end as nav_eth
    from summary s
    left join query_3802258 er
        on s.day = er.day
        and s.base_symbol = er.symbol
)

-- Across WETH LP
, across_naveth as (
    select
        day
        , contract_address
        , symbol
        , nav_eth
    from (
        select
            date_trunc('day', block_time) as day
            , 'ACX-WETH-LP' as symbol
            , 0x28F77208728B0A45cAb24c4868334581Fe86F95B as contract_address
            , amount / lpTokens as nav_eth
            , row_number() over (partition by date_trunc('day', block_time) order by block_time desc) as rnb
        from (
            -- LiquidityAdded
            select
                el.block_time
                , cast(bytearray_to_int256(bytearray_substring(el.data, 1, 32)) as double) as amount
                , cast(bytearray_to_int256(bytearray_substring(el.data, 33, 32)) as double) as lpTokens
            from ethereum.logs el
            where contract_address = 0xc186fA914353c44b2E33eBE05f21846F1048bEda
            and topic0 = 0x3c69701a61c79a92ef9692903aaa0068bce8771361ecb09547391e4fb4df8537
            and bytearray_substring(topic1, 13, 20) = 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
            and el.block_time >= timestamp '2024-04-10'

            union all

            -- LiquidityRemoved
            select
                el.block_time
                , cast(bytearray_to_int256(bytearray_substring(el.data, 1, 32)) as double) as amount
                , cast(bytearray_to_int256(bytearray_substring(el.data, 33, 32)) as double) as lpTokens
            from ethereum.logs el
            where contract_address = 0xc186fA914353c44b2E33eBE05f21846F1048bEda
            and topic0 = 0xcda1185f28599e6bd14ab8a68b3c30a11e1dce4256b5e67e94dd3fd846a6c589
            and bytearray_substring(topic1, 13, 20) = 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
            and el.block_time >= timestamp '2024-04-10'
        )
    )
    where rnb = 1
)

-- Instadapp iETHv2
, instadapp_naveth as (
    select
        day
        , contract_address
        , symbol
        , nav_eth
    from (
        select
            date_trunc('day', evt_block_time) as day
            , contract_address
            , 'iETHv2' as symbol
            , nav_eth
            , row_number() over (partition by date_trunc('day', evt_block_time) order by evt_block_time desc) as rnb
        from (
            select
                evt_block_time
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from instadapp_lite_ethereum.iETHv2_evt_Deposit

            union all

            select
                evt_block_time
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from instadapp_lite_ethereum.iETHv2_evt_Withdraw
        )
    )
    where rnb = 1
)

-- Re7 MetaMorpho WETH
, re7weth_naveth as (
    select
        day
        , contract_address
        , symbol
        , nav_eth
    from (
        select
            date_trunc('day', evt_block_time) as day
            , contract_address
            , 'Re7WETH' as symbol
            , nav_eth
            , row_number() over (partition by date_trunc('day', evt_block_time) order by evt_block_time desc) as rnb
        from (
            select
                evt_block_time
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Deposit
            where contract_address = 0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0

            union all

            select
                evt_block_time
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Withdraw
            where contract_address = 0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0
        )
    )
    where rnb = 1
)

-- New mhyETH vault raw data
, new_mhyeth_vault as (
    select
        block_time as evt_block_time
        , contract_address
        , cast(varbinary_to_uint256(varbinary_substring(data, 1, 32)) as decimal(38, 0)) / 1e18 as assets
        , cast(varbinary_to_uint256(varbinary_substring(data, 33, 32)) as decimal(38, 0)) / 1e18 as shares
    from ethereum.logs
    where contract_address = 0x701907283a57FF77E255C3f1aAD790466B8CE4ef
    and topic0 in (
        0xfbde797d201c681b91056529119e0b02407c7bb96a4a2c75c01fc9667232c8db,  -- Withdraw
        0xdcbc1c05240f31ff3ad067ef1ee35ce4997762752e3a095284754544f4c709d7   -- Deposit
    )
)

-- mhyETH MetaMorpho (old + new)
, morphohyeth_naveth as (
    select
        day
        , contract_address
        , symbol
        , nav_eth
    from (
        select
            date_trunc('day', evt_block_time) as day
            , contract_address
            , symbol
            , nav_eth
            , row_number() over (partition by date_trunc('day', evt_block_time) order by evt_block_time desc) as rnb
        from (
            -- Old mhyETH vault (before 2025-01-08)
            select
                evt_block_time
                , 'mhyETH-old' as symbol
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Deposit
            where contract_address = 0xc554929a61d862F2741077F8aafa147479c0b308
            and evt_block_time < timestamp '2025-01-08'

            union all

            select
                evt_block_time
                , 'mhyETH-old' as symbol
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from metamorpho_vaults_ethereum.MetaMorpho_evt_Withdraw
            where contract_address = 0xc554929a61d862F2741077F8aafa147479c0b308
            and evt_block_time < timestamp '2025-01-08'

            union all

            -- New mhyETH vault
            select
                evt_block_time
                , 'mhyETH' as symbol
                , contract_address
                , cast(assets as double) / cast(shares as double) as nav_eth
            from new_mhyeth_vault
        )
    )
    where rnb = 1
)

-- Combine Across, Instadapp, Re7, Morpho with gap-fill
, inst_across_morpho_naveth as (
    select
        day
        , contract_address
        , symbol
        , nav_eth
        , lead(day, 1, now()) over (partition by contract_address order by day) as next_day
    from (
        select day, contract_address, symbol, nav_eth from across_naveth
        union all
        select day, contract_address, symbol, nav_eth from instadapp_naveth
        union all
        select day, contract_address, symbol, nav_eth from re7weth_naveth
        union all
        select day, contract_address, symbol, nav_eth from morphohyeth_naveth
    )
)

-- wstETH exchange rate
, wsteth_eth_naveth as (
    select
        day
        , 0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0 as contract_address
        , 'wstETH' as symbol
        , pd_start_nav as nav_eth
    from (
        select
            date_trunc('day', pd_start) as day
            , pd_start_nav
        from (
            select
                ref_time as pd_start
                , er as pd_start_nav
            from (
                select
                    evt_block_time as ref_time
                    , cast(postTotalPooledEther as double) / cast(totalShares as double) as er
                from lido_ethereum.LegacyOracle_evt_PostTotalShares
                where evt_block_time >= timestamp '2024-04-10'
            )
        )
    )
)

-- Final combination
, final as (
    -- Gap-filled sources (Across, Instadapp, Re7, Morpho)
    select
        d.day
        , ac.contract_address
        , ac.symbol
        , ac.nav_eth
    from days d
    inner join inst_across_morpho_naveth ac
        on ac.day <= d.day
        and d.day < ac.next_day

    union all

    -- Pendle PT tokens
    select day, contract_address, symbol, nav_eth
    from pt_tokens_naveth

    union all

    -- wstETH
    select day, contract_address, symbol, nav_eth
    from wsteth_eth_naveth
)

-- Output filtered by current hyETH composition
select
    f.day
    , f.contract_address
    , f.symbol
    , f.nav_eth
from final f
inner join hyeth_comp_current hc
    on hc.contract_address = f.contract_address
    and f.day >= hc.first_day
    and f.day < hc.last_next_day
order by 1
