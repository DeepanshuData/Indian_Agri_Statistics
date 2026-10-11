

-- TOPIC: SQL WINDOW FUNCTIONS
-- STEP 1: CHECK THE AGRICULTURE TABLE

SELECT COUNT(*) AS total_records
FROM agriculture;


SELECT
    state,
    district,
    crop,
    year,
    season,
    area,
    production,
    "yield"
FROM agriculture
LIMIT 10;


-- STEP 2: CHECK WHICH CROPS ARE AVAILABLE

SELECT
    crop,
    COUNT(*) AS total_records
FROM agriculture
GROUP BY crop
ORDER BY total_records DESC;


-- STEP 3: CALCULATE AVERAGE YIELD BY STATE, DISTRICT, CROP

WITH district_crop_yield AS (
    SELECT
        state,
        district,
        crop,
        COUNT(*) AS total_records,
        COUNT("yield") AS records_with_yield,
        AVG("yield") AS average_yield
    FROM agriculture
    WHERE "yield" IS NOT NULL
    GROUP BY
        state,
        district,
        crop
)
SELECT
    state,
    district,
    crop,
    total_records,
    records_with_yield,
    ROUND(average_yield::NUMERIC, 3) AS average_yield
FROM district_crop_yield
ORDER BY
    state,
    crop,
    average_yield DESC;


-- STEP 4: RANK DISTRICTS WITHIN EACH STATE AND CROP

WITH district_crop_yield AS (
    SELECT
        state,
        district,
        crop,
        AVG("yield") AS average_yield
    FROM agriculture
    WHERE "yield" IS NOT NULL
    GROUP BY
        state,
        district,
        crop
),
ranked_districts AS (
    SELECT
        state,
        district,
        crop,
        average_yield,

        RANK() OVER (
            PARTITION BY state, crop
            ORDER BY average_yield DESC
        ) AS yield_rank

    FROM district_crop_yield
)
SELECT
    state,
    crop,
    district,
    ROUND(average_yield::NUMERIC, 3) AS average_yield,
    yield_rank
FROM ranked_districts
ORDER BY
    state,
    crop,
    yield_rank,
    district;


-- STEP 5: FIND THE TOP 3 DISTRICTS FOR EACH CROP IN EACH STATE

WITH district_crop_yield AS (
    SELECT
        state,
        district,
        crop,
        AVG("yield") AS average_yield
    FROM agriculture
    WHERE "yield" IS NOT NULL
    GROUP BY
        state,
        district,
        crop
),
ranked_districts AS (
    SELECT
        state,
        district,
        crop,
        average_yield,

        RANK() OVER (
            PARTITION BY state, crop
            ORDER BY average_yield DESC
        ) AS yield_rank

    FROM district_crop_yield
)
SELECT
    state,
    crop,
    district,
    ROUND(average_yield::NUMERIC, 3) AS average_yield,
    yield_rank
FROM ranked_districts
WHERE yield_rank <= 3
ORDER BY
    state,
    crop,
    yield_rank,
    district;

-- STEP 6: COMPARE RANK, DENSE_RANK AND ROW_NUMBER

WITH district_crop_yield AS (
    SELECT
        state,
        district,
        crop,
        AVG("yield") AS average_yield
    FROM agriculture
    WHERE "yield" IS NOT NULL
    GROUP BY
        state,
        district,
        crop
)
SELECT
    state,
    crop,
    district,
    ROUND(average_yield::NUMERIC, 3) AS average_yield,

    RANK() OVER (
        PARTITION BY state, crop
        ORDER BY average_yield DESC
    ) AS rank_number,

    DENSE_RANK() OVER (
        PARTITION BY state, crop
        ORDER BY average_yield DESC
    ) AS dense_rank_number,

    ROW_NUMBER() OVER (
        PARTITION BY state, crop
        ORDER BY average_yield DESC, district ASC
    ) AS row_number

FROM district_crop_yield
ORDER BY
    state,
    crop,
    average_yield DESC,
    district;


-- STEP 7: RANK DISTRICTS FOR RICE ONLY

WITH rice_district_yield AS (
    SELECT
        state,
        district,
        AVG("yield") AS average_yield
    FROM agriculture
    WHERE LOWER(crop) = 'rice'
      AND "yield" IS NOT NULL
    GROUP BY
        state,
        district
),
ranked_rice_districts AS (
    SELECT
        state,
        district,
        average_yield,

        RANK() OVER (
            PARTITION BY state
            ORDER BY average_yield DESC
        ) AS rice_yield_rank

    FROM rice_district_yield
)
SELECT
    state,
    district,
    ROUND(average_yield::NUMERIC, 3) AS average_rice_yield,
    rice_yield_rank
FROM ranked_rice_districts
ORDER BY
    state,
    rice_yield_rank,
    district;

