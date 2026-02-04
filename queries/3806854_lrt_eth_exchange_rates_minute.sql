-- ============================================================================
-- Query: lrt-eth-exchange-rates-minute
-- Dune ID: 3806854
-- URL: https://dune.com/queries/3806854
-- Description: LRT exchange rates by minute (weETH, rswETH, rsETH, ezETH, agETH)
-- Parameters: none
--
-- Columns: minute, symbol, contract_address, rate, next_minute
-- Depends on: etherfiwrappedeth_ethereum, swell_v3_ethereum, kelpdao_ethereum, renzo_ethereum, kelp_gain_ethereum
--
-- Note: Returns rate CHANGE events with next_minute for gap-fill by downstream queries.
--       Downstream join pattern: er.minute <= d.minute and d.minute < er.next_minute
--
-- Start date: 2024-04-11 (hyETH launch + 1 day)
-- ============================================================================

with

exchange_rates as (
    select
        time
        , symbol
        , contract_address
        , rate
        , lead(time, 1, now()) over (partition by symbol order by time) as next_minute
    from (
        -- weETH
        select
            date_trunc('minute', call_block_time) as time
            , 'weETH' as symbol
            , 0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee as contract_address
            , max_by(output_0 / 1e18, call_block_time) as rate
        from etherfiwrappedeth_ethereum.WeETH_call_getRate
        where call_success
        and call_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1

        union all  -- Different symbols, no duplicates

        -- rswETH
        select
            date_trunc('minute', call_block_time) as time
            , 'rswETH' as symbol
            , 0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0 as contract_address
            , max_by(output_0 / 1e18, call_block_time) as rate
        from swell_v3_ethereum.RswETH_call_getRate
        where call_success
        and call_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1

        union all

        -- rsETH
        select
            date_trunc('minute', evt_block_time) as time
            , 'rsETH' as symbol
            , 0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7 as contract_address
            , max_by((depositAmount / 1e18 / (rsethMintAmount / 1e18)), evt_block_time) as rate
        from kelpdao_ethereum.LRTDepositPool_evt_AssetDeposit
        where asset in (0x0000000000000000000000000000000000000000, 0xae7ab96520de3a18e5e111b5eaab095312d7fe84)
        and evt_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1

        union all

        -- ezETH
        select
            date_trunc('minute', evt_block_time) as time
            , 'ezETH' as symbol
            , 0xbf5495Efe5DB9ce00f80364C8B423567e58d2110 as contract_address
            , max_by((amount / 1e18 / (ezETHMinted / 1e18)), evt_block_time) as rate
        from renzo_ethereum.RestakeManager_evt_Deposit
        where token = 0x0000000000000000000000000000000000000000
        and evt_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1

        union all

        -- agETH (from WithdrawalRequested)
        select
            date_trunc('minute', evt_block_time) as time
            , 'agETH' as symbol
            , 0xe1B4d34E8754600962Cd944B535180Bd758E6c2e as contract_address
            , max_by(cast(assets as double) / cast(shares as double), evt_block_time) as rate
        from kelp_gain_ethereum.LendingPool_evt_WithdrawalRequested
        where evt_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1

        union  -- UNION to dedupe if same minute exists in both sources

        -- agETH (from Deposit)
        select
            date_trunc('minute', evt_block_time) as time
            , 'agETH' as symbol
            , 0xe1B4d34E8754600962Cd944B535180Bd758E6c2e as contract_address
            , max_by(cast(assets as double) / cast(shares as double), evt_block_time) as rate
        from kelp_gain_ethereum.LendingPool_evt_Deposit
        where evt_block_time >= timestamp '2024-04-11'  -- Partition pruning
        group by 1
    )
)

-- Self-join to calculate agETH rate (agETH rate * rsETH rate)
-- Returns rate change events with next_minute for downstream gap-fill
select
    er.time as minute
    , er.symbol
    , er.contract_address
    , case
        when er.symbol = 'agETH' then er.rate * rseth.rate
        else er.rate
      end as rate
    , er.next_minute
from exchange_rates er
left join exchange_rates rseth
    on er.symbol = 'agETH'
    and rseth.symbol = 'rsETH'
    and rseth.time <= er.time
    and er.time < rseth.next_minute
