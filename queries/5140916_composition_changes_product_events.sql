-- Query: multichain-composition-changes-product-events
-- Dune ID: 5140916
-- URL: https://dune.com/queries/5140916
-- Materialized View: dune.index_coop.result_multichain_composition_changes_product_events
-- Description: Composition changes and product events for all Index Coop tokens
-- Parameters: none
--
-- Columns: blockchain, minute, token_address, token_symbol, unit_supply, component, component_symbol, realunits, default_units, multiplier_ratio, component_balance, evt_type
-- Depends on: result_multichain_indexcoop_tokenlist (5140527), result_multichain_components_with_hardcoded_values (5140966)
--
-- KNOWN ISSUE: Arbitrum iBTC2x/iETH2x only show aArbUSDCn component, missing collateral (aArbWETH/aArbWBTC)
-- and debt (variableDebtArbUSDCn). Need to investigate if Arbitrum uses different event sources.

with
-- Define the time range for better performance
time_filter as (
    select
        timestamp '2020-09-09 00:00:00' as start_date,
        now() as end_date
),

-- First materialize tokens list with complete information
token_info as (
    select
        blockchain,
        contract_address,
        symbol,
        decimals,
        product_segment,
        composite,
        leverage,
        is_bridged,
        category,
        cast(end_date as date) as end_date
    from dune.index_coop.result_multichain_indexcoop_tokenlist -- multichain-indexcoop-tokenlist
    where blockchain in ('ethereum', 'arbitrum', 'base')
    and is_bridged = FALSE
),

-- For backward compatibility, maintain simpler token_addresses reference
token_addresses as (
    select
        blockchain,
        contract_address
    from token_info
),

-- Token metadata for all blockchain tokens (not just Index Coop tokens)
token_metadata as (
    select
        blockchain,
        contract_address,
        symbol,
        decimals
    from dune.index_coop.result_multichain_components_with_hardcoded_values -- multichain-components-with-hardcoded-values
    where blockchain in ('ethereum', 'arbitrum', 'base')
),

-- Combine position unit changes from both schemas to reduce joins
all_position_changes as (
    -- Default position changes combined from both schemas
    select
        t1.chain as blockchain,
        t1.evt_block_time as block_time,
        t1.evt_block_number as block_number,
        t1.evt_index,
        t1.evt_tx_hash,
        t1.contract_address as token_address,
        t1._component as component,
        cast(_realunit as int256) as units,
        date_trunc('minute', t1.evt_block_time) as minute
    from
    (
        select
            chain,
            evt_block_time,
            evt_block_number,
            evt_index,
            evt_tx_hash,
            contract_address,
            _component,
            _realunit
        from indexprotocol_multichain.settoken_evt_defaultpositionunitedited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)

        union all

        select
            chain,
            evt_block_time,
            evt_block_number,
            evt_index,
            evt_tx_hash,
            contract_address,
            _component,
            _realunit
        from setprotocol_v2_multichain.settoken_evt_defaultpositionunitedited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)
    ) t1
    inner join token_addresses q
        on t1.contract_address = q.contract_address
        and t1.chain = q.blockchain

    union all

    -- External position changes combined from both schemas
    select
        t1.chain as blockchain,
        t1.evt_block_time as block_time,
        t1.evt_block_number as block_number,
        t1.evt_index,
        t1.evt_tx_hash,
        t1.contract_address as token_address,
        t1._component as component,
        cast(_realunit as int256) as units,
        date_trunc('minute', t1.evt_block_time) as minute
    from
    (
        select
            chain,
            evt_block_time,
            evt_block_number,
            evt_index,
            evt_tx_hash,
            contract_address,
            _component,
            _realunit
        from indexprotocol_multichain.settoken_evt_externalpositionunitedited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)

        union all

        select
            chain,
            evt_block_time,
            evt_block_number,
            evt_index,
            evt_tx_hash,
            contract_address,
            _component,
            _realunit
        from setprotocol_v2_multichain.settoken_evt_externalpositionunitedited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)
    ) t1
    inner join token_addresses q
        on t1.contract_address = q.contract_address
        and t1.chain = q.blockchain

    union all

    -- Initial position setup combined from both schemas
    select
        t1.chain as blockchain,
        t1.call_block_time as block_time,
        t1.call_block_number as block_number,
        1 as evt_index,
        t1.call_tx_hash as evt_tx_hash,
        t1.output_0 as token_address,
        t.component,
        cast(t.units as int256) as units,
        date_trunc('minute', t1.call_block_time) as minute
    from
    (
        select
            chain,
            call_block_time,
            call_block_number,
            call_tx_hash,
            output_0,
            _components,
            _units
        from indexprotocol_multichain.settokencreator_call_create
        where chain in ('ethereum', 'arbitrum', 'base')
          and call_block_time >= (select start_date from time_filter)

        union all

        select
            chain,
            call_block_time,
            call_block_number,
            call_tx_hash,
            output_0,
            _components,
            _units
        from setprotocol_v2_multichain.settokencreator_call_create
        where chain in ('ethereum', 'arbitrum', 'base')
          and call_block_time >= (select start_date from time_filter)
    ) t1
    cross join unnest(_components, _units) as t(component, units)
    inner join token_addresses q
        on t1.output_0 = q.contract_address
        and t1.chain = q.blockchain
),

