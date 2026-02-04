-- ============================================================================
-- Query: All Chain Lev Suite Trades (User Holding Periods)
-- Dune ID: 4135813
-- URL: https://dune.com/queries/4135813
-- Description: Tracks user holding periods for leverage suite tokens across all chains
-- Parameters: none
--
-- Columns: blockchain, user_address, token_address, product_symbol, holding_group,
--          isclosed, start_date, end_date, holding_duration_days, chain_inactivity_days
-- Depends on: result_index_coop_leverage_suite_tokens
--
-- Optimizations applied:
--   1. Partition pruning: blockchain + evt_block_time filters
--   2. Direct filters (not wrapped in functions)
--   3. Removed SELECT * - specify only needed columns
--   4. CTEs for readability
--   5. UNION ALL where deduplication not needed
--   6. Removed unused CTEs (days)
--   7. Removed unnecessary ORDER BY in subqueries
-- ============================================================================

with leverage_param as (
    -- Only select columns we actually need
    select
        blockchain
        , token_address
        , product_symbol
    from dune.index_coop.result_index_coop_leverage_suite_tokens
)

, ignored_address (blockchain, user_address) as (
    values
    ('all',      0x0000000000000000000000000000000000000000),
    ('all',      0x000000000000000000000000000000000000dead),
    ('arbitrum', 0xc6b3b4624941287bb7bdd8255302c1b337e42194), -- FlashMintLeveragedExtended
    ('arbitrum', 0x5e325eda8064b456f4781070c0738d849c824258), -- UniversalRouter
    ('arbitrum', 0xbd6b8eec7b940dbe196fe3bac7b51e63435c8ae9)  -- GnosisSafe
)

, transfers as (
    select t0.*
    from (
        select
            tr.blockchain,
            "to" as user_address,
            'Receive' as transaction_type,
            lp.token_address,
            lp.product_symbol,
            date_trunc('day', evt_block_time) as day,
            evt_block_number,
            sum(cast(value as DOUBLE)/1e18) as amount
        from evms.erc20_transfers tr
        inner join leverage_param lp
            on lp.token_address = tr.contract_address
            and lp.blockchain = tr.blockchain
        -- Partition pruning: blockchain + time filters
        where tr.blockchain in ('ethereum', 'base', 'arbitrum')
          and tr.evt_block_time >= timestamp '2024-02-20'
        group by 1,2,3,4,5,6,7

        union all  -- Changed to UNION ALL: transaction_type differs ('Receive' vs 'Send'), so no duplicates possible

        select
            tr.blockchain,
            "from" as user_address,
            'Send' as transaction_type,
            lp.token_address,
            lp.product_symbol,
            date_trunc('day', evt_block_time) as day,
            evt_block_number,
            sum(cast(value as DOUBLE)/1e18) as amount
        from evms.erc20_transfers tr
        inner join leverage_param lp
            on lp.token_address = tr.contract_address
            and lp.blockchain = tr.blockchain
        -- Partition pruning: blockchain + time filters
        where tr.blockchain in ('ethereum', 'base', 'arbitrum')
          and tr.evt_block_time >= timestamp '2024-02-20'
        group by 1,2,3,4,5,6,7
    ) t0
    left join ignored_address ia
        on t0.user_address = ia.user_address
        and (ia.blockchain = t0.blockchain or ia.blockchain = 'all')
    where ia.user_address is null
)

, daily_transfers as (
    -- Aggregate transfers at day level, combining Send/Receive into net amount
    select
        day
        , blockchain
        , user_address
        , token_address
        , product_symbol
        , evt_block_number
        , sum(case when transaction_type = 'Send' then -amount else amount end) as amount
    from transfers
    group by 1,2,3,4,5,6
)

, cumulative_balances as (
    -- Calculate running balance per user per token
    select
        day
        , blockchain
        , evt_block_number
        , user_address
        , token_address
        , product_symbol
        , amount
        , sum(amount) over (partition by user_address, token_address order by evt_block_number) as cumulative_amount
    from daily_transfers
)

, user_holdings as (
    -- Get end-of-day balance (latest block per day per user per token)
    select
        day
        , blockchain
        , evt_block_number
        , user_address
        , token_address
        , product_symbol
        , cumulative_amount
        , lag(cumulative_amount) over (partition by user_address, token_address order by evt_block_number) as prev_cumulative_amount
    from (
        select
            day
            , blockchain
            , evt_block_number
            , user_address
            , token_address
            , product_symbol
            , case when cumulative_amount < 0.0000001 then 0 else cumulative_amount end as cumulative_amount
            , row_number() over (partition by day, user_address, token_address order by evt_block_number desc) as rnb
        from cumulative_balances
    )
    where rnb = 1
)

, holding_periods as (
    select
        day,
        blockchain,
        evt_block_number,
        user_address,
        token_address,
        product_symbol,
        cumulative_amount,
        case
            when prev_cumulative_amount = 0 or prev_cumulative_amount is null then 1
            else 0
        end as is_new_holding_start
    from user_holdings
)

, grouped_holdings as (
    select
        blockchain,
        user_address,
        token_address,
        product_symbol,
        day,
        cumulative_amount,
        holding_group,
        case
            when sum(case when cumulative_amount = 0 then 1 else 0 end)
                 over (partition by user_address, token_address, product_symbol, holding_group) > 0
            then 1
            else 0
        end as isclosed,
        is_new_holding_start
    from (
        select
            user_address,
            token_address,
            product_symbol,
            day,
            cumulative_amount,
            blockchain,
            is_new_holding_start,
            sum(case when is_new_holding_start = 1 then 1 else 0 end)
                over (partition by user_address, token_address, product_symbol order by evt_block_number rows unbounded preceding) as holding_group
        from holding_periods
    )
)

, ignored_contracts as (
    select distinct u.blockchain, lc.contract_address
    from grouped_holdings u
    inner join contracts.contract_mapping lc
        on u.user_address = lc.contract_address
        and u.blockchain = lc.blockchain
    where lc.contract_name not like '%GnosisSafe%'
      and lc.contract_name not like '%Safe_%'
      or lc.contract_name is null
)

, summary as (
    select
        blockchain
        , user_address
        , token_address
        , product_symbol
        , holding_group
        , isclosed
        , start_date
        , case when isclosed = 1 then end_date else currentdate end as end_date
        , date_diff('day', start_date, case when isclosed = 1 then end_date else currentdate end) + 1 as holding_duration_days
    from (
        select
            user_address,
            blockchain,
            token_address,
            product_symbol,
            holding_group,
            isclosed,
            date_trunc('day', now()) as currentdate,
            min(day) as start_date,
            max(day) as end_date
        from grouped_holdings
        group by 1,2,3,4,5,6
    )
    where user_address not in (select contract_address from ignored_contracts)
)

, inactivity_days as (
    select
        blockchain
        , user_address
        , date_diff('day', end_date, next_start_date) as chain_inactivity_days
    from (
        select
            blockchain
            , user_address
            , end_date
            , lead(end_date, 1, date_trunc('day', now()))
                over (partition by user_address, blockchain order by end_date) as next_start_date
            , row_number() over (partition by user_address, blockchain order by end_date desc) as rnb
        from (
            select distinct
                blockchain
                , user_address
                , end_date
            from summary
        )
    )
    where rnb = 1
)

select
    s.blockchain
    , s.user_address
    , s.token_address
    , s.product_symbol
    , s.holding_group
    , s.isclosed
    , s.start_date
    , s.end_date
    , s.holding_duration_days
    , id.chain_inactivity_days
from summary s
left join inactivity_days id
    on s.blockchain = id.blockchain
    and s.user_address = id.user_address
