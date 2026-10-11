
-- =====================================================
-- AGRICULTURE DATABASE: BEFORE INDEXING
-- =====================================================

-- Query 1: Count records
SELECT COUNT(*) AS total_records
FROM public.agriculture;

-- Query 2: Check existing indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'agriculture'
ORDER BY indexname;

-- Query 3: District lookup performance
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

-- Query 4: Rice yield analysis performance
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

