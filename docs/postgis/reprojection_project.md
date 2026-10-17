# Indian District Boundaries: CRS Reprojection

## Objective

Reproject Indian district boundaries from EPSG:4326 to EPSG:7755 using PostGIS, and compare area calculations.

## Technology stack

- PostgreSQL 18
- PostGIS 3.6.2
- VS Code
- SQL
- EPSG coordinate reference systems

## Input data

- Source table: `public.indian_districts`
- Source geometry column: `geom`
- Original CRS: EPSG:4326
- Expected source features: 693
- Geometry type: MultiPolygon

## Output data

- Output table: `public.indian_districts_7755`
- Projected CRS: EPSG:7755
- Geometry type: MultiPolygon
- Coordinate units: metres

## Workflow

1. Inspect the original geometry type and CRS.
2. Verify that EPSG:7755 is available in `spatial_ref_sys`.
3. Transform the geometry using `ST_Transform()`.
4. Create a separate table for projected geometries.
5. Add a primary key and GiST spatial index.
6. Validate the projected geometries.
7. Compare geography-based and projected planar area calculations.
8. Transform sample coordinates back to EPSG:4326.
9. Verify feature counts and index creation.

## Why reprojection matters

EPSG:4326 stores longitude and latitude in degrees. Planar `ST_Area()` on that geometry does not return square metres.

The geography version of `ST_Area()` calculates geodesic area in square metres. After transformation to EPSG:7755, the geometry version calculates planar area in square metres.

The choice of projected CRS affects measurement accuracy because map projections introduce distortion. For India-wide measurements, compare projected area with geography-based area and document the CRS used.

## Important functions

- `ST_SRID()` — reads the CRS identifier.
- `ST_Transform()` — transforms coordinates into another CRS.
- `ST_Area()` — calculates area.
- `ST_IsValid()` — checks geometry validity.
- `ST_PointOnSurface()` — returns a point on the surface of a geometry.
- `ST_AsText()` — converts geometry to readable WKT.
- `ST_GeometryType()` — identifies geometry type.

## Limitations

The input dataset may reflect an older district-boundary configuration. The 693 features should not automatically be treated as a current official district count.

The area difference between EPSG:7755 and geography calculations should be evaluated empirically. Neither result should be assumed to be exact for every district without considering the measurement method and projection distortion.

## Project files

- `sql/postgis/01_basic_geometry_queries.sql`
- `sql/postgis/02_reproject_and_area.sql`
- `docs/postgis/reprojection_project.md`
