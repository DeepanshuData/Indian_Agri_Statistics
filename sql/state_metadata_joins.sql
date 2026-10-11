
-- STEP 1: CHECK EXISTING AGRICULTURE TABLE

SELECT *
FROM agriculture
LIMIT 5;

-- STEP 2: CHECK TOTAL AGRICULTURE RECORDS

SELECT COUNT(*) AS total_records
FROM agriculture

-- STEP 3: CHECK ALL STATES AVAILABLE IN AGRICULTURE TABLE

SELECT DISTINCT state
FROM agriculture
ORDER BY state;

-- STEP 4: CREATE STATE METADATA TABLE

CREATE TABLE IF NOT EXISTS state_metadata (
    state TEXT PRIMARY KEY,
    capital TEXT,
    region TEXT,
    agro_climate_zone TEXT
);

-- STEP 5: INSERT STATE METADATA

INSERT INTO state_metadata
    (state, capital, region, agro_climate_zone)
VALUES
    ('ANDHRA PRADESH', 'Amaravati', 'South India', 'Southern Plateau'),
    ('ASSAM', 'Dispur', 'Northeast India', 'Eastern Himalayan'),
    ('BIHAR', 'Patna', 'East India', 'Middle Gangetic Plain'),
    ('GUJARAT', 'Gandhinagar', 'West India', 'Gujarat Plains and Hills'),
    ('HARYANA', 'Chandigarh', 'North India', 'Trans-Gangetic Plain'),
    ('KARNATAKA', 'Bengaluru', 'South India', 'Southern Plateau'),
    ('KERALA', 'Thiruvananthapuram', 'South India', 'Western Ghats'),
    ('MADHYA PRADESH', 'Bhopal', 'Central India', 'Central Plateau'),
    ('MAHARASHTRA', 'Mumbai', 'West India', 'Western Plateau'),
    ('ODISHA', 'Bhubaneswar', 'East India', 'Eastern Plateau'),
    ('PUNJAB', 'Chandigarh', 'North India', 'Trans-Gangetic Plain'),
    ('RAJASTHAN', 'Jaipur', 'Northwest India', 'Western Dry Region'),
    ('TAMIL NADU', 'Chennai', 'South India', 'Tamil Nadu Plains'),
    ('TELANGANA', 'Hyderabad', 'South India', 'Deccan Plateau'),
    ('UTTAR PRADESH', 'Lucknow', 'North India', 'Middle Gangetic Plain'),
    ('WEST BENGAL', 'Kolkata', 'East India', 'Lower Gangetic Plain')
ON CONFLICT (state) DO NOTHING;

-- STEP 6: CHECK STATE METADATA TABLE

SELECT *
FROM state_metadata
ORDER BY state;


-- STEP 7: CHECK STATES WITHOUT METADATA

SELECT DISTINCT
    a.state
FROM agriculture AS a
LEFT JOIN state_metadata AS s
    ON a.state = s.state
WHERE s.state IS NULL
ORDER BY a.state;


-- STEP 8: BASIC INNER JOIN

SELECT
    a.state,
    a.district,
    a.crop,
    a.year,
    a.season,
    a.area,
    a.production,
    a.yield,
    s.capital,
    s.region,
    s.agro_climate_zone
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
LIMIT 20;

-- STEP 9: STATE-LEVEL TOTAL PRODUCTION

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


-- STEP 10: COMPLETE STATE-LEVEL AGRICULTURE REPORT

SELECT
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone,
    COUNT(*) AS total_records,
    SUM(a.area) AS total_area,
    SUM(a.production) AS total_production,
    ROUND(AVG(a.yield)::numeric, 2) AS average_yield
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY
    a.state,
    s.capital,
    s.region,
    s.agro_climate_zone
ORDER BY total_production DESC;

-- STEP 11: STATE + CROP PRODUCTION REPORT

SELECT
    a.state,
    s.region,
    a.crop,
    SUM(a.production) AS total_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY
    a.state,
    s.region,
    a.crop
ORDER BY
    a.state,
    total_production DESC;

-- STEP 12: RICE PRODUCTION BY STATE

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

-- STEP 13: WHEAT PRODUCTION BY STATE

SELECT
    a.state,
    s.capital,
    s.region,
    SUM(a.production) AS wheat_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE LOWER(a.crop) = 'wheat'
GROUP BY
    a.state,
    s.capital,
    s.region
ORDER BY wheat_production DESC;

-- STEP 14: WHEAT PRODUCTION BY REGION

SELECT
    s.region,
    SUM(a.production) AS wheat_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE LOWER(a.crop) = 'wheat'
GROUP BY s.region
ORDER BY wheat_production DESC;

-- STEP 15: WHEAT PRODUCTION BY REGION WITH HAVING

SELECT
    s.region,
    SUM(a.production) AS wheat_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE LOWER(a.crop) = 'wheat'
GROUP BY s.region
HAVING SUM(a.production) > 1000000
ORDER BY wheat_production DESC;

-- STEP 16: AVERAGE YIELD BY REGION

SELECT
    s.region,
    ROUND(AVG(a.yield)::numeric, 2) AS average_yield
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE a.yield IS NOT NULL
GROUP BY s.region
ORDER BY average_yield DESC;

-- STEP 17: TOTAL AREA BY REGION

SELECT
    s.region,
    SUM(a.area) AS total_area
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY s.region
ORDER BY total_area DESC;

-- STEP 18: TOP 10 STATES BY PRODUCTION

SELECT
    a.state,
    s.capital,
    s.region,
    SUM(a.production) AS total_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY
    a.state,
    s.capital,
    s.region
ORDER BY total_production DESC
LIMIT 10;


-- STEP 19: TOP 10 STATES BY AVERAGE YIELD

SELECT
    a.state,
    s.region,
    ROUND(AVG(a.yield)::numeric, 2) AS average_yield
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
WHERE a.yield IS NOT NULL
GROUP BY
    a.state,
    s.region
ORDER BY average_yield DESC
LIMIT 10;



-- STEP 20: CROP PRODUCTION BY REGION

SELECT
    s.region,
    a.crop,
    SUM(a.production) AS total_production
FROM agriculture AS a
INNER JOIN state_metadata AS s
    ON a.state = s.state
GROUP BY
    s.region,
    a.crop
ORDER BY
    s.region,
    total_production DESC;