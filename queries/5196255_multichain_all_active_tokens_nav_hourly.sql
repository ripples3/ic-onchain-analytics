-- ============================================================================
-- FINAL OPTIMIZED: multichain-all-active-tokens-nav-hourly
-- Dune ID: 5196255
-- URL: https://dune.com/queries/5196255
-- Materialized View: dune.index_coop.result_multichain_all_active_tokens_nav_hourly
-- Description: Hourly NAV calculation for all active Index Coop tokens
-- Parameters: none
--
-- Columns: hour, blockchain, token_address, token_symbol, unit_supply, collateral, debt, tvl, nav, leverage_ratio
-- Depends on: result_multichain_indexcoop_tokenlist (5140527), result_multichain_components_with_hardcoded_values (5140966), result_multichain_composition_changes_product_events
--
-- Dune Optimization Docs Compliance:
--   1. ✅ prices.hour: blockchain + timestamp filters (prices.usd is LEGACY - no new tokens)
--   2. ✅ Base tokens (uSOL, uSUI, uXRP) have direct prices in prices.hour - no cross-chain lookup needed
--   3. ✅ utils.hours: timestamp filter
--   4. ✅ Direct filters (not wrapped in functions)
--   5. ✅ No SELECT *
--   6. ✅ UNION ALL where safe
--
-- Start dates per chain:
--   - ethereum: 2022-03-20 16:00
--   - arbitrum: 2024-05-22 22:00
--   - base:     2024-08-28 02:00
-- ============================================================================

with

-- Filter for indexcoop_tokens by product segment
indexcoop_tokens as (
    select
        blockchain
        , contract_address
        , symbol
        , decimals
        , product_segment
        , end_date
    from dune.index_coop.result_multichain_indexcoop_tokenlist
    where (
        product_segment in ('earn', 'trade')
        and contract_address not in (
            0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd,  -- ETH2x-FLI
            0x0b498ff89709d3838a063f1dfa463091f9801c2b   -- BTC2x-FLI
        )
        and blockchain in ('arbitrum', 'base', 'ethereum')
    )
    or (
        symbol in ('MVI', 'DPI', 'mhyETH')
        and blockchain = 'ethereum'
    )
)

-- Get distinct components from composition changes
, distinct_components as (
    select distinct
        e.blockchain
        , e.component
        , e.component_symbol
    from dune.index_coop.result_multichain_composition_changes_product_events e
    inner join indexcoop_tokens lt
        on e.blockchain = lt.blockchain
        and e.token_address = lt.contract_address
)

-- Component mapping using 5140966 materialized view
, component_mapping as (
    select
        dc.blockchain
        , dc.component
        , dc.component_symbol
        , cm.price_address  -- underlying token address for price lookup
        , cm.base_symbol
    from distinct_components dc
    inner join dune.index_coop.result_multichain_components_with_hardcoded_values cm  -- query_5140966
        on dc.component = cm.contract_address
        and dc.blockchain = cm.blockchain
)

-- Pre-compute required price addresses per blockchain
, required_prices as (
    select distinct blockchain, price_address as contract_address, base_symbol
    from component_mapping
)

-- ============================================================================
-- PRICES: Using prices.hour (prices.usd is LEGACY - no new tokens added)
-- ============================================================================
, prices as (
    -- Ethereum prices (from 2022-03-20)
    select
        p.timestamp as hour
        , p.symbol
        , p.contract_address
        , p.blockchain
        , p.price
    from prices.hour p
    inner join required_prices rp
        on rp.contract_address = p.contract_address
        and rp.blockchain = p.blockchain
    where p.blockchain = 'ethereum'
    and p.timestamp >= timestamp '2022-03-20 16:00'

    union all

    -- Arbitrum prices (from 2024-05-22)
    select
        p.timestamp as hour
        , p.symbol
        , p.contract_address
        , p.blockchain
        , p.price
    from prices.hour p
    inner join required_prices rp
        on rp.contract_address = p.contract_address
        and rp.blockchain = p.blockchain
    where p.blockchain = 'arbitrum'
    and p.timestamp >= timestamp '2024-05-22 22:00'

    union all

    -- Base prices (from 2024-08-28)
    -- Note: uSOL, uSUI, uXRP have direct prices in prices.hour on Base chain
    select
        p.timestamp as hour
        , p.symbol
        , p.contract_address
        , p.blockchain
        , p.price
    from prices.hour p
    inner join required_prices rp
        on rp.contract_address = p.contract_address
        and rp.blockchain = p.blockchain
    where p.blockchain = 'base'
    and p.timestamp >= timestamp '2024-08-28 02:00'
)

