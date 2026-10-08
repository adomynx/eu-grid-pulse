-- Plausibility: generation can't be negative, and no single fuel in one hour
-- should exceed an absurd ceiling (150 GW).
select *
from {{ ref('fact_generation') }}
where generation_mw < 0
   or generation_mw > 150000
