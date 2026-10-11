
-- STEP 1: CHECK AGRICULTURE TABLE
SELECT *
FROM agriculture
LIMIT 5;


-- STEP 2: AVERAGE YIELD PER STATE
SELECT
    state,
    ROUND(AVG(yield)::numeric, 2) AS average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY state
ORDER BY average_yield DESC;


-- STEP 3: NATIONAL AVERAGE YIELD
SELECT
    ROUND(AVG(yield)::numeric, 2) AS national_average_yield
FROM agriculture
WHERE yield IS NOT NULL;

-- STEP 4: STATES WITH YIELD ABOVE NATIONAL AVERAGE
SELECT
    state,
    ROUND(AVG(yield)::numeric, 2) AS average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY state
HAVING AVG(yield) > (
    SELECT AVG(yield)
    FROM agriculture
    WHERE yield IS NOT NULL
)
ORDER BY average_yield DESC;

-- STEP 5: STATES WITH YIELD ABOVE NATIONAL AVERAGE
-- WITH STATE METADATA
SELECT
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone,
    ROUND(AVG(a.yield)::numeric, 2) AS average_yield
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE a.yield IS NOT NULL
GROUP BY
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone
HAVING AVG(a.yield) > (
    SELECT AVG(yield)
    FROM agriculture
    WHERE yield IS NOT NULL
)
ORDER BY average_yield DESC;

-- STEP 6: TOP 10 STATES BY AVERAGE YIELD

SELECT
    state,
    ROUND(AVG(yield)::numeric, 2) AS average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY state
ORDER BY average_yield DESC
LIMIT 10;

-- STEP 7: STATES BELOW NATIONAL AVERAGE
SELECT
    state,
    ROUND(AVG(yield)::numeric, 2) AS average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY state
HAVING AVG(yield) < (
    SELECT AVG(yield)
    FROM agriculture
    WHERE yield IS NOT NULL
)
ORDER BY average_yield ASC;

-- STEP 8: STATE YIELD WITH NATIONAL AVERAGE
SELECT
    state,
    ROUND(AVG(yield)::numeric, 2) AS state_average_yield,
    ROUND(
        (
            SELECT AVG(yield)
            FROM agriculture
            WHERE yield IS NOT NULL
        )::numeric,
        2
    ) AS national_average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY state
ORDER BY state_average_yield DESC;


