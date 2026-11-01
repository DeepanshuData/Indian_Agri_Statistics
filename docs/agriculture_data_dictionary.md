# Agricultural GIS data dictionary

## Source dataset

The pipeline reads `public.agriculture`, loaded from the project agriculture
CSV. Its fields are `state`, `district`, `crop`, `year`, `season`, `area`,
`production`, and `yield`. The project has no authoritative source document or
data dictionary establishing the publisher, download date, or measurement
units for this CSV. The source-unit status is therefore **unverified**; values
must not be described as hectares, tonnes, or tonnes per hectare.

Use `config/agriculture_source_metadata.csv` to record the publisher, source
URL, acquisition date, measurement units, and documentary evidence. Change
`verification_status` to `verified` only after checking an authoritative
source document and retain the evidence citation in the file. The pipeline
does not infer units from the magnitudes of values.

## Important fields

| Field | Meaning | Unit / status |
|---|---|---|
| `state`, `district` | Original agriculture labels (cleaned for display in summary outputs) | Text; original labels retained in spatial match audit |
| `crop`, `season` | Source crop and season labels | Text |
| `year` | Source agricultural year label | Text; parsed for inclusion, original value retained |
| `area` | Source agriculture area | **Unverified** |
| `production` | Source production | **Unverified** |
| `yield` | Source-reported row-level yield | Unit and use are unverified; not averaged for district yield |
| `total_area` | Sum of valid Rice area observations by source state/district | Same unverified source unit as `area` |
| `total_production` | Sum of valid Rice production observations by source state/district | Same unverified source unit as `production` |
| `crop_yield`, `average_yield` | Aggregated production divided by aggregated area | Production unit / area unit; **unverified** |
| `boundary_area_km2` | District polygon area measured after projection to EPSG:6933 | Square kilometres; geometric boundary area, not agricultural area |
| `match_status`, `match_method` | Spatial join outcome and the method used | Categoricals / text; inspect `output/csv/district_match_audit.csv` |

## Calculation rules

- Exact duplicate source rows are excluded from analytical calculations only;
  the source database is not changed.
- Missing/non-numeric area or production and non-positive area or negative or
  non-finite numeric values are excluded from calculations and counted.
- District and state yields are calculated after summing valid production and
  area. Row-level yields are not averaged.
- A district is spatially matched automatically only by normalized state plus
  district name, or by a verified crosswalk entry with a documentary evidence
  reference. District-only and fuzzy-name candidates are review hints, never
  accepted matches.
- No-match or ambiguous records remain null in the spatial output, not zero.
