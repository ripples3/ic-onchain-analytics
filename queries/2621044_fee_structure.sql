-- Query: fee-structure
-- Dune ID: 2621044
-- URL: https://dune.com/queries/2621044
-- Description: Index Coop token fee structure (streaming, issue, redeem fees)
-- Parameters: none
-- Depends on: query_5140527 (tokenlist)
--
-- Columns: blockchain, symbol, token_address, block_time, priority, streaming_fee, issue_fee, redeem_fee

with

set_created as (
select
    s.blockchain,
    t.contract_address as token_address,
    t.symbol,
    'Token Creation' as event,
    evt_block_time as block_time,
    0 as priority
from    (
        select _setToken, evt_block_time, 'ethereum' as blockchain from setprotocol_v2_ethereum.SetTokenCreator_evt_SetTokenCreated
        union
        select _setToken, evt_block_time, 'ethereum' as blockchain from indexprotocol_ethereum.SetTokenCreator_evt_SetTokenCreated
        union
        select _setToken, evt_block_time, 'arbitrum' as blockchain from indexprotocol_arbitrum.SetTokenCreator_evt_SetTokenCreated
        union
        select _setToken, evt_block_time, 'base'     as blockchain from indexprotocol_base.SetTokenCreator_evt_SetTokenCreated
        ) as s
inner join dune.index_coop.result_multichain_indexcoop_tokenlist as t on s."_setToken" = t.contract_address and s.blockchain = t.blockchain
),

streaming_fees as (
SELECT
    'Streaming Fee Initialized' as event,
    "call_block_time" as block_time,
    symbol,
    t.contract_address as token_address,
    CAST(json_extract_scalar("_settings", '$.streamingFeePercentage') as DECIMAL) / CAST(1e18 as DOUBLE) AS streaming_fee,
    1 as priority
from    (
         select _setToken, call_block_time, _settings, call_success, 'ethereum' as blockchain from setprotocol_v2_ethereum.StreamingFeeModule_call_initialize
         union
         select _setToken, call_block_time, _settings, call_success, 'ethereum' as blockchain from indexprotocol_ethereum.StreamingFeeModule_call_initialize
         union
         select _setToken, call_block_time, _settings, call_success, 'arbitrum' as blockchain from indexprotocol_arbitrum.StreamingFeeModule_call_initialize
         union
         select _setToken, call_block_time, _settings, call_success, 'base'     as blockchain from indexprotocol_base.StreamingFeeModule_call_initialize
        ) AS s
inner join dune.index_coop.result_multichain_indexcoop_tokenlist AS t ON s."_setToken" = t.contract_address and s.blockchain = t.blockchain
where "call_success" = TRUE
union
SELECT
    'Streaming Fee Updated' AS event,
    "evt_block_time" AS block_time,
    symbol,
    t.contract_address as token_address,
    "_newStreamingFee" / CAST(1e18 AS DOUBLE) AS streaming_fee,
    2 AS priority
FROM    (
        select evt_block_time, _setToken, _newStreamingFee, 'ethereum' as blockchain from setprotocol_v2_ethereum.StreamingFeeModule_evt_StreamingFeeUpdated
        union
        select evt_block_time, _setToken, _newStreamingFee, 'ethereum' as blockchain from indexprotocol_ethereum.StreamingFeeModule_evt_StreamingFeeUpdated
        union
        select evt_block_time, _setToken, _newStreamingFee, 'arbitrum' as blockchain from indexprotocol_arbitrum.StreamingFeeModule_evt_StreamingFeeUpdated
        union
        select evt_block_time, _setToken, _newStreamingFee, 'base'     as blockchain from indexprotocol_base.StreamingFeeModule_evt_StreamingFeeUpdated
        ) AS s
INNER JOIN dune.index_coop.result_multichain_indexcoop_tokenlist AS t ON s."_setToken" = t.contract_address and s.blockchain = t.blockchain
),

