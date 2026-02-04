-- Query: latest-open-exposure-by-asset
-- Dune ID: 5298403
-- URL: https://dune.com/queries/5298403
-- Description: Latest open exposure by asset for earn, trade, and strategy products
-- Parameters: {{End Date:}}, {{Trailing Days:}}
--
-- Columns: day, blockchain, token_address, token_symbol, symbol_chain, product_segment, unit_supply, tvl, open_exposure, unit_supply_change, unit_supply_pct_change, nav, leverage_ratio, row_type
-- Depends on: result_multichain_indexcoop_tokenlist (5140527), result_multichain_all_active_tokens_nav_hourly (5196255)

with

-- Filter for indexcoop_tokens by product segment
indexcoop_tokens as (
select
    blockchain
    , contract_address
    , symbol
    , product_segment
from dune.index_coop.result_multichain_indexcoop_tokenlist -- query_5140527
where (
    -- Earn products
    (product_segment = 'earn'
     and symbol in ('icETH', 'wstETH15x')
     and blockchain in ('arbitrum', 'base', 'ethereum'))
    or
    -- Trade products (exclude deprecated FLI tokens)
    (product_segment = 'trade'
     and contract_address not in (
         0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd,  -- ETH2x-FLI
         0x0b498ff89709d3838a063f1dfa463091f9801c2b   -- BTC2x-FLI
     )
     and blockchain in ('arbitrum', 'base', 'ethereum'))
    or
    -- Specific strategy symbols on Ethereum
    (symbol in ('DPI', 'MVI', 'mhyETH')
     and blockchain = 'ethereum')
)
)

-- Get the latest data point for each day
, daily_latest as (
select
    date_trunc('day', te.hour) as day
    , te.blockchain
    , te.token_address
    , te.token_symbol
    , it.product_segment
    , te.unit_supply
    , te.tvl
    , case
        when te.leverage_ratio > 0 then te.tvl * te.leverage_ratio
        else te.tvl
      end as open_exposure
    , te.nav
    , te.leverage_ratio
    , row_number() over (
        partition by date_trunc('day', te.hour), te.blockchain, te.token_address
        order by te.hour desc
      ) as rn
from dune.index_coop.result_multichain_all_active_tokens_nav_hourly te -- query_5196255
inner join indexcoop_tokens it
    on it.contract_address = te.token_address
    and it.blockchain = te.blockchain
)

-- Select only the latest record for each day
, daily_values as (
select
    day
    , blockchain
    , token_address
    , token_symbol
    , product_segment
    , unit_supply
    , tvl
    , open_exposure
    , nav
    , leverage_ratio
from daily_latest
where rn = 1
)

-- Calculate day-over-day changes
, daily_with_changes as (
select
    day
    , blockchain
    , token_address
    , token_symbol
    , product_segment
    , unit_supply
    , tvl
    , open_exposure
    , nav
    , leverage_ratio
    , unit_supply - lag(unit_supply, 1) over (
        partition by blockchain, token_address
        order by day
      ) as unit_supply_change
    , case
        when lag(unit_supply, 1) over (
            partition by blockchain, token_address
            order by day
          ) > 0 then
            (unit_supply - lag(unit_supply, 1) over (
                partition by blockchain, token_address
                order by day
              )) / lag(unit_supply, 1) over (
                partition by blockchain, token_address
                order by day
              ) * 100
        else null
      end as unit_supply_pct_change
from daily_values
)

-- Get the maximum date within parameter range
, max_date as (
select max(day) as latest_date
from daily_with_changes
where day > date_trunc('day', least(timestamp '{{End Date:}}', now())) - interval '{{Trailing Days:}}' day
and day <= date_trunc('day', least(timestamp '{{End Date:}}', now()))
)

-- Final output
select
    day
    , blockchain
    , token_address
    , token_symbol
    , concat(
        token_symbol, ' | ',
        case
          when blockchain = 'base' then upper(blockchain)
          else upper(substr(blockchain, 1, 3))
        end
      ) as symbol_chain
    , product_segment
    , unit_supply
    , tvl
    , open_exposure
    , unit_supply_change
    , unit_supply_pct_change
    , nav
    , leverage_ratio
    , 'individual' as row_type
from daily_with_changes
cross join max_date
where day = max_date.latest_date
order by
    blockchain
    , token_symbol
