
-- ============================================================
-- PROJECT: Indian Agriculture Statistics
-- STEP 04: Spatial Filtering with PostGIS
-- Database: agriculture_db
-- Table: public.indian_districts_7755
-- CRS: EPSG:7755
-- ============================================================


-- ------------------------------------------------------------
-- 1. CHECK THE DISTRICT TABLE
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS total_districts,
    ST_SRID(geom) AS srid,
    GeometryType(geom) AS geometry_type,
    COUNT(*) FILTER (
        WHERE ST_IsValid(geom)
    ) AS valid_geometries
FROM public.indian_districts_7755
GROUP BY ST_SRID(geom), GeometryType(geom);


-- ------------------------------------------------------------
-- 2. SELECT ONE DISTRICT AS OUR STUDY AREA
-- ------------------------------------------------------------
-- We use the district with the smallest gid for this example.
-- This is a demonstration study area, not a real-world
-- agricultural study boundary.

SELECT
    gid,
    COALESCE(
        to_jsonb(d)->>'district',
        to_jsonb(d)->>'DISTRICT',
        to_jsonb(d)->>'dtname',
        to_jsonb(d)->>'DTNAME',
        to_jsonb(d)->>'name_2',
        to_jsonb(d)->>'NAME_2',
        to_jsonb(d)->>'name'
    ) AS district_name,
    ST_SRID(geom) AS srid
FROM public.indian_districts_7755 AS d
ORDER BY gid
LIMIT 10;


-- ------------------------------------------------------------
-- 3. ST_INTERSECTS: FIND DISTRICTS THAT INTERSECT THE STUDY
-- ------------------------------------------------------------
-- The selected district intersects itself.
-- We exclude it from the neighbor list to show other districts.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
)
SELECT
    d.gid,
    COALESCE(
        to_jsonb(d)->>'district',
        to_jsonb(d)->>'DISTRICT',
        to_jsonb(d)->>'dtname',
        to_jsonb(d)->>'DTNAME',
        to_jsonb(d)->>'name_2',
        to_jsonb(d)->>'NAME_2',
        to_jsonb(d)->>'name'
    ) AS district_name,
    ST_Intersects(d.geom, s.geom) AS intersects_study_area
FROM public.indian_districts_7755 AS d
CROSS JOIN study_area AS s
WHERE d.gid <> s.gid
  AND ST_Intersects(d.geom, s.geom)
ORDER BY d.gid;


-- ------------------------------------------------------------
-- 4. COUNT ALL INTERSECTING DISTRICTS
-- ------------------------------------------------------------
-- This count includes the study district itself.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
)
SELECT
    COUNT(*) AS intersecting_districts_including_study_area
FROM public.indian_districts_7755 AS d
CROSS JOIN study_area AS s
WHERE ST_Intersects(d.geom, s.geom);


-- ------------------------------------------------------------
-- 5. ST_CONTAINS: CHECK WHETHER A DISTRICT CONTAINS A POINT
-- ------------------------------------------------------------
-- ST_PointOnSurface creates a point inside the selected district.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
),
study_point AS (
    SELECT
        gid,
        ST_PointOnSurface(geom) AS geom
    FROM study_area
)
SELECT
    d.gid,
    COALESCE(
        to_jsonb(d)->>'district',
        to_jsonb(d)->>'DISTRICT',
        to_jsonb(d)->>'dtname',
        to_jsonb(d)->>'DTNAME',
        to_jsonb(d)->>'name_2',
        to_jsonb(d)->>'NAME_2',
        to_jsonb(d)->>'name'
    ) AS district_name,
    ST_Contains(d.geom, p.geom) AS contains_point
FROM public.indian_districts_7755 AS d
CROSS JOIN study_point AS p
WHERE ST_Contains(d.geom, p.geom);


-- ------------------------------------------------------------
-- 6. ST_WITHIN: THE REVERSE CONTAINMENT TEST
-- ------------------------------------------------------------
-- The point is within the district if the district contains it.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
),
study_point AS (
    SELECT ST_PointOnSurface(geom) AS geom
    FROM study_area
)
SELECT
    d.gid,
    ST_Within(p.geom, d.geom) AS point_is_within_district
FROM public.indian_districts_7755 AS d
CROSS JOIN study_point AS p
WHERE ST_Within(p.geom, d.geom);


-- ------------------------------------------------------------
-- 7. BOUNDING-BOX FILTER: &&
-- ------------------------------------------------------------
-- && checks whether geometry bounding boxes overlap.
-- It does not guarantee that the actual geometries intersect.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
)
SELECT
    COUNT(*) FILTER (
        WHERE d.geom && s.geom
    ) AS bounding_box_candidates,
    COUNT(*) FILTER (
        WHERE ST_Intersects(d.geom, s.geom)
    ) AS actual_intersections
FROM public.indian_districts_7755 AS d
CROSS JOIN study_area AS s;


-- ------------------------------------------------------------
-- 8. COMBINE BOUNDING BOX AND EXACT SPATIAL FILTER
-- ------------------------------------------------------------
-- First use && to identify candidates, then ST_Intersects
-- to check the actual geometries.
-- The GiST spatial index can help accelerate the candidate search.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
)
SELECT
    d.gid,
    COALESCE(
        to_jsonb(d)->>'district',
        to_jsonb(d)->>'DISTRICT',
        to_jsonb(d)->>'dtname',
        to_jsonb(d)->>'DTNAME',
        to_jsonb(d)->>'name_2',
        to_jsonb(d)->>'NAME_2',
        to_jsonb(d)->>'name'
    ) AS district_name
FROM public.indian_districts_7755 AS d
CROSS JOIN study_area AS s
WHERE d.geom && s.geom
  AND ST_Intersects(d.geom, s.geom)
  AND d.gid <> s.gid
ORDER BY d.gid;


-- ------------------------------------------------------------
-- 9. COMBINE SPATIAL AND NORMAL SQL FILTERS
-- ------------------------------------------------------------
-- Example: find intersecting districts whose gid is positive.
-- The gid condition is an ordinary SQL attribute filter.
-- Replace it with a state/crop/other attribute condition
-- after checking the actual column names in your table.

WITH study_area AS (
    SELECT gid, geom
    FROM public.indian_districts_7755
    ORDER BY gid
    LIMIT 1
)
SELECT
    d.gid,
    COALESCE(
        to_jsonb(d)->>'district',
        to_jsonb(d)->>'DISTRICT',
        to_jsonb(d)->>'dtname',
        to_jsonb(d)->>'DTNAME',
        to_jsonb(d)->>'name_2',
        to_jsonb(d)->>'NAME_2',
        to_jsonb(d)->>'name'
    ) AS district_name
FROM public.indian_districts_7755 AS d
CROSS JOIN study_area AS s
WHERE d.geom && s.geom
  AND ST_Intersects(d.geom, s.geom)
  AND d.gid <> s.gid
  AND d.gid > 0
ORDER BY d.gid;


-- ------------------------------------------------------------
-- 10. CHECK THE SPATIAL INDEX
-- ------------------------------------------------------------

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'indian_districts_7755';
