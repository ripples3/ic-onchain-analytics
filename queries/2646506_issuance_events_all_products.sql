-- Query: issuance-events-all-products
-- Dune ID: 2646506
-- URL: https://dune.com/queries/2646506
-- Description: Index Coop token issuance and redemption events across all chains
-- Parameters: none
--
-- Columns: blockchain, evt_block_time, contract_address, symbol, qty
-- Uses chain-specific tables instead of evms.erc20_transfers to avoid indexing lag

with transfers as (
    select 'ethereum' as blockchain, evt_block_time, contract_address, "from", "to", value
    from erc20_ethereum.evt_transfer
    where evt_block_time >= timestamp '2020-09-10'
    and ("from" = 0x0000000000000000000000000000000000000000
         or "to" = 0x0000000000000000000000000000000000000000)

    union all

    select 'arbitrum' as blockchain, evt_block_time, contract_address, "from", "to", value
    from erc20_arbitrum.evt_transfer
    where evt_block_time >= timestamp '2020-09-10'
    and ("from" = 0x0000000000000000000000000000000000000000
         or "to" = 0x0000000000000000000000000000000000000000)

    union all

    select 'base' as blockchain, evt_block_time, contract_address, "from", "to", value
    from erc20_base.evt_transfer
    where evt_block_time >= timestamp '2020-09-10'
    and ("from" = 0x0000000000000000000000000000000000000000
         or "to" = 0x0000000000000000000000000000000000000000)
)

select
    t.blockchain
    , e.evt_block_time
    , t.contract_address
    , t.symbol
    , case
        when e."from" = 0x0000000000000000000000000000000000000000 then cast(e.value as double)
        when e."to" = 0x0000000000000000000000000000000000000000 then -cast(e.value as double)
      end as qty
from transfers e
inner join dune.index_coop.result_multichain_indexcoop_tokenlist t
    on t.contract_address = e.contract_address
    and t.blockchain = e.blockchain
order by blockchain, evt_block_time
