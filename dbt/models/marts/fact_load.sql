-- Fact: actual load. Grain = country x hour. Measure = load_mw.
select
    md5(country_code)                                as country_key,
    md5(cast(date_trunc('hour', datetime_utc) as varchar)) as date_key,
    datetime_utc,
    country_code,
    load_mw
from {{ ref('stg_load') }}
