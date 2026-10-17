
-- ============================================================
-- DAY PROJECT 05
-- District Area Calculation and Reference Comparison
-- Database: agriculture_db
-- Source: public.indian_districts (EPSG:4326)
-- Area method: PostGIS geography / spheroid-based area
-- ============================================================

-- 1. CHECK THE SOURCE TABLE

SELECT
    COUNT(*) AS total_districts,
    ST_SRID(geom) AS srid,
    GeometryType(geom) AS geometry_type,
    COUNT(*) FILTER (WHERE geom IS NULL) AS missing_geometries,
    COUNT(*) FILTER (
        WHERE geom IS NOT NULL AND NOT ST_IsValid(geom)
    ) AS invalid_geometries
FROM public.indian_districts
GROUP BY ST_SRID(geom), GeometryType(geom);


-- 2. CREATE A TABLE TO STORE CALCULATED AREAS
-- JSONB preserves the original attributes so we can identify
-- the actual district/state field names later.

CREATE TABLE IF NOT EXISTS public.district_area_calculated (
    gid BIGINT PRIMARY KEY,
    attributes JSONB NOT NULL,
    area_km2 NUMERIC(16, 4) NOT NULL,
    area_method TEXT NOT NULL,
    reference_year INTEGER
);


-- 3. REFRESH THE CALCULATED RESULTS
-- This only replaces rows in the results table, not source data.

TRUNCATE TABLE public.district_area_calculated;

INSERT INTO public.district_area_calculated (
    gid,
    attributes,
    area_km2,
    area_method,
    reference_year
)
SELECT
    d.gid,
    to_jsonb(d) - 'geom',
    ST_Area(d.geom::geography) / 1000000.0,
    'ST_Area(geom::geography)',
    NULL
FROM public.indian_districts AS d
WHERE d.geom IS NOT NULL;


-- 4. CHECK THE NUMBER OF CALCULATED AREAS

SELECT
    COUNT(*) AS calculated_districts,
    COUNT(*) FILTER (WHERE area_km2 <= 0) AS non_positive_areas,
    COUNT(*) FILTER (WHERE area_km2 IS NULL) AS missing_areas
FROM public.district_area_calculated;


-- 5. VIEW THE LARGEST 10 DISTRICT AREAS

SELECT
    gid,
    attributes,
    ROUND(area_km2, 2) AS area_km2
FROM public.district_area_calculated
ORDER BY area_km2 DESC
LIMIT 10;


-- 6. VIEW THE SMALLEST 10 DISTRICT AREAS

SELECT
    gid,
    attributes,
    ROUND(area_km2, 2) AS area_km2
FROM public.district_area_calculated
ORDER BY area_km2 ASC
LIMIT 10;


-- 7. AREA STATISTICS

SELECT
    ROUND(MIN(area_km2), 2) AS smallest_area_km2,
    ROUND(MAX(area_km2), 2) AS largest_area_km2,
    ROUND(AVG(area_km2), 2) AS average_area_km2,
    ROUND(SUM(area_km2), 2) AS sum_of_district_areas_km2
FROM public.district_area_calculated;


-- 8. SHOW THE STORED ATTRIBUTE KEYS
-- Use this output to identify district and state columns.

SELECT
    gid,
    jsonb_object_keys(attributes) AS attribute_name
FROM public.district_area_calculated
WHERE gid = (
    SELECT MIN(gid)
    FROM public.district_area_calculated
)
ORDER BY attribute_name;


-- 9. CHECK THE SAVED AREA RESULTS

SELECT
    gid,
    ROUND(area_km2, 2) AS area_km2,
    area_method
FROM public.district_area_calculated
ORDER BY gid
LIMIT 20;
