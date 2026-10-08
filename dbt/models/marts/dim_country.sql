-- Country dimension: one row per bidding zone we ingest.
with codes as (
    select distinct country_code from {{ ref('stg_load') }}
    union
    select distinct country_code from {{ ref('stg_generation') }}
)

select
    md5(country_code)         as country_key,
    country_code,
    case country_code
        when 'DE_LU' then 'Germany-Luxembourg'
        when 'FR'    then 'France'
        when 'NL'    then 'Netherlands'
        when 'ES'    then 'Spain'
        when 'PL'    then 'Poland'
        else country_code
    end                        as country_name,
    country_code               as bidding_zone
from codes
