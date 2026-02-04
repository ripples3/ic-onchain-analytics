-- Query: post-merge-staking-yield
-- Dune ID: 3989545
-- URL: https://dune.com/queries/3989545
-- Description: Calculates daily ETH staking yield combining consensus layer (CL) and execution layer (EL) rewards
-- Original queries: 2981412, 2981407, 2981348, 2411779, 1933076, 2393816, 2981339, 2489635, 3090893, 3266360
-- Parameters: none
--
-- Columns: day, staking_yield
--
-- Key block numbers:
--   EIP-1559 (London): 12965000 (2021-08-05)
--   Merge: 15537394 (2022-09-15)

with
-- =============================================================================
-- BLOCK DATA (single scan for post-merge, separate for pre-merge burn)
-- =============================================================================

-- Block burn from EIP-1559 base fees (query_2981407)
-- Pre-merge burn (EIP-1559 to merge) - smaller dataset
block_burn_premerge as (
    select
        date_trunc('day', time) as time,
        SUM(base_fee_per_gas * gas_used) / CAST(1e18 as double) as burn
    from ethereum.blocks
    where number >= 12965000   -- EIP-1559 block
      and number < 15537394    -- Merge block
    group by 1
),

-- Post-merge: combined scan for burn and intervals
block_data_postmerge as (
    select
        number,
        time,
        base_fee_per_gas,
        gas_used,
        date_diff('second', LAG(time) over (order by number), time) as interval_seconds
    from ethereum.blocks
    where number >= 15537394  -- Merge block
),

-- Post-merge burn
block_burn_postmerge as (
    select
        date_trunc('day', time) as time,
        SUM(base_fee_per_gas * gas_used) / CAST(1e18 as double) as burn
    from block_data_postmerge
    group by 1
),

-- Combined burn (all EIP-1559 era)
block_burn as (
    select * from block_burn_premerge
    union all
    select * from block_burn_postmerge
),

-- Block success rate / slot utilization (query_2981339)
block_success_rate as (
    select
        date_trunc('day', time) as time,
        AVG(interval_seconds) as avg_interval,
        12.0 / AVG(interval_seconds) as block_success_rate
    from block_data_postmerge
    where interval_seconds IS NOT NULL
      and time > CAST('2022-09-16' as timestamp)
    group by 1
),

-- =============================================================================
-- FEE DATA (query_2981412)
-- Block number filter is critical for performance on ethereum.transactions
-- =============================================================================
fee_data as (
    select
        date_trunc('day', tx.block_time) as time,
        SUM((tx.gas_price / 1.0e9) * (tx.gas_used / 1.0e9)) as total_fees,
        MAX(bb.burn) as total_burn,  -- MAX instead of AVG since burn is same for all tx in a day
        SUM((tx.gas_price / 1.0e9) * (tx.gas_used / 1.0e9)) - MAX(bb.burn) as total_priority_fees
    from ethereum.transactions tx
    inner join block_burn bb on date_trunc('day', tx.block_time) = bb.time
    where tx.block_number >= 12965000  -- EIP-1559 block - enables partition pruning
    group by 1
),

-- =============================================================================
-- PRE-LAUNCH STAKING DATA (query_3090893, query_3266360)
-- =============================================================================

-- Diva pre-launch: pubkey message commitments
-- Block filter critical - contract deployed ~block 17000000
diva_committed_vals as (
    select
        block_time,
        block_number,
        case
            when position('0x' IN t.pubkey) != 0
                and LENGTH(t.pubkey) - position('0x' IN t.pubkey) >= 98
            then from_hex(REPLACE(SUBSTRING(t.pubkey, position('0x' IN t.pubkey), 98), '"', ''))
            else NULL
        end as pubkey,
        "from" as tx_from,
        hash as tx_hash
    from ethereum.transactions
    cross join UNNEST(split(REPLACE(REPLACE(from_utf8(data), '{keys:[', ''), ']}', ''), ',')) as t(pubkey)
    where "to" = 0x93f3d5bb7901a00c88703cf78fa27bb6647774e9
      and block_number >= 17000000  -- Contract deployed after this
),

-- Diva pre-launch: ETH vault deposits
diva_eth_vault as (
    select
        t.block_time,
        t.block_number,
        SUM(t.value / 1e18) as eth_amount,
        "from" as tx_from,
        t.tx_hash
    from ethereum.traces t
    inner join ethereum.logs l
        on t.block_number = l.block_number
        and t.tx_hash = l.tx_hash
        and t.success
        and t.to = 0x59ea865ebb903ebc3e345efbbd4206dbd20d9c3f -- enzyme vault
        and l.topic0 = 0x1e6728e7f6ab409f42c28a298d4691e94f5426e54658999f76770bff70e56eaf
        and bytearray_ltrim(l.topic1) = 0x16770d642e882e1769ce4ac8612b8bc0601506fc
        and t.block_number >= 15478228
        and l.block_number >= 15478228
    group by 1, 2, 4, 5
),

