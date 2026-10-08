-- Date/time dimension at hourly grain, built from the timestamps actually present.
with hours as (
    select distinct date_trunc('hour', datetime_utc) as datetime_utc from {{ ref('stg_load') }}
    union
    select distinct date_trunc('hour', datetime_utc) as datetime_utc from {{ ref('stg_generation') }}
)

select
    md5(cast(datetime_utc as varchar)) as date_key,
    datetime_utc,
    cast(datetime_utc as date)         as date,
    year(datetime_utc)                 as year,
    month(datetime_utc)                as month,
    day(datetime_utc)                  as day,
    hour(datetime_utc)                 as hour,
    dayofweek(datetime_utc) in (0, 6)  as is_weekend   -- DuckDB: 0=Sun, 6=Sat
from hours
