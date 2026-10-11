
-- =====================================================
-- AGRICULTURE DATABASE: AFTER INDEXING
-- =====================================================

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'agriculture'
ORDER BY indexname;

-- District lookup after indexing
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    state,
    district,
    crop,
    year,
    season,
    area,
    production,
    "yield"
FROM public.agriculture
WHERE state = 'PUNJAB'
  AND district = 'FIROZPUR';

-- Rice yield analysis after indexing
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    state,
    district,
    AVG("yield") AS average_rice_yield
FROM public.agriculture
WHERE LOWER(crop) = 'rice'
  AND "yield" IS NOT NULL
GROUP BY state, district
ORDER BY state, average_rice_yield DESC;
