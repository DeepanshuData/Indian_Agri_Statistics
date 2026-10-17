
WITH comparison AS (
    SELECT
        d.area_km2 AS calculated_area_km2,
        c.reference_area_km2,
        ABS(d.area_km2 - c.reference_area_km2)
            AS absolute_difference_km2,
        100.0 * ABS(d.area_km2 - c.reference_area_km2)
            / NULLIF(c.reference_area_km2, 0)
            AS percentage_difference
    FROM public.district_area_calculated AS d
    JOIN public.census_2011_district_areas AS c
      ON LOWER(TRIM(d.attributes ->> 'statename'))
         = LOWER(TRIM(c.state_name))
     AND LOWER(TRIM(d.attributes ->> 'distname'))
         = LOWER(TRIM(c.district_name))
)
SELECT
    COUNT(*) AS matched_districts,
    ROUND(AVG(absolute_difference_km2)::numeric, 2)
        AS average_absolute_difference_km2,
    ROUND(AVG(percentage_difference)::numeric, 2)
        AS average_percentage_difference,
    ROUND(MAX(percentage_difference)::numeric, 2)
        AS maximum_percentage_difference
FROM comparison;
