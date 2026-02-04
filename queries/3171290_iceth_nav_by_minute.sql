-- ============================================================================
-- Query: icETH NAV by Minute
-- Dune ID: 3171290
-- URL: https://dune.com/queries/3171290
-- Description: Calculates icETH NAV in stETH/ETH/USD and leverage ratios per minute
-- Parameters: none
--
-- Columns: minute, nav_steth, nav_eth, nav_usd, steth_price, weth_price,
--          steth_eth_price, true_leverage_ratio, target_leverage_ratio
-- Depends on: DebtIssuanceModuleV2 events, prices.usd
--
-- Optimizations applied (logic preserved):
--   1. ethereum.blocks -> utils.minutes (for time series generation)
--   2. Added time filter on erc20 transfers for partition pruning
--   3. Added time filter on prices.usd for partition pruning
--   4. Use WETH contract address instead of symbol lookup for ETH price
--
-- Token addresses:
--   icETH: 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84
--   aSTETH: 0x1982b2F5814301d4e9a8b0201555376e62F82428
--   variableDebtWETH: 0xF63B34710400CAd3e044cFfDcAb00a0f32E33eCf
--   WETH: 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
--   stETH: 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84
--
-- ============================================================================

with

issue_events as (
    select
        i.evt_block_time
        , i.evt_tx_hash
        , sum(e.value / 1e18) filter (where e.contract_address = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84 and e."from" = 0x0000000000000000000000000000000000000000) as iceth_amount
        , sum(e.value / 1e18) filter (where e.contract_address = 0x1982b2F5814301d4e9a8b0201555376e62F82428 and e.to = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84) as asteth_amount
        , sum(e.value / 1e18) filter (where e.contract_address = 0xF63B34710400CAd3e044cFfDcAb00a0f32E33eCf and e.to = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84) as variabledebtweth_amount
    from setprotocol_v2_ethereum.DebtIssuanceModuleV2_evt_SetTokenIssued i
    left join erc20_ethereum.evt_Transfer e
        on i.evt_tx_hash = e.evt_tx_hash
        and e.evt_block_time >= timestamp '2022-03-21'
    where _setToken = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84
    group by 1, 2
)

, redeem_events as (
    select
        i.evt_block_time
        , i.evt_tx_hash
        , sum(e.value / 1e18) filter (where e.contract_address = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84 and e.to = 0x0000000000000000000000000000000000000000) as iceth_amount
        , sum(e.value / 1e18) filter (where e.contract_address = 0x1982b2F5814301d4e9a8b0201555376e62F82428 and e."from" = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84) as asteth_amount
        , sum(e.value / 1e18) filter (where e.contract_address = 0xF63B34710400CAd3e044cFfDcAb00a0f32E33eCf and e."from" = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84) as variabledebtweth_amount
    from setprotocol_v2_ethereum.DebtIssuanceModuleV2_evt_SetTokenRedeemed i
    left join erc20_ethereum.evt_Transfer e
        on i.evt_tx_hash = e.evt_tx_hash
        and e.evt_block_time >= timestamp '2022-03-21'
    where _setToken = 0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84
    group by 1, 2
)

, all_events as (
    select
        evt_block_time
        , evt_tx_hash
        , asteth_amount / iceth_amount as asteth
        , variabledebtweth_amount / iceth_amount as variabledebtweth
    from issue_events

    union

    select
        evt_block_time
        , evt_tx_hash
        , asteth_amount / iceth_amount as asteth
        , variabledebtweth_amount / iceth_amount as variabledebtweth
    from redeem_events
)

-- There is no NAV before 2022-03-21 14:06
, minutes as (
    select timestamp as minute
    from utils.minutes
    where timestamp > timestamp '2022-03-21 14:06'
)

, lastest_event as (
    select
        minute
        , evt_tx_hash as hash
    from (
        select
            m.minute
            , e.evt_tx_hash
            , row_number() over (partition by m.minute order by e.evt_block_time desc) as rn
        from minutes m
        left join all_events e on e.evt_block_time <= m.minute
    )
    where rn = 1
)

select
    minute
    , nav_steth
    , (steth_price * asteth - weth_price * variabledebtweth) / weth_price as nav_eth
    , (steth_price * asteth - weth_price * variabledebtweth) as nav_usd
    , steth_price
    , weth_price
    , steth_price / weth_price as steth_eth_price
    , (asteth * steth_price) / (asteth * steth_price - variabledebtweth * weth_price) as true_leverage_ratio
    , (asteth) / (asteth - variabledebtweth) as target_leverage_ratio
from (
    select
        minute
        , first_value(steth_price) over (partition by steth_price_part order by minute) as steth_price
        , first_value(weth_price) over (partition by weth_price_part order by minute) as weth_price
        , asteth
        , variabledebtweth
        , asteth - variabledebtweth as nav_steth
    from (
        select
            t.minute
            , p1.price as weth_price
            , p2.price as steth_price
            , sum(case when p1.price is null then 0 else 1 end) over (order by t.minute) as weth_price_part
            , sum(case when p2.price is null then 0 else 1 end) over (order by t.minute) as steth_price_part
            , asteth
            , variabledebtweth
        from lastest_event t
        left join all_events a on t.hash = a.evt_tx_hash
        left join prices.usd p1
            on p1.minute = t.minute
            and p1.blockchain = 'ethereum'
            and p1.contract_address = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2  -- WETH
        left join prices.usd p2
            on p2.minute = t.minute
            and p2.blockchain = 'ethereum'
            and p2.contract_address = 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84  -- stETH
        where t.minute >= timestamp '2022-03-21'
    )
)
