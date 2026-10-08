-- Plausibility: load must be positive and below an absurd ceiling (200 GW).
-- Returns offending rows; dbt fails the test if any are returned.
select *
from {{ ref('fact_load') }}
where load_mw <= 0
   or load_mw > 200000
