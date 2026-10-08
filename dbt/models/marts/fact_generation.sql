-- Fact: actual generation by fuel. Grain = country x hour x fuel. Measure = generation_mw.
select
    md5(country_code)                                as country_key,
    md5(cast(date_trunc('hour', datetime_utc) as varchar)) as date_key,
    md5(production_type)                             as fuel_key,
    datetime_utc,
    country_code,
    production_type,
    generation_mw
from {{ ref('stg_generation') }}
