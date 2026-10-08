-- Staging: clean + harmonise raw_load into one honest grain.
--  * normalise the timestamp to a single UTC wall-clock column (kills TZ/DST mess)
--  * de-duplicate overlapping incremental re-pulls (keep the latest ingested_at)
--  * drop null load readings explicitly (the API returns gaps)
with ranked as (
    select
        country_code,
        timezone('UTC', datetime) as datetime_utc,  -- TIMESTAMPTZ instant -> UTC wall clock
        resolution,
        load_mw,
        row_number() over (
            partition by country_code, datetime
            order by ingested_at desc
        ) as rn
    from {{ source('raw', 'raw_load') }}
)

select
    country_code,
    datetime_utc,
    resolution,
    load_mw
from ranked
where rn = 1
  and load_mw is not null
