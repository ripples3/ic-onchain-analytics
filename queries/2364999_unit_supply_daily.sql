-- Query: unit-supply-daily
-- Dune ID: 2364999
-- URL: https://dune.com/queries/2364999
-- Description: Daily unit supply for all Index Coop products
-- Parameters: none
--
-- Columns: blockchain, day, address, symbol, product_segment, end_date, issue_units, redeem_units, unit_flow, unit_supply
-- Depends on: query_5140527 (tokenlist), query_2646506 (issuance events)

with

tokens as (
select
    blockchain
    , contract_address
    , symbol
    , product_segment
    , end_date
from dune.index_coop.result_multichain_indexcoop_tokenlist -- query_5140527
where is_bridged = false
)

, daily_events as (
select
    contract_address
    , date_trunc('day', evt_block_time) as day
    , sum(qty) filter (where qty > 0) / 1e18 as issue_units
    , sum(qty) filter (where qty < 0) / 1e18 as redeem_units
    , sum(qty) / 1e18 as unit_flow
from dune.index_coop.result_index_coop_issuance_events_all_products -- query_2646506
group by 1, 2
)

, token_days as (
select
    t.blockchain
    , d.timestamp as day
    , t.contract_address
    , t.symbol
    , t.product_segment
    , t.end_date
from tokens t
cross join (
    select timestamp
    from utils.days
    where timestamp >= timestamp '2020-09-10'
) d
)

, unit_supply as (
select
    td.blockchain
    , td.day
    , td.contract_address as address
    , td.symbol
    , td.product_segment
    , td.end_date
    , e.issue_units
    , e.redeem_units
    , e.unit_flow
    , sum(e.unit_flow) over (partition by td.contract_address order by td.day) as unit_supply
from token_days td
left join daily_events e
    on e.contract_address = td.contract_address
    and e.day = td.day
)

select *
from unit_supply
where unit_supply is not null
order by blockchain, day