-- Diva pre-launch: stETH vault deposits
diva_steth_vault as (
    select
        evt_block_time as block_time,
        evt_block_number as block_number,
        SUM(value / 1e18) as eth_amount,
        "from" as tx_from,
        evt_tx_hash as tx_hash
    from erc20_ethereum.evt_Transfer
    where to = 0x1ce8aafb51e79f6bdc0ef2ebd6fd34b00620f6db
        and contract_address = 0xae7ab96520de3a18e5e111b5eaab095312d7fe84
        and evt_block_number >= 18162932
    group by 1, 2, 4, 5
),

-- Diva pre-launch: message commitments with staking data
diva_message as (
    select
        'Message' as commitment_type,
        cv.block_time,
        cv.block_number,
        GREATEST(SUM(COALESCE(s.amount_staked, 0)), 0) as eth_amount,
        cv.tx_from,
        cv.tx_hash,
        cv.pubkey,
        MAX(s.entity) as currently_staked_with
    from diva_committed_vals cv
    left join staking_ethereum.deposits s
        on s.pubkey = cv.pubkey
        and (cv.tx_from IN (s.depositor_address, s.tx_from)
             or (s.depositor_address IS NULL and s.tx_from IS NULL))
    group by 1, 2, 3, 5, 6, 7
),

-- Combined Diva pre-launch (query_3090893)
diva_prelaunch as (
    select block_time, block_number, eth_amount, tx_from, tx_hash
    from (
        select
            'Octant Commitment' as commitment_type,
            date('2023-12-05') as block_time,
            NULL as block_number,
            100000 as eth_amount,
            NULL as tx_from,
            NULL as tx_hash

        union all

        select 'ETH Vault', block_time, block_number, eth_amount, tx_from, tx_hash
        from diva_eth_vault

        union all

        select 'stETH Vault', block_time, block_number, eth_amount, tx_from, tx_hash
        from diva_steth_vault

        union all

        select commitment_type, block_time, block_number, eth_amount, tx_from, tx_hash
        from diva_message
    )
),

-- Swell pre-launch (query_3266360)
swell_prelaunch as (
    select
        evt_block_time as block_time,
        evt_block_number as block_number,
        SUM(value / 1e18) as eth_amount,
        "from" as tx_from,
        evt_tx_hash as tx_hash
    from erc20_ethereum.evt_Transfer
    where to = 0x325a0e5c84b4d961b19161956f57ae8ba5bb3c26
        and contract_address = 0xae7ab96520de3a18e5e111b5eaab095312d7fe84
        and evt_block_number >= 18428812
    group by 1, 2, 4, 5
),

-- =============================================================================
-- VALIDATOR FLOWS (query_2393816)
-- Simplified: only select columns actually used downstream
-- =============================================================================
unadjusted_flows as (
    select
        block_time,
        amount_staked,
        amount_full_withdrawn,
        entity_category,
        sub_entity,
        validator_index
    from staking_ethereum.flows

    union all

    select
        block_time,
        eth_amount as amount_staked,
        0 as amount_full_withdrawn,
        'Liquid Staking' as entity_category,
        NULL as sub_entity,
        -1 as validator_index
    from diva_prelaunch

    union all

    select
        block_time,
        eth_amount as amount_staked,
        0 as amount_full_withdrawn,
        'Liquid Staking' as entity_category,
        NULL as sub_entity,
        -1 as validator_index
    from swell_prelaunch
),

-- Identify small solo stakers to group as "Other"
other_independent_stakers as (
    select sub_entity
    from unadjusted_flows
    where entity_category = 'Solo Staker'
    group by 1
    HAVING SUM(amount_staked) - COALESCE(SUM(amount_full_withdrawn), 0) < 4500
),

-- =============================================================================
-- ETH STAKED & VALIDATORS (query_1933076)
-- Using ROWS instead of RANGE for better performance
-- =============================================================================
staked as (
    select
        date_trunc('day', block_time) as time,
        SUM(SUM(amount_staked) - SUM(amount_full_withdrawn))
            over (order by date_trunc('day', block_time) ROWS UNBOUNDED PRECEDING) as cum_deposited_eth,
        SUM((SUM(amount_staked) - SUM(amount_full_withdrawn)) / 32)
            over (order by date_trunc('day', block_time) ROWS UNBOUNDED PRECEDING) as cum_validators
    from unadjusted_flows
    where validator_index >= 0
    group by 1
),

