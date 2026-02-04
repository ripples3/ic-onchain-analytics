-- Query: issuance-events-all-products
-- Dune ID: 2646506
-- URL: https://dune.com/queries/2646506
-- Description: Index Coop token issuance and redemption events across all chains
-- Parameters: none
--
-- Columns: blockchain, evt_block_time, contract_address, symbol, qty
-- Optimization: Single scan with CASE (verify row count matches original)

select
    t.blockchain
    , e.evt_block_time
    , t.contract_address
    , t.symbol
    , case
        when e."from" = 0x0000000000000000000000000000000000000000 then cast(e.value as double)
        when e."to" = 0x0000000000000000000000000000000000000000 then -cast(e.value as double)
      end as qty
from evms.erc20_transfers e
inner join dune.index_coop.result_multichain_indexcoop_tokenlist t -- query_5140527
    on t.contract_address = e.contract_address
    and t.blockchain = e.blockchain
where e.blockchain in ('ethereum', 'arbitrum', 'base')
and e.evt_block_time >= timestamp '2020-09-10'
and (
    e."from" = 0x0000000000000000000000000000000000000000
    or e."to" = 0x0000000000000000000000000000000000000000
)
order by blockchain, evt_block_time
