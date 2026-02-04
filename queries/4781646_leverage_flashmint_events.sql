-- ============================================================================
-- Query: Index Coop - Leverage - FlashMint Events
-- Dune ID: 4781646
-- URL: https://dune.com/queries/4781646
-- Description: Tracks FlashMint issue and redeem events for leverage suite tokens
--              across Ethereum, Arbitrum, and Base (v1 and v2 contracts)
-- Parameters: none
--
-- Columns: version, blockchain, user_address, fl_contract, tx_type, token_address,
--          ic_token_address, product_symbol, evt_block_time, evt_block_number,
--          evt_index, evt_tx_hash, amount, ic_amount
-- Depends on: result_index_coop_leverage_suite_tokens
--
-- Notes:
--   - v1: Legacy FlashMint contracts (flashmintleveraged*, flashmintleveragedextended)
--   - v2: New ZeroEx-based contracts (flashmintleveragedzeroex*)
--   - Uses prices.usd for minute-level price lookups (prices.minute is 7x slower for this query)
--
-- ============================================================================

with

levsuite_tokens as (
    select *
    from dune.index_coop.result_index_coop_leverage_suite_tokens
)

, all_flasmint_events as (
    --- flashmints on unique on BASE
    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorphov2_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetIssued as amount
        , (cast(_amountInputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedaerodrome_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorpho_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorphoaavelm_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountInputToken as amount
        , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorphov2_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedaerodrome_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountInputToken as amount
        , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorpho_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    select
        'base' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountInputToken as amount
        , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_base.flashmintleveragedmorphoaavelm_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'base'
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_redeem events from multichain
    select
        chain as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetIssued as amount
        , (cast(_amountInputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_multichain.flashmintleveragedextended_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = fm.chain
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_issue events from multichain
    select
        chain as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_multichain.flashmintleveragedextended_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = fm.chain
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_redeem events from ethereum
    select
        'ethereum' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetIssued as amount
        , (cast(_amountInputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_ethereum.flashmintleveraged_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'ethereum'
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_issue events from ethereum
    select
        'ethereum' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_ethereum.flashmintleveraged_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'ethereum'
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_redeem events from arbitrum
    select
        'arbitrum' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Redeem' as tx_type
        , _inputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetIssued as amount
        , (cast(_amountInputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_arbitrum.flashmintleveragedaavefl_evt_flashmint fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'arbitrum'
    where evt_block_time >= timestamp '2024-03-13'

    union

    -- flashmint_issue events from arbitrum
    select
        'arbitrum' as blockchain
        , _recipient as user_address
        , contract_address as fl_contract
        , 'Issue' as tx_type
        , _outputToken as token_address
        , _setToken as ic_token_address
        , lp.product_symbol
        , evt_block_time
        , evt_block_number
        , evt_index
        , evt_tx_hash
        , _amountSetRedeemed as amount
        , (cast(_amountOutputToken as DECIMAL(38,0))/1e18) as ic_amount
    from indexprotocol_arbitrum.flashmintleveragedaavefl_evt_flashredeem fm
    inner join levsuite_tokens lp on lp.token_address = fm._setToken and lp.blockchain = 'arbitrum'
    where evt_block_time >= timestamp '2024-03-13'
)

, all_flasmintv2_events as (
    with

    flashmints as (
        -- ========================
        -- Redeem Contracts =======
        -- ========================
        -- == Ethereum ==
        select
            'ethereum' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Redeem' as tx_type
            , _outputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetRedeemed as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_ethereum.flashmintleveragedzeroex_evt_flashredeem fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'

        union all
        -- == Arbitrum ==
        select
            'arbitrum' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Redeem' as tx_type
            , _outputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetRedeemed as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_arbitrum.flashmintleveragedzeroexbalancerfl_evt_flashredeem fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'

        union all
        -- == Base ==
        select
            'base' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Redeem' as tx_type
            , _outputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetRedeemed as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_base.flashmintleveragedzeroex_evt_flashredeem fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'

        union all
        -- ========================
        -- Issue Contracts ========
        -- ========================
        -- == Ethereum ==
        select
            'ethereum' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Issue' as tx_type
            , _inputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_ethereum.flashmintleveragedzeroex_evt_flashmint fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'

        union all
        -- == Arbitrum ==
        select
            'arbitrum' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Issue' as tx_type
            , _inputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_arbitrum.flashmintleveragedzeroexbalancerfl_evt_flashmint fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'

        union all
        -- == Base ==
        select
            'base' as blockchain
            , contract_address as fl_contract
            , _recipient as user_address
            , 'Issue' as tx_type
            , _inputToken as token_address
            , _setToken as ic_token_address
            , lp.product_symbol
            , evt_block_time
            , evt_block_number
            , evt_index
            , evt_tx_hash
            , (cast(_amountSetIssued as DECIMAL(38,0))/1e18) as ic_amount
        from indexprotocol_base.flashmintleveragedzeroex_evt_flashmint fm
        inner join levsuite_tokens lp on lp.token_address = fm._setToken
        where evt_block_time >= timestamp '2025-03-20'
    )

    -- Create a temp table with transaction hashes for more efficient joins
    , tx_hashes as (
        select distinct
            evt_tx_hash
            , blockchain
            , user_address
            , fl_contract
            , tx_type
            , token_address
            , ic_token_address
        from flashmints
    )

    , erc20_transfers as (
        -- For Issue transactions (from user_address)
        select
            tr.contract_address
            , tr.evt_tx_hash
            , tr.evt_block_time
            , case
                -- Issue: user sending funds (POSITIVE - represents value of new token)
                when tx.tx_type = 'Issue' and tr."from" = tx.user_address then cast(value as DECIMAL(38,0))
                -- Issue: dust from contract (NEGATIVE - reduces effective value)
                when tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0)) * -1
                -- Redeem: user receiving funds (POSITIVE - value received)
                when tx.tx_type = 'Redeem' and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
                -- Redeem: dust from contract (POSITIVE - adds to value received)
                when tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
            end as amount
            , tx.blockchain
        from erc20_ethereum.evt_transfer tr
        inner join tx_hashes tx on tr.evt_tx_hash = tx.evt_tx_hash
            and (
                -- User sending funds
                (tx.tx_type = 'Issue' and tr."from" = tx.user_address) or
                -- User receiving dust from contract during issue
                (tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address) or
                -- User receiving funds
                (tx.tx_type = 'Redeem' and tr."to" = tx.user_address) or
                -- User receiving dust from contract during redeem
                (tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address)
            )
        where evt_block_time >= timestamp '2025-03-20'
        and tr.contract_address != tx.ic_token_address

        union all

        -- == For Arbitrum chain ==
        select
            tr.contract_address
            , tr.evt_tx_hash
            , tr.evt_block_time
            , case
                when tx.tx_type = 'Issue' and tr."from" = tx.user_address then cast(value as DECIMAL(38,0))
                when tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0)) * -1
                when tx.tx_type = 'Redeem' and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
                when tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
            end as amount
            , tx.blockchain
        from erc20_arbitrum.evt_transfer tr
        inner join tx_hashes tx on tr.evt_tx_hash = tx.evt_tx_hash
            and (
                (tx.tx_type = 'Issue' and tr."from" = tx.user_address) or
                (tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address) or
                (tx.tx_type = 'Redeem' and tr."to" = tx.user_address) or
                (tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address)
            )
        where evt_block_time >= timestamp '2025-03-20'
        and tr.contract_address != tx.ic_token_address

        union all
        -- == For Base chain ==
        select
            tr.contract_address
            , tr.evt_tx_hash
            , tr.evt_block_time
            , case
                when tx.tx_type = 'Issue' and tr."from" = tx.user_address then cast(value as DECIMAL(38,0))
                when tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0)) * -1
                when tx.tx_type = 'Redeem' and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
                when tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address then cast(value as DECIMAL(38,0))
            end as amount
            , tx.blockchain
        from erc20_base.evt_transfer tr
        inner join tx_hashes tx on tr.evt_tx_hash = tx.evt_tx_hash
            and (
                (tx.tx_type = 'Issue' and tr."from" = tx.user_address) or
                (tx.tx_type = 'Issue' and tr."from" = tx.fl_contract and tr."to" = tx.user_address) or
                (tx.tx_type = 'Redeem' and tr."to" = tx.user_address) or
                (tx.tx_type = 'Redeem' and tr."from" = tx.fl_contract and tr."to" = tx.user_address)
            )
        where evt_block_time >= timestamp '2025-03-20'
        and tr.contract_address != tx.ic_token_address
    )

    , eth_transfers as (
        -- == Ethereum ==
        select
            blockchain
            , contract_address
            , we.evt_tx_hash
            , tx_type
            , evt_block_time
            , 'withdrawal' as evt_type
            , src as fl_contract
            , (cast(wad as DECIMAL(38,0))/1e18) as amount
        from zeroex_ethereum.weth9_evt_withdrawal we
        inner join tx_hashes tx on we.evt_tx_hash = tx.evt_tx_hash and we.src = tx.fl_contract and tx.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
        where evt_block_time >= timestamp '2025-03-20'

        union all

        select
            blockchain
            , contract_address
            , we.evt_tx_hash
            , tx_type
            , evt_block_time
            , 'deposit' as evt_type
            , dst as fl_contract
            , (cast(wad as DECIMAL(38,0))/1e18) as amount
        from zeroex_ethereum.weth9_evt_deposit we
        inner join tx_hashes tx on we.evt_tx_hash = tx.evt_tx_hash and we.dst = tx.fl_contract and tx.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
        where evt_block_time >= timestamp '2025-03-20'

        union all

        -- == Arbitrum ==
        select
            blockchain
            , contract_address
            , tx.evt_tx_hash
            , tx_type
            , evt_block_time
            , evt_type
            , src as fl_contract
            , (cast(value as DECIMAL(38,0))/1e18) as amount
        from (
            select
                contract_address
                , evt_tx_hash
                , evt_block_time
                , value
                , case
                    when "from" = 0x0000000000000000000000000000000000000000 then 'deposit'
                    when "to" = 0x0000000000000000000000000000000000000000 then 'withdrawal'
                end as evt_type
                , case
                    when "from" = 0x0000000000000000000000000000000000000000 then "to"
                    when "to" = 0x0000000000000000000000000000000000000000 then "from"
                end as src
            from weth_arbitrum.aeweth_evt_transfer
            where evt_block_time >= timestamp '2025-03-20'
            and (
                ("to" = 0x0000000000000000000000000000000000000000 and "from" != 0x0000000000000000000000000000000000000000) or
                ("from" = 0x0000000000000000000000000000000000000000 and "to" != 0x0000000000000000000000000000000000000000)
            )
        ) tr
        inner join tx_hashes tx on tr.evt_tx_hash = tx.evt_tx_hash and tr.src = tx.fl_contract and tx.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee

        union all
        -- == Base ==
        select
            blockchain
            , contract_address
            , we.evt_tx_hash
            , tx_type
            , evt_block_time
            , 'withdrawal' as evt_type
            , src as fl_contract
            , (cast(wad as DECIMAL(38,0))/1e18) as amount
        from weth_base.weth9_evt_withdrawal we
        inner join tx_hashes tx on we.evt_tx_hash = tx.evt_tx_hash and we.src = tx.fl_contract and tx.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
        where evt_block_time >= timestamp '2025-03-20'
        and we.evt_tx_hash != 0xa36cc3ae2199a7675b04464ab380e281f507ce6b2a7c6d1470db0a8fe0600cf9

        union all

        select
            blockchain
            , contract_address
            , we.evt_tx_hash
            , tx_type
            , evt_block_time
            , 'deposit' as evt_type
            , dst as fl_contract
            , (cast(wad as DECIMAL(38,0))/1e18) as amount
        from weth_base.weth9_evt_deposit we
        inner join tx_hashes tx on we.evt_tx_hash = tx.evt_tx_hash and we.dst = tx.fl_contract and tx.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
        where evt_block_time >= timestamp '2025-03-20'
    )

    , eth_tx as (
        select
            blockchain
            , contract_address
            , evt_tx_hash
            , evt_block_time
            , case
                when amount < 0 then amount * -1
                else amount
            end as amount
        from (
            select
                blockchain
                , contract_address
                , evt_tx_hash
                , evt_block_time
                , fl_contract
                , tx_type
                , sum(case
                    when evt_type = 'withdrawal' then -1 * amount
                    when evt_type = 'deposit' then amount
                end) as amount
            from eth_transfers
            group by 1,2,3,4,5,6
        )
    )

    , summary as (
        select
            evt_tx_hash
            , tr.blockchain
            , sum(
                case
                    when type = 'erc20_transfer'
                    then (amount / power(10, coalesce(p.decimals, 18))) * coalesce(p.price, 0)
                    else amount * p.price
                end
            ) as amount_usd
        from (
            select
                blockchain
                , contract_address
                , evt_tx_hash
                , evt_block_time
                , amount
                , 'erc20_transfer' as type
            from erc20_transfers

            union all

            select
                blockchain
                , contract_address
                , evt_tx_hash
                , evt_block_time
                , amount
                , 'eth_transfer' as type
            from eth_tx
        ) tr
        left join prices.usd p on p.contract_address = tr.contract_address and p.blockchain = tr.blockchain and p.minute = date_trunc('minute', tr.evt_block_time)
        where p.blockchain in ('ethereum', 'base', 'arbitrum')
        and p.minute >= timestamp '2025-03-20'
        group by 1,2
    )

    , io_tokenaddress as (
        select
            fm.blockchain
            , fm.user_address
            , fm.fl_contract
            , fm.tx_type
            , fm.token_address
            , case
                when fm.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee and fm.blockchain = 'ethereum' then 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
                when fm.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee and fm.blockchain = 'arbitrum' then 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1
                when fm.token_address = 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee and fm.blockchain = 'base' then 0x4200000000000000000000000000000000000006
                else token_address
            end as io_tokenaddress
            , fm.ic_token_address
            , fm.product_symbol
            , fm.evt_block_time
            , fm.evt_block_number
            , fm.evt_index
            , fm.evt_tx_hash
            , s.amount_usd as amount
            , fm.ic_amount
        from flashmints fm
        left join summary s on s.evt_tx_hash = fm.evt_tx_hash
        where amount_usd is not null
    )

    select
        iot.blockchain
        , iot.user_address
        , iot.fl_contract
        , iot.tx_type
        , iot.token_address
        , iot.ic_token_address
        , iot.product_symbol
        , iot.evt_block_time
        , iot.evt_block_number
        , iot.evt_index
        , iot.evt_tx_hash
        , (iot.amount/p.price) as amount
        , iot.ic_amount
    from io_tokenaddress iot
    left join prices.usd p on p.contract_address = iot.io_tokenaddress and p.blockchain = iot.blockchain and p.minute = date_trunc('minute', iot.evt_block_time)
    where p.blockchain in ('ethereum', 'base', 'arbitrum')
    and p.minute >= timestamp '2025-03-20'
)

select 'v1' as version, * from all_flasmint_events
union
select 'v2' as version, * from all_flasmintv2_events
