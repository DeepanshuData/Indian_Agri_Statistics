
-- =====================================================
-- AGRICULTURE DATABASE: CREATE INDEXES
-- =====================================================

-- Index 1: Speed up state and district lookups
CREATE INDEX IF NOT EXISTS idx_agriculture_state_district
ON public.agriculture (state, district);

-- Index 2: Support crop-based analysis
CREATE INDEX IF NOT EXISTS idx_agriculture_crop_state_district
ON public.agriculture (LOWER(crop), state, district)
INCLUDE ("yield");

-- Update PostgreSQL table statistics
ANALYZE public.agriculture;

-- Verify indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'agriculture'
ORDER BY indexname;