-- Get latest data per hour from composition changes
, latest_hourly_data as (
    select
        blockchain
        , hour
        , token_address
        , token_symbol
        , component
        , component_symbol
        , unit_supply
        , component_balance
    from (
        select
            e.blockchain
            , e.token_address
            , e.token_symbol
            , e.component
            , e.component_symbol
            , e.unit_supply
            , date_trunc('hour', e.minute) as hour
            , e.component_balance
            , row_number() over (
                partition by
                    e.blockchain
                    , e.token_address
                    , e.component
                    , date_trunc('hour', e.minute)
                order by e.minute desc
            ) as rn
        from dune.index_coop.result_multichain_composition_changes_product_events e
        inner join indexcoop_tokens lt
            on e.blockchain = lt.blockchain
            and e.token_address = lt.contract_address
    )
    where rn = 1
)

-- Track balance changes and determine valid ranges
, valid_components as (
    select
        blockchain
        , token_address
        , token_symbol
        , component
        , component_symbol
        , hour
        , unit_supply
        , component_balance
        , case
            when component_balance = 0 then hour
            else coalesce(next_change_hour, now())
          end as next_hour
    from (
        select
            blockchain
            , token_address
            , token_symbol
            , component
            , component_symbol
            , hour
            , unit_supply
            , component_balance
            , lag(component_balance, 1, 0) over (
                partition by blockchain, token_address, component
                order by hour
            ) as prev_balance
            , lead(hour, 1) over (
                partition by blockchain, token_address, component
                order by hour
            ) as next_change_hour
        from latest_hourly_data
    )
    where component_balance != 0
    or (component_balance = 0 and prev_balance != 0)
)

-- ============================================================================
-- GAP-FILL: Join with utils.hours (with timestamp filter per chain)
-- ============================================================================
, all_component as (
    -- Ethereum (from 2022-03-20)
    select
        h.timestamp as hour
        , vc.blockchain
        , vc.token_address
        , vc.token_symbol
        , vc.component
        , vc.component_symbol
        , vc.unit_supply
        , vc.component_balance
    from utils.hours h
    inner join valid_components vc
        on vc.hour <= h.timestamp
        and h.timestamp < vc.next_hour
        and vc.component_balance != 0
    where vc.blockchain = 'ethereum'
    and h.timestamp >= timestamp '2022-03-20 16:00'

    union all

    -- Arbitrum (from 2024-05-22)
    select
        h.timestamp as hour
        , vc.blockchain
        , vc.token_address
        , vc.token_symbol
        , vc.component
        , vc.component_symbol
        , vc.unit_supply
        , vc.component_balance
    from utils.hours h
    inner join valid_components vc
        on vc.hour <= h.timestamp
        and h.timestamp < vc.next_hour
        and vc.component_balance != 0
    where vc.blockchain = 'arbitrum'
    and h.timestamp >= timestamp '2024-05-22 22:00'

    union all

    -- Base (from 2024-08-28)
    select
        h.timestamp as hour
        , vc.blockchain
        , vc.token_address
        , vc.token_symbol
        , vc.component
        , vc.component_symbol
        , vc.unit_supply
        , vc.component_balance
    from utils.hours h
    inner join valid_components vc
        on vc.hour <= h.timestamp
        and h.timestamp < vc.next_hour
        and vc.component_balance != 0
    where vc.blockchain = 'base'
    and h.timestamp >= timestamp '2024-08-28 02:00'
)