-- Use a single ranking CTE to get the latest changes and time ranges
ranked_position_changes as (
    select
        blockchain,
        minute,
        block_time,
        block_number,
        evt_index,
        token_address,
        component,
        units,
        row_number() over (
            partition by blockchain, token_address, component, minute
            order by block_number desc, evt_index desc
        ) as rn,
        lead(minute, 1, now()) over (
            partition by blockchain, token_address, component
            order by minute asc, block_number asc, evt_index asc
        ) as next_minute
    from all_position_changes
),

-- Skip intermediate CTEs and directly join with token metadata
position_with_metadata as (
    select
        p.blockchain,
        p.minute,
        p.block_time,
        p.block_number,
        p.evt_index,
        p.token_address,
        p.component,
        p.units,
        p.next_minute,
        coalesce(ti.symbol, tm.symbol) as symbol, -- Try Index Coop first, then general metadata
        coalesce(ti.decimals, tm.decimals) as decimals -- Try Index Coop first, then general metadata
    from ranked_position_changes p
    left join token_info ti on -- Index Coop tokens (small table - 41 rows)
        ti.blockchain = p.blockchain and
        ti.contract_address = p.component
    left join token_metadata tm on -- All blockchain tokens (large table - 2M+ rows)
        tm.blockchain = p.blockchain and
        tm.contract_address = p.component
    where p.rn = 1 -- Filter early to reduce joined rows
),

-- Combine multiplier changes from both schemas with efficient filtering
multiplier_changes as (
    select
        m.blockchain,
        date_trunc('minute', m.evt_block_time) as minute,
        m.contract_address as token_address,
        m._newmultiplier,
        m.evt_tx_hash,
        lead(date_trunc('minute', m.evt_block_time), 1, now()) over (
            partition by m.blockchain, m.contract_address
            order by m.evt_block_time asc
        ) as next_minute
    from (
        select
            evt_tx_hash,
            chain as blockchain,
            evt_block_time,
            _newmultiplier,
            contract_address
        from indexprotocol_multichain.settoken_evt_positionmultiplieredited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)

        union all

        select
            evt_tx_hash,
            chain as blockchain,
            evt_block_time,
            _newmultiplier,
            contract_address
        from setprotocol_v2_multichain.settoken_evt_positionmultiplieredited
        where chain in ('ethereum', 'arbitrum', 'base')
          and evt_block_time >= (select start_date from time_filter)
    ) m
    inner join token_addresses ta
        on m.contract_address = ta.contract_address
        and m.blockchain = ta.blockchain
),

