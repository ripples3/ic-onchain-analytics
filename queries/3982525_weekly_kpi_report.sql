-- Query: weekly-kpi-report
-- Dune ID: 3982525
-- URL: https://dune.com/queries/3982525
-- Description: Weekly KPI report with TVL, NSF, revenue metrics
-- Parameters: none
--
-- Columns: symbol_chain, tvl, tvl_change_usd, tvl_change, nsf_7day_change, nsf, nsf_change, revenue_7d_avg_annualized, revenue_30d_avg_annualized, mr_rev, stream_rev, total_rev, stream_share_pct
-- Depends on: query_3668275 (product core KPIs), query_5140527 (tokenlist), query_2364999 (unit supply), query_2621012 (fee structure), query_2878827 (fee split)

with

-- ============================================================================
-- FLI TOKENS (top-level so accessible by all CTEs)
-- ============================================================================
fli_tokens as (
    select
        'ethereum' as blockchain
        , contract_address
        , symbol
    from (values
        (0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd, 'ETH2x-FLI'),
        (0x0b498ff89709d3838a063f1dfa463091f9801c2b, 'BTC2x-FLI')
    ) as t(contract_address, symbol)
)

-- FLI NAV from result_fli_token_nav_lr (hourly) -> daily average
, fli_nav_daily as (
    select
        date_trunc('day', hour) as day
        , address as token_address
        , symbol
        , avg(price) as price
    from dune.index_coop.result_fli_token_nav_lr
    where hour >= date_trunc('day', now()) - interval '35' day
    group by 1, 2, 3
)

, fli_revenue_daily as (
    select
        s.day
        , t.blockchain
        , t.symbol
        , concat(t.symbol, '|', t.blockchain) as symbol_chain
        , p.price as nav
        , (f.issue_fee * coalesce(s.issue_units, 0) * p.price) + (f.redeem_fee * abs(coalesce(s.redeem_units, 0)) * p.price) as mr_rev
        , f.streaming_fee / 365 * coalesce(s.unit_supply, 0) * p.price as stream_rev
    from query_2364999 s
    inner join fli_tokens t on s.address = t.contract_address and s.blockchain = t.blockchain
    left join fli_nav_daily p on p.token_address = t.contract_address and p.day = s.day
    left join query_2621012 f on f.day = s.day and f.token_address = s.address and f.blockchain = s.blockchain
    where s.day >= date_trunc('day', now()) - interval '35' day
    and p.price is not null
)

, fli_revenue as (
    select
        day
        , blockchain
        , symbol
        , symbol_chain
        , nav
        , mr_rev
        , stream_rev
        , round(avg(mr_rev + stream_rev) over (partition by symbol order by day rows between 6 preceding and current row) * 365, 0) as revenue_7d_avg_annualized
        , round(avg(mr_rev + stream_rev) over (partition by symbol order by day rows between 29 preceding and current row) * 365, 0) as revenue_30d_avg_annualized
    from fli_revenue_daily
)