-- ============================================================================
-- PASS 1: Price regular tokens (components have prices in prices.hour)
-- Excludes wrapper tokens (ETH2XW, BTC2XW) whose components are other Index tokens
-- ============================================================================
, wrapper_tokens as (
    select contract_address, blockchain
    from (values
        (0xBFb2E2b1790E98779CF78Ab0F045075BFd0A6be5, 'ethereum'),  -- ETH2XW
        (0x35D782DAb840A64D22A8109d1CDe0936e7305858, 'ethereum')   -- BTC2XW
    ) as t(contract_address, blockchain)
)

-- Apply component mapping for price lookup (pass 1: non-wrapper tokens only)
, component_with_prices as (
    select
        ac.hour
        , ac.blockchain
        , ac.token_address
        , ac.token_symbol
        , ac.component
        , ac.component_symbol
        , ac.unit_supply
        , ac.component_balance
        , ac.component_balance * p.price as component_value
    from all_component ac
    inner join component_mapping cm
        on ac.blockchain = cm.blockchain
        and ac.component = cm.component
    inner join prices p
        on ac.hour = p.hour
        and p.blockchain = ac.blockchain
        and p.contract_address = cm.price_address
    where not exists (
        select 1 from wrapper_tokens wt
        where wt.contract_address = ac.token_address
        and wt.blockchain = ac.blockchain
    )
)

-- Calculate token metrics (pass 1: includes ETH2X, BTC2X NAV)
, token_metrics as (
    select
        hour
        , blockchain
        , token_address
        , token_symbol
        , max(unit_supply) as unit_supply
        , case
            when max(unit_supply) > 0 then
                sum(case when component_value > 0 then component_value else 0 end) / max(unit_supply)
            else null
          end as collateral
        , case
            when max(unit_supply) > 0 then
                sum(case when component_value < 0 then component_value else 0 end) / max(unit_supply)
            else null
          end as debt
        , sum(component_value) as tvl
        , case
            when max(unit_supply) > 0 then sum(component_value) / max(unit_supply)
            else null
          end as nav
    from component_with_prices
    group by 1, 2, 3, 4
)

-- ============================================================================
-- PASS 2: Price wrapper tokens using pass 1 NAV as component price
-- ETH2XW component = ETH2X, BTC2XW component = BTC2X
-- ============================================================================
, wrapper_component_with_prices as (
    select
        ac.hour
        , ac.blockchain
        , ac.token_address
        , ac.token_symbol
        , ac.component
        , ac.component_symbol
        , ac.unit_supply
        , ac.component_balance
        , ac.component_balance * tm.nav as component_value
    from all_component ac
    inner join wrapper_tokens wt
        on wt.contract_address = ac.token_address
        and wt.blockchain = ac.blockchain
    inner join token_metrics tm
        on tm.token_address = ac.component
        and tm.blockchain = ac.blockchain
        and tm.hour = ac.hour
)

, wrapper_token_metrics as (
    select
        hour
        , blockchain
        , token_address
        , token_symbol
        , max(unit_supply) as unit_supply
        , case
            when max(unit_supply) > 0 then
                sum(case when component_value > 0 then component_value else 0 end) / max(unit_supply)
            else null
          end as collateral
        , case
            when max(unit_supply) > 0 then
                sum(case when component_value < 0 then component_value else 0 end) / max(unit_supply)
            else null
          end as debt
        , sum(component_value) as tvl
        , case
            when max(unit_supply) > 0 then sum(component_value) / max(unit_supply)
            else null
          end as nav
    from wrapper_component_with_prices
    group by 1, 2, 3, 4
)

-- ============================================================================
-- FINAL: Combine pass 1 and pass 2 with leverage ratio
-- ============================================================================
, all_token_metrics as (
    select * from token_metrics
    union all
    select * from wrapper_token_metrics
)

-- Final result with leverage ratio
select
    hour
    , blockchain
    , token_address
    , token_symbol
    , unit_supply
    , collateral
    , debt
    , tvl
    , nav
    , case
        when unit_supply is null or unit_supply = 0 then null
        when coalesce(debt, 0) = 0 then 1.0
        when (collateral + debt) = 0 then null
        else collateral / (collateral + debt)
      end as leverage_ratio
from all_token_metrics
