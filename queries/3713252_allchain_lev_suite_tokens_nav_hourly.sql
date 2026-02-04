-- Query: allchain-lev-suite-tokens-nav-hourly
-- Dune ID: 3713252
-- URL: https://dune.com/queries/3713252
-- Description: Hourly NAV and leverage ratio for all leverage suite tokens
-- Parameters: none
--
-- Columns: blockchain, hour, symbol, contract_address, collateral, debt, price, leverage_ratio, underlying_symbol, tlr, maxlr, minlr
-- Depends on: query_4771298 (leverage_suite_tokens), query_3018988 (components-with-hardcoded-values)

with

product_token as (
    select
        blockchain
        , token_address as address
        , product_symbol as symbol
        , decimals
        , supply_dec
        , debt_dec
        , tlr
        , maxlr
        , minlr
    from dune.index_coop.result_index_coop_leverage_suite_tokens -- query_4771298
)

, lev_collateral_changes as (
select
    uf.blockchain
    , dp.evt_block_time
    , dp.evt_index
    , uf.symbol
    , dp.contract_address
    , dp._component
    , dp._realUnit / power(10, uf.supply_dec) as _realUnit
    , 'collateral' as position
from (
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_ethereum.SetToken_evt_DefaultPositionUnitEdited
    union
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_arbitrum.SetToken_evt_DefaultPositionUnitEdited
    union
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_base.SetToken_evt_DefaultPositionUnitEdited
    ) dp
inner join product_token uf on dp.contract_address = uf.address
)

, lev_debt_changes as (
select
    uf.blockchain
    , dp.evt_block_time
    , dp.evt_index
    , uf.symbol
    , dp.contract_address
    , dp._component
    , dp._realUnit / power(10, uf.debt_dec) as _realUnit
    , 'debt' as position
from (
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_ethereum.SetToken_evt_ExternalPositionUnitEdited
    union
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_arbitrum.SetToken_evt_ExternalPositionUnitEdited
    union
    select contract_address, evt_tx_hash, evt_index, evt_block_time, evt_block_number, _component, _realUnit from indexprotocol_base.SetToken_evt_ExternalPositionUnitEdited
    ) dp
inner join product_token uf on dp.contract_address = uf.address
)

, join_levchanges as (
select
    *
    , lead(hour, 1, now()) over (partition by token_address, component order by hour) as next_hour
from (
    select
        blockchain
        , date_trunc('hour', evt_block_time) as hour
        , contract_address as token_address
        , symbol
        , _component as component
        , _realUnit
        , position
        , row_number() over (partition by date_trunc('hour', evt_block_time), contract_address, _component order by evt_block_time desc, evt_index desc) as rnb
    from (
        select * from lev_collateral_changes
        union
        select * from lev_debt_changes
        )
    )
where rnb = 1
)

, hours as (
select date_trunc('hour', timestamp) as hour
from utils.hours
where date_trunc('hour', timestamp) >= (select min(hour) from join_levchanges)
)

, join_levchanges_alldays as (
select
    l.blockchain
    , h.hour
    , l.token_address
    , l.symbol
    , l.component
    , l._realUnit
    , l.position
from hours h
inner join join_levchanges l on l.hour <= h.hour and h.hour < l.next_hour
)

, prices as (
select
    date_trunc('hour', timestamp) as hour
    , price
    , symbol
    , p.contract_address
    , blockchain
from prices.hour p
where (
    (blockchain = 'ethereum' and contract_address in (
        0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48, -- USDC
        0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2, -- WETH
        0x2260fac5e5542a773aa44fbcfedf7c193bc2c599, -- WBTC
        0xdAC17F958D2ee523a2206206994597C13D831ec7, -- USDT
        0x68749665FF8D2d112Fa859AA293F07A622782F38  -- XAUt
    ))
    or
    (blockchain = 'arbitrum' and contract_address in (
        0xaf88d065e77c8cC2239327C5EDb3A432268e5831, -- USDC
        0x82af49447d8a07e3bd95bd0d56f35241523fbab1, -- WETH
        0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f, -- WBTC
        0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9, -- USDT
        0xf97f4df75117a78c1A5a0DBb814Af92458539FB4, -- LINK
        0xba5DdD1f9d7F570dc94a51479a000E3BCE967196, -- AAVE
        0x912CE59144191C1204E64559FE8253a0e49E6548  -- ARB
    ))
    or
    (blockchain = 'base' and contract_address in (
        0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, -- USDC
        0x4200000000000000000000000000000000000006, -- WETH
        0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf, -- cbBTC
        0x9B8Df6E244526ab5F6e6400d331DB28C8fdDdb55, -- uSOL
        0xb0505e5a99abd03d94a1169e638B78EDfEd26ea4, -- uSUI
        0x2615a94df961278DcbC41Fb0a54fEC5f10a693aE  -- uXRP
    ))
)
)