-- ============================================================================
-- REVENUE SHARE (for mr_rev, stream_rev, total_rev columns)
-- ============================================================================
, revenue_share as (
    with

    indexcoop_tokens as (
        select
            blockchain
            , contract_address
            , symbol
            , product_segment
            , end_date
        from dune.index_coop.result_multichain_indexcoop_tokenlist
        where is_bridged = false
        and contract_address not in (
            -- FLI tokens handled separately above
            0xaa6e8127831c9de45ae56bb1b0d4d4da6e5665bd,  -- ETH2x-FLI
            0x0b498ff89709d3838a063f1dfa463091f9801c2b,  -- BTC2x-FLI
            0x2af1df3ab0ab157e1e2ad8f88a7d04fbea0c7dc6,  -- BED
            0x341c05c0e9b33c0e38d64de76516b2ce970bb3be,  -- dsETH
            0x1b5e16c5b20fb5ee87c61fe9afe735cca3b21a65,  -- ic21
            0x36c833eed0d376f75d1ff9dfdee260191336065e,  -- gtcETH
            0x55b2cfcfe99110c773f00b023560dd9ef6c8a13b,  -- cDETI
            0xbe03026716a4d5e0992f22a3e6494b4f2809a9c6,  -- sPrtHyETH
            0x99f6539df9840592a862ab916ddc3258a1d7a773   -- prtHyETH
        )
        and blockchain in ('arbitrum', 'base', 'ethereum')
    )

    , token_nav_daily as (
        select
            date_trunc('day', nav.hour) as day
            , nav.blockchain
            , nav.token_address
            , nav.token_symbol
            , avg(nav.nav) as nav
        from dune.index_coop.result_multichain_all_active_tokens_nav_hourly nav
        inner join indexcoop_tokens it on nav.token_address = it.contract_address and nav.blockchain = it.blockchain
        group by 1, 2, 3, 4
    )

    , revenue as (
        select
            day
            , blockchain
            , symbol
            , concat(symbol, '|', blockchain) as symbol_chain
            , nav
            , (issue_fee * unit_issue * nav) + (redeem_fee * abs(unit_redeem) * nav) as mr_rev
            , streaming_fee / 365 * unit_supply * nav as stream_rev
        from (
            select
                s.day
                , t.blockchain
                , t.symbol
                , p.nav
                , f.issue_fee
                , f.redeem_fee
                , f.streaming_fee
                , fs.indexcoop as fee_split
                , coalesce(s.unit_flow, 0) as unit_flow
                , coalesce(s.unit_supply, 0) as unit_supply
                , coalesce(s.issue_units, 0) as unit_issue
                , coalesce(s.redeem_units, 0) as unit_redeem
            from query_2364999 s
            inner join indexcoop_tokens t on s.address = t.contract_address and s.blockchain = t.blockchain
            left join token_nav_daily p on s.day = p.day and s.address = p.token_address and s.blockchain = p.blockchain
            left join query_2621012 f on f.day = s.day and f.token_address = s.address and f.blockchain = s.blockchain
            left join query_2878827 fs on fs.day = s.day and fs.symbol = s.symbol
            where nav is not null
            and (s.day <= cast(t.end_date as date) or t.end_date is null)
            and s.day >= date_trunc('day', now()) - interval '6' day
        ) temp
    )

    , summary as (
        select
            symbol
            , symbol_chain
            , sum(mr_rev) as mr_rev
            , sum(stream_rev) as stream_rev
        from revenue
        group by 1, 2
    )

    -- Add FLI token revenue
    , fli_summary as (
        select
            symbol
            , symbol_chain
            , sum(mr_rev) as mr_rev
            , sum(stream_rev) as stream_rev
        from fli_revenue
        where day >= date_trunc('day', now()) - interval '6' day
        group by 1, 2
    )

    -- Combine all products
    , all_products as (
        select * from summary
        union all
        select * from fli_summary
    )

    select
        symbol_chain
        , mr_rev
        , stream_rev
        , mr_rev + stream_rev as total_rev
        , stream_rev / nullif(mr_rev + stream_rev, 0) as stream_share_pct
    from all_products

    union all

    -- Total row
    select
        'Total|all_chains' as symbol_chain
        , sum(mr_rev) as mr_rev
        , sum(stream_rev) as stream_rev
        , sum(mr_rev) + sum(stream_rev) as total_rev
        , sum(stream_rev) / nullif(sum(mr_rev) + sum(stream_rev), 0) as stream_share_pct
    from all_products
)

