
-- ============================================================
-- PROJECT: Compare Equal-Area and Other CRS Area Calculations
-- DATABASE: agriculture_db
-- SOURCE TABLE: public.indian_districts
-- ORIGINAL CRS: EPSG:4326
-- PREVIOUS PROJECTED CRS: EPSG:7755
-- EQUAL-AREA CRS: EPSG:6933
-- OUTPUT TABLE: public.indian_districts_6933
-- ============================================================


-- 1. Verify that EPSG:6933 is available

SELECT
    srid,
    auth_name,
    auth_srid
FROM spatial_ref_sys
WHERE srid = 6933;


-- 2. Create the equal-area projected table
-- This replaces only the derived EPSG:6933 table.

BEGIN;

DROP TABLE IF EXISTS public.indian_districts_6933;

CREATE TABLE public.indian_districts_6933 AS
SELECT
    gid,
    objectid,
    statecode,
    statename,
    state_ut,
    distcode,
    distname,
    distarea,
    totalpopul,
    totalhh,
    totpopmale,
    totpopfema,
    st_areasha,
    st_lengths,
    ST_Transform(geom, 6933)
        ::geometry(MultiPolygon, 6933) AS geom
FROM public.indian_districts;

-- 3. Add a primary key

ALTER TABLE public.indian_districts_6933
ADD PRIMARY KEY (gid);

-- 4. Create a spatial index

CREATE INDEX idx_indian_districts_6933_geom
ON public.indian_districts_6933
USING GIST (geom);

-- 5. Update table statistics

ANALYZE public.indian_districts_6933;

COMMIT;


-- 6. Verify count, CRS, geometry type and validity

SELECT
    COUNT(*) AS total_districts,
    ST_SRID(geom) AS projected_srid,
    ST_GeometryType(geom) AS geometry_type,
    COUNT(*) FILTER (
        WHERE ST_IsValid(geom)
    ) AS valid_geometries,
    COUNT(*) FILTER (
        WHERE NOT ST_IsValid(geom)
    ) AS invalid_geometries
FROM public.indian_districts_6933
GROUP BY
    ST_SRID(geom),
    ST_GeometryType(geom);


-- 7. Compare three area calculation methods
-- All reported areas are in square kilometres.

SELECT
    a.distname,
    a.statename,

    ROUND(
        (ST_Area(a.geom::geography) / 1000000)::numeric,
        2
    ) AS geography_area_sq_km,

    ROUND(
        (ST_Area(b.geom) / 1000000)::numeric,
        2
    ) AS epsg7755_area_sq_km,

    ROUND(
        (ST_Area(c.geom) / 1000000)::numeric,
        2
    ) AS epsg6933_area_sq_km,

    ROUND(
        (
            (
                ST_Area(b.geom)
                - ST_Area(a.geom::geography)
            )
            / NULLIF(ST_Area(a.geom::geography), 0)
            * 100
        )::numeric,
        4
    ) AS epsg7755_difference_percent,

    ROUND(
        (
            (
                ST_Area(c.geom)
                - ST_Area(a.geom::geography)
            )
            / NULLIF(ST_Area(a.geom::geography), 0)
            * 100
        )::numeric,
        4
    ) AS epsg6933_difference_percent

FROM public.indian_districts AS a

JOIN public.indian_districts_7755 AS b
    ON a.gid = b.gid

JOIN public.indian_districts_6933 AS c
    ON a.gid = c.gid

ORDER BY geography_area_sq_km DESC
LIMIT 15;


-- 8. Rank districts by equal-area calculation

SELECT
    distname,
    statename,
    ROUND(
        (ST_Area(geom) / 1000000)::numeric,
        2
    ) AS area_sq_km
FROM public.indian_districts_6933
ORDER BY ST_Area(geom) DESC
LIMIT 10;


-- 9. Check the equal-area spatial index

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'indian_districts_6933';


-- 10. Confirm that all three tables have the same count

SELECT
    (SELECT COUNT(*)
     FROM public.indian_districts) AS epsg4326_count,

    (SELECT COUNT(*)
     FROM public.indian_districts_7755) AS epsg7755_count,

    (SELECT COUNT(*)
     FROM public.indian_districts_6933) AS epsg6933_count;
