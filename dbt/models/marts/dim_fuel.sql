-- Fuel dimension: one row per production type, with the renewable flag that
-- powers the renewable-share story. Nuclear is low-carbon but NOT renewable
-- (standard convention), so it is false here.
with fuels as (
    select distinct production_type from {{ ref('stg_generation') }}
)

select
    md5(production_type) as fuel_key,
    production_type      as fuel_type,
    production_type in (
        'Solar',
        'Wind Onshore',
        'Wind Offshore',
        'Hydro Water Reservoir',
        'Hydro Run-of-river and poundage',
        'Hydro Pumped Storage',
        'Biomass',
        'Geothermal',
        'Marine',
        'Other renewable'
    )                     as is_renewable
from fuels