-- Get all filtered components with their latest state
filtered_component_state as (
    select
        p.blockchain,
        p.minute as block_time,
        p.block_number,
        p.evt_index,
        p.component,
        p.token_address,
        p.units,
        p.symbol,
        p.decimals
    from position_with_metadata p
),

-- Join component state with unit values to create component_values
component_values as (
    select
        s.blockchain,
        s.block_time,
        s.block_number,
        s.evt_index,
        s.token_address,
        s.component,
        s.symbol,
        s.units,
        s.decimals
    from filtered_component_state s
),

-- Calculate rebalance events with proper handling of zero units
rebalance_events as (
    select
        cv.*,
        row_number() over (
            partition by blockchain, token_address, component, block_time
            order by block_time desc, block_number desc, evt_index desc
        ) as rnb,
        case
            when units = cast(0 as int256) and lag(units) over (
                partition by blockchain, token_address, component
                order by block_time
            ) > cast(0 as int256)
            then lead(block_time, 1, now()) over (
                partition by blockchain, token_address, component
                order by block_time asc, block_number asc, evt_index asc
            )
            else lead(block_time, 1, now()) over (
                partition by blockchain, token_address, component
                order by block_time asc, block_number asc, evt_index asc
            )
        end as next_time
    from component_values cv
),

-- Filter out tokens that have been delisted
filtered_positions as (
    select
        blockchain,
        date_trunc('minute', block_time) as minute,
        evt_index,
        token_address,
        component,
        symbol,
        units,
        decimals,
        rnb,
        date_trunc('minute', next_time) as next_minute
    from rebalance_events
    where rnb = 1
      and next_time is not null
),

-- ===== Beginning of mm_part logic restoration =====

-- Generate time series for multiplier and position changes
multiplier_position_timeline as (
    -- Position events
    select distinct
        blockchain,
        minute,
        token_address,
        'position' as evt_type
    from filtered_positions

    union all

    -- Multiplier events
    select
        blockchain,
        minute,
        token_address,
        'multiplier' as evt_type
    from multiplier_changes
),

-- Join timeline with multiplier data - improved version of your multiplier_ts
multiplier_values as (
    select
        mpt.blockchain,
        mpt.minute,
        mpt.token_address,
        mpt.evt_type,
        coalesce(m._newmultiplier, cast(power(10,18) as int256)) as multiplier,
        lead(mpt.evt_type) over (
            partition by mpt.blockchain, mpt.token_address
            order by mpt.minute
        ) as next_evt_type,
        dense_rank() over (
            partition by mpt.blockchain, mpt.token_address
            order by coalesce(m._newmultiplier, cast(power(10,18) as int256)) desc
        ) as rnb
    from multiplier_position_timeline mpt
    left join multiplier_changes m on
        m.blockchain = mpt.blockchain and
        m.token_address = mpt.token_address and
        m.minute <= mpt.minute and
        mpt.minute < m.next_minute
),

-- Calculate multiplier parts using your original logic
multiplier_segments as (
    select
        blockchain,
        minute,
        token_address,
        evt_type,
        next_evt_type,
        multiplier,
        rnb,
        -- This is the key mm_part logic that identifies position → multiplier transitions
        sum(case
            when evt_type = 'position' and next_evt_type = 'position' then 0
            when evt_type = 'position' and next_evt_type = 'multiplier' then 1
            when evt_type = 'multiplier' and next_evt_type = 'multiplier' then 0
            when evt_type = 'multiplier' and next_evt_type = 'position' then 0
            else 0
        end) over (
            partition by blockchain, token_address
            order by minute
        ) as mm_part
    from multiplier_values
),