issue_redeem_fees as (
select
    'Issue/Redeem Fee Initialize' as event,
    "call_block_time"  as block_time,
    symbol,
    t.contract_address as token_address,
    "_managerIssueFee" / CAST(1e18 as DOUBLE) as issue_fee,
    "_managerRedeemFee" / CAST(1e18 as DOUBLE) as redeem_fee,
    1 as priority
from (
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'ethereum' as blockchain from setprotocol_v2_ethereum.DebtIssuanceModule_call_initialize
    UNION
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'ethereum' as blockchain from setprotocol_v2_ethereum.DebtIssuanceModuleV2_call_initialize
    UNION
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'ethereum' as blockchain from indexprotocol_ethereum.DebtIssuanceModuleV2_call_initialize
    UNION
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'arbitrum' as blockchain from indexprotocol_arbitrum.DebtIssuanceModuleV3_call_initialize
    UNION
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV2_call_initialize
    UNION
    select call_block_time, _setToken, _managerIssueFee, _managerRedeemFee, call_success, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV3_call_initialize
    ) as s
inner join dune.index_coop.result_multichain_indexcoop_tokenlist as t on s."_setToken" = t.contract_address and s.blockchain = t.blockchain
where "call_success" = TRUE
union
SELECT
    'Redeem Fee Updated' AS event,
    "evt_block_time" AS block_time,
    symbol,
    t.contract_address as token_address,
    TRY_CAST(NULL AS DECIMAL) AS issue_fee,
    "_newRedeemFee" / CAST(1e18 AS DOUBLE) AS redeem_fee,
    2 AS priority
FROM (
    SELECT evt_block_time, _setToken, _newRedeemFee,  'ethereum' as blockchain FROM setprotocol_v2_ethereum.DebtIssuanceModule_evt_RedeemFeeUpdated
    UNION
    SELECT evt_block_time, _setToken, _newRedeemFee, 'ethereum' as blockchain FROM setprotocol_v2_ethereum.DebtIssuanceModuleV2_evt_RedeemFeeUpdated
    union
    select evt_block_time, _setToken, _newRedeemFee, 'ethereum' as blockchain from indexprotocol_ethereum.DebtIssuanceModuleV2_evt_RedeemFeeUpdated
    union
    select evt_block_time, _setToken, _newRedeemFee, 'arbitrum' as blockchain from indexprotocol_arbitrum.DebtIssuanceModuleV3_evt_RedeemFeeUpdated
    union
    select evt_block_time, _setToken, _newRedeemFee, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV2_evt_RedeemFeeUpdated
    union
    select evt_block_time, _setToken, _newRedeemFee, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV3_evt_RedeemFeeUpdated
    ) AS s
inner join dune.index_coop.result_multichain_indexcoop_tokenlist AS t ON s."_setToken" = t.contract_address and s.blockchain = t.blockchain
UNION
SELECT
    'Issue Fee Updated' AS event,
    "evt_block_time" AS block_time,
    symbol,
    t.contract_address as token_address,
    "_newIssueFee" / CAST(1e18 AS DOUBLE) AS issue_fee,
    TRY_CAST(NULL AS DECIMAL) AS redeem_fee,
    2 AS priority
FROM (
    SELECT evt_block_time, _setToken, _newIssueFee, 'ethereum' as blockchain FROM setprotocol_v2_ethereum.DebtIssuanceModule_evt_IssueFeeUpdated
    UNION
    SELECT evt_block_time, _setToken, _newIssueFee, 'ethereum' as blockchain FROM setprotocol_v2_ethereum.DebtIssuanceModuleV2_evt_IssueFeeUpdated
    union
    select evt_block_time, _setToken, _newIssueFee, 'ethereum' as blockchain from indexprotocol_ethereum.DebtIssuanceModuleV2_evt_IssueFeeUpdated
    union
    select evt_block_time, _setToken, _newIssueFee, 'arbitrum' as blockchain from indexprotocol_arbitrum.DebtIssuanceModuleV3_evt_IssueFeeUpdated
    union
    select evt_block_time, _setToken, _newIssueFee, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV2_evt_IssueFeeUpdated
    union
    select evt_block_time, _setToken, _newIssueFee, 'base'     as blockchain from indexprotocol_base.DebtIssuanceModuleV3_evt_IssueFeeUpdated
    ) as s
inner join dune.index_coop.result_multichain_indexcoop_tokenlist AS t ON s."_setToken" = t.contract_address and s.blockchain = t.blockchain
)

, all_fees AS (
SELECT
    token_address,
    block_time,
    priority,
    FIRST_VALUE(streaming_fee) OVER (PARTITION BY token_address, sf_part ORDER BY block_time, priority) AS streaming_fee,
    FIRST_VALUE(issue_fee) OVER (PARTITION BY token_address, if_part ORDER BY block_time, priority) AS issue_fee,
    FIRST_VALUE(redeem_fee) OVER (PARTITION BY token_address, rf_part ORDER BY block_time, priority) AS redeem_fee
FROM (
    SELECT
        token_address,
        event,
        block_time,
        streaming_fee,
        issue_fee,
        redeem_fee,
        priority,
        SUM(CASE WHEN streaming_fee IS NULL THEN 0 ELSE 1 END) OVER (PARTITION BY token_address ORDER BY block_time, priority, event) AS sf_part,
        SUM(CASE WHEN issue_fee IS NULL THEN 0 ELSE 1 END) OVER (PARTITION BY token_address ORDER BY block_time, priority, event) AS if_part,
        SUM(CASE WHEN redeem_fee IS NULL THEN 0 ELSE 1 END) OVER (PARTITION BY token_address ORDER BY block_time, priority, event) AS rf_part
    FROM (

        SELECT
            token_address,
            block_time,
            priority,
            event,
            TRY_CAST(NULL AS DECIMAL) AS streaming_fee,
            TRY_CAST(NULL AS DECIMAL) AS issue_fee,
            TRY_CAST(NULL AS DECIMAL) AS redeem_fee
        FROM set_created
        UNION
        SELECT
            token_address,
            block_time,
            priority,
            event,
            streaming_fee,
            TRY_CAST(NULL AS DECIMAL) AS issue_fee,
            TRY_CAST(NULL AS DECIMAL) AS redeem_fee
        FROM streaming_fees
        UNION
        SELECT
            token_address,
            block_time,
            priority,
            event,
            TRY_CAST(NULL AS DECIMAL) AS streaming_fee,
            issue_fee,
            redeem_fee
        FROM issue_redeem_fees
    ) AS t0
        ) AS t1
)

select
    MIN(z.blockchain) as blockchain,
    MIN(z.symbol) as symbol,
    a.token_address,
    a.block_time,
    a.priority,
    MAX(a.streaming_fee) as streaming_fee,
    MAX(a.issue_fee) as issue_fee,
    MAX(a.redeem_fee) as redeem_fee
from  all_fees a
left join dune.index_coop.result_multichain_indexcoop_tokenlist z on z.contract_address = a.token_address
group by 3,4,5