, component_symbols as (
select
    l.blockchain
    , l.hour
    , l.token_address
    , l.symbol as token_symbol
    , l.component
    , t.symbol
    , t.base_symbol
    , case when t.base_symbol in ('uSOL', 'uSUI', 'uXRP') then l._realUnit / 1e12 else l._realUnit end as _realUnit
    , case when t.base_symbol in ('uSOL', 'uSUI', 'uXRP') then 'collateral' else l.position end as position
from join_levchanges_alldays l
inner join query_3018988 t on l.component = t.contract_address and l.blockchain = t.blockchain -- components-with-hardcoded-values
where t.blockchain in ('ethereum', 'arbitrum', 'base')
and t.symbol != 'COMP'
)

, transpose_position as (
select
    blockchain
    , hour
    , token_symbol
    , token_address
    , max(case when position = 'collateral' then nav_position else null end) as collateral
    , max(case when position = 'debt' then nav_position else null end) as debt
from (
    select
        blockchain
        , hour
        , token_symbol
        , position
        , token_address
        , sum(component_nav) as nav_position
    from (
        select
            cs.blockchain
            , cs.hour
            , cs.token_address
            , cs.token_symbol
            , cs.component
            , cs.symbol
            , cs.base_symbol
            , cs.position
            , avg(cs._realUnit) as _realUnit
            , avg(p.price) as component_price
            , avg(p.price) * avg(_realUnit) as component_nav
        from component_symbols cs
        left join prices p on cs.hour = p.hour and cs.base_symbol = p.symbol and cs.blockchain = p.blockchain
        group by 1, 2, 3, 4, 5, 6, 7, 8
        )
    group by 1, 2, 3, 4, 5
    )
group by 1, 2, 3, 4
)

, summary as (
select
    t.blockchain
    , hour
    , token_symbol as symbol
    , token_address as contract_address
    , coalesce(collateral, 0) as collateral
    , coalesce(debt, 0) as debt
    , coalesce(collateral, 0) + coalesce(debt, 0) as price
    , case
        when debt = 0 then 1
        else (coalesce(collateral, 0)) / (coalesce(collateral, 0) + coalesce(debt, 0))
      end as leverage_ratio
    , case
        when token_symbol like '%ETH%' and token_symbol not like 'BTC%' then 'WETH'
        when token_symbol like '%GOLD%' and token_symbol not like 'BTC%' then 'XAUt'
        when token_symbol like '%LINK%' and token_symbol not like 'BTC%' then 'LINK'
        when token_symbol like '%AAVE%' and token_symbol not like 'BTC%' then 'AAVE'
        when token_symbol like '%ARB%' and token_symbol not like 'BTC%' then 'ARB'
        when token_symbol like '%uSOL%' and token_symbol not like 'BTC%' then 'uSOL'
        when token_symbol like '%uSUI%' and token_symbol not like 'BTC%' then 'uSUI'
        when token_symbol like '%uXRP%' and token_symbol not like 'BTC%' then 'uXRP'
        when token_symbol like '%BTC%' then (
            case when t.blockchain = 'base' then 'cbBTC' else 'WBTC' end
        )
        else null
      end as underlying_symbol
    , p.tlr
    , p.maxlr
    , p.minlr
from transpose_position t
left join product_token p on t.token_symbol = p.symbol and t.blockchain = p.blockchain
)

select * from summary
where collateral is not null
and not is_nan(leverage_ratio)