-- Per-validator cumulative deposits (filtered to sample early for performance)
validator_flow_details as (
    select
        date_trunc('day', block_time) as time,
        validator_index,
        SUM(SUM(amount_staked) - SUM(amount_full_withdrawn))
            over (partition by validator_index order by date_trunc('day', block_time) ROWS UNBOUNDED PRECEDING) as cum_deposited_eth
    from unadjusted_flows
    where validator_index >= 0 and validator_index < 1000  -- Filter early for performance
    group by 1, 2
),

-- Track validator state changes
validator_changes as (
    select
        time,
        validator_index,
        cum_deposited_eth,
        LAG(cum_deposited_eth) over (partition by validator_index order by time) as cum_deposited_eth_old
    from validator_flow_details
),

-- Count validators crossing 32 ETH threshold
validators as (
    select
        time,
        SUM(SUM(case
            when cum_deposited_eth >= 32 and (cum_deposited_eth_old < 32 or cum_deposited_eth_old IS NULL) then 1
            when cum_deposited_eth < 32 and cum_deposited_eth_old >= 32 then -1
        end)) over (order by time) as staked_validators
    from validator_changes
    where cum_deposited_eth != cum_deposited_eth_old
    group by 1
),

-- Daily ETH prices (first price of each day for consistency)
daily_eth_price as (
    select day, price
    from (
        select
            date_trunc('day', minute) as day,
            price,
            ROW_NUMBER() over (partition by date_trunc('day', minute) order by minute) as rn
        from prices.usd
        where blockchain IS NULL
          and symbol = 'ETH'
          and minute >= TIMESTAMP '2020-12-01'
    )
    where rn = 1
),

-- Combine staked ETH with validator counts and prices
eth_staked_validators as (
    select
        s.time,
        s.cum_deposited_eth,
        s.cum_deposited_eth * p.price as economic_security,
        s.cum_validators,
        v.staked_validators
    from staked s
    inner join daily_eth_price p on p.day = s.time
    left join validators v on v.time = s.time
),

-- =============================================================================
-- POS ISSUANCE (query_2411779)
-- =============================================================================
pos_issuance as (
    select
        time,
        cum_deposited_eth,
        economic_security,
        cum_validators,
        staked_validators,
        -- Approximation via Ben Edgington (eth2book)
        940.8659 / 365 * sqrt(cum_validators) as max_daily_issuance,
        29.4021 / sqrt(cum_validators) as validator_base_apr_raw,
        case
            when 29.4021 / sqrt(cum_validators) < 0.20
            then 29.4021 / sqrt(cum_validators)
            else 0.20
        end as validator_base_apr_viz
    from eth_staked_validators
    where time >= CAST('2020-12-01' as timestamp)
),

-- =============================================================================
-- STAKING METRICS (query_2981348)
-- =============================================================================
staking_metrics as (
    select
        c_issuance.time as time,
        c_network.block_success_rate as slot_utilization,
        c_issuance.cum_deposited_eth as eth2_count,
        c_issuance.cum_validators as validator_count,
        c_issuance.max_daily_issuance as max_issuance,
        c_issuance.max_daily_issuance * c_network.block_success_rate as approx_issuance,
        c_issuance.validator_base_apr_raw as unadjusted_base_yield,
        c_issuance.validator_base_apr_raw * c_network.block_success_rate as adjusted_base_yield,
        c_issuance.validator_base_apr_viz * c_network.block_success_rate as base_yield_viz_only
    from pos_issuance c_issuance
    inner join block_success_rate c_network on c_issuance.time = c_network.time
    where c_issuance.time > CAST('2022-09-15' as timestamp)
),

-- =============================================================================
-- ETH STAKING SUMMARY
-- =============================================================================
eth_staking_summary as (
    select
        c_fee.time as day,
        (1 + c_fee.total_priority_fees / c_staking.approx_issuance) * c_staking.adjusted_base_yield as total_yield,
        (c_fee.total_priority_fees / c_staking.approx_issuance) * c_staking.adjusted_base_yield as execution_yield,
        (1 + (c_fee.total_burn + c_fee.total_priority_fees) / c_staking.approx_issuance) * c_staking.adjusted_base_yield as burnless_yield,
        c_staking.approx_issuance - c_fee.total_burn as net_issuance,
        SUM(c_staking.approx_issuance - c_fee.total_burn)
            over (order by c_fee.time ROWS UNBOUNDED PRECEDING) as cumulative_issuance,
        c_staking.unadjusted_base_yield as consensus_yield
    from fee_data c_fee
    inner join staking_metrics c_staking on c_fee.time = c_staking.time
    where c_fee.time < date_trunc('day', NOW())
)

-- =============================================================================
-- OUTPUT
-- =============================================================================
select
    day,
    execution_yield + consensus_yield as staking_yield
from eth_staking_summary
order by day ASC