-- ============================================================================
-- 7 DAY REVENUE (for TVL, NSF, annualized revenue columns)
-- ============================================================================
, _7dayrevenue as (
    with

    all_data as (
        select
            day
            , symbol
            , blockchain as chain
            , price
            , price / lag(price, 1) over (partition by symbol, blockchain order by day) - 1 as price_change
            , tvl
            , tvl - lag(tvl, 7) over (partition by symbol, blockchain order by day) as tvl_change_USD
            , tvl / lag(tvl, 7) over (partition by symbol, blockchain order by day) - 1 as tvl_change
            , lag(tvl, 1) over (partition by symbol, blockchain order by day) as old_tvl
            , lag(tvl, 7) over (partition by symbol, blockchain order by day) as old_tvl_7d
            , sum(nsf) over (partition by symbol, blockchain order by day rows between 6 preceding and current row) as nsf_7_day
            , sum(nsf) over (partition by symbol, blockchain order by day rows between 13 preceding and 7 preceding) as nsf_14_day
            , nsf
            , round(sum(nsf) over (partition by symbol, blockchain order by day rows between 6 preceding and current row) / lag(tvl, 7) over (partition by symbol, blockchain order by day), 4) as nsf_change
            , revenue
            , round(avg(revenue) over (partition by symbol, blockchain order by day rows between 6 preceding and current row) * 365, 0) as revenue_7d_avg_annualized
            , round(avg(revenue) over (partition by symbol, blockchain order by day rows between 29 preceding and current row) * 365, 0) as revenue_30d_avg_annualized
        from dune.index_coop.result_index_coop_product_core_kpi_daily
    )

    , total as (
        select
            day
            , 'Total' as symbol
            , 'all_chains' as chain
            , null as price
            , null as price_change
            , sum(tvl) as tvl
            , sum(tvl_change_usd) as tvl_change_usd
            , sum(tvl) / sum(old_tvl_7d) - 1 as tvl_change
            , sum(nsf_7_day) / sum(nsf_14_day) - 1 as nsf_7day_change
            , sum(nsf_7_day) as nsf
            , sum(nsf_7_day) / sum(old_tvl_7d) as nsf_change
            , sum(revenue_7d_avg_annualized) + coalesce((
                select sum(revenue_7d_avg_annualized)
                from fli_revenue
                where day = date_trunc('day', now()) - interval '1' day
              ), 0) as revenue_7d_avg_annualized
            , sum(revenue_30d_avg_annualized) + coalesce((
                select sum(revenue_30d_avg_annualized)
                from fli_revenue
                where day = date_trunc('day', now()) - interval '1' day
              ), 0) as revenue_30d_avg_annualized
        from all_data
        group by 1, 2, 3, 4, 5
    )

    -- FLI tokens annualized revenue (null for TVL/NSF)
    , fli_annualized as (
        select
            symbol_chain
            , day
            , symbol
            , blockchain as chain
            , cast(null as double) as price
            , cast(null as double) as price_change
            , cast(null as double) as tvl
            , cast(null as double) as tvl_change_usd
            , cast(null as double) as tvl_change
            , cast(null as double) as nsf_7day_change
            , cast(null as double) as nsf
            , cast(null as double) as nsf_change
            , revenue_7d_avg_annualized
            , revenue_30d_avg_annualized
        from fli_revenue
        where day = date_trunc('day', now()) - interval '1' day
    )

    select symbol_chain, day, symbol, chain, price, price_change, tvl, tvl_change_usd, tvl_change, nsf_7day_change, nsf, nsf_change, revenue_7d_avg_annualized, revenue_30d_avg_annualized from (
        (select
            concat(symbol, '|', chain) as symbol_chain
            , day
            , symbol
            , chain
            , price
            , price_change
            , tvl
            , tvl_change_usd
            , tvl_change
            , (nsf_7_day) / (nsf_14_day) - 1 as nsf_7day_change
            , case
                when nsf_7_day between -0.1 and 0.1 then 0
                else nsf_7_day
              end as nsf
            , nsf_change
            , revenue_7d_avg_annualized
            , revenue_30d_avg_annualized
        from all_data
        where day = (select max(day) from all_data) - interval '1' day)

        union all

        (select concat(symbol, '|', chain) as symbol_chain, * from total where day = (select max(day) from all_data) - interval '1' day)

        union all

        (select * from fli_annualized)
    )
)

-- ============================================================================
-- FINAL OUTPUT
-- ============================================================================
select
    coalesce(dr.symbol_chain, sr.symbol_chain) as symbol_chain
    , tvl
    , tvl_change_usd
    , tvl_change
    , nsf_7day_change
    , nsf
    , nsf_change
    , coalesce(dr.revenue_7d_avg_annualized, sr.mr_rev + sr.stream_rev) as revenue_7d_avg_annualized
    , coalesce(dr.revenue_30d_avg_annualized, sr.mr_rev + sr.stream_rev) as revenue_30d_avg_annualized
    , coalesce(dr.revenue_30d_avg_annualized, sr.mr_rev + sr.stream_rev) as rev_30d_progress_bar
    , mr_rev
    , stream_rev
    , total_rev
    , stream_share_pct
from _7dayrevenue dr
full outer join revenue_share sr on dr.symbol_chain = sr.symbol_chain
where coalesce(dr.symbol, split_part(sr.symbol_chain, '|', 1)) not in ('BED', 'dsETH', 'ic21', 'gtcETH', 'cDETI', 'sPrtHyETH', 'prtHyETH', 'cdETI', 'ETH2x-FLI', 'BTC2x-FLI')
order by total_rev desc nulls last
