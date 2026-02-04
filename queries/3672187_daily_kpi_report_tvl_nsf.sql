-- ============================================================================
-- Query: Daily KPI Report - TVL & NSF
-- Dune ID: 3672187
-- URL: https://dune.com/queries/3672187
-- Description: Daily KPI report with TVL, NSF, revenue metrics for all products
-- Parameters: none
--
-- Columns: day, symbol, symbol_chain, tvl, tvl_change_usd, tvl_change, nsf, nsf_change,
--          revenue_7d_avg_annualized, revenue_30d_avg_annualized, price, price_change
-- Depends on: result_index_coop_product_core_kpi_daily
--
-- Filters:
--   - Excludes sPrtHyETH, prtHyETH, dsETH, ic21, gtcETH, cdETI
--   - Only includes rows where price (NAV) is not null
--
-- Fixes:
--   - Window functions partition by symbol AND blockchain (not just symbol)
--   - Single grand total row (not per-symbol totals)
--
-- ============================================================================

with

all_data as (
    select
        day
        , symbol
        , blockchain
        , symbol || ' | ' || blockchain as symbol_chain
        , price
        , price / lag(price, 1) over (partition by symbol, blockchain order by day) - 1 as price_change
        , tvl
        , tvl - lag(tvl, 1) over (partition by symbol, blockchain order by day) as tvl_change_usd
        , tvl / lag(tvl, 1) over (partition by symbol, blockchain order by day) - 1 as tvl_change
        , lag(tvl, 1) over (partition by symbol, blockchain order by day) as old_tvl
        , lag(tvl, 7) over (partition by symbol, blockchain order by day) as old_tvl_7d
        , sum(nsf) over (partition by symbol, blockchain order by day rows between 6 preceding and current row) as nsf_7_day
        , nsf
        , round(sum(nsf) over (partition by symbol, blockchain order by day rows between 6 preceding and current row)
            / nullif(lag(tvl, 7) over (partition by symbol, blockchain order by day), 0), 4) as nsf_change
        , revenue
        , round(avg(revenue) over (partition by symbol, blockchain order by day rows between 6 preceding and current row) * 365, 0) as revenue_7d_avg_annualized
        , round(avg(revenue) over (partition by symbol, blockchain order by day rows between 29 preceding and current row) * 365, 0) as revenue_30d_avg_annualized
    from dune.index_coop.result_index_coop_product_core_kpi_daily
    where symbol not in ('sPrtHyETH', 'prtHyETH')
    and price is not null  -- Only include rows with valid NAV
)

-- Single grand total (not per-symbol)
, grand_total as (
    select
        day
        , 'Total' as symbol
        , 'all' as blockchain
        , 'Total | all' as symbol_chain
        , null as price
        , null as price_change
        , sum(tvl) as tvl
        , sum(tvl_change_usd) as tvl_change_usd
        , sum(tvl) / nullif(sum(old_tvl), 0) - 1 as tvl_change
        , sum(old_tvl) as old_tvl
        , sum(old_tvl_7d) as old_tvl_7d
        , sum(nsf_7_day) as nsf_7_day
        , sum(nsf) as nsf
        , round(sum(nsf_7_day) / nullif(sum(old_tvl_7d), 0), 4) as nsf_change
        , sum(revenue) as revenue
        , sum(revenue_7d_avg_annualized) as revenue_7d_avg_annualized
        , sum(revenue_30d_avg_annualized) as revenue_30d_avg_annualized
    from all_data
    group by 1
)

select
    day
    , symbol
    , symbol_chain
    , tvl
    , tvl_change_usd
    , tvl_change
    , nsf
    , nsf_change
    , revenue_7d_avg_annualized
    , revenue_30d_avg_annualized
    , price
    , price_change
from all_data
where day = (select max(day) from all_data) - interval '1' day
and symbol not in ('dsETH', 'ic21', 'gtcETH', 'cdETI')

union all

select
    day
    , symbol
    , symbol_chain
    , tvl
    , tvl_change_usd
    , tvl_change
    , nsf
    , nsf_change
    , revenue_7d_avg_annualized
    , revenue_30d_avg_annualized
    , price
    , price_change
from grand_total
where day = (select max(day) from all_data) - interval '1' day

order by tvl desc
