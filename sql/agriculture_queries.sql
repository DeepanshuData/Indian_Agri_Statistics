-- 1. Count total number of records
SELECT COUNT(*) AS total_records
FROM agriculture;


-- 2. Top 5 wheat districts by total cultivated area
SELECT
    district,
    SUM(area) AS total_wheat_area
FROM agriculture
WHERE LOWER(crop) = 'wheat'
GROUP BY district
ORDER BY total_wheat_area DESC
LIMIT 5;


-- 3. Top 5 districts by total production
SELECT
    district,
    SUM(production) AS total_production
FROM agriculture
GROUP BY district
ORDER BY total_production DESC
LIMIT 5;


-- 4. Total cultivated area by state
SELECT
    state,
    SUM(area) AS total_area
FROM agriculture
GROUP BY state
ORDER BY total_area DESC;


-- 5. Top 10 crops by total production
SELECT
    crop,
    SUM(production) AS total_production
FROM agriculture
GROUP BY crop
ORDER BY total_production DESC
LIMIT 10;


-- 6. Average yield by crop
SELECT
    crop,
    ROUND(AVG(yield)::numeric, 2) AS average_yield
FROM agriculture
WHERE yield IS NOT NULL
GROUP BY crop
ORDER BY average_yield DESC;


-- 7. Rice production by state
SELECT
    state,
    SUM(production) AS rice_production
FROM agriculture
WHERE LOWER(crop) = 'rice'
GROUP BY state
ORDER BY rice_production DESC;


-- 8. Number of different crops by state
SELECT
    state,
    COUNT(DISTINCT crop) AS number_of_crops
FROM agriculture
GROUP BY state
ORDER BY number_of_crops DESC;


-- 9. Year-wise total production
SELECT
    year,
    SUM(production) AS total_production
FROM agriculture
GROUP BY year
ORDER BY year;


-- 10. Top 10 rice districts by average yield
SELECT
    district,
    ROUND(AVG(yield)::numeric, 2) AS average_rice_yield
FROM agriculture
WHERE LOWER(crop) = 'rice'
  AND yield IS NOT NULL
GROUP BY district
HAVING COUNT(yield) >= 5
ORDER BY average_rice_yield DESC
LIMIT 10;
