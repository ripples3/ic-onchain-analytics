-- Query: fee-structure-all-products-daily
-- Dune ID: 2621012
-- URL: https://dune.com/queries/2621012
-- Description: Fee structure for all Index Coop products, daily (gap-filled)
-- Parameters: none
--
-- Columns: blockchain, symbol, token_address, day, streaming_fee, issue_fee, redeem_fee
-- Depends on: query_5140527 (tokenlist), fee_changes_events

with

-- Single scan: get fee changes with dedup + min_day per token
daily_fee_changes as (
select
    blockchain
    , token_address
    , day
    , streaming_fee
    , issue_fee
    , redeem_fee
    , min_day
from (
    select
        blockchain
        , token_address
        , date_trunc('day', block_time) as day
        , coalesce(streaming_fee, 0) as streaming_fee
        , coalesce(issue_fee, 0) as issue_fee
        , coalesce(redeem_fee, 0) as redeem_fee
        , row_number() over (partition by blockchain, token_address, date_trunc('day', block_time) order by block_time desc, priority desc) as rn
        , min(date_trunc('day', block_time)) over (partition by blockchain, token_address) as min_day
    from dune.index_coop.result_index_coop_fee_changes_all_products_events
)
where rn = 1
)

-- Get unique tokens with their min_day
, token_min_day as (
select distinct
    blockchain
    , token_address
    , min_day
from daily_fee_changes
)

-- Generate all days for each token (from their first fee change)
, token_days as (
select
    t.blockchain
    , t.token_address
    , d.timestamp as day
from token_min_day t
cross join utils.days d
where d.timestamp >= t.min_day
)

-- Join days with fee changes and create partition markers for gap-filling
, fees_with_partitions as (
select
    td.blockchain
    , td.token_address
    , td.day
    , fc.streaming_fee
    , fc.issue_fee
    , fc.redeem_fee
    , sum(case when fc.streaming_fee is null then 0 else 1 end) over (partition by td.blockchain, td.token_address order by td.day) as sf_part
    , sum(case when fc.issue_fee is null then 0 else 1 end) over (partition by td.blockchain, td.token_address order by td.day) as if_part
    , sum(case when fc.redeem_fee is null then 0 else 1 end) over (partition by td.blockchain, td.token_address order by td.day) as rf_part
from token_days td
left join daily_fee_changes fc
    on fc.token_address = td.token_address
    and fc.blockchain = td.blockchain
    and fc.day = td.day
)

-- Gap-fill fees using FIRST_VALUE within each partition
, index_protocol_tokens as (
select
    fp.blockchain
    , t.symbol
    , fp.token_address
    , fp.day
    , first_value(fp.streaming_fee) over (partition by fp.blockchain, fp.token_address, fp.sf_part order by fp.day) as streaming_fee
    , case
        when t.symbol = 'ETH2X' and fp.day = date('2024-03-12') then 0
        else first_value(fp.issue_fee) over (partition by fp.blockchain, fp.token_address, fp.if_part order by fp.day)
      end as issue_fee
    , first_value(fp.redeem_fee) over (partition by fp.blockchain, fp.token_address, fp.rf_part order by fp.day) as redeem_fee
from fees_with_partitions fp
left join dune.index_coop.result_multichain_indexcoop_tokenlist t -- query_5140527
    on t.contract_address = fp.token_address
    and t.blockchain = fp.blockchain
)

-- Add mhyETH with zero fees (not in fee_changes table)
select distinct
    'ethereum' as blockchain
    , 'mhyETH' as symbol
    , 0x701907283a57FF77E255C3f1aAD790466B8CE4ef as token_address
    , day
    , cast(0 as double) as streaming_fee
    , cast(0 as double) as issue_fee
    , cast(0 as double) as redeem_fee
from index_protocol_tokens

union all

select * from index_protocol_tokens
