-- ============================================================================
-- Query: pendle-hyeth-swap-hold-incentive-tracker
-- Dune ID: 4007736
-- URL: https://dune.com/queries/4007736
-- Description: PENDLE hyETH Swap & Hold Incentive Tracker on Arbitrum
-- Parameters: none
--
-- Columns: day, user_address, token_bought, current_balance, eligible_balance, eligible_value, pct_of_rewards, arb_rewards, price, arb_price
-- Depends on: erc20_arbitrum.evt_transfer, dex.trades, prices.usd, result_hyeth_nav_by_minute
--
-- Start date: 2024-08-22 (campaign start)
-- End date: 2024-09-12 (campaign end)
-- ============================================================================

with

-- Token parameters
token_param (chain, token_address, symbol, decimals) as (
    values
    ('arbitrum', 0x8b5D1d8B3466eC21f8eE33cE63F319642c026142, 'hyETH', 18)
)

-- DEX pool parameters
, dex_param (chain, pool_address, dex) as (
    values
    ('arbitrum', 0x470d0d72C975a7F328Bd63808bFFfD28194B3eB6, 'UniswapV3Pool')
)

, txns_from_univ3 as (
    select
        date_trunc('day', evt_block_time) as day
        , user
        , sum(value) as value
        , symbol
    from (
        select
            tr.evt_block_time
            , tr.to as user
            , tr.evt_tx_hash
            , sum(cast(value as double) / power(10, tp.decimals)) as value
            , tp.symbol
        from erc20_arbitrum.evt_transfer tr
        inner join dex_param dp
            on dp.pool_address = tr."from"
        inner join token_param tp
            on tp.token_address = tr.contract_address
        where tr."from" != 0x5E325eDA8064b456f4781070C0738d849c824258 -- UniversalRouter
        group by 1, 2, 3, 5
    )
    group by 1, 2, 4
)

, hyeth_dextrades as (
    select tx_hash
    from dex.trades dt
    where blockchain = 'arbitrum'
    and token_bought_address = 0x8b5D1d8B3466eC21f8eE33cE63F319642c026142
    and project_contract_address = 0x470d0d72c975a7f328bd63808bfffd28194b3eb6
    and block_time >= cast('2024-08-22' as timestamp)
)

, hyeth_txbuy_gap as (
    select
        day
        , user
        , symbol
        , case
            when sum(value) over (partition by user order by day) < 0.00001 then 0
            else sum(value) over (partition by user order by day)
          end as running_balance
        , lead(day, 1, now()) over (partition by user order by day) as next_day
    from (
        select
            day
            , user
            , symbol
            , sum(value) as value
        from (
            select
                date_trunc('day', tr.evt_block_time) as day
                , tr.evt_index
                , tr.evt_block_number
                , tr.to as user
                , tr.evt_tx_hash
                , tp.symbol
                , row_number() over (partition by evt_tx_hash order by tr.evt_index desc) as rn
                , sum(cast(value as double) / power(10, 18)) as value
            from erc20_arbitrum.evt_transfer tr
            inner join hyeth_dextrades ht
                on ht.tx_hash = tr.evt_tx_hash
            inner join token_param tp
                on tp.token_address = tr.contract_address
            group by 1, 2, 3, 4, 5, 6
        )
        where rn = 1
        group by 1, 2, 3
    )
)

, transfers_gap as (
    select
        day
        , user
        , symbol
        , case
            when sum(value) over (partition by user order by day) < 0.00001 then 0
            else sum(value) over (partition by user order by day)
          end as running_balance
        , lead(day, 1, now()) over (partition by user order by day) as next_day
    from (
        select
            day
            , user
            , symbol
            , sum(value) as value
        from (
            select
                date_trunc('day', tr.evt_block_time) as day
                , tr.to as user
                , tp.symbol
                , sum(cast(value as double) / power(10, 18)) as value
            from erc20_arbitrum.evt_transfer tr
            inner join token_param tp
                on tp.token_address = tr.contract_address
            group by 1, 2, 3

            union

            select
                date_trunc('day', tr.evt_block_time) as day
                , tr."from" as user
                , tp.symbol
                , -sum(cast(value as double) / power(10, 18)) as value
            from erc20_arbitrum.evt_transfer tr
            inner join token_param tp
                on tp.token_address = tr.contract_address
            group by 1, 2, 3
        )
        group by 1, 2, 3
    )
)

, days as (
    select distinct date_trunc('day', time) as day
    from ethereum.blocks
    where time >= timestamp '2024-08-22 00:00'
)

, hyeth_txbuy_all as (
    select
        d.day
        , hp.user
        , hp.symbol
        , hp.running_balance
    from days d
    inner join hyeth_txbuy_gap hp
        on hp.day <= d.day
        and d.day < hp.next_day
)

, transfers_all as (
    select
        d.day
        , hp.user
        , hp.symbol
        , hp.running_balance
    from days d
    inner join transfers_gap hp
        on hp.day <= d.day
        and d.day < hp.next_day
)

, arb_price as (
    select
        day
        , price
    from (
        select
            date_trunc('day', minute) as day
            , minute
            , price
            , row_number() over (partition by date_trunc('day', minute) order by minute desc) as rn
        from prices.usd
        where blockchain = 'ethereum'
        and contract_address = 0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1
        and minute >= cast('2024-08-22' as timestamp)
    )
    where rn = 1
)

, hyeth_price as (
    select
        day
        , price
    from (
        select
            date_trunc('day', minute) as day
            , minute
            , hyeth_nav_usd as price
            , row_number() over (partition by date_trunc('day', minute) order by minute desc) as rn
        from dune.index_coop.result_hyeth_nav_by_minute
    )
    where rn = 1
)

, summary as (
    select
        t0.day
        , user
        , symbol
        , amount_bought
        , running_balance
        , eligible_balance
        , price
    from (
        select
            ha.day
            , ha.user
            , ha.symbol
            , ha.running_balance as amount_bought
            , ta.running_balance as running_balance
            , case
                when ha.running_balance >= ta.running_balance then ta.running_balance
                else ha.running_balance
              end as eligible_balance
        from hyeth_txbuy_all ha
        inner join transfers_all ta
            on ha.day = ta.day
            and ha.user = ta.user
    ) t0
    left join hyeth_price hp
        on hp.day = t0.day
)

, total as (
    select
        day
        , 500 as total_rewards
        , sum(price * eligible_balance) as total_value
    from summary
    group by 1, 2
)

select
    ts.day
    , ts.user as user_address
    , ts.amount_bought as token_bought
    , ts.running_balance as current_balance
    , ts.eligible_balance
    , ts.price * ts.eligible_balance as eligible_value
    , (ts.price * ts.eligible_balance) / t.total_value as pct_of_rewards
    , (ts.price * ts.eligible_balance) / t.total_value * total_rewards as arb_rewards
    , ts.price
    , a.price as arb_price
from summary ts
left join total t
    on ts.day = t.day
left join arb_price a
    on ts.day = a.day
where ts.day < cast('2024-09-12' as timestamp)
