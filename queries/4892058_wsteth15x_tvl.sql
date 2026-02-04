-- Smart Loop: Lido stETH 15x - TVL
-- Query ID: 4892058
-- Tracks TVL, unit supply, fees, and revenue for wstETH15x token

with
-- Parameters
params as (
  select
    'wstETH15x' as symbol,
    0xc8df827157adaf693fcb0c6f305610c28de739fd as address
),

-- Base token data
token_data as (
  select
    s.blockchain,
    s.day,
    s.address,
    s.symbol,
    e.price,
    coalesce(s.unit_flow, 0) as unit_flow,
    s.unit_supply,
    s.unit_supply * e.price as tvl,
    s.unit_flow * e.price as nsf,
    sum(s.unit_flow * e.price) over (order by s.day asc) as c_nsf
  from query_2364999 s
  left join dune.index_coop.result_index_coop_token_prices_daily e on s.day = e.day and e.symbol = (select symbol from params)
  where s.symbol = (select symbol from params)
),

-- All fee data in one place
fee_data as (
  select
    date_trunc('day', block_time) as day,
    case when streaming_fee is null then 0 else streaming_fee end as streaming_fee,
    case when issue_fee is null then 0 else issue_fee end as issue_fee,
    case when redeem_fee is null then 0 else redeem_fee end as redeem_fee,
    row_number() over (partition by date_trunc('day', block_time) order by block_time desc, priority desc) as rn
  from query_2621044
  where token_address = (select address from params)
),

-- All event data in one place
events as (
  select
    date_trunc('day', evt_block_time) as day,
    sum(case when cast(qty/1e18 as double) >= 0 then cast(qty/1e18 as double) else 0 end) as issue_units,
    sum(case when cast(qty/1e18 as double) < 0 then cast(qty/1e18 as double) else 0 end) as redeem_units
  from query_2646506
  where symbol = (select symbol from params)
  group by 1
),

-- Fee rates simplified
daily_fee_rates as (
  select
    d.day,
    coalesce(last_value(f.streaming_fee) ignore nulls over (
      order by d.day rows between unbounded preceding and current row
    ), 0) as streaming_fee_rate,
    coalesce(last_value(f.issue_fee) ignore nulls over (
      order by d.day rows between unbounded preceding and current row
    ), 0) as issue_fee_rate,
    coalesce(last_value(f.redeem_fee) ignore nulls over (
      order by d.day rows between unbounded preceding and current row
    ), 0) as redeem_fee_rate
  from (select distinct day from token_data) d
  left join fee_data f on f.day <= d.day and f.rn = 1
)

-- Final summary with all data combined
select
  td.blockchain,
  td.day,
  td.address,
  td.symbol,
  td.price,
  td.unit_flow,
  td.unit_supply,
  td.tvl,
  td.nsf,
  td.c_nsf,
  (coalesce(e.issue_units, 0)) * td.price as issue_vol,
  (coalesce(e.redeem_units, 0) * -1) * td.price as redeem_vol,
  (coalesce(e.issue_units, 0)) * td.price * f.issue_fee_rate as issue_fee,
  (coalesce(e.redeem_units, 0) * -1) * td.price * f.redeem_fee_rate as redeem_fee,
  ((coalesce(e.issue_units, 0)) * td.price * f.issue_fee_rate) +
  ((coalesce(e.redeem_units, 0) * -1) * td.price * f.redeem_fee_rate) as mint_redeem_fee,
  td.tvl * f.streaming_fee_rate/365 as streaming_fee,
  ((coalesce(e.issue_units, 0)) * td.price * f.issue_fee_rate) +
  ((coalesce(e.redeem_units, 0) * -1) * td.price * f.redeem_fee_rate) +
  (td.tvl * f.streaming_fee_rate/365) as revenue,
  f.issue_fee_rate,
  f.redeem_fee_rate,
  f.streaming_fee_rate,
  sum(((coalesce(e.issue_units, 0)) * td.price * f.issue_fee_rate) +
      ((coalesce(e.redeem_units, 0) * -1) * td.price * f.redeem_fee_rate))
      over (order by td.day asc) as cumulative_mint_redeem_fee,
  sum(td.tvl * f.streaming_fee_rate/365)
      over (order by td.day asc) as cumulative_streaming_fee,
  sum(((coalesce(e.issue_units, 0)) * td.price * f.issue_fee_rate) +
      ((coalesce(e.redeem_units, 0) * -1) * td.price * f.redeem_fee_rate) +
      (td.tvl * f.streaming_fee_rate/365))
      over (order by td.day asc) as cumulative_revenue
from token_data td
left join daily_fee_rates f on f.day = td.day
left join events e on e.day = td.day
where e.day >= timestamp '2025-02-04'
order by td.day desc