-- Get initial multiplier for each segment using first_value
initial_multipliers as (
    select
        blockchain,
        minute,
        token_address,
        evt_type,
        next_evt_type,
        multiplier,
        rnb,
        mm_part,
        -- Get the first multiplier value in each segment
        first_value(multiplier) over (
            partition by blockchain, token_address, mm_part
            order by minute
        ) as old_multiplier
    from multiplier_segments
),

-- Handle the special case for position → multiplier transitions
adjusted_multipliers as (
    select
        blockchain,
        minute,
        token_address,
        evt_type,
        multiplier as new_multiplier,
        -- Critical logic: adjust old_multiplier for position → multiplier transitions
        case
            when evt_type = 'position' and next_evt_type = 'multiplier'
            then lag(old_multiplier) over (
                partition by blockchain, token_address, rnb
                order by minute
            )
            else old_multiplier
        end as old_multiplier_adjusted
    from initial_multipliers
),

-- Final multiplier analysis using the original quotient calculation
multiplier_analysis as (
    select
        blockchain,
        minute,
        token_address,
        evt_type,
        new_multiplier,
        cast(coalesce(
            cast(old_multiplier_adjusted as int256),
            cast(power(10,18) as int256)
        ) as int256) as old_multiplier,
        -- This is your original quotient calculation
        cast(new_multiplier as double) / cast(
            coalesce(
                cast(old_multiplier_adjusted as int256),
                cast(power(10,18) as int256)
            ) as double
        ) as multiplier_ratio,
        lead(minute, 1, now()) over (
            partition by blockchain, token_address
            order by minute
        ) as next_minute
    from adjusted_multipliers
),

-- ===== End of mm_part logic restoration =====

-- Efficiently process transfers with strong filters and pre-aggregation
supply_changes as (
    select
        et.blockchain,
        date_trunc('minute', et.evt_block_time) as minute,
        et.contract_address as token_address,
        sum(case
            when et."from" = 0x0000000000000000000000000000000000000000 then cast(et.value as double)
            when et."to" = 0x0000000000000000000000000000000000000000 then -cast(et.value as double)
            else 0
        end) as supply_change
    from evms.erc20_transfers et
    inner join (
        select distinct
            blockchain,
            token_address
        from multiplier_analysis
    ) tt
    on et.blockchain = tt.blockchain and
       et.contract_address = tt.token_address
    where et.blockchain in ('ethereum', 'arbitrum', 'base')
      and (et."from" = 0x0000000000000000000000000000000000000000 or
           et."to" = 0x0000000000000000000000000000000000000000)
      and et.evt_block_time >= (select start_date from time_filter)
    group by 1, 2, 3
),

-- Enhanced supply calculation with time-series
supply_with_metadata as (
    select
        s.blockchain,
        s.minute,
        s.token_address,
        coalesce(ti.symbol, tm.symbol) as symbol,
        coalesce(ti.decimals, tm.decimals) as decimals,
        sum(s.supply_change / power(10, coalesce(ti.decimals, tm.decimals, 18))) over (
            partition by s.blockchain, s.token_address
            order by s.minute
        ) as unit_supply,
        lead(s.minute, 1, now()) over (
            partition by s.blockchain, s.token_address
            order by s.minute
        ) as next_minute
    from supply_changes s
    left join token_info ti on -- Index Coop tokens (small table - 41 rows)
        ti.blockchain = s.blockchain and
        ti.contract_address = s.token_address
    left join token_metadata tm on -- All blockchain tokens (large table - 2M+ rows)
        tm.blockchain = s.blockchain and
        tm.contract_address = s.token_address
),

-- Combine data keeping the original range-based joins to maintain data completeness
combined_data as (
    select
        coalesce(s.blockchain, m.blockchain) as blockchain,
        coalesce(s.minute, m.minute) as minute,
        coalesce(s.token_address, m.token_address) as token_address,
        s.symbol as token_symbol,
        s.unit_supply,
        s.next_minute as supply_next_minute,
        m.evt_type,
        m.multiplier_ratio,
        m.next_minute as multiplier_next_minute
    from supply_with_metadata s
    full outer join multiplier_analysis m on
        s.blockchain = m.blockchain and
        s.token_address = m.token_address and
        -- Use the original range-based join to maintain data completeness
        ((s.minute <= m.minute and m.minute < s.next_minute) or
         (m.minute <= s.minute and s.minute < m.next_minute))
),

