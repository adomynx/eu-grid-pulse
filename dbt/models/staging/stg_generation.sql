-- Staging: clean + harmonise raw_generation.
--  * normalise timestamp to a single UTC wall-clock column
--  * de-duplicate overlapping re-pulls per (country, timestamp, fuel)
--  * trim/normalise the raw production-type label
--  * drop null generation readings explicitly
with ranked as (
    select
        country_code,
        timezone('UTC', datetime) as datetime_utc,
        resolution,
        trim(production_type) as production_type,
        generation_mw,
        consumption_mw,
        row_number() over (
            partition by country_code, datetime, trim(production_type)
            order by ingested_at desc
        ) as rn
    from {{ source('raw', 'raw_generation') }}
)

select
    country_code,
    datetime_utc,
    resolution,
    production_type,
    generation_mw,
    consumption_mw
from ranked
where rn = 1
  and generation_mw is not null
