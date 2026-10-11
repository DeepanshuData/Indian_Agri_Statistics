
# PostgreSQL Index Performance Analysis

## 1. Project Overview

- **Database:** agriculture_db
- **Table:** public.agriculture
- **Dataset:** Indian agriculture statistics
- **Topic:** Indexing and query performance
- **Tool:** PostgreSQL EXPLAIN (ANALYZE, BUFFERS)

## 2. Objective

The objective is to compare query execution plans and execution
times before and after creating indexes on the agriculture table.

## 3. Indexes Created

### Index 1: State and District

```sql
CREATE INDEX IF NOT EXISTS idx_agriculture_state_district
ON public.agriculture (state, district);
```

Purpose: Support queries that filter by state and district.

### Index 2: Crop, State, District, and Yield

```sql
CREATE INDEX IF NOT EXISTS idx_agriculture_crop_state_district
ON public.agriculture (LOWER(crop), state, district)
INCLUDE ("yield");
```

Purpose: Support queries that filter on LOWER(crop) and potentially
help with district-level yield analysis.

## 4. Test Queries

### Query A: District Lookup

Filters records using state = 'PUNJAB' and district = 'FIROZPUR'.

### Query B: Rice Yield Analysis

Filters for rice, calculates average yield by state and district,
and sorts the results.

## 5. Before-and-After Measurements

Record the actual values reported by PostgreSQL.

| Query | Measurement | Before | After |
|---|---|---|---|
| District lookup | Execution Time (ms) | [enter value] | [enter value] |
| District lookup | Planning Time (ms) | [enter value] | [enter value] |
| Rice yield analysis | Execution Time (ms) | [enter value] | [enter value] |
| Rice yield analysis | Planning Time (ms) | [enter value] | [enter value] |

## 6. Execution Plan Observations

### Before Indexing

- Scan method: [enter actual scan method]
- Buffer activity: [record relevant buffer values]
- Execution Time: [enter actual value]

### After Indexing

- Scan method: [enter actual scan method]
- Buffer activity: [record relevant buffer values]
- Execution Time: [enter actual value]

## 7. Performance Calculation

Percentage change in execution time:

((Before Time - After Time) / Before Time) * 100

A positive result means execution time decreased.
A negative result means execution time increased.

## 8. Conclusion

[Write your conclusion after comparing the actual execution plans
and timings. State whether each index helped, had little effect,
or was not used by the planner.]

Note: Query timings vary with cache state, system load, PostgreSQL
statistics, and the query execution plan. The conclusion should
be based on observed measurements, not assumptions.
