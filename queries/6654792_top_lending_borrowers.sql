-- Top lending protocol borrowers ($10M+) with identity labels
-- https://dune.com/queries/6654792
-- Uses Dune's label tables for wallet identification

with borrower_totals as (
    select
        borrower,
        project,
        sum(case when transaction_type = 'borrow' then amount_usd else 0 end) as total_borrowed,
        sum(case when transaction_type = 'repay' then amount_usd else 0 end) as total_repaid,
        sum(case when transaction_type = 'borrow' then amount_usd
                 when transaction_type = 'repay' then -amount_usd
                 else 0 end) as net_position
    from lending.borrow
    where blockchain = 'ethereum'
      and project in ('compound', 'aave', 'aave_lido', 'aave_horizon', 'morpho', 'spark')
      and transaction_type in ('borrow', 'repay')
    group by 1, 2
    having sum(case when transaction_type = 'borrow' then amount_usd else 0 end) >= 10000000
),

asset_breakdown as (
    select
        borrower,
        project,
        array_agg(distinct symbol) as borrowed_assets
    from lending.borrow
    where blockchain = 'ethereum'
      and project in ('compound', 'aave', 'aave_lido', 'aave_horizon', 'morpho', 'spark')
      and transaction_type = 'borrow'
    group by 1, 2
)

select
    bt.project,
    bt.borrower,
    round(bt.total_borrowed / 1e6, 2) as total_borrowed_m,
    round(bt.net_position / 1e6, 2) as net_position_m,
    ab.borrowed_assets,

    -- Owner/Entity labels
    lab.owner_key,
    lab.custody_owner,
    lab.contract_name as owner_contract_name,

    -- ENS
    ens.name as ens_name,

    -- Social/Twitter
    owner_det.social as social_links,
    owner_det.website as project_website,

    -- CEX
    cex.cex_name,
    cex.distinct_name as cex_distinct_name,

    -- CEX Info with Twitter
    cex_info.x_username as cex_twitter,

    -- CEX Deposit Address
    cex_dep.cex_name as cex_deposit_for,

    -- Contract identification
    cm.contract_project,
    cm.contract_name,
    case when cm.contract_address is not null then 'Contract' else 'EOA' end as address_type,

    -- Safe/Multi-sig
    case when safe.address is not null then 'Safe Wallet' else null end as safe_label,

    -- DAO
    dao.dao_creator_tool,

    -- DeFi Protocol
    defi.project as defi_protocol,

    -- MEV
    case when mev.address is not null then 'MEV Bot' else null end as mev_label,

    -- Bridge
    case when bridge.address is not null then 'Bridge' else null end as bridge_label,

    -- L2 Operator
    l2.protocol_name as l2_protocol,

    -- OFAC
    case when ofac.address is not null then 'OFAC Sanctioned' else null end as ofac_label,

    -- Burn Address
    case when burn.address is not null then 'Burn Address' else null end as burn_label,

    -- Staking Entity
    staker.entity as staking_entity,
    staker.category as staking_category
from borrower_totals bt
left join asset_breakdown ab
    on bt.borrower = ab.borrower
    and bt.project = ab.project
left join labels.owner_addresses lab
    on bt.borrower = lab.address
    and lab.blockchain = 'ethereum'
left join labels.owner_details owner_det
    on lab.owner_key = owner_det.owner_key
left join labels.ens ens
    on bt.borrower = ens.address
left join cex.addresses cex
    on bt.borrower = cex.address
    and cex.blockchain = 'ethereum'
left join cex.info cex_info
    on cex.cex_name = cex_info.cex_name
left join cex.deposit_addresses cex_dep
    on bt.borrower = cex_dep.address
    and cex_dep.blockchain = 'ethereum'
left join contracts.contract_mapping cm
    on bt.borrower = cm.contract_address
    and cm.blockchain = 'ethereum'
left join safe.safes_all safe
    on bt.borrower = safe.address
    and safe.blockchain = 'ethereum'
left join dao.addresses dao
    on bt.borrower = dao.dao_wallet_address
    and dao.blockchain = 'ethereum'
left join addresses_ethereum.defi defi
    on bt.borrower = defi.address
left join addresses_ethereum.mev mev
    on bt.borrower = mev.address
left join addresses_ethereum.bridges bridge
    on bt.borrower = bridge.address
left join addresses_ethereum.l2_batch_submitters l2
    on bt.borrower = l2.address
left join addresses_ethereum.ofac_sanctioned ofac
    on bt.borrower = ofac.address
left join labels.burn_addresses burn
    on bt.borrower = burn.address
    and burn.blockchain = 'ethereum'
left join staking_ethereum.entities staker
    on bt.borrower = staker.depositor_address
where cm.contract_address is null
   or safe.address is not null
order by bt.total_borrowed desc