-- Get token symbols for set token products
set_token_info as (
    select
        tokens.blockchain,
        tokens.contract_address,
        coalesce(ti.symbol, tm.symbol) as symbol
    from (
        select distinct
            blockchain,
            contract_address
        from (
            select blockchain, token_address as contract_address from combined_data
            union
            select blockchain, contract_address from token_info
        ) combined_addresses
    ) tokens
    left join token_info ti on -- Index Coop tokens (small table - 41 rows)
        tokens.blockchain = ti.blockchain and
        tokens.contract_address = ti.contract_address
    left join token_metadata tm on -- All blockchain tokens (large table - 2M+ rows)
        tokens.blockchain = tm.blockchain and
        tokens.contract_address = tm.contract_address
),

-- Build preliminary result with range-based joins to ensure complete data
preliminary_result as (
    select
        coalesce(c.blockchain, p.blockchain) as blockchain,
        coalesce(c.minute, p.minute) as minute,
        coalesce(c.token_address, p.token_address) as token_address,
        coalesce(c.token_symbol, sti.symbol) as token_symbol,
        c.unit_supply,
        p.component,
        coalesce(p.symbol, sti.symbol) as component_symbol,
        p.units as realunits,
        case
            when p.decimals is not null then cast(p.units / power(10, p.decimals) as double)
            else null
        end as default_units,
        c.multiplier_ratio,
        -- Component balance calculation respecting NULL values
        case
            when p.decimals is not null and c.unit_supply is not null then
                cast(p.units / power(10, p.decimals) as double) *
                coalesce(c.multiplier_ratio, 1) *
                c.unit_supply
            else null
        end as component_balance,
        c.evt_type
    from combined_data c
    full outer join filtered_positions p on
        c.blockchain = p.blockchain and
        c.token_address = p.token_address and
        -- Use the original range conditions to ensure data completeness
        ((p.minute <= c.minute and c.minute < p.next_minute) or
         (c.minute <= p.minute and p.minute < c.supply_next_minute))
    left join set_token_info sti on
        sti.blockchain = coalesce(c.blockchain, p.blockchain) and
        sti.contract_address = coalesce(c.token_address, p.token_address)
)

-- Final result using window functions to get the latest data per minute
select
    blockchain,
    minute,
    token_address,
    token_symbol,
    unit_supply,
    component,
    component_symbol,
    realunits,
    default_units,
    multiplier_ratio,
    component_balance,
    evt_type
from (
    select
        blockchain,
        minute,
        token_address,
        token_symbol,
        unit_supply,
        component,
        component_symbol,
        realunits,
        default_units,
        multiplier_ratio,
        component_balance,
        evt_type,
        -- Rank records within each minute to get the latest one
        row_number() over (
            partition by blockchain, minute, token_address, component
            order by
                -- Prioritize non-null values
                case when unit_supply is not null then 0 else 1 end,
                case when realunits is not null then 0 else 1 end,
                case when multiplier_ratio is not null then 0 else 1 end,
                -- If there are still ties, use the highest values
                coalesce(unit_supply, 0) desc,
                coalesce(multiplier_ratio, 0) desc
        ) as rn
    from preliminary_result
    -- Filter out specific token-component combinations while keeping other combinations
    where not (
        token_address in (
            0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd, -- ETH2x-FLI
            0x0b498ff89709d3838a063f1dfa463091f9801c2b -- BTC2x-FLI
        )
        and component = 0xc00e94cb662c3520282e6f5717214004a7f26888 -- COMP
    )
) ranked_results
where rn = 1
order by blockchain, minute desc
