
-- ============================================================
-- PROJECT: Indian District Boundaries Reprojection
-- DATABASE: agriculture_db
-- SOURCE TABLE: public.indian_districts
-- SOURCE CRS: EPSG:4326
-- TARGET CRS: EPSG:7755 (WGS 84 / India NSF LCC)
-- OUTPUT TABLE: public.indian_districts_7755
-- ============================================================

-- SECTION 1: Inspect the original district table

SELECT
    COUNT(*) AS total_districts,
    ST_SRID(geom) AS original_srid,
    ST_GeometryType(geom) AS geometry_type
FROM public.indian_districts
GROUP BY
    ST_SRID(geom),
    ST_GeometryType(geom);


-- SECTION 2: Confirm that the target CRS is available

SELECT
    srid,
    auth_name,
    auth_srid,
    srtext
FROM spatial_ref_sys
WHERE srid = 7755;


-- SECTION 3: Recreate the projected output table
-- Only the derived table is replaced. The source is preserved.

BEGIN;

DROP TABLE IF EXISTS public.indian_districts_7755;

CREATE TABLE public.indian_districts_7755 AS
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
    ST_Transform(geom, 7755)
        ::geometry(MultiPolygon, 7755) AS geom
FROM public.indian_districts;

-- SECTION 4: Add a primary key

ALTER TABLE public.indian_districts_7755
ADD PRIMARY KEY (gid);

-- SECTION 5: Create a spatial index

CREATE INDEX idx_indian_districts_7755_geom
ON public.indian_districts_7755
USING GIST (geom);

-- SECTION 6: Update query planner statistics

ANALYZE public.indian_districts_7755;

COMMIT;


-- SECTION 7: Verify the new table

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
FROM public.indian_districts_7755
GROUP BY
    ST_SRID(geom),
    ST_GeometryType(geom);


-- SECTION 8: Compare original and projected area
-- Areas are converted from square metres to square kilometres.

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
    ) AS projected_area_sq_km,

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
    ) AS difference_percent

FROM public.indian_districts AS a
JOIN public.indian_districts_7755 AS b
    ON a.gid = b.gid
ORDER BY geography_area_sq_km DESC
LIMIT 10;


-- SECTION 9: Rank districts by projected area

SELECT
    distname,
    statename,
    ROUND(
        (ST_Area(geom) / 1000000)::numeric,
        2
    ) AS area_sq_km
FROM public.indian_districts_7755
ORDER BY ST_Area(geom) DESC
LIMIT 10;


-- SECTION 10: Transform projected coordinates back to EPSG:4326

SELECT
    distname,
    ST_SRID(geom) AS projected_srid,
    ST_SRID(
        ST_Transform(geom, 4326)
    ) AS returned_srid,
    ST_AsText(
        ST_PointOnSurface(geom)
    ) AS projected_point,
    ST_AsText(
        ST_Transform(
            ST_PointOnSurface(geom),
            4326
        )
    ) AS geographic_point
FROM public.indian_districts_7755
LIMIT 5;


-- SECTION 11: Verify the spatial index

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'indian_districts_7755';


-- SECTION 12: Confirm source and output row counts

SELECT
    (
        SELECT COUNT(*)
        FROM public.indian_districts
    ) AS original_count,
    (
        SELECT COUNT(*)
        FROM public.indian_districts_7755
    ) AS projected_count;
