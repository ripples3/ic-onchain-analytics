-- ============================================================================
-- Query: lrt-eth-exchange-rates
-- Dune ID: 3802258
-- URL: https://dune.com/queries/3802258
-- Description: Daily exchange rates for weETH, rswETH, rsETH, ezETH, agETH
-- Parameters: none
--
-- Columns: day, symbol, contract_address, rate
-- Depends on: etherfiwrappedeth_ethereum, swell_v3_ethereum, kelpdao_ethereum, renzo_ethereum, kelp_gain_ethereum
--
-- Optimizations (logic preserved):
--   1. Replaced ethereum.blocks with utils.days
--   2. Replaced correlated subquery with self-join for agETH
--   3. Used UNION ALL between different symbols (no duplicates possible)
--   4. Fixed inconsistent column naming (rate_rseth → rate)
--   5. Added contract_address for each token
--
-- Start date: 2024-01-11
-- ============================================================================

with

exchange_rates as (
    select
        time
        , symbol
        , contract_address
        , rate
        , lead(time, 1, now()) over (partition by symbol order by time) as next_day
    from (
        -- weETH
        select
            date_trunc('day', call_block_time) as time
            , 'weETH' as symbol
            , 0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee as contract_address
            , max_by(output_0 / 1e18, call_block_time) as rate
        from etherfiwrappedeth_ethereum.WeETH_call_getRate
        where call_success
        group by 1

        union all

        -- rswETH
        select
            date_trunc('day', call_block_time) as time
            , 'rswETH' as symbol
            , 0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0 as contract_address
            , max_by(output_0 / 1e18, call_block_time) as rate
        from swell_v3_ethereum.RswETH_call_getRate
        where call_success
        group by 1

        union all

        -- rsETH
        select
            date_trunc('day', evt_block_time) as time
            , 'rsETH' as symbol
            , 0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7 as contract_address
            , max_by(depositAmount / 1e18 / (rsethMintAmount / 1e18), evt_block_time) as rate
        from kelpdao_ethereum.LRTDepositPool_evt_AssetDeposit
        where asset in (0x0000000000000000000000000000000000000000, 0xae7ab96520de3a18e5e111b5eaab095312d7fe84)
        group by 1

        union all

        -- ezETH
        select
            date_trunc('day', evt_block_time) as time
            , 'ezETH' as symbol
            , 0xbf5495Efe5DB9ce00f80364C8B423567e58d2110 as contract_address
            , max_by(amount / 1e18 / (ezETHMinted / 1e18), evt_block_time) as rate
        from renzo_ethereum.RestakeManager_evt_Deposit
        where token = 0x0000000000000000000000000000000000000000
        group by 1

        union all

        -- agETH (from WithdrawalRequested)
        select
            date_trunc('day', evt_block_time) as time
            , 'agETH' as symbol
            , 0xe1B4d34E8754600962Cd944B535180Bd758E6c2e as contract_address
            , max_by(cast(assets as double) / cast(shares as double), evt_block_time) as rate
        from kelp_gain_ethereum.LendingPool_evt_WithdrawalRequested
        group by 1

        union

        -- agETH (from Deposit) - UNION to dedupe if same day exists in both sources
        select
            date_trunc('day', evt_block_time) as time
            , 'agETH' as symbol
            , 0xe1B4d34E8754600962Cd944B535180Bd758E6c2e as contract_address
            , max_by(cast(assets as double) / cast(shares as double), evt_block_time) as rate
        from kelp_gain_ethereum.LendingPool_evt_Deposit
        group by 1
    )
)

-- Use utils.days instead of ethereum.blocks
, days as (
    select timestamp as day
    from utils.days
    where timestamp >= timestamp '2024-01-11'
)

, summary as (
    select
        d.day
        , er.symbol
        , er.contract_address
        , er.rate
    from days d
    inner join exchange_rates er
        on er.time <= d.day
        and d.day < er.next_day
)

-- Self-join instead of correlated subquery for agETH
select
    s.day
    , s.symbol
    , s.contract_address
    , case
        when s.symbol = 'agETH' then s.rate * rseth.rate
        else s.rate
      end as rate
from summary s
left join summary rseth
    on s.symbol = 'agETH'
    and rseth.symbol = 'rsETH'
    and rseth.day = s.day
