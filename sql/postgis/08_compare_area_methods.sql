
SELECT
    attributes ->> 'statename' AS state_name,
    attributes ->> 'distname' AS district_name,

    ROUND(
        area_km2::numeric,
        2
    ) AS stored_area_km2,

    ROUND(
        (
            ST_Area(
                ST_Transform(
                    ST_SetSRID(
                        ST_GeomFromGeoJSON(
                            ST_AsGeoJSON(
                                ST_GeomFromText('POINT(0 0)')
                            )
                        ),
                        4326
                    ),
                    6933
                )
            ) / 1000000.0
        )::numeric,
        2
    ) AS placeholder_area_km2

FROM public.district_area_calculated
LIMIT 5;
