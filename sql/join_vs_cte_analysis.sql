


-- STEP 1: VERIFY TABLES

SELECT COUNT(*) AS agriculture_records
FROM agriculture;

SELECT COUNT(*) AS metadata_records
FROM state_metadata;



-- QUERY 1A: STATE-LEVEL PRODUCTION USING A JOIN

SELECT
    a.state,
    s.region,
    s.agro_climate_zone,
    SUM(a.production) AS total_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY
    a.state,
    s.region,
    s.agro_climate_zone
ORDER BY total_production DESC;



-- QUERY 1B: STATE-LEVEL PRODUCTION USING A CTE

WITH state_production AS (
    SELECT
        a.state,
        s.region,
        s.agro_climate_zone,
        SUM(a.production) AS total_production
    FROM agriculture AS a
    INNER JOIN state_metadata AS s
        ON a.state = s.state
    GROUP BY
        a.state,
        s.region,
        s.agro_climate_zone
)
SELECT
    state,
    region,
    agro_climate_zone,
    total_production
FROM state_production
ORDER BY total_production DESC;


-- QUERY 2A: RICE PRODUCTION BY STATE USING A JOIN

SELECT
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone,
    SUM(a.production) AS rice_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE LOWER(a.crop) = 'rice'
GROUP BY
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone
ORDER BY rice_production DESC;


-- QUERY 2B: RICE PRODUCTION BY STATE USING CTES

WITH rice_records AS (
    SELECT
        state,
        production
    FROM agriculture
    WHERE LOWER(crop) = 'rice'
),
rice_state_production AS (
    SELECT
        r.state,
        s.capital,
        s.region,
        s.agro_climate_zone,
        SUM(r.production) AS rice_production
    FROM rice_records AS r
    INNER JOIN state_metadata AS s
        ON r.state = s.state
    GROUP BY
        r.state,
        s.capital,
        s.region,
        s.agro_climate_zone
)
SELECT
    state,
    capital,
    region,
    agro_climate_zone,
    rice_production
FROM rice_state_production
ORDER BY rice_production DESC;


-- QUERY 3A: WHEAT PRODUCTION BY REGION USING A JOIN

SELECT
    s.region,
    SUM(a.production) AS wheat_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE LOWER(a.crop) = 'wheat'
GROUP BY s.region
ORDER BY wheat_production DESC;


-- QUERY 3B: WHEAT PRODUCTION BY REGION USING CTES

WITH wheat_records AS (
    SELECT
        state,
        production
    FROM agriculture
    WHERE LOWER(crop) = 'wheat'
),
wheat_region_production AS (
    SELECT
        s.region,
        SUM(w.production) AS wheat_production
    FROM wheat_records AS w
    INNER JOIN state_metadata AS s
        ON w.state = s.state
    GROUP BY s.region
)
SELECT
    region,
    wheat_production
FROM wheat_region_production
ORDER BY wheat_production DESC;


