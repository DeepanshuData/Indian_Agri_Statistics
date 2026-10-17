```sql
-- =====================================================
-- Project: Indian District Boundaries using PostGIS
-- Database: agriculture_db
-- Table: public.indian_districts
-- Geometry column: geom
-- Coordinate Reference System: EPSG:4326
-- =====================================================


-- 1. Count the total number of districts
SELECT COUNT(*) AS total_districts
FROM public.indian_districts;


-- 2. Check geometry type and coordinate reference system
SELECT
    ST_GeometryType(geom) AS geometry_type,
    ST_SRID(geom) AS srid,
    COUNT(*) AS feature_count
FROM public.indian_districts
GROUP BY
    ST_GeometryType(geom),
    ST_SRID(geom);


-- 3. Check geometry validity
SELECT
    COUNT(*) AS total_districts,
    COUNT(*) FILTER (
        WHERE ST_IsValid(geom)
    ) AS valid_geometries,
    COUNT(*) FILTER (
        WHERE NOT ST_IsValid(geom)
    ) AS invalid_geometries
FROM public.indian_districts;


-- 4. Find the 10 districts with the largest areas
SELECT
    distname,
    statename,
    ROUND(
        (ST_Area(geom::geography) / 1000000)::numeric,
        2
    ) AS area_sq_km
FROM public.indian_districts
ORDER BY area_sq_km DESC
LIMIT 10;


-- 5. Get a point inside each district
SELECT
    distname,
    statename,
    ST_AsText(ST_PointOnSurface(geom)) AS district_point
FROM public.indian_districts
LIMIT 10;


-- 6. Check the table's indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'indian_districts';


-- 7. Find neighboring districts
SELECT
    a.distname AS district_a,
    a.statename AS state_a,
    b.distname AS district_b,
    b.statename AS state_b
FROM public.indian_districts AS a
JOIN public.indian_districts AS b
    ON a.gid < b.gid
   AND a.geom && b.geom
   AND ST_Touches(a.geom, b.geom)
LIMIT 20;


-- 8. Count the neighbors of each district
SELECT
    a.distname,
    a.statename,
    COUNT(*) AS neighboring_districts
FROM public.indian_districts AS a
JOIN public.indian_districts AS b
    ON a.gid <> b.gid
   AND a.geom && b.geom
   AND ST_Touches(a.geom, b.geom)
GROUP BY
    a.gid,
    a.distname,
    a.statename
ORDER BY neighboring_districts DESC
LIMIT 10;
