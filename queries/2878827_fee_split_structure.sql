-- Query: fee-split-structure
-- Dune ID: 2878827
-- URL: https://dune.com/queries/2878827
-- Description: Fee split structure showing Index Coop share of fees by product
-- Parameters: none
--
-- Columns: day, token_address, symbol, evt_name, indexcoop, methodologist
-- Depends on: query_2874559 (fee split events)

with

fee_splits as (
select
    date_trunc('day', block_time) as day
    , token_address
    , symbol
    , evt_type as evt_name
    , indexcoop
    , methodologist
    , lead(date_trunc('day', block_time), 1, now()) over (partition by symbol order by date_trunc('day', block_time)) as next_day
from (
    select
        *
        , row_number() over (partition by date_trunc('day', block_time), symbol order by block_time desc) as rnb
    from query_2874559
)
where rnb = 1
)

-- Generate days since the creation of DPI
-- TODO: Replace with utils.days for better performance
, days as (
select distinct date_trunc('day', time) as day
from ethereum.blocks
where time >= timestamp '2020-10-09'
)

--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##
--## hardcoded tokens
--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##
, missing_tokens (token_address, symbol, evt_name, deploy_date, indexcoop, methodologist) as (
-- missing_tokens are tokens which fees haven't yet collected, thus no transaction to automatically get the values yet.
values
(0x36c833Eed0D376f75D1ff9dFDeE260191336065e, 'gtcETH', 'hardcoded', '2023-02-10', 0.125, 0.875),
(0xcCdAE12162566E3f29fEfA7Bf7F5b24C644493b5, 'icRETH', 'hardcoded', '2023-08-16', 1,     0    ),
(0xc30FBa978743a43E736fc32FBeEd364b8A2039cD, 'icSMMT', 'hardcoded', '2023-04-22', 1,     0    ),
(0x1b5e16c5b20fb5ee87c61fe9afe735cca3b21a65, 'ic21',   'hardcoded', '2023-09-01', 0.6,   0.4  ),
(0x55b2cfcfe99110c773f00b023560dd9ef6c8a13b, 'cdETI',  'hardcoded', '2023-10-12', 0.67,  0.33 )
)

, temp as (
select
    d.day
    , token_address
    , symbol
    , evt_name
    , indexcoop
    , methodologist
from missing_tokens ms
cross join days d
where d.day >= cast(ms.deploy_date as timestamp)
)

--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##--##

, final as (
select
    d.day
    , token_address
    , symbol
    , evt_name
    , indexcoop
    , methodologist
from days d
inner join fee_splits fs on fs.day <= d.day and d.day < fs.next_day
)

select * from final

union all

select * from temp
