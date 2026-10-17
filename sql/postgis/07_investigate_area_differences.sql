
SELECT
    d.attributes ->> 'statename' AS state_name,
    d.attributes ->> 'distname' AS district_name,
    ROUND(d.area_km2, 2) AS calculated_area_km2,
    ROUND(c.reference_area_km2, 2) AS census_area_km2,
    ROUND(
        ABS(d.area_km2 - c.reference_area_km2)::numeric,
        2
    ) AS absolute_difference_km2,
    ROUND(
        (
            100.0 * ABS(d.area_km2 - c.reference_area_km2)
            / NULLIF(c.reference_area_km2, 0)
        )::numeric,
        2
    ) AS percentage_difference
FROM public.district_area_calculated AS d
JOIN public.census_2011_district_areas AS c
    ON LOWER(TRIM(d.attributes ->> 'statename'))
       = LOWER(TRIM(c.state_name))
   AND LOWER(TRIM(d.attributes ->> 'distname'))
       = LOWER(TRIM(c.district_name))
ORDER BY percentage_difference DESC
LIMIT 20;
